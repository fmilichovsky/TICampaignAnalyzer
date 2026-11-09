from __future__ import annotations

import pytest

from tinarrative.kinds import KINDS, known_event_types
from tinarrative.model.kinds import EvidenceRole
from tinarrative.narrative.evidence import EVIDENCE_PREFIXES, NARRATOR_EVIDENCE, is_evidence


def test_every_evidence_type_is_a_known_type() -> None:
    known = known_event_types()
    assert NARRATOR_EVIDENCE <= known, sorted(NARRATOR_EVIDENCE - known)
    for prefix in EVIDENCE_PREFIXES:
        assert any(event_type.startswith(prefix) for event_type in known), prefix


def test_a_kind_declares_its_role_and_is_never_also_in_the_table() -> None:
    assert not set(KINDS) & NARRATOR_EVIDENCE
    for event_type, kind in KINDS.items():
        assert is_evidence(event_type) is (kind.evidence is EvidenceRole.EVIDENCE), event_type


@pytest.mark.parametrize(
    "event_type",
    ["nation.rank_changed", "control_point.controller_changed", "army.appeared", "ship.appeared", "hab.appeared"],
)
def test_what_a_narrative_event_summarizes_is_not_evidence(event_type: str) -> None:
    assert event_type in known_event_types()
    assert not is_evidence(event_type)
