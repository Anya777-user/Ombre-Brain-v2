from __future__ import annotations
import random
from dataclasses import dataclass
from typing import Optional

from .lexicon import Lexicon
from .scorer import Scorer, RatingInput, RatingResult
from .mood import MoodEvent, MoodSnapshot, compute_mood, is_down_batch
from .attachment import (
    Affinity, AttachmentStyle,
    compute_longing, longing_phase, longing_to_mood,
    longing_pa_suppression,
    check_reunion, proactive_policy, capsule_should_show,
    LONGING_MOODS,
)
from .prompt import PromptContext, build_mood_prompt
from .store import Store, now_ms


@dataclass
class TickResult:
    snapshot: MoodSnapshot
    longing: float
    phase: str
    reunion_hint: str
    proactive: dict


class HeartCore:
    def __init__(
        self,
        store: Optional[Store] = None,
        lexicon: Optional[Lexicon] = None,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.store = store or Store()
        self.lexicon = lexicon or Lexicon()
        self.scorer = Scorer(self.lexicon)
        self.rng = rng or random.Random()

    def rate_and_apply(
        self,
        name: str,
        rating_json: dict,
        channel: str = "secondary",
    ) -> RatingResult:
        text = rating_json.get("text", "")
        inp = RatingInput(text=text, channel=channel)
        result = self.scorer.score(inp)
        snap, last_tick = self.store.load_mood(name)
        events = [MoodEvent(
            valence=result.valence,
            arousal=result.arousal,
            channel=channel,
            weight=1.0,
        )]
        new_snap = compute_mood(snap, events)
        self.store.save_mood(name, new_snap, last_tick)
        self.store.update_contact_time(name)
        return result

    def tick(self, name: str) -> TickResult:
        snap, last_tick = self.store.load_mood(name)
        now = now_ms()
        hours_elapsed = max(0.0, (now - last_tick) / 3_600_000)

        new_snap = compute_mood(snap, [])
        self.store.save_mood(name, new_snap, now)

        aff, style, hours_since = self.store.load_affinity(name)
        hours_since += hours_elapsed
        self.store.save_affinity(name, aff, hours_since)

        longing = compute_longing(hours_since, aff, style)
        phase = longing_phase(longing, hours_since)

        last_contact_ms = self.store.get_last_contact_ms(name)
        gap_before = max(0.0, (last_tick - last_contact_ms) / 3_600_000)
        hours_since_last = max(0.0, (now - last_contact_ms) / 3_600_000)
        reunion = check_reunion(hours_since_last, gap_before, longing, phase)
        reunion_hint = reunion.prompt_hint if reunion.triggered else ""

        proactive = proactive_policy(phase, longing, style)

        return TickResult(
            snapshot=new_snap,
            longing=round(longing, 4),
            phase=phase,
            reunion_hint=reunion_hint,
            proactive=proactive,
        )

    def build_context(self, name: str) -> str:
        snap, _ = self.store.load_mood(name)
        aff, style, hours_since = self.store.load_affinity(name)
        longing = compute_longing(hours_since, aff, style)
        phase = longing_phase(longing, hours_since)
        ctx = PromptContext(
            longing=longing,
            phase=phase,
            pa=snap.pa,
            na=snap.na,
            arousal=snap.arousal,
            sternberg_type=aff.sternberg_type,
            fatigue=0.15,
        )
        return build_mood_prompt(ctx)

    def get_state(self, name: str):
        snap, _ = self.store.load_mood(name)
        aff, style, hours_since = self.store.load_affinity(name)
        longing = compute_longing(hours_since, aff, style)

        class _State:
            pass
        state = _State()

        class _Attachment:
            pass
        att = _Attachment()
        att.longing = longing
        state.attachment = att
        state.mood = snap
        return state

    def inject_body_signals(self, name: str, signals: dict) -> None:
        pass
