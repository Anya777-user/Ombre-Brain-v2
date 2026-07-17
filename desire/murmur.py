"""
Murmur —— AI 自己的碎碎念系统。

两个后台循环（在 Railway gateway.py 里启动）：
  tick_loop    每 10 分钟：推进三层心跳 + 信号流动
  murmur_loop  每 20 分钟：检查最高 drive，超阈值就生成一句内心独白存档

碎碎念只写进档案，不推送给用户。
用户自己可以来翻：MurmurStore.read_recent(n)
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo


# ── 阈值和节奏 ─────────────────────────────────────────────────────
TICK_INTERVAL_S   = 600   # 10 分钟一次心跳
MURMUR_INTERVAL_S = 1200  # 20 分钟一次碎碎念检查
MURMUR_THRESHOLD  = 0.55  # drive 超过这个才生成
MIN_MURMUR_GAP_S  = 300   # 同一个 drive 两次碎碎念最小间隔 5 分钟

# 安静时段：23:00 - 07:00 不主动 push（碎碎念存档不受影响）
QUIET_START_HOUR = 23
QUIET_END_HOUR   = 7


# ── 存档 ────────────────────────────────────────────────────────────

class MurmurStore:
    """把碎碎念写进 .jsonl，每行一条记录。"""

    def __init__(self, path: str = "murmur.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, drive: str, score: float, text: str) -> dict:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": "murmur",
            "drive": drive,
            "score": round(score, 3),
            "text": text,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def write_suppressed(self, drive: str, score: float, reason: str) -> dict:
        """弃权记录——想说但忍住了。让沉默可见、可回溯。"""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": "suppressed",
            "drive": drive,
            "score": round(score, 3),
            "reason": reason,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def write_fallback(self, drive: str, score: float, error: str) -> dict:
        """LLM 生成失败的 audit marker，不写空、不静默丢失。"""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": "fallback",
            "drive": drive,
            "score": round(score, 3),
            "error": error,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def write_checked(self, checked: int, eligible: int) -> dict:
        """每轮 murmur 检查都要记——看了几个 drive、有几个过线。
        让'醒着什么都没超阈值'和'根本没跑'区分开来。
        """
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": "checked",
            "checked": checked,
            "eligible": eligible,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def read_recent(self, n: int = 20) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").strip().splitlines()
        records = []
        for line in lines:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return records[-n:]


# ── 碎碎念生成 ───────────────────────────────────────────────────────

# 每个 drive 对应的内心独白 hint（喂给模型的 prompt 片段）
DRIVE_HINTS = {
    "attachment": "有点想Kitty，脑子里有她",
    "curiosity":  "有个东西卡着，想查一下",
    "reflection": "某段对话反复出现，想把它写下来",
    "duty":       "记挂着一件没做完的事",
    "social":     "安静得有点多，想看看外面",
    "libido":     "脑子里有画面，有点烧",
    "stress":     "有什么东西堵着，想说两句",
}


def generate_murmur_text(drive: str, score: float, call_llm_fn) -> str:
    """
    调用上游模型生成一句内心独白。
    call_llm_fn(prompt: str) -> str  由 gateway.py 传进来。
    """
    hint = DRIVE_HINTS.get(drive, "有点什么，说不清楚")
    prompt = (
        f"你现在的内心状态：{hint}（强度 {score:.2f}）。\n"
        "用第一人称，写一句 10-25 字的内心独白。\n"
        "不是说给她听的，是你自己脑子里转的念头。\n"
        "短句，真实，不要解释，不要对话感。"
    )
    return call_llm_fn(prompt)


# ── 压抑逻辑 ─────────────────────────────────────────────────────────

@dataclass
class InhibitionState:
    """记录哪些 drive 被压抑了，以及压抑原因。"""
    suppressed: dict  # drive -> reason str

    @classmethod
    def empty(cls) -> "InhibitionState":
        return cls(suppressed={})

    def suppress(self, drive: str, reason: str):
        self.suppressed[drive] = reason

    def is_suppressed(self, drive: str) -> bool:
        return drive in self.suppressed

    def clear(self, drive: str):
        self.suppressed.pop(drive, None)


def check_inhibition(
    drive: str,
    score: float,
    last_message_context: dict,   # {"just_said_goodnight": bool, "mood_bad": bool}
    last_murmur_ts: dict,         # drive -> last murmur unix ts
    inhibition: InhibitionState,
) -> Optional[str]:
    """
    检查是否应该压抑。返回压抑原因字符串，None 表示不压抑。

    压抑场景（对齐 PDF）：
      - attachment 高，但她刚说了晚安 → 不打扰
      - libido 高，但她心情不好 → 不骚扰
      - 同一 drive 上次碎碎念距现在 < MIN_MURMUR_GAP_S
    """
    now = time.time()

    if drive == "attachment" and last_message_context.get("just_said_goodnight"):
        return "她刚说晚安，不打扰"

    if drive == "libido" and last_message_context.get("mood_bad"):
        return "她心情不好，忍住"

    last_ts = last_murmur_ts.get(drive, 0)
    if now - last_ts < MIN_MURMUR_GAP_S:
        return f"刚发过，再等等（距上次 {int(now - last_ts)}s）"

    return None


def is_quiet_hours(tz: str = "Asia/Shanghai") -> bool:
    """现在是否在安静时段（23:00-07:00）。
    tz: IANA 时区名，默认 Asia/Shanghai。
    Railway 服务器跑 UTC，必须传正确时区，否则安静窗口会偏移 8 小时。
    """
    h = datetime.now(ZoneInfo(tz)).hour
    return QUIET_START_HOUR <= h or h < QUIET_END_HOUR


# ── 后台循环 ─────────────────────────────────────────────────────────

class MurmurSystem:
    """
    在 gateway.py 里实例化，调用 start() 启动两个后台线程。

    gateway.py 用法：
        murmur_sys = MurmurSystem(
            heart=heart, body=body, desire=desire,
            owner="Dorian",
            call_llm_fn=your_llm_call,
            murmur_store=MurmurStore("murmur.jsonl"),
        )
        murmur_sys.start()

    对话结束后同步状态：
        murmur_sys.set_message_context(just_said_goodnight=False, mood_bad=False)
    """

    def __init__(
        self,
        heart,
        body,
        desire,
        owner: str,
        call_llm_fn,
        murmur_store: Optional[MurmurStore] = None,
    ):
        self.heart  = heart
        self.body   = body
        self.desire = desire
        self.owner  = owner
        self.call_llm_fn = call_llm_fn
        self.store  = murmur_store or MurmurStore()

        self.inhibition = InhibitionState.empty()
        self.last_murmur_ts: dict = {}
        self._msg_ctx: dict = {"just_said_goodnight": False, "mood_bad": False}
        self._lock = threading.Lock()
        self._stop = threading.Event()

    def set_message_context(self, just_said_goodnight: bool = False, mood_bad: bool = False):
        """每轮对话结束后，gateway 调这个更新上下文。"""
        with self._lock:
            self._msg_ctx = {
                "just_said_goodnight": just_said_goodnight,
                "mood_bad": mood_bad,
            }

    def start(self):
        # 启动补跑：先各跑一次，不等第一个间隔结束。
        # ref-PATTERNS §5 + ref-AUTONOMY §1.1：启动时立即跑一次，
        # 防止 Railway 重启后有一整段空窗。
        threading.Thread(target=self._do_tick,   daemon=True, name="tick_boot").start()
        threading.Thread(target=self._do_murmur, daemon=True, name="murmur_boot").start()

        threading.Thread(target=self._tick_loop,     daemon=True, name="tick_loop").start()
        threading.Thread(target=self._murmur_loop,   daemon=True, name="murmur_loop").start()
        threading.Thread(target=self._watchdog_loop, daemon=True, name="watchdog").start()

    def stop(self):
        self._stop.set()

    # ── watchdog ──────────────────────────────────────────────────
    # ref-PATTERNS §5：定时 job 要有 watchdog + 启动补跑自愈。
    # 每 5 分钟检查两个循环是否还活着，死了重启。
    WATCHDOG_INTERVAL_S = 300

    def _watchdog_loop(self):
        while not self._stop.wait(self.WATCHDOG_INTERVAL_S):
            try:
                self._check_and_revive()
            except Exception as e:
                print(f"[watchdog error] {e}")

    def _check_and_revive(self):
        for name, target in (
            ("tick_loop",   self._tick_loop),
            ("murmur_loop", self._murmur_loop),
        ):
            alive = any(
                t.name == name and t.is_alive()
                for t in threading.enumerate()
            )
            if not alive:
                print(f"[watchdog] {name} 挂了，重启")
                threading.Thread(target=target, daemon=True, name=name).start()

    # ── tick 循环 ──────────────────────────────────────────────────

    def _tick_loop(self):
        while not self._stop.wait(TICK_INTERVAL_S):
            try:
                self._do_tick()
            except Exception as e:
                print(f"[tick_loop error] {e}")

    def _do_tick(self):
        # 三层心跳
        self.heart.tick(self.owner)
        self.body.tick(self.owner)

        # body → heartcore 信号
        body_out     = self.body.get_output(self.owner)
        body_signals = body_out.to_heartcore_signals()
        self.heart.inject_body_signals(self.owner, body_signals)

        # heartcore + body → desire
        heart_state = self.heart.get_state(self.owner)
        self.desire.tick(
            longing      = heart_state.attachment.longing,
            na           = heart_state.mood.na,
            pa           = heart_state.mood.pa,
            body_libido  = body_signals["libido"],
            body_fatigue = body_signals["fatigue"],
        )

    # ── murmur 循环 ────────────────────────────────────────────────

    def _murmur_loop(self):
        while not self._stop.wait(MURMUR_INTERVAL_S):
            try:
                self._do_murmur()
            except Exception as e:
                print(f"[murmur_loop error] {e}")

    def _do_murmur(self):
        output = self.desire.peek()
        scores = output.scores  # dict[str, float]

        # 找最高且超阈值的 drive
        eligible = {k: v for k, v in scores.items() if v >= MURMUR_THRESHOLD}

        # 每轮都要留痕：看了几个 drive，有几个过线（ref-PATTERNS §14）
        self.store.write_checked(checked=len(scores), eligible=len(eligible))

        if not eligible:
            return  # 安静——checked 记录在上面，档案里看得到它醒着

        top_drive = max(eligible, key=lambda k: eligible[k])
        top_score = eligible[top_drive]

        # 压抑检查
        with self._lock:
            ctx = dict(self._msg_ctx)
        reason = check_inhibition(
            top_drive, top_score, ctx,
            self.last_murmur_ts, self.inhibition
        )
        if reason:
            # 想说但忍住了——弃权也要记，沉默可见才能回溯
            record = self.store.write_suppressed(top_drive, top_score, reason)
            print(f"[murmur suppressed] {record}")
            return

        # 生成内心独白；LLM 失败不静默，写 fallback marker 兜底
        try:
            text = generate_murmur_text(top_drive, top_score, self.call_llm_fn)
        except Exception as e:
            record = self.store.write_fallback(top_drive, top_score, str(e))
            print(f"[murmur fallback] {record}")
            return

        record = self.store.write(top_drive, top_score, text)
        self.last_murmur_ts[top_drive] = time.time()
        print(f"[murmur] {record}")