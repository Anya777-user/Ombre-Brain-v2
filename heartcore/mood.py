"""
心情系统 — HeartCore 第二层。
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass
class MoodEvent:
    valence: float = 0.0
    arousal: float = 0.4
    channel: str = ""
    weight: float = 1.0

    @property
    def pa_delta(self) -> float:
        return max(0.0, self.valence) * self.weight * 0.1

    @property
    def na_delta(self) -> float:
        return max(0.0, -self.valence) * self.weight * 0.1


@dataclass
class MoodSnapshot:
    pa: float = 0.5
    na: float = 0.1
    arousal: float = 0.4
    event_count: int = 0

    def as_dict(self) -> dict:
        return {
            "pa": round(self.pa, 4),
            "na": round(self.na, 4),
            "arousal": round(self.arousal, 4),
            "event_count": self.event_count,
        }


def compute_mood(
    current: MoodSnapshot,
    events: List[MoodEvent],
    *,
    pa_decay: float = 0.02,
    na_decay: float = 0.03,
) -> MoodSnapshot:
    pa = current.pa * (1.0 - pa_decay) + 0.5 * pa_decay
    na = current.na * (1.0 - na_decay) + 0.1 * na_decay
    arousal = current.arousal

    for ev in events:
        pa = _clamp(pa + ev.pa_delta, 0.0, 1.0)
        na = _clamp(na + ev.na_delta, 0.0, 1.0)
        arousal = _clamp(arousal * 0.9 + ev.arousal * 0.1, 0.0, 1.0)

    return MoodSnapshot(
        pa=round(pa, 4),
        na=round(na, 4),
        arousal=round(arousal, 4),
        event_count=current.event_count + len(events),
    )


def is_down_batch(events: List[MoodEvent], threshold: float = 0.3) -> bool:
    if not events:
        return False
    net = sum(e.pa_delta - e.na_delta for e in events)
    return net < -threshold


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
