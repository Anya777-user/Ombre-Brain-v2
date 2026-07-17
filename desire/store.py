"""
DesireStore —— desire 层的持久化。
把 Drive 和 Thought 列表存到 JSON 文件，重启恢复。
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import List, Optional
from .drive import Drive, DRIVE_KEYS
from .thoughts import Thought


def now_ms() -> int:
    return int(time.time() * 1000)


class DesireStore:
    def __init__(self, path: str = "desire_state.json") -> None:
        self.path = Path(path)

    def load_or_init_drive(self, owner: str):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                d = data.get(owner, {})
                drive = Drive()
                for k in DRIVE_KEYS:
                    if k in d.get("drive", {}):
                        drive.set(k, d["drive"][k])
                last = d.get("last_tick_ms", now_ms())
                return drive, last
            except Exception:
                pass
        return Drive(), now_ms()

    def save_drive(self, drive: Drive, ts: int, owner: str) -> None:
        data = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
            except Exception:
                pass
        data.setdefault(owner, {})
        data[owner]["drive"] = drive.as_dict()
        data[owner]["last_tick_ms"] = ts
        self.path.write_text(json.dumps(data, ensure_ascii=False))

    def load_thoughts(self, owner: str) -> List[Thought]:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                raw = data.get(owner, {}).get("thoughts", [])
                return [Thought(**t) for t in raw]
            except Exception:
                pass
        return []

    def save_thoughts(self, thoughts: List[Thought], owner: str) -> None:
        data = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
            except Exception:
                pass
        data.setdefault(owner, {})
        data[owner]["thoughts"] = [t.as_dict() for t in thoughts]
        self.path.write_text(json.dumps(data, ensure_ascii=False))
