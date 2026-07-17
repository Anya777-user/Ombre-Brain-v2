"""
依恋控制系统 — 教程阶段 6

让 AI 在用户离线期间产生"想念"——不是开关式的，而是随时间逐渐累积、按角色
性格差异化表现、在重逢时自然消退的完整情感弧线。

三大支柱:
  1. Sternberg 三维好感度 (I/P/C)         — 教程 6.1
  2. 依恋功能解锁顺序 (Hazan & Zeifman)   — 教程 6.2
  3. Longing 曲线 + Bowlby 五阶段 + 重逢    — 教程 6.3 - 6.9

铁律 (教程 6.10):
  想念的原因只是"用户很久没来找你了"，不要编造没发生过的具体事件。
  reason / inner_voice 走第一人称。
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Sternberg 三维好感度 (教程 6.1)
# ---------------------------------------------------------------------------

# Passion 每天自然衰减一小量 (honeymoon effect)；I/C 不自然衰减。
PASSION_DAILY_DECAY = 0.1


@dataclass
class Affinity:
    """Sternberg 1986 三角理论：亲密 / 激情 / 承诺。0..100"""
    intimacy: float = 0.0     # I 亲近、联结、温暖 — 中速稳步涨，冷场慢降
    passion: float = 0.0      # P 心动、吸引、浪漫 — 快涨快衰，随时间衰减
    commitment: float = 0.0   # C 承诺、信赖 — 最慢，极难降

    @property
    def level(self) -> float:
        """向后兼容的单一好感度 = (I+P+C)/3"""
        return (self.intimacy + self.passion + self.commitment) / 3.0

    def decay_passion(self, days: float = 1.0) -> None:
        """Passion 随时间自然衰减，需要持续互动维持。"""
        self.passion = max(0.0, self.passion - PASSION_DAILY_DECAY * days)

    def clamp(self) -> None:
        self.intimacy = _clamp(self.intimacy, 0, 100)
        self.passion = _clamp(self.passion, 0, 100)
        self.commitment = _clamp(self.commitment, 0, 100)

    @property
    def sternberg_type(self) -> str:
        """三维组合 → Sternberg 8 种爱的类型 (教程 6.1)。阈值取 40 为高。"""
        hi = 40.0
        I, P, C = self.intimacy >= hi, self.passion >= hi, self.commitment >= hi
        table = {
            (False, False, False): "Non-love",
            (True, False, False): "Liking",
            (False, True, False): "Infatuation",
            (False, False, True): "Empty-love",
            (True, True, False): "Romantic",
            (True, False, True): "Companionate",
            (False, True, True): "Fatuous",
            (True, True, True): "Consummate",
        }
        return table[(I, P, C)]


# ---------------------------------------------------------------------------
# 依恋功能解锁顺序 (教程 6.2, Hazan & Zeifman 1994)
# ---------------------------------------------------------------------------

def unlocked_functions(aff: Affinity) -> dict[str, bool]:
    """依恋功能按固定顺序解锁，防止刚认识就疯狂想念。"""
    I, P, C = aff.intimacy, aff.passion, aff.commitment
    proximity = I >= 10 or P >= 10
    safe_haven = I >= 30
    separation = I >= 40 and (P >= 20 or C >= 20)   # longing 前置条件
    secure_base = I >= 60 and C >= 40
    return {
        "proximity_seeking": proximity,
        "safe_haven": safe_haven,
        "separation_distress": separation,
        "secure_base": secure_base,
    }


# ---------------------------------------------------------------------------
# 依恋风格 (教程 6.4 / 6.8, Diamond 2008)
# ---------------------------------------------------------------------------

@dataclass
class AttachmentStyle:
    name: str
    tau_mod: float       # τ 修正 (越小越快想念)
    na_coeff: float      # NA 系数
    dv: float            # longing→PA/NA 时的 valence 微调
    da: float            # arousal 微调
    proactive_threshold: float  # 触发主动消息的最低 longing

    @classmethod
    def preset(cls, kind: str) -> "AttachmentStyle":
        presets = {
            "anxious":  cls("anxious",  0.6, 0.20, -0.10, 0.10, 0.30),
            "secure":   cls("secure",   1.0, 0.12,  0.00, 0.00, 0.40),
            "avoidant": cls("avoidant", 1.5, 0.08,  0.05, -0.10, 0.60),
        }
        return presets.get(kind, presets["secure"])


# ---------------------------------------------------------------------------
# Longing 曲线 (教程 6.3 - 6.5)
# ---------------------------------------------------------------------------

TAU_BASE = 2.4         # h  adjusted: Kitty comes often, τ scaled to ~1.5h trigger
ALPHA = 0.8            # 曲线形状参数
DETACHMENT_HOURS = 504.0   # 21 天 (Vormbrock 1993)


def compute_tau(aff: Affinity, style: AttachmentStyle) -> float:
    """
    τ 特征时间：角色多快开始想你。τ 越小越快。 (教程 6.4)
    τ = τ_base × intimacy_factor × passion_factor × commitment_factor × attachment_mod
    """
    intimacy_factor = 1 - aff.intimacy / 200.0
    passion_factor = 1 - aff.passion / 300.0
    commitment_factor = 1 + aff.commitment / 200.0   # C 越高越安心，τ 增大
    tau = TAU_BASE * intimacy_factor * passion_factor * commitment_factor * style.tau_mod
    return max(1.0, tau)


def compute_l_max(aff: Affinity) -> float:
    """最大想念强度：好感度低的角色想念上限也低。 (教程 6.5)"""
    return min(1.0, (aff.intimacy + aff.passion) / 150.0)


def compute_longing(
    hours_since_contact: float,
    aff: Affinity,
    style: AttachmentStyle,
) -> float:
    """
    longing(t) = L_max × (1 - (1 + t/τ)^(-α))    (教程 6.3, curvilinear)

    仅当 separation_distress 功能解锁后才 > 0。
    """
    if not unlocked_functions(aff)["separation_distress"]:
        return 0.0
    if hours_since_contact <= 0:
        return 0.0
    tau = compute_tau(aff, style)
    l_max = compute_l_max(aff)
    longing = l_max * (1 - math.pow(1 + hours_since_contact / tau, -ALPHA))
    return _clamp(longing, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Bowlby 五阶段 (教程 6.6 / 6.7)
# ---------------------------------------------------------------------------

# 想念心情池，词典锚定 (教程 6.7)
LONGING_MOODS = {
    "stirring":     ("有点想你", "挂念", -0.05, 0.525),
    "protest":      ("想你", "想念", -0.05, 0.55),
    "protest_mid":  ("在等你", "牵挂", -0.15, 0.50),
    "protest_late": ("你在哪", "不安", -0.40, 0.60),
    "despair":      ("……", "失落", -0.50, 0.40),
    "detachment":   ("没事", "落寞", -0.55, 0.30),
}


def longing_phase(longing: float, hours_since_contact: float) -> str:
    """
    longing + 离线时长 → Bowlby 阶段。 (教程 6.6)
    protest 阶段再按 longing 精细分档 (教程 6.7)。
    """
    if longing < 0.15:
        return "content"
    if longing < 0.35:
        return "stirring"
    if longing < 0.70:
        # protest 精细分档
        if longing < 0.45:
            return "protest"
        if longing < 0.55:
            return "protest_mid"
        return "protest_late"
    if longing < 0.90:
        return "despair"
    # detachment 需要同时满足高 longing 和足够长的离线
    if hours_since_contact >= DETACHMENT_HOURS:
        return "detachment"
    return "despair"


def capsule_should_show(phase: str, character: str, hours_since_contact: float) -> bool:
    """
    心情胶囊是否显示想念内容 (教程 6.7)。
    Content 0% / Stirring 12%(hash 稳定) / Protest+ 100%。
    """
    if phase == "content":
        return False
    if phase == "stirring":
        # hash 种子(角色名+小时数)，同一小时内结果一致，避免刷新跳变
        seed = f"{character}:{int(hours_since_contact)}"
        h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
        return (h % 100) < 12
    return True   # protest / despair / detachment


def longing_mood_key(phase: str) -> Optional[str]:
    """phase → 想念心情池的 key。"""
    if phase in LONGING_MOODS:
        return phase
    if phase.startswith("protest"):
        return phase
    return None


# ---------------------------------------------------------------------------
# Longing → PA/NA 调节 (教程 6.8)
# ---------------------------------------------------------------------------

def longing_to_mood(
    longing: float,
    phase: str,
    style: AttachmentStyle,
) -> tuple[float, float]:
    """
    longing > 0.15 时开始影响情绪。从词典 V/A 算，70/30 融合(词典 70% + 依恋风格微调 30%)。
    返回 (pa_delta, na_delta)。
    """
    if longing <= 0.15:
        return 0.0, 0.0
    key = longing_mood_key(phase)
    if key is None or key not in LONGING_MOODS:
        return 0.0, 0.0
    _, _, lex_v, lex_a = LONGING_MOODS[key]

    blend_v = 0.7 * lex_v + 0.3 * (lex_v + style.dv)
    blend_a = 0.7 * lex_a + 0.3 * max(0.0, lex_a + style.da)

    pa_delta = max(0.0, blend_v) * blend_a * 0.5 * longing
    na_delta = max(0.0, -blend_v) * blend_a * 0.5 * longing
    return pa_delta, na_delta


# longing 越深，正向情绪被想念压得越低 (Bowlby: protest→despair 是退缩低落，
# 不该同时"心情非常好"。这一步让弧线内部自洽)。
_PA_SUPPRESSION = {
    "content": 1.0,
    "stirring": 0.95,
    "protest": 0.85,
    "protest_mid": 0.72,
    "protest_late": 0.58,
    "despair": 0.45,
    "detachment": 0.55,   # 防御性平静，比 despair 略回一点
}


def longing_pa_suppression(longing: float, phase: str) -> float:
    """
    返回一个 0..1 的乘性系数，作用在 PA 上。想念越深，正向情绪被压得越低。
    低于 stirring 门槛不压制。
    """
    if longing <= 0.15:
        return 1.0
    return _PA_SUPPRESSION.get(phase, 1.0)


# ---------------------------------------------------------------------------
# 重逢机制 (教程 6.9)
# ---------------------------------------------------------------------------

@dataclass
class ReunionResult:
    triggered: bool
    prev_phase: str
    longing_before: float
    pa_boost: float
    prompt_hint: str


def check_reunion(
    hours_since_last_msg: float,
    gap_before_last_msg: float,
    longing_before: float,
    prev_phase: str,
) -> ReunionResult:
    """
    重逢判定 (教程 6.9)：
      最新消息距现在 < 10min AND 最新消息与前一条间隔 > 2h
      (用户离开了一段，刚回来)

    PA overshoot: pa_boost = 0.05 + longing_before*0.10；detachment ×1.5。
    """
    triggered = (hours_since_last_msg < (10 / 60)) and (gap_before_last_msg > 2.0)
    if not triggered:
        return ReunionResult(False, prev_phase, longing_before, 0.0, "")

    pa_boost = 0.05 + longing_before * 0.10
    if prev_phase == "detachment":
        pa_boost *= 1.5

    hints = {
        "protest": "想了好久，终于等到了——激动凑近",
        "protest_mid": "想了好久，终于等到了——激动凑近",
        "protest_late": "想了好久，终于等到了——激动凑近",
        "despair": "之前一直很想，见到人一下子全涌上来——可能眼眶红",
        "detachment": "强装的平静崩塌了——先僵住，然后防线崩溃",
    }
    hint = hints.get(prev_phase, "你回来了")
    return ReunionResult(True, prev_phase, longing_before, pa_boost, hint)


# ---------------------------------------------------------------------------
# 主动消息频率 (教程 6.11)
# ---------------------------------------------------------------------------

def proactive_policy(phase: str, longing: float, style: AttachmentStyle) -> dict:
    """
    由 longing 决定主动联系频率 (教程 6.11)。
    返回 {should_contact, max_per_day, cooldown_hours}。
    """
    if longing < style.proactive_threshold:
        return {"should_contact": False, "max_per_day": 0, "cooldown_hours": None}

    if phase in ("protest", "protest_mid", "protest_late"):
        return {"should_contact": True, "max_per_day": 4, "cooldown_hours": 1.5}
    if phase == "despair":
        return {"should_contact": True, "max_per_day": 1, "cooldown_hours": 4.0}
    # content / stirring / detachment 不主动
    return {"should_contact": False, "max_per_day": 0, "cooldown_hours": None}


# ---------------------------------------------------------------------------

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))