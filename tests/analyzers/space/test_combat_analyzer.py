"""The combat-log analyzer on synthetic snapshots: edge cases the fixture pair does not cover."""

from tests.analyzers.support import AFTER, BEFORE, analyze, faction_ref, record_set, snapshot, state
from tinarrative.analyzers.space import CombatAnalyzer
from tinarrative.analyzers.space.combat import attack_count
from tinarrative.kinds import describe_event
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, DateBasis, Event
from tinarrative.model.records import CombatEntry, RecordKind
from tinarrative.model.snapshot import SaveSnapshot
from tinarrative.model.values import FrozenMap, Observed, Unknown, UnknownReason, freeze

FIELD = "CombatLogs"
ESCORTS = FrozenMap((("FixtureEscort", 2),))
OWNER = faction_ref("15")
OTHER = faction_ref("16")


def entry(index: int, sides: Observed, winner: Observed = OWNER, date: Observed = None) -> CombatEntry:
    return CombatEntry(index, date, sides, None, winner, (), "No")


def run(before: tuple[CombatEntry, ...], after: tuple[CombatEntry, ...]) -> list[Event]:
    def save(name: str, entries: tuple[CombatEntry, ...]) -> SaveSnapshot:
        return snapshot(
            name,
            state(EntityDomain.FACTION, "15", name),
            state(EntityDomain.FACTION, "16", name),
            records=(record_set(name, OWNER, FIELD, RecordKind.COMBAT_LOG, entries),),
        )

    return analyze(CombatAnalyzer(), save(BEFORE, before), save(AFTER, after))


def test_an_unchanged_log_yields_nothing() -> None:
    kept = entry(0, ((OWNER, ESCORTS),))
    assert run((kept,), (entry(3, ((OWNER, ESCORTS),)),)) == []


def test_a_dated_entry_is_dated_by_the_record_and_the_owner_is_named_once() -> None:
    sides = ((OWNER, ESCORTS), (OTHER, ESCORTS))
    (event,) = run((), (entry(0, sides, OTHER, "2032-02-01T00:00:00"),))
    assert (event.date, event.date_basis, event.confidence) == (
        "2032-02-01T00:00:00",
        DateBasis.RECORD,
        Confidence.HIGH,
    )
    assert [str(ref.entity_id) for ref in event.entities] == ["faction:15", "faction:16"]
    assert describe_event(event) == (
        "Fixture faction 15 (faction:15) records a combat entry (dated 2032-02-01T00:00:00): "
        "Fixture faction 15 (faction:15) (2 ships) vs Fixture faction 16 (faction:16) (2 "
        "ships); "
        "winner Fixture faction 16 (faction:16), hab faction null, attacks 0"
    )


def test_unresolved_sides_or_winner_give_low_confidence_and_stay_literal() -> None:
    gone = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze([{"value": 999}]))
    (event,) = run((), (entry(0, gone, Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze({"value": 998}))),))
    assert event.confidence is Confidence.LOW and event.date_basis is DateBasis.INTERVAL
    assert [str(ref.entity_id) for ref in event.entities] == ["faction:15"]
    assert event.attribute("sides") == gone
    assert describe_event(event).startswith(
        "Fixture faction 15 (faction:15) records a combat entry (undated): "
        'unknown (unresolved_reference, raw=[{"value": 999}]); winner unknown'
    )


def test_a_removed_entry_is_interval_dated_and_cites_the_earlier_save() -> None:
    (event,) = run((entry(0, ((OWNER, ESCORTS),)),), ())
    assert event.event_type == "faction.combat_entry_removed"
    assert event.date_basis is DateBasis.INTERVAL
    (source,) = event.sources
    assert source.entry is not None and source.entry.save_id == BEFORE and source.entry.path.endswith("/CombatLogs/0")
    assert describe_event(event).startswith("Fixture faction 15 (faction:15) no longer lists a combat entry (undated)")


def test_attack_count_is_the_list_length_or_the_literal_value() -> None:
    assert attack_count((FrozenMap(), FrozenMap())) == 2
    assert attack_count(Unknown()) == Unknown()
