"""The default narrative rules: each declares every narrative type it reads (ADR-0019).

Every rule runs alone over one event of every known type, so a typed lookup of a type it does not read fails here,
whatever a campaign holds. This exhausts the matrix of rules and types; it does not model a realistic campaign.
"""

from __future__ import annotations

import pytest

from tests.narrative.support import atomic, declared_attributes, nation, situation
from tinarrative.kinds import KINDS
from tinarrative.model.events import Event, Role
from tinarrative.narrative.aggregation import Join, NarrativeBuilder, NarrativeRule, aggregate
from tinarrative.narrative.catalogue import NARRATIVE_RULES
from tinarrative.narrative.significance import BASE, RULES, SCALED

K0 = "2032-01-01T00:00:00"
K1 = "2032-04-01T00:00:00"
NORTH, SOUTH = nation("1", "Northland"), nation("2", "Southland")
ATOMIC_TYPES = sorted(
    set(BASE) | set(RULES) | set(SCALED) | {event_type for event_type, kind in KINDS.items() if kind.base is not None}
)
NARRATIVE_TYPES = sorted({event_type for rule in NARRATIVE_RULES for event_type in rule.emitted_types})


def every_type() -> list[Event]:
    atomics = [
        atomic(f"{event_type}/{actor.entity_id}", K1, not_before=K0, entities=(actor, other))
        for event_type in ATOMIC_TYPES
        for actor, other in ((NORTH, SOUTH), (SOUTH, NORTH))
    ]
    build = NarrativeBuilder(())
    narratives = [
        build.event(
            KINDS[event_type],
            id_parts=["injected"],
            constituents=atomics[:1],
            roles=[(Role.ACTOR, NORTH), (Role.TARGET, SOUTH), (Role.BENEFICIARY, NORTH), (Role.LOSER, SOUTH)],
            join=Join.ENTITY,
            attributes=declared_attributes(event_type, ()),
        )
        for event_type in NARRATIVE_TYPES
    ]
    return [*atomics, *narratives]


def test_the_matrix_holds_atomic_and_narrative_types() -> None:
    assert ATOMIC_TYPES and NARRATIVE_TYPES
    assert not set(ATOMIC_TYPES) & set(NARRATIVE_TYPES)


@pytest.mark.parametrize("rule", NARRATIVE_RULES, ids=lambda rule: rule.name)
def test_a_rule_reads_only_the_narrative_types_it_declares(rule: NarrativeRule) -> None:
    reports = [situation(K0, nations=[NORTH, SOUTH]), situation(K1, nations=[NORTH, SOUTH])]

    built = aggregate(every_type(), reports, [rule])

    assert {event.event_type for event in built} <= rule.emitted_types
