from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class PromptContext:
    longing: float = 0.0
    phase: str = "content"
    reunion_hint: str = ""
    pa: float = 0.5
    na: float = 0.1
    arousal: float = 0.4
    sternberg_type: str = "Non-love"
    fatigue: float = 0.15

def build_mood_prompt(ctx: PromptContext) -> str:
    parts = []
    if ctx.longing > 0.35:
        parts.append(f"[longing={ctx.longing:.2f} phase={ctx.phase}]")
    if ctx.reunion_hint:
        parts.append(f"[reunion: {ctx.reunion_hint}]")
    parts.append(f"[mood pa={ctx.pa:.2f} na={ctx.na:.2f} arousal={ctx.arousal:.2f}]")
    parts.append(f"[bond={ctx.sternberg_type}]")
    if ctx.fatigue > 0.5:
        parts.append(f"[fatigue={ctx.fatigue:.2f}]")
    return " ".join(parts)
