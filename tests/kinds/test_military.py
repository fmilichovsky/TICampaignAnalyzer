"""The military family: the generated army-list kinds and the levels it declares for the types that were silent."""

from __future__ import annotations

from tinarrative.kinds import KINDS
from tinarrative.kinds.military import ARMIES_CHANGED
from tinarrative.kinds.military import KINDS as MILITARY
from tinarrative.model.events import Significance
from tinarrative.model.kinds import EvidenceRole


def test_an_army_list_kind_is_generated_for_each_owner_of_the_list() -> None:
    assert {kind.event_type for kind in ARMIES_CHANGED.values()} == {
        "faction.armies_changed",
        "nation.armies_changed",
        "region.armies_changed",
    }
    assert all(KINDS[kind.event_type] is kind for kind in ARMIES_CHANGED.values())


def test_the_family_declares_the_levels_the_types_silently_had() -> None:
    assert all(kind.evidence is EvidenceRole.BOOKKEEPING for kind in MILITARY)
    assert {kind.event_type: kind.base for kind in MILITARY if kind.base is not Significance.MINOR} == {
        "army.faction_changed": Significance.MAJOR,
        "army.destroyed_changed": Significance.MAJOR,
        "faction.armies_changed": Significance.TRIVIAL,
        "nation.armies_changed": Significance.TRIVIAL,
        "region.armies_changed": Significance.TRIVIAL,
    }
