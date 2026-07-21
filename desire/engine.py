"""
DesireCore —— 第四层主入口。

一拍 tick 发生什么 (对齐攻略 §8 端到端闭环)：
  1. ease_drive         驱动条按时间缓动
  2. inject_signals     灌 heartcore(longing/na/pa) + body(libido/fatigue) 的信号
  3. tick_thoughts      念头池衰减/加强/反哺 drive
  4. pick_intent        八维擂台选出此刻最想做的事
  5. 存档

做完某件事后调 satisfy(action) 让对应欲望回落。
自动冒念头：autofeed_voice (内向碎语) / autofeed_material (外部素材)。

gating：driven_behavior_enabled 默认 False —— 只读状态照常算，但不覆盖真实行为。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .drive import Drive, DRIVE_KEYS, ease_drive, inject_signals, fatigue_gated
from .thoughts import (
    Thought, tick_thoughts, feed_thought, fixation_boost_map,
    THOUGHT_MAX_DEFAULT, KIND_FLIT,
)
from .intent import (
    Intent, pick_intent, satisfy, SOURCE_DRIVE_FOR,
)
from .store import DesireStore, now_ms


MS_PER_TICK = 1800 * 1000       # 攻略默认心跳 1800s，用于把真实时间换成"拍数"


@dataclass
class DesireOutput:
    """一次 tick 的对外产物。"""
    drive: Dict[str, float]
    scores: Dict[str, float]
    intent: dict
    fatigue_gated: bool
    thought_count: int
    thoughts: List[dict]
    resolved: List[dict]        # 本拍想透了出池的念头
    driven_behavior_enabled: bool

    def as_dict(self) -> dict:
        return {
            "drive": self.drive,
            "scores": self.scores,
            "intent": self.intent,
            "fatigue_gated": self.fatigue_gated,
            "thought_count": self.thought_count,
            "thoughts": self.thoughts,
            "resolved": self.resolved,
            "driven_behavior_enabled": self.driven_behavior_enabled,
        }


class DesireCore:
    def __init__(
        self,
        store: Optional[DesireStore] = None,
        owner: str = "dorian",
        driven_behavior_enabled: bool = False,
        thought_max: int = THOUGHT_MAX_DEFAULT,
    ) -> None:
        self.store = store or DesireStore()
        self.owner = owner
        self.driven_behavior_enabled = driven_behavior_enabled
        self.thought_max = thought_max
        self.drive, self._last_tick_ms = self.store.load_or_init_drive(owner)
        self.thoughts: List[Thought] = self.store.load_thoughts(owner)

    # -- 主循环 -----------------------------------------------------------

    def tick(
        self,
        to_ms: Optional[int] = None,
        *,
        longing: float = 0.0,
        na: float = 0.0,
        pa: float = 0.0,
        body_libido: float = 0.0,
        body_fatigue: float = 0.0,
        query_hint: str = "",
    ) -> DesireOutput:
        now = to_ms if to_ms is not None else now_ms()
        elapsed = max(0, now - self._last_tick_ms)
        ticks = elapsed / MS_PER_TICK if MS_PER_TICK else 1.0

        # 1. 缓动
        ease_drive(self.drive, ticks)
        # 2. 注入外层信号
        inject_signals(
            self.drive,
            longing=longing, na=na, pa=pa,
            body_libido=body_libido, body_fatigue=body_fatigue,
        )
        # 3. 念头池推进 (会反哺 drive)
        resolved = tick_thoughts(self.thoughts, self.drive)
        # 4. 选意图
        boost = fixation_boost_map(self.thoughts)
        intent = pick_intent(self.drive, boost, query_hint=query_hint)

        # 5. 存档
        self._last_tick_ms = now
        self.store.save_drive(self.drive, now, self.owner)
        self.store.save_thoughts(self.thoughts, self.owner)

        return self._output(intent, resolved)

    def _output(self, intent: Intent, resolved: List[Thought]) -> DesireOutput:
        from .drive import desire_scores
        boost = fixation_boost_map(self.thoughts)
        return DesireOutput(
            drive=self.drive.as_dict(),
            scores=desire_scores(self.drive, boost),
            intent=intent.as_dict(),
            fatigue_gated=fatigue_gated(self.drive),
            thought_count=len(self.thoughts),
            thoughts=[t.as_dict() for t in self.thoughts],
            resolved=[t.as_dict() for t in resolved],
            driven_behavior_enabled=self.driven_behavior_enabled,
        )

    def peek(self, query_hint: str = "") -> DesireOutput:
        """只读当前状态，不推进时间、不存档。"""
        boost = fixation_boost_map(self.thoughts)
        intent = pick_intent(self.drive, boost, query_hint=query_hint)
        return self._output(intent, [])

    # -- 互动积累 ---------------------------------------------------------

    def observe_interaction(self) -> None:
        """每次真实对话后调一次：attachment += 0.03，独立于 longing。"""
        from .drive import observe_interaction as _observe
        _observe(self.drive)
        self.store.save_drive(self.drive, self._last_tick_ms, self.owner)

    # -- 做完事，回落 -----------------------------------------------------

    def satisfy(self, action: str) -> None:
        satisfy(self.drive, action)
        self.store.save_drive(self.drive, self._last_tick_ms, self.owner)

    # -- 喂念头 -----------------------------------------------------------

    def feed(self, text: str, drive: str, kind: str = KIND_FLIT,
             strength: float = 0.5) -> Thought:
        th = feed_thought(self.thoughts, text, drive, kind, strength, self.thought_max)
        self.store.save_thoughts(self.thoughts, self.owner)
        return th

    def autofeed_voice(self, text: str, strength: float = 0.45) -> Optional[Thought]:
        """
        内向碎语 → 关联当下最强欲望维度 (argmax，fatigue 除外)，落成闪念。
        对齐攻略 §9-1 内向碎语来源。
        """
        candidates = {k: self.drive.get(k) for k in DRIVE_KEYS if k != "fatigue"}
        if not candidates:
            return None
        top = max(candidates, key=lambda k: candidates[k])
        th = feed_thought(self.thoughts, text, top, KIND_FLIT, strength, self.thought_max)
        self.store.save_thoughts(self.thoughts, self.owner)
        return th

    def autofeed_material(self, text: str, action: str,
                          strength: float = 0.5) -> Optional[Thought]:
        """
        外部素材 (翻到的书摘/刷到的帖/查到的世界) → 按 action 反向映射到来源维度。
        对齐攻略 §9-1 外部素材来源 + source_drive_for。
        """
        drive = SOURCE_DRIVE_FOR.get(action)
        if drive is None:
            return None
        th = feed_thought(self.thoughts, text, drive, KIND_FLIT, strength, self.thought_max)
        self.store.save_thoughts(self.thoughts, self.owner)
        return th

    # -- 驱动行为门控 -----------------------------------------------------

    def resolve_action(self, sentinel_action: str) -> str:
        """
        宿主决定要冒头时调这个。
        gated 关：返回 sentinel 原本的决定 (只观察，不动手)。
        gated 开：用当前最高欲望覆盖 want_action。
        """
        if not self.driven_behavior_enabled:
            return sentinel_action
        boost = fixation_boost_map(self.thoughts)
        return pick_intent(self.drive, boost).want_action