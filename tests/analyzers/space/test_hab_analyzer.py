"""Hab events: literal field transitions, presence, and the faction's hab destruction log."""

from tests.analyzers.support import (
    AFTER,
    BEFORE,
    analyze,
    by_type,
    faction_ref,
    named,
    only,
    record_set,
    ref,
    snapshot,
    state,
)
from tinarrative.analyzers.space import HabAnalyzer
from tinarrative.analyzers.space.habs import (
    APPEARED,
    CORE_COMPLETED_CHANGED,
    DESTRUCTION_RECORDED,
    DISAPPEARED,
    FACTION_CHANGED,
    TIER_CHANGED,
    TYPE_CHANGED,
    UNDER_ASSAULT_CHANGED,
)
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, DateBasis, SourceRole
from tinarrative.model.records import DestructionEntry, RecordKind
from tinarrative.model.values import Unknown, UnknownReason, freeze

ANALYZER = HabAnalyzer()
HAB = EntityDomain.SPACE_OBJECT
FACTION = EntityDomain.FACTION


def test_field_transitions_are_separate_events_with_the_faction_as_context() -> None:
    before = snapshot(
        BEFORE,
        state(
            HAB,
            "140",
            BEFORE,
            faction=faction_ref("16"),
            habType="Base",
            tier=1,
            underAssault=False,
            anyCoreCompleted=False,
        ),
        state(FACTION, "15", BEFORE),
        state(FACTION, "16", BEFORE),
    )
    after = snapshot(
        AFTER,
        state(
            HAB,
            "140",
            AFTER,
            faction=faction_ref("15"),
            habType="Station",
            tier=2,
            underAssault=True,
            anyCoreCompleted=True,
        ),
        state(FACTION, "15", AFTER),
        state(FACTION, "16", AFTER),
    )
    events = analyze(ANALYZER, before, after)
    assert [event.event_type for event in events] == [
        FACTION_CHANGED,
        TYPE_CHANGED,
        TIER_CHANGED,
        UNDER_ASSAULT_CHANGED,
        CORE_COMPLETED_CHANGED,
    ]
    faction, hab_type, tier = events[:3]
    assert [str(r.entity_id) for r in faction.entities] == ["space object:140", "faction:16", "faction:15"]
    assert dict(hab_type.attributes) == {"transition": "changed", "before": "Base", "after": "Station"}
    assert [str(r.entity_id) for r in tier.entities] == ["space object:140", "faction:15"]
    assert all(len(event.sources) == 1 and event.sources[0].role is SourceRole.PRIMARY for event in events)


def test_presence_has_no_corroboration_and_never_says_destroyed() -> None:
    before = snapshot(BEFORE, state(HAB, "141", BEFORE, faction=faction_ref("15")))
    after = snapshot(AFTER, state(HAB, "142", AFTER, faction=None))
    events = analyze(ANALYZER, before, after)
    gone = only(events, DISAPPEARED)
    assert gone.attribute("side") == "before" and len(gone.sources) == 1
    assert [str(r.entity_id) for r in gone.entities] == ["space object:141", "faction:15"]
    assert "destroy" not in gone.event_type
    assert [str(r.entity_id) for r in only(events, APPEARED).entities] == ["space object:142"]


def test_destruction_log_entries_added_are_record_dated_events() -> None:
    owner = faction_ref("15")
    kept = DestructionEntry(0, "Station", ref(EntityDomain.SPACE_BODY, "50"), "2032-01-10T00:00:00", faction_ref("16"))
    added = DestructionEntry(1, "Base", ref(EntityDomain.SPACE_BODY, "50"), "2032-05-20T00:00:00", faction_ref("16"))
    unresolved = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze({"value": 998}))
    vague = DestructionEntry(2, "Base", unresolved, "2032-06-02T00:00:00", None)
    field = "HabDestructionLog"
    before = snapshot(
        BEFORE,
        state(FACTION, "15", BEFORE),
        state(FACTION, "16", BEFORE),
        state(HAB, "50", BEFORE),
        records=(record_set(BEFORE, owner, field, RecordKind.DESTRUCTION_LOG, (kept,)),),
    )
    after = snapshot(
        AFTER,
        state(FACTION, "15", AFTER),
        state(FACTION, "16", AFTER),
        state(HAB, "50", AFTER),
        records=(record_set(AFTER, owner, field, RecordKind.DESTRUCTION_LOG, (kept, added, vague)),),
    )
    events = analyze(ANALYZER, before, after)
    assert {event.event_type for event in events} == {DESTRUCTION_RECORDED}
    assert [event.id for event in events] == [
        "faction.hab_destruction_recorded/faction:15/1",
        "faction.hab_destruction_recorded/faction:15/2",
    ]
    first, second = events
    assert (first.date, first.date_basis, first.confidence) == (
        "2032-05-20T00:00:00",
        DateBasis.RECORD,
        Confidence.HIGH,
    )
    assert dict(first.attributes) == {
        "hab_type": "Base",
        "space_body": ref(EntityDomain.SPACE_BODY, "50"),
        "destroyer": named(faction_ref("16")),
        "recorded_on": "2032-05-20T00:00:00",
    }
    assert [str(r.entity_id) for r in first.entities] == ["faction:15", "space body:50", "faction:16"]
    assert first.sources[0].change.field == field  # the only evidence that may be worded "destruction"
    assert first.sources[0].entry is not None and first.sources[0].entry.path.endswith(f"/{field}/1")  # type: ignore[union-attr]
    assert second.confidence is Confidence.LOW and second.attribute("destroyer") is None
    assert not by_type(events, DISAPPEARED)  # a log entry never claims that a hab vanished


def test_identical_snapshots_and_unhandled_lists_produce_nothing() -> None:
    before = snapshot(BEFORE, state(HAB, "140", BEFORE, faction=faction_ref("15"), councilorsOnBoard=()))
    after = snapshot(
        AFTER,
        state(HAB, "140", AFTER, faction=faction_ref("15"), councilorsOnBoard=(ref(EntityDomain.COUNCILOR, "100"),)),
    )
    assert analyze(ANALYZER, before, after) == []
    assert analyze(ANALYZER, before, before) == []
