from __future__ import annotations

import pytest

# The describe templates are the one registry of every known event type (as in test_significance.py).
from tinarrative.analyzers.render import _TEMPLATES
from tinarrative.narrative.evidence import EVIDENCE_PREFIXES, NARRATOR_EVIDENCE, is_evidence


def test_every_evidence_type_is_a_known_type() -> None:
    assert NARRATOR_EVIDENCE <= set(_TEMPLATES), sorted(NARRATOR_EVIDENCE - set(_TEMPLATES))
    for prefix in EVIDENCE_PREFIXES:
        assert any(event_type.startswith(prefix) for event_type in _TEMPLATES), prefix


@pytest.mark.parametrize(
    "event_type",
    ["nation.rank_changed", "control_point.controller_changed", "army.appeared", "ship.appeared", "hab.appeared"],
)
def test_what_a_narrative_event_summarizes_is_not_evidence(event_type: str) -> None:
    assert event_type in _TEMPLATES
    assert not is_evidence(event_type)
