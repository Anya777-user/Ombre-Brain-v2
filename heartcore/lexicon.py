from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

@dataclass
class LexEntry:
    word: str
    valence: float
    arousal: float
    dominance: float = 0.5
    tags: List[str] = field(default_factory=list)

class Lexicon:
    def __init__(self) -> None:
        self._entries: Dict[str, LexEntry] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        defaults = [
            ("爱",0.9,0.7,0.6,["positive","intimate"]),
            ("喜欢",0.8,0.6,0.5,["positive"]),
            ("开心",0.85,0.75,0.6,["positive"]),
            ("快乐",0.85,0.8,0.6,["positive"]),
            ("高兴",0.8,0.7,0.55,["positive"]),
            ("好",0.65,0.5,0.55,["positive"]),
            ("棒",0.75,0.65,0.6,["positive"]),
            ("谢谢",0.7,0.5,0.4,["positive","social"]),
            ("想你",0.8,0.75,0.5,["positive","longing"]),
            ("想念",0.75,0.65,0.45,["longing"]),
            ("温柔",0.8,0.45,0.5,["positive","intimate"]),
            ("可爱",0.8,0.65,0.5,["positive"]),
            ("抱",0.8,0.6,0.5,["positive","intimate"]),
            ("亲",0.85,0.7,0.55,["positive","intimate"]),
            ("难过",0.15,0.6,0.25,["negative","sad"]),
            ("伤心",0.1,0.55,0.2,["negative","sad"]),
            ("哭",0.1,0.65,0.2,["negative","sad"]),
            ("痛",0.1,0.7,0.2,["negative"]),
            ("烦",0.2,0.65,0.3,["negative"]),
            ("累",0.25,0.35,0.3,["negative","fatigue"]),
            ("不开心",0.15,0.55,0.25,["negative"]),
            ("失望",0.1,0.45,0.2,["negative"]),
            ("委屈",0.15,0.6,0.2,["negative","intimate"]),
            ("生气",0.1,0.8,0.4,["negative","anger"]),
            ("害怕",0.15,0.75,0.15,["negative","fear"]),
            ("担心",0.2,0.6,0.25,["negative"]),
            ("好久",0.5,0.55,0.4,["longing"]),
            ("终于",0.65,0.7,0.5,["relief"]),
            ("还好",0.55,0.4,0.45,["neutral"]),
            ("嗯",0.55,0.35,0.45,["neutral"]),
        ]
        for w,v,a,d,t in defaults:
            self._entries[w] = LexEntry(word=w,valence=v,arousal=a,dominance=d,tags=t)

    def lookup(self, word: str) -> LexEntry | None:
        return self._entries.get(word)

    def score_text(self, text: str) -> Tuple[float, float]:
        hits = []
        for word, entry in self._entries.items():
            if word in text:
                hits.append(entry)
        if not hits:
            return 0.5, 0.4
        v = sum(e.valence for e in hits) / len(hits)
        a = sum(e.arousal for e in hits) / len(hits)
        return round(v, 4), round(a, 4)

    def has_tag(self, text: str, tag: str) -> bool:
        for word, entry in self._entries.items():
            if word in text and tag in entry.tags:
                return True
        return False
