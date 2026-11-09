"""The kind registry: one declaration per type, a checked attribute contract, and a home for every emitted type."""

from __future__ import annotations

from collections import Counter

import pytest

from tests.analyzers.support import AFTER, BEFORE, snapshot
from tests.fixtures import FIXTURES_ROOT
from tinarrative.analyzers.common import EventBuilder
from tinarrative.kinds import KINDS, attributes, known_event_types
from tinarrative.kinds.describe import NOTIFICATION_PREFIX
from tinarrative.kinds.registry import FAMILIES
from tinarrative.model.kinds import EventKind, EvidenceRole
from tinarrative.model.values import Unknown
from tinarrative.sequence import narrative_events, plan_sequence, run_sequence, survey

FIXTURE_DIR = FIXTURES_ROOT / "io" / "terra_invicta_json_v1"
PAIRS = sorted(path.name.removesuffix("_before.json") for path in FIXTURE_DIR.glob("*_before.json"))
KIND = EventKind(
    "fixture.kind_checked",
    lambda event: event.id,
    None,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"before", "after"}),
    optional=frozenset({"note"}),
)


def test_every_declared_kind_has_exactly_one_entry() -> None:
    declared = Counter(kind.event_type for family in FAMILIES for kind in family)
    assert declared and all(count == 1 for count in declared.values()), declared.most_common(3)
    assert set(KINDS) == set(declared)
    assert all(KINDS[kind.event_type] is kind for family in FAMILIES for kind in family)


def test_every_atomic_kind_declares_a_base_level() -> None:
    assert all(kind.base is not None for kind in KINDS.values())


def test_the_constructor_keeps_required_and_optional_attributes_in_order() -> None:
    built = attributes(KIND, (("before", 1),), after=Unknown(), note="x")
    assert built == (("before", 1), ("after", Unknown()), ("note", "x"))
    assert attributes(KIND, before=None, after=2) == (("before", None), ("after", 2))


@pytest.mark.parametrize(
    ("given", "problem"),
    [
        ({"before": 1}, "missing ['after']"),
        ({"before": 1, "after": 2, "extra": 3}, "undeclared ['extra']"),
    ],
)
def test_the_constructor_raises_on_a_missing_or_undeclared_key(given: dict[str, int], problem: str) -> None:
    with pytest.raises(ValueError, match=f"fixture.kind_checked: {problem}".replace("[", r"\[")):
        attributes(KIND, **given)


def test_the_constructor_raises_on_a_key_given_twice() -> None:
    with pytest.raises(ValueError, match="repeated"):
        attributes(KIND, (("before", 1), ("after", 2)), before=3)


def test_an_emitter_passing_a_kind_gets_its_attributes_checked() -> None:
    build = EventBuilder(snapshot(BEFORE), snapshot(AFTER))
    event = build.event(KIND, id_parts=("1",), sources=(), entities=(), attributes=(("before", 1), ("after", 2)))
    assert event.event_type == KIND.event_type and event.attribute("after") == 2
    with pytest.raises(ValueError, match="missing"):
        build.event(KIND, id_parts=("1",), sources=(), entities=(), attributes=(("before", 1),))


@pytest.mark.parametrize("pair", PAIRS)
def test_every_emitted_type_matches_exactly_one_kind_or_table_entry(pair: str) -> None:
    plan = plan_sequence([survey(FIXTURE_DIR / f"{pair}_before.json"), survey(FIXTURE_DIR / f"{pair}_after.json")])
    intervals = list(run_sequence(plan, inferred=True))
    emitted = {event.event_type for interval in intervals for event in interval.events()}
    emitted |= {event.event_type for event in narrative_events(intervals)}
    assert emitted
    legacy = known_event_types() - set(KINDS)
    for event_type in emitted:
        homes = [
            event_type in KINDS,
            event_type in legacy,
            event_type.startswith(NOTIFICATION_PREFIX) and event_type not in legacy,
        ]
        assert homes.count(True) == 1, (event_type, homes)
