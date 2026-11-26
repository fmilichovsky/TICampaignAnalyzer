"""The profile of a sample campaign: its game settings, its save cadence and whether it is a standard game."""

from __future__ import annotations

import lzma
import os
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Any

from ..parsing.errors import SaveLoadError
from ..parsing.settings import CampaignSettings
from ..parsing.survey import survey_settings

STANDARD: dict[str, object] = {
    "custom_difficulty": False,
    "scenario": "FullScenario/2026Scenario",
    "factions": (
        "AlienCouncil",
        "AppeaseCouncil",
        "CooperateCouncil",
        "DestroyCouncil",
        "EscapeCouncil",
        "ExploitCouncil",
        "ResistCouncil",
        "SubmitCouncil",
    ),
    "mods": False,
    "alien_progression_speed": 1.0,
    "research_speed": 1.0,
}
"""The settings of a standard game (factions sorted, as ``CampaignSettings`` holds them); any difficulty preset is
standard, custom difficulty modifiers are not."""

SETTING_FIELDS = ("player_faction", "difficulty", "custom_difficulty", "scenario", "mods")
SPEED_FIELDS = ("alien_progression_speed", "research_speed")
PROFILE_FIELDS = (
    *SETTING_FIELDS,
    *SPEED_FIELDS,
    "first_save",
    "last_save",
    "saves",
    "longest_gap_days",
    "non_standard",
)
"""The keys of a profile in ``samples.json``, in order."""

# Lzma releases the GIL, so threads decompress in parallel; each holds one whole save in memory.
MAX_READERS = 4


@dataclass(frozen=True)
class SampleSave:
    """What one compressed sample save contributes to the manifest; an unreadable save carries no settings."""

    raw_bytes: int
    date: datetime | None = None
    settings: CampaignSettings = field(default_factory=CampaignSettings)


def read_sample(file: Path) -> SampleSave:
    """Decompress one sample save and read its size, game date and settings; raises only for a corrupt archive."""
    with lzma.open(file) as handle:
        data = handle.read()
    try:
        date, settings = survey_settings(data, source=file.name)
    except SaveLoadError:
        return SampleSave(len(data))
    return SampleSave(len(data), date, settings)


def read_samples(files: Iterable[Path]) -> list[SampleSave]:
    """``read_sample`` of every file, in order."""
    paths = list(files)
    if not paths:
        return []
    with ThreadPoolExecutor(max_workers=min(len(paths), MAX_READERS, os.cpu_count() or 1)) as pool:
        return list(pool.map(read_sample, paths))


def _agreed(values: set[Any]) -> tuple[Any, bool]:
    """The one value the saves that carry a setting agree on, or ``None``; and whether they disagree."""
    values.discard(None)
    if len(values) == 1:
        return next(iter(values)), False
    return None, len(values) > 1


def sample_profile(saves: Sequence[SampleSave]) -> dict[str, Any]:
    """The profile of a campaign's saves, keyed by ``PROFILE_FIELDS``; ``None`` is a setting no save carries, and a
    campaign is standard only when every setting in ``STANDARD`` is known and matches."""
    settings: dict[str, Any] = {}
    non_standard: list[str] = []
    for item in fields(CampaignSettings):
        values = {getattr(save.settings, item.name) for save in saves}
        if item.name == "mods" and True in values:
            values = {True}
        value, changes = _agreed(values)
        settings[item.name] = value
        if changes:
            non_standard.append(f"{item.name} changes")
        elif item.name in STANDARD and value is None:
            non_standard.append(f"{item.name} unknown")
        elif item.name in STANDARD and value != STANDARD[item.name]:
            non_standard.append(item.name)
    dates = sorted({save.date for save in saves if save.date is not None})
    gaps = [(later - earlier).days for earlier, later in zip(dates, dates[1:], strict=False)]
    return {
        **{name: settings[name] for name in (*SETTING_FIELDS, *SPEED_FIELDS)},
        "first_save": dates[0].date().isoformat() if dates else None,
        "last_save": dates[-1].date().isoformat() if dates else None,
        "saves": len(saves),
        "longest_gap_days": max(gaps, default=0) if dates else None,
        "non_standard": non_standard,
    }
