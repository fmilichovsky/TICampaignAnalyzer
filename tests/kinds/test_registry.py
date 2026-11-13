"""The kind registry: one declaration per type, a checked attribute contract, and a home for every emitted type."""

from __future__ import annotations

from collections import Counter

import pytest

from tests.analyzers.support import AFTER, BEFORE, snapshot
from tests.fixtures import FIXTURES_ROOT
from tinarrative.analyzers.common import EventBuilder
from tinarrative.config import DEFAULT_SETTINGS, GeopoliticsSettings
from tinarrative.kinds import KINDS, attributes, describe_event, kind_for, known_event_types
from tinarrative.kinds.campaign import INTERSTATE_WARS_CHANGED, NOTIFICATION_ENTRY, NOTIFICATION_UNKNOWN_TEMPLATE
from tinarrative.kinds.registry import FAMILIES, PREFIX_KINDS
from tinarrative.model.kinds import EventKind, EvidenceRole
from tinarrative.model.values import Unknown
from tinarrative.narrative.assets import asset_rules
from tinarrative.narrative.catalogue import NARRATIVE_RULES
from tinarrative.narrative.diplomacy import diplomacy_rules
from tinarrative.narrative.geopolitics import geopolitical_rules
from tinarrative.narrative.nation_metrics import nation_metric_rules
from tinarrative.narrative.space import space_rules
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


def test_a_narrative_event_kind_is_exactly_one_a_rule_emits_and_only_it_may_lack_a_base_level() -> None:
    narrative = {event_type for rule in NARRATIVE_RULES for event_type in rule.emitted_types}
    assert {event_type for event_type, kind in KINDS.items() if kind.narrative} == narrative
    assert {event_type for event_type, kind in KINDS.items() if kind.base is None} <= narrative
    assert all(KINDS[event_type].evidence is EvidenceRole.BOOKKEEPING for event_type in narrative)


def test_every_geopolitics_kind_declares_its_base_level_and_no_narrative_event_kind_a_stake() -> None:
    geopolitical = {
        event_type for rule in geopolitical_rules(GeopoliticsSettings()) for event_type in rule.emitted_types
    }
    assert all(KINDS[event_type].base is not None for event_type in geopolitical)
    assert not [event_type for event_type, kind in KINDS.items() if kind.narrative and kind.stake is not None]


def test_every_nation_metric_and_diplomacy_kind_declares_its_base_level() -> None:
    rules = (*nation_metric_rules(DEFAULT_SETTINGS.narrative), *diplomacy_rules(GeopoliticsSettings()))
    assert all(KINDS[event_type].base is not None for rule in rules for event_type in rule.emitted_types)


def test_every_asset_and_space_kind_declares_its_base_level() -> None:
    emitted = {
        event_type
        for rule in (*asset_rules(DEFAULT_SETTINGS.narrative), *space_rules(DEFAULT_SETTINGS.narrative.space))
        for event_type in rule.emitted_types
    }
    assert emitted
    assert all(KINDS[event_type].base is not None for event_type in emitted)


def test_the_constructor_keeps_required_and_optional_attributes_in_order() -> None:
    built = attributes(KIND, (("before", 1),), after=Unknown(), note="x")
    assert built == (("before", 1), ("after", Unknown()), ("note", "x"))
    assert attributes(KIND, before=None, after=2) == (("before", None), ("after", 2))


@pytest.mark.parametrize(
    ("given", "problem"),
    [
        ({"before": 1}, "missing"),
        ({"before": 1, "after": 2, "extra": 3}, "undeclared"),
    ],
)
def test_the_constructor_raises_on_a_missing_or_undeclared_key(given: dict[str, int], problem: str) -> None:
    with pytest.raises(ValueError, match=problem):
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


def test_a_type_resolves_to_its_exact_kind_before_a_prefix_kind() -> None:
    assert kind_for("notification.unknown_template") is NOTIFICATION_UNKNOWN_TEMPLATE
    assert kind_for("notification.LogHabDestroyed") is NOTIFICATION_ENTRY
    assert kind_for("campaign.nothing_like_this") is None
    assert PREFIX_KINDS == (NOTIFICATION_ENTRY,)
    assert "notification.*" not in known_event_types()


def _entry_attributes() -> tuple[tuple[str, Unknown], ...]:
    return tuple((key, Unknown()) for key in sorted(NOTIFICATION_ENTRY.required))


def test_a_prefix_kind_takes_the_concrete_type_the_save_supplied() -> None:
    build = EventBuilder(snapshot(BEFORE), snapshot(AFTER))
    event = build.event(
        NOTIFICATION_ENTRY,
        type_id="notification.LogHabDestroyed",
        id_parts=("1",),
        sources=(),
        entities=(),
        attributes=_entry_attributes(),
    )
    assert event.event_type == "notification.LogHabDestroyed"


@pytest.mark.parametrize("type_id", [None, "campaign.global_value_changed"])
def test_a_prefix_kind_raises_without_a_type_under_its_prefix(type_id: str | None) -> None:
    build = EventBuilder(snapshot(BEFORE), snapshot(AFTER))
    with pytest.raises(ValueError, match="prefix kind"):
        build.event(
            NOTIFICATION_ENTRY,
            type_id=type_id,
            id_parts=("1",),
            sources=(),
            entities=(),
            attributes=_entry_attributes(),
        )


def test_an_exact_kind_raises_when_given_a_type() -> None:
    build = EventBuilder(snapshot(BEFORE), snapshot(AFTER))
    with pytest.raises(ValueError, match="exact"):
        build.event(
            NOTIFICATION_UNKNOWN_TEMPLATE,
            type_id="notification.other",
            id_parts=("1",),
            sources=(),
            entities=(),
            attributes=_entry_attributes(),
        )


def test_interstate_wars_read_as_a_list_change() -> None:
    build = EventBuilder(snapshot(BEFORE), snapshot(AFTER))
    event = build.event(
        INTERSTATE_WARS_CHANGED,
        id_parts=("1",),
        sources=(),
        entities=(),
        attributes=(("transition", "added"), ("member", "war:1")),
    )
    assert describe_event(event).endswith('list list: +"war:1"')


@pytest.mark.parametrize("pair", PAIRS)
def test_every_emitted_type_matches_exactly_one_kind(pair: str) -> None:
    plan = plan_sequence([survey(FIXTURE_DIR / f"{pair}_before.json"), survey(FIXTURE_DIR / f"{pair}_after.json")])
    intervals = list(run_sequence(plan, inferred=True))
    emitted = {event.event_type for interval in intervals for event in interval.events()}
    emitted |= {event.event_type for event in narrative_events(intervals)}
    assert emitted
    for event_type in emitted:
        homes = [event_type in KINDS, event_type not in KINDS and kind_for(event_type) is not None]
        assert homes.count(True) == 1, (event_type, homes)


def test_the_merger_the_cession_and_the_expansion_own_their_constituents() -> None:
    owners = sorted(event_type for event_type, kind in KINDS.items() if kind.exclusive_constituents)

    assert owners == ["nation.cession", "nation.expansion", "nation.merger"]
