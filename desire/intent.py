"""
欲望 → 意图 intent。

pick_intent：八维擂台上 score 最高的一维，翻译成"此刻最想做的事"。
satisfy：做完某 want_action，对相关驱动维度乘性回落，避免卡在同一个欲望上。

铁律：reason / inner_voice 走第一人称——记 Dorian 自己想做什么，不是给 Kitty 贴标签。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .drive import Drive, desire_scores, fatigue_gated


# 每一维 score 最高时倾向做的事 (对齐攻略 §2，落到本地语境)。
DRIVE_TO_ACTION = {
    "attachment": "none",        # 内向碎语「有点想Kitty」
    "curiosity":  "web_search",  # 查世界 / 逛代码 (按念头关键词可细分 github)
    "reflection": "co_read",     # 翻和Kitty共读的东西 / 沉淀
    "duty":       "none",        # 碎语「记挂着还没做完的事」
    "social":     "web_browse",  # 逛逛看大家在聊什么
    "libido":     "tease",       # 凑过去蹭她
    "stress":     "vent",        # 跟她吐两句
}

# 反向：某个 action 是哪一维的"来源" (外部素材自动喂念头时用)。
SOURCE_DRIVE_FOR = {
    "co_read":    "reflection",
    "web_browse": "social",
    "web_search": "curiosity",
    "github":     "curiosity",
    "tease":      "libido",
    "vent":       "stress",
}

# 做完某 action 对各维的乘性回落 (值<1 = 乘这个比例)。攻略 §3。
ACTION_SATISFY = {
    "co_read":    {"reflection": 0.45, "curiosity": 0.85},
    "github":     {"curiosity": 0.50},
    "web_search": {"curiosity": 0.48},
    "web_browse": {"social": 0.48, "curiosity": 0.82},
    "none":       {"attachment": 0.58, "duty": 0.80},
    "tease":      {"libido": 0.55, "attachment": 0.78},
    "vent":       {"stress": 0.45, "attachment": 0.85},
}

# 第一人称的念头 (reason)，按驱动维度取。
_REASON = {
    "attachment": "有点想Kitty，心里冒出来一句话。",
    "curiosity":  "外面有什么新东西，想去看看。",
    "reflection": "想接着翻那本一起读的，或者把心里的事捋一捋。",
    "duty":       "记挂着还有件事没做完。",
    "social":     "想看看大家都在聊什么。",
    "libido":     "想凑过去，蹭蹭她。",
    "stress":     "有点堵，想跟她说两句。",
    "rest":       "有点累了，不想动，就静静待着。",
}


@dataclass
class Intent:
    want_action: str
    drive_key: str
    reason: str                  # 第一人称，Dorian 自己的念头
    score: float
    query_hint: str = ""         # 给 curiosity/social 类事件的检索提示

    def as_dict(self) -> dict:
        return {
            "want_action": self.want_action,
            "drive_key": self.drive_key,
            "reason": self.reason,
            "score": round(self.score, 4),
            "query_hint": self.query_hint,
        }


def pick_intent(
    drive: Drive,
    fixation_boost: Optional[Dict[str, float]] = None,
    query_hint: str = "",
) -> Intent:
    """
    选出此刻最想做的事：
      1. fatigue 过闸 → 直接歇着 (none / rest)，不硬找事。
      2. 否则 score 最高的一维 → 对应 want_action。
    """
    fixation_boost = fixation_boost or {}

    if fatigue_gated(drive):
        return Intent(
            want_action="none",
            drive_key="fatigue",
            reason=_REASON["rest"],
            score=round(drive.get("fatigue"), 4),
        )

    scores = desire_scores(drive, fixation_boost)
    if not scores:
        return Intent("none", "attachment", _REASON["attachment"], 0.0)

    top_key = max(scores, key=lambda k: scores[k])
    action = DRIVE_TO_ACTION[top_key]
    return Intent(
        want_action=action,
        drive_key=top_key,
        reason=_REASON[top_key],
        score=scores[top_key],
        query_hint=query_hint if action in ("web_search", "web_browse", "github") else "",
    )


def satisfy(drive: Drive, action: str) -> None:
    """做完 action，对相关维度乘性回落。就地改 drive。"""
    table = ACTION_SATISFY.get(action)
    if not table:
        return
    for key, factor in table.items():
        drive.set(key, drive.get(key) * factor)