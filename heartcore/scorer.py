from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .lexicon import Lexicon

@dataclass
class RatingInput:
    text: str
    channel: str = "secondary"
    context: str = ""

@dataclass
class RatingResult:
    valence: float
    arousal: float
    dominance: float
    has_intimate: bool
    has_negative: bool
    raw_text: str

class Scorer:
    def __init__(self, lexicon: Lexicon) -> None:
        self.lexicon = lexicon

    def score(self, inp: RatingInput) -> RatingResult:
        text = inp.text
        v, a = self.lexicon.score_text(text)
        has_intimate = self.lexicon.has_tag(text, "intimate")
        has_negative = self.lexicon.has_tag(text, "negative")
        d = 0.5
        return RatingResult(
            valence=v,
            arousal=a,
            dominance=d,
            has_intimate=has_intimate,
            has_negative=has_negative,
            raw_text=text,
        )
