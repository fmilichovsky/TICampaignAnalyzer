"""Army events: region and faction with mirrored lists, literal flags and values, presence, list leftovers."""

from tests.analyzers.support import (
    AFTER,
    BEFORE,
    MEGAFAUNA_STATE_TYPE,
    analyze,
    army_ref,
    by_type,
    faction_ref,
    named,
    nation_ref,
    only,
    region_ref,
    snapshot,
    state,
)
from tinarrative.analyzers.military import ArmyAnalyzer
from tinarrative.analyzers.military.armies import (
    APPEARED,
    DESTROYED_CHANGED,
    DISAPPEARED,
    FACTION_CHANGED,
    REGION_CHANGED,
    STRENGTH_CHANGED,
    TYPE_CHANGED,
)
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, SourceRole
from tinarrative.model.values import Unknown, UnknownReason, freeze

ANALYZER = ArmyAnalyzer()
ARMY = EntityDomain.ARMY
FACTION = EntityDomain.FACTION
NATION = EntityDomain.NATION
REGION = EntityDomain.REGION


def test_region_change_cites_both_region_lists_and_leaves_nation_lists_as_leftovers() -> None:
    before = snapshot(
        BEFORE,
        state(
            ARMY, "110", BEFORE, currentRegion=region_ref("40"), faction=faction_ref("15"), priorRegion=region_ref("41")
        ),
        state(REGION, "40", BEFORE, armies=(army_ref("110"),)),
        state(REGION, "42", BEFORE, armies=()),
        state(NATION, "20", BEFORE, armies=(army_ref("110"),)),
        state(NATION, "21", BEFORE, armies=()),
    )
    after = snapshot(
        AFTER,
        state(
            ARMY, "110", AFTER, currentRegion=region_ref("42"), faction=faction_ref("15"), priorRegion=region_ref("40")
        ),
        state(REGION, "40", AFTER, armies=()),
        state(REGION, "42", AFTER, armies=(army_ref("110"),)),
        state(NATION, "20", AFTER, armies=()),
        state(NATION, "21", AFTER, armies=(army_ref("110"),)),
    )
    events = analyze(ANALYZER, before, after)
    moved = only(events, REGION_CHANGED)
    assert moved.confidence is Confidence.HIGH
    assert [str(r.entity_id) for r in moved.entities] == ["army:110", "faction:15", "region:40", "region:42"]
    assert dict(moved.attributes) == {
        "transition": "changed",
        "before": named(region_ref("40")),
        "after": named(region_ref("42")),
    }
    assert [(s.role, str(s.change.entity_id), s.member) for s in moved.sources] == [
        (SourceRole.PRIMARY, "army:110", None),
        (SourceRole.CORROBORATING, "region:40", army_ref("110")),
        (SourceRole.CORROBORATING, "region:42", army_ref("110")),
    ]
    assert sorted(event.id for event in by_type(events, "nation.armies_changed")) == [
        "nation.armies_changed/nation:20/army:110/removed",
        "nation.armies_changed/nation:21/army:110/added",
    ]
    assert len(events) == 3  # priorRegion is not an event


