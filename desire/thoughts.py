"""
念头池 —— 执念与闪念。

Thought: 一个念头，有驱动来源、强度、寿命。
tick_thoughts: 每拍衰减/加强/反哺 drive。
feed_thought: 外部喂入一个念头。
fixation_boost_map: 返回各维执念加成。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional

KIND_FLIT = "flit"
KIND_FIXATION = "fixation"
THOUGHT_MAX_DEFAULT = 12
DECAY_FLIT = 0.15
DECAY_FIXATION = 0.05
FIXATION_THRESHOLD = 0.65


@dataclass
class Thought:
    text: str
    drive: str
    kind: str = KIND_FLIT
    strength: float = 0.5
    age: int = 0

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "drive": self.drive,
            "kind": self.kind,
            "strength": round(self.strength, 4),
            "age": self.age,
        }


def tick_thoughts(thoughts: List[Thought], drive) -> List[Thought]:
    resolved = []
    decay_map = {KIND_FLIT: DECAY_FLIT, KIND_FIXATION: DECAY_FIXATION}
    surviving = []
    for t in thoughts:
        t.age += 1
        decay = decay_map.get(t.kind, DECAY_FLIT)
        t.strength = max(0.0, t.strength - decay)
        if t.strength >= FIXATION_THRESHOLD:
            t.kind = KIND_FIXATION if t.strength > 0.05 else t.kind
            surviving.append(t)
            cur = drive.get(t.drive) if hasattr(drive, "get") else getattr(drive, t.drive, 0.0)
            boost = t.strength * 0.08
            new_val = min(1.0, cur + boost)
            if hasattr(drive, "set"):
                drive.set(t.drive, new_val)
        else:
            resolved.append(t)
    thoughts[:] = surviving
    return resolved


def feed_thought(
    thoughts: List[Thought],
    text: str,
    drive: str,
    kind: str = KIND_FLIT,
    strength: float = 0.5,
    max_size: int = THOUGHT_MAX_DEFAULT,
) -> Thought:
    for t in thoughts:
        if t.text == text and t.drive == drive:
            t.strength = min(1.0, t.strength + strength * 0.5)
            t.age = 0
            return t
    th = Thought(text=text, drive=drive, kind=kind, strength=strength)
    thoughts.append(th)
    if len(thoughts) > max_size:
        thoughts.sort(key=lambda x: x.strength)
        thoughts.pop(0)
    return th


def fixation_boost_map(thoughts: List[Thought]) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for t in thoughts:
        if t.kind == KIND_FIXATION:
            result[t.drive] = result.get(t.drive, 0.0) + t.strength
    return result
