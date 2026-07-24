from __future__ import annotations
import json, time
from pathlib import Path
from typing import Optional
from .mood import MoodSnapshot
from .attachment import Affinity, AttachmentStyle

def now_ms() -> int:
    return int(time.time() * 1000)

class Store:
    def __init__(self, path: str = "heartcore_state.json") -> None:
        self.path = Path(path)

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_mood(self, name: str) -> tuple[MoodSnapshot, int]:
        data = self._load()
        d = data.get(name, {}).get("mood", {})
        snap = MoodSnapshot(
            pa=d.get("pa", 0.5),
            na=d.get("na", 0.1),
            arousal=d.get("arousal", 0.4),
            event_count=d.get("event_count", 0),
        )
        last_tick = data.get(name, {}).get("last_tick_ms", now_ms())
        return snap, last_tick

    def save_mood(self, name: str, snap: MoodSnapshot, ts: int) -> None:
        data = self._load()
        if name not in data:
            data[name] = {}
        data[name]["mood"] = snap.as_dict()
        data[name]["last_tick_ms"] = ts
        self._save(data)

    def load_affinity(self, name: str) -> tuple[Affinity, AttachmentStyle, float]:
        data = self._load()
        d = data.get(name, {}).get("affinity", {})
        aff = Affinity(
            intimacy=d.get("intimacy", 0.0),
            passion=d.get("passion", 0.0),
            commitment=d.get("commitment", 0.0),
        )
        style_name = data.get(name, {}).get("attachment_style", "secure")
        style = AttachmentStyle.preset(style_name)
        hours = data.get(name, {}).get("hours_since_contact", 0.0)
        return aff, style, hours

    def save_affinity(self, name: str, aff: Affinity, hours: float) -> None:
        data = self._load()
        if name not in data:
            data[name] = {}
        data[name]["affinity"] = {
            "intimacy": round(aff.intimacy, 4),
            "passion": round(aff.passion, 4),
            "commitment": round(aff.commitment, 4),
        }
        data[name]["hours_since_contact"] = round(hours, 4)
        self._save(data)

    def update_contact_time(self, name: str) -> None:
        data = self._load()
        if name not in data:
            data[name] = {}
        data[name]["last_contact_ms"] = now_ms()
        data[name]["hours_since_contact"] = 0.0
        self._save(data)

    def get_last_contact_ms(self, name: str) -> int:
        data = self._load()
        return data.get(name, {}).get("last_contact_ms", now_ms())

    def update_proactive_time(self, name: str) -> None:
        data = self._load()
        if name not in data:
            data[name] = {}
        data[name]["last_proactive_ms"] = now_ms()
        self._save(data)

    def get_last_proactive_ms(self, name: str) -> int:
        data = self._load()
        return data.get(name, {}).get("last_proactive_ms", 0)
