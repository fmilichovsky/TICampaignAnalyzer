"""Fast extraction of chronology and campaign continuity for save surveying."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..identity import STATE_PREFIX
from .continuity import CampaignProfile, campaign_profile_from_states
from .normalization import save_timestamp_from_states
from .raw_save import SURVEY_STATE_TYPES, parse_raw_save, parse_survey_states
from .settings import CampaignSettings, campaign_settings_from_states


def _survey_states(data: bytes, *, source: str) -> dict[str, Any]:
    """The survey containers, using the full parser when selected-container decoding is incomplete."""
    states = parse_survey_states(data)
    if states is None or not all(f"{STATE_PREFIX}{name}" in states for name in SURVEY_STATE_TYPES):
        states = parse_raw_save(data, source=source).root["gamestates"]
    return states


def survey_metadata(data: bytes, *, source: str) -> tuple[datetime | None, CampaignProfile]:
    """The save's game date and its campaign continuity signals."""
    states = _survey_states(data, source=source)
    return save_timestamp_from_states(states), campaign_profile_from_states(states)


def survey_settings(data: bytes, *, source: str) -> tuple[datetime | None, CampaignSettings]:
    """The save's game date and the campaign settings it records."""
    states = _survey_states(data, source=source)
    return save_timestamp_from_states(states), campaign_settings_from_states(states)
