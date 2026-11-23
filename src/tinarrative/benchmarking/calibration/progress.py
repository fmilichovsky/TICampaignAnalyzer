"""How far an extraction of the calibration table has come: per campaign, and as a share of the work and time left."""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal

Phase = Literal["waiting", "decompress", "survey", "sequence", "narrative", "done"]
PHASE_WEIGHTS: Final[Mapping[Phase, float]] = {"decompress": 0.03, "survey": 0.14, "sequence": 0.75, "narrative": 0.08}
"""Each phase's share of a campaign's work, as measured on a clean extraction; they add up to 1."""
SAVE_PHASES: Final[tuple[Phase, ...]] = ("survey", "sequence")
"""The phases that report each save they finish; the others are credited whole when they end."""
ESTIMATE_FROM: Final = 0.05
"""The share of the work done before a time left is estimated, so the first saves give no wild estimate."""


@dataclass(frozen=True)
class CampaignStep:
    """Where one campaign is: its phase and the saves of that phase done, out of its saves."""

    name: str
    phase: Phase
    done: int
    total: int


@dataclass(frozen=True)
class ProgressSnapshot:
    """The extraction at one moment: each campaign's step, the work done and the time spent. A unit of work is a
    decompressed byte of a save taken through every phase."""

    campaigns: tuple[CampaignStep, ...]
    done_work: float
    total_work: float
    elapsed: float
    """Seconds since the extraction started."""

    @property
    def fraction(self) -> float:
        """The share of the work done, from 0 to 1; 1 when there is no work."""
        # Rounded so that the weighted credits of a finished extraction add up to exactly 1.
        return 1.0 if self.total_work <= 0 else min(round(self.done_work / self.total_work, 9), 1.0)

    @property
    def remaining(self) -> float | None:
        """Seconds left at the throughput so far; None before ``ESTIMATE_FROM`` of the work is done or once it is all
        done."""
        fraction = self.fraction
        if fraction < ESTIMATE_FROM or fraction >= 1:
            return None
        return self.elapsed * (1 - fraction) / fraction

    @property
    def running(self) -> tuple[CampaignStep, ...]:
        return tuple(step for step in self.campaigns if step.phase not in {"waiting", "done"})

    def text(self) -> str:
        """One line for a person, e.g. ``resist-long: sequence 41/63 · 58% · about 30 s left``."""
        parts = [", ".join(_step_text(step) for step in self.running), f"{math.floor(self.fraction * 100)}%"]
        remaining = self.remaining
        if remaining is not None:
            parts.append(f"{_duration(remaining)} left")
        return " · ".join(part for part in parts if part)

    def to_status(self) -> dict[str, Any]:
        """The ``progress`` member of ``status.js``: everything a reader shows, worked out here."""
        remaining = self.remaining
        return {
            "percent": math.floor(self.fraction * 1000) / 10,
            "elapsed_seconds": round(self.elapsed),
            "remaining_seconds": None if remaining is None else round(remaining),
            "text": self.text(),
            "campaigns": [
                {"name": step.name, "phase": step.phase, "done": step.done, "total": step.total}
                for step in self.campaigns
            ],
        }


class ExtractionProgress:
    """The progress of one extraction, told to ``on_change`` after every change; safe to update from any thread.

    A save's decompressed size, times a phase's weight, is credited once per phase: when a save phase finishes the
    save, or when any other phase ends. The order in which saves finish does not matter.
    """

    def __init__(
        self,
        campaigns: Mapping[str, Mapping[str, int]],
        *,
        on_change: Callable[[ProgressSnapshot], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """``campaigns`` gives, in extraction order, each campaign's decompressed save names and their sizes."""
        self._sizes = {name: dict(saves) for name, saves in campaigns.items()}
        self._phases: dict[str, Phase] = dict.fromkeys(self._sizes, "waiting")
        self._credited: dict[str, set[str]] = {name: set() for name in self._sizes}
        self._done_work = 0.0
        self._total_work = sum(sum(saves.values()) for saves in self._sizes.values()) * sum(PHASE_WEIGHTS.values())
        self._on_change = on_change
        self._clock = clock
        self._started = clock()
        self._lock = threading.Lock()

    def phase(self, campaign: str, phase: Phase) -> None:
        """Move ``campaign`` to ``phase``; leaving a phase credits the saves it did not report (all of them for a
        phase that reports none, merged duplicates for one that does), so a finished campaign is fully credited."""
        with self._lock:
            self._top_up(campaign)
            self._phases[campaign] = phase
            self._credited[campaign] = set()
            snapshot = self._snapshot()
        self._tell(snapshot)

    def saves_done(self, campaign: str, names: Iterable[str]) -> None:
        """Credit the saves ``names`` (decompressed file names) to ``campaign``'s current phase; a save already
        credited, a name the campaign does not list, or a phase that reports no saves changes nothing."""
        with self._lock:
            phase = self._phases[campaign]
            if phase not in SAVE_PHASES:
                return
            sizes = self._sizes[campaign]
            fresh = {name for name in names if name in sizes} - self._credited[campaign]
            if not fresh:
                return
            self._credited[campaign] |= fresh
            self._done_work += sum(sizes[name] for name in fresh) * PHASE_WEIGHTS[phase]
            snapshot = self._snapshot()
        self._tell(snapshot)

    def snapshot(self) -> ProgressSnapshot:
        with self._lock:
            return self._snapshot()

    def campaign(self, name: str) -> CampaignProgress:
        return CampaignProgress(self, name)

    def _top_up(self, campaign: str) -> None:
        weight = PHASE_WEIGHTS.get(self._phases[campaign], 0.0)
        sizes = self._sizes[campaign]
        self._done_work += sum(size for name, size in sizes.items() if name not in self._credited[campaign]) * weight

    def _snapshot(self) -> ProgressSnapshot:
        steps = tuple(
            CampaignStep(
                name,
                self._phases[name],
                len(saves) if self._phases[name] == "done" else len(self._credited[name]),
                len(saves),
            )
            for name, saves in self._sizes.items()
        )
        return ProgressSnapshot(steps, self._done_work, self._total_work, self._clock() - self._started)

    def _tell(self, snapshot: ProgressSnapshot) -> None:
        if self._on_change is not None:
            self._on_change(snapshot)


@dataclass(frozen=True)
class CampaignProgress:
    """The progress of one campaign of an extraction, for the code that extracts it."""

    extraction: ExtractionProgress
    name: str

    def phase(self, phase: Phase) -> None:
        self.extraction.phase(self.name, phase)

    def saves_done(self, names: Iterable[str]) -> None:
        self.extraction.saves_done(self.name, names)


def _step_text(step: CampaignStep) -> str:
    if step.phase in SAVE_PHASES:
        return f"{step.name}: {step.phase} {step.done}/{step.total}"
    return f"{step.name}: {step.phase}"


def _duration(seconds: float) -> str:
    if seconds < 60:
        return f"about {max(1, round(seconds))} s"
    return f"about {math.ceil(seconds / 60)} min"
