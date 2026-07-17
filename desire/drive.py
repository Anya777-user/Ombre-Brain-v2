"""
八维驱动条 drive —— 需求栏。

八维 (对齐攻略 §2)：
  attachment  想Kitty        curiosity  好奇外面
  reflection  想沉淀/倾诉     duty       记挂没做完的事
  social      想看人群        libido     性驱动
  fatigue     累 (抑制闸)      stress     压力堵

值域 0..1。随时间缓动 (ease_drive)，被 heartcore/body 的信号注入 (inject_signals)，
召唤力 = 驱动值 + 执念加成 (desire_scores)。

分工铁律 (和前两层敲定的)：
- attachment / longing 的"想"由 heartcore.attachment 算好喂进来，desire 不重算曲线。
- libido / fatigue / possess 由 body 算好喂进来，desire 不重算生理。
- stress 主要吃 heartcore 的 NA。
- desire 只负责：把这些缺口放到同一个擂台上比高低，选出"现在最想做的事"。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict


DRIVE_KEYS = (
    "attachment", "curiosity", "reflection", "duty",
    "social", "fatigue", "libido", "stress",
)

# fatigue 是闸，不进擂台 (不计 score)。
GATE_KEYS = ("fatigue",)

# 执念对关联驱动的加成系数 (攻略 FIXATION_DRIVE_BOOST)。
FIXATION_DRIVE_BOOST = 0.35

# fatigue 过线就歇着 (攻略 FATIGUE_REST_GATE)。
FATIGUE_REST_GATE = 0.72

# 每一维的"归位"目标和缓动速率 (idle 时向 baseline 漂)。
# rate = 每拍向 baseline 靠近的比例。attachment/curiosity 慢漂 (缺口累积)，
# fatigue 自己不漂 (靠 body 喂 / 休息回落)。
_EASE = {
    "attachment": (0.15, 0.04),   # (baseline, rate)
    "curiosity":  (0.20, 0.05),
    "reflection": (0.15, 0.05),
    "duty":       (0.10, 0.06),
    "social":     (0.15, 0.06),
    "fatigue":    (0.15, 0.00),   # 不自漂，body 说了算
    "libido":     (0.10, 0.00),   # 不自漂，body 说了算
    "stress":     (0.10, 0.05),
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class Drive:
    """八维驱动条当前值 (0..1)。"""
    attachment: float = 0.15
    curiosity: float = 0.20
    reflection: float = 0.15
    duty: float = 0.10
    social: float = 0.15
    fatigue: float = 0.15
    libido: float = 0.10
    stress: float = 0.10

    def as_dict(self) -> Dict[str, float]:
        return {k: round(getattr(self, k), 4) for k in DRIVE_KEYS}

    def get(self, key: str) -> float:
        return getattr(self, key)

    def set(self, key: str, value: float) -> None:
        setattr(self, key, _clamp01(value))


def ease_drive(drive: Drive, ticks: float = 1.0) -> None:
    """
    随时间向 baseline 缓动。ticks 是经过的心跳拍数 (可小数)。
    idle 越久，自漂的维度越往 baseline 收；喂过信号的维度 (fatigue/libido) 不自漂。
    """
    for key in DRIVE_KEYS:
        baseline, rate = _EASE[key]
        if rate <= 0.0:
            continue
        cur = drive.get(key)
        # 指数式靠近：cur += (baseline - cur) * (1 - (1-rate)^ticks)
        factor = 1.0 - (1.0 - rate) ** max(0.0, ticks)
        drive.set(key, cur + (baseline - cur) * factor)


def inject_signals(
    drive: Drive,
    *,
    longing: float = None,
    na: float = None,
    pa: float = None,
    body_libido: float = None,
    body_fatigue: float = None,
    weight: float = 0.6,
) -> None:
    """
    把 heartcore / body 的信号灌进对应驱动维度。
    None 哨兵语义：None = 本拍无信号跳过，0.0 = 真实低信号。
    """
    w = _clamp01(weight)

    def blend(key: str, target: float) -> None:
        cur = drive.get(key)
        drive.set(key, cur * (1.0 - w) + _clamp01(target) * w)

    if longing is not None:
        blend("attachment", longing)
    if body_libido is not None:
        blend("libido", body_libido / 100.0)
    if body_fatigue is not None:
        blend("fatigue", body_fatigue / 100.0)
    if na is not None:
        pa_val = pa if pa is not None else 0.0
        stress_target = _clamp01(na - 0.3 * pa_val)
        blend("stress", stress_target)

def desire_scores(drive: Drive, fixation_boost: Dict[str, float]) -> Dict[str, float]:
    """
    召唤力 score = 驱动值 + FIXATION_DRIVE_BOOST × 关联执念强度之和。
    fatigue 是闸不计 score (它决定歇不歇，不参与"想做什么"的擂台)。

    fixation_boost: {drive_key: 该维关联执念的强度之和}
    """
    scores: Dict[str, float] = {}
    for key in DRIVE_KEYS:
        if key in GATE_KEYS:
            continue
        boost = FIXATION_DRIVE_BOOST * fixation_boost.get(key, 0.0)
        scores[key] = round(drive.get(key) + boost, 4)
    return scores


def fatigue_gated(drive: Drive) -> bool:
    """疲惫过线 → 该歇着，别硬找事。"""
    return drive.get("fatigue") >= FATIGUE_REST_GATE