def test_faction_change_cites_both_faction_lists_and_flags_are_literal() -> None:
    before = snapshot(
        BEFORE,
        state(
            ARMY,
            "111",
            BEFORE,
            faction=faction_ref("15"),
            currentRegion=region_ref("40"),
            destroyed=False,
            strength=1.0,
        ),
        state(FACTION, "15", BEFORE, armies=(army_ref("111"),)),
        state(FACTION, "16", BEFORE, armies=()),
    )
    after = snapshot(
        AFTER,
        state(
            ARMY, "111", AFTER, faction=faction_ref("16"), currentRegion=region_ref("40"), destroyed=True, strength=0.5
        ),
        state(FACTION, "15", AFTER, armies=()),
        state(FACTION, "16", AFTER, armies=(army_ref("111"),)),
    )
    events = analyze(ANALYZER, before, after)
    assert [event.event_type for event in events] == [FACTION_CHANGED, DESTROYED_CHANGED, STRENGTH_CHANGED]
    faction, destroyed, strength = events
    assert [str(r.entity_id) for r in faction.entities] == ["army:111", "region:40", "faction:15", "faction:16"]
    assert [(s.role, str(s.change.entity_id)) for s in faction.sources] == [
        (SourceRole.PRIMARY, "army:111"),
        (SourceRole.CORROBORATING, "faction:15"),
        (SourceRole.CORROBORATING, "faction:16"),
    ]
    assert dict(destroyed.attributes) == {"transition": "changed", "before": False, "after": True}
    assert destroyed.sources[0].change.field == "destroyed"  # the only evidence that may be worded "destroyed"
    assert [str(r.entity_id) for r in destroyed.entities] == ["army:111", "faction:16", "region:40"]
    assert dict(strength.attributes) == {"transition": "changed", "before": 1.0, "after": 0.5}


def test_presence_cites_every_list_naming_the_army_on_the_existing_side() -> None:
    before = snapshot(
        BEFORE,
        state(ARMY, "113", BEFORE, faction=faction_ref("15"), currentRegion=region_ref("41")),
        state(FACTION, "15", BEFORE, armies=(army_ref("113"),)),
        state(NATION, "20", BEFORE, armies=(army_ref("113"),)),
        state(REGION, "41", BEFORE, armies=(army_ref("113"),)),
    )
    megafauna = state(
        ARMY, "112", AFTER, state_type=MEGAFAUNA_STATE_TYPE, faction=faction_ref("16"), currentRegion=region_ref("41")
    )
    after = snapshot(
        AFTER,
        megafauna,
        state(FACTION, "15", AFTER, armies=()),
        state(NATION, "20", AFTER, armies=()),
        state(REGION, "41", AFTER, armies=(army_ref("112"),)),
    )
    events = analyze(ANALYZER, before, after)
    gone = only(events, DISAPPEARED)
    assert gone.attribute("side") == "before"
    assert [str(r.entity_id) for r in gone.entities] == ["army:113", "faction:15", "region:41"]
    assert [(s.role, str(s.change.entity_id)) for s in gone.sources] == [
        (SourceRole.PRIMARY, "army:113"),
        (SourceRole.CORROBORATING, "faction:15"),
        (SourceRole.CORROBORATING, "nation:20"),
        (SourceRole.CORROBORATING, "region:41"),
    ]
    assert isinstance(gone.attribute("megafauna"), Unknown)  # only megafauna armies are marked
    new = only(events, APPEARED)
    assert new.entities[0].state_type == MEGAFAUNA_STATE_TYPE
    assert new.attribute("megafauna") is True
    assert [(s.role, str(s.change.entity_id)) for s in new.sources] == [
        (SourceRole.PRIMARY, "army:112"),
        (SourceRole.CORROBORATING, "region:41"),
    ]
    assert len(events) == 2
    for word in ("destroy", "kill", "creat"):
        assert word not in f"{gone.event_type} {new.event_type}"


def test_unresolved_region_is_low_confidence_and_identical_snapshots_produce_nothing() -> None:
    unresolved = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze({"value": 999}))
    before = snapshot(BEFORE, state(ARMY, "110", BEFORE, currentRegion=region_ref("40"), armyType="A"))
    after = snapshot(AFTER, state(ARMY, "110", AFTER, currentRegion=unresolved, armyType="B"))
    events = analyze(ANALYZER, before, after)
    moved = only(events, REGION_CHANGED)
    assert moved.confidence is Confidence.LOW and moved.attribute("transition") == "unresolved"
    assert only(events, TYPE_CHANGED).attribute("after") == "B"
    assert analyze(ANALYZER, before, before) == []
    assert (
        analyze(ANALYZER, snapshot(BEFORE, state(NATION, "20", BEFORE)), snapshot(AFTER, state(NATION, "20", AFTER)))
        == []
    )
    assert nation_ref("20").entity_id.domain is NATION
