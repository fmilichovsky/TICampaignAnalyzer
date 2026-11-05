"""Fast extraction of chronology and campaign continuity for save surveying."""

from __future__ import annotations

from datetime import datetime

from ..identity import STATE_PREFIX
from .continuity import CampaignProfile, campaign_profile_from_states
from .normalization import save_timestamp_from_states
from .raw_save import SURVEY_STATE_TYPES, parse_raw_save, parse_survey_states


def survey_metadata(data: bytes, *, source: str) -> tuple[datetime | None, CampaignProfile]:
    """Extract survey metadata, using the full parser when selected-container decoding is incomplete."""
    states = parse_survey_states(data)
    if states is None or not all(f"{STATE_PREFIX}{name}" in states for name in SURVEY_STATE_TYPES):
        states = parse_raw_save(data, source=source).root["gamestates"]
    return save_timestamp_from_states(states), campaign_profile_from_states(states)
