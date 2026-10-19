"""The ledger analyzer on synthetic snapshots: the date window, the allow-list and the cited entry."""

from tests.analyzers.support import (
    AFTER,
    AFTER_DATE,
    BEFORE,
    BEFORE_DATE,
    analyze,
    faction_ref,
    record_set,
    snapshot,
    state,
)
from tinarrative.analyzers.faction import LedgerAnalyzer
from tinarrative.analyzers.faction.ledger import ALLOWED_LABELS, in_window
from tinarrative.analyzers.render import describe_event
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, DateBasis, Event, SourceRole
from tinarrative.model.records import LedgerEntry, RecordKind
from tinarrative.model.snapshot import SaveSnapshot
from tinarrative.model.values import Observed, Unknown

FIELD = "Transactions"
OWNER = faction_ref("15")
INSIDE = "2031-04-15T00:00:00"


def entry(index: int, label: str, date: Observed = INSIDE, amount: Observed = -4.0) -> LedgerEntry:
    return LedgerEntry(index, label, "Operations", amount, date)


def run(
    before: tuple[LedgerEntry, ...], after: tuple[LedgerEntry, ...], after_date: Observed = AFTER_DATE
) -> list[Event]:
    def save(name: str, entries: tuple[LedgerEntry, ...], date: Observed) -> SaveSnapshot:
        return snapshot(
            name,
            state(EntityDomain.FACTION, "15", name, templateName="FixtureResistance"),
            records=(record_set(name, OWNER, FIELD, RecordKind.LEDGER, entries),),
            date=date,
        )

    return analyze(LedgerAnalyzer(), save(BEFORE, before, BEFORE_DATE), save(AFTER, after, after_date))


def test_the_window_is_open_at_the_earlier_save_and_closed_at_the_later_one() -> None:
    assert in_window(BEFORE_DATE, AFTER_DATE, INSIDE)
    assert not in_window(BEFORE_DATE, AFTER_DATE, BEFORE_DATE)
    assert in_window(BEFORE_DATE, AFTER_DATE, AFTER_DATE)
    assert not in_window(BEFORE_DATE, AFTER_DATE, "2031-07-01T00:00:00")
    assert not in_window(BEFORE_DATE, AFTER_DATE, None)
    assert not in_window(BEFORE_DATE, AFTER_DATE, Unknown())
    assert not in_window(Unknown(), AFTER_DATE, INSIDE)


def test_an_allow_listed_entry_inside_the_interval_is_record_dated_and_cites_the_entry() -> None:
    (event,) = run((), (entry(0, "Coup"),))
    assert event.event_type == "faction.transaction_recorded"
    assert event.id == "faction.transaction_recorded/faction:15/Coup/0"
    assert (event.date, event.date_basis, event.confidence) == (INSIDE, DateBasis.RECORD, Confidence.HIGH)
    assert [str(ref.entity_id) for ref in event.entities] == ["faction:15"]
    (source,) = event.sources
    assert source.role is SourceRole.PRIMARY and source.change.field == FIELD
    assert (
        source.entry is not None
        and source.entry.save_id == AFTER
        and source.entry.path.endswith("/Transactions/Coup/0")
    )
    assert event.attribute("label") == "Coup" and event.attribute("amount") == -4.0
    assert event.attribute("faction_kinds") is not None
    assert describe_event(event) == (
        "Fixture faction 15 (faction:15) ledger records a Coup charge: -4.0 Operations (dated 2031-04-15T00:00:00)"
    )


def test_entries_outside_the_window_or_undated_are_skipped() -> None:
    kept = entry(0, "Purge", "2031-01-01T00:00:00")
    events = run(
        (kept,),
        (
            kept,
            entry(1, "Purge", BEFORE_DATE),  # dated on the earlier save day: the earlier interval's
            entry(2, "Purge", AFTER_DATE),  # dated on the later save day: this interval's
            entry(3, "Purge", None),
            entry(4, "Purge", Unknown()),
            entry(5, "Purge", "2031-09-01T00:00:00"),
        ),
    )
    assert [event.id for event in events] == ["faction.transaction_recorded/faction:15/Purge/2"]


def test_labels_outside_the_allow_list_are_left_in_the_diff() -> None:
    events = run((), (entry(0, "Daily Income"), entry(0, "1234567890"), entry(0, "Spoils"), entry(0, "Stabilize")))
    assert [event.id for event in events] == ["faction.transaction_recorded/faction:15/Stabilize/0"]
    assert "Daily Income" not in ALLOWED_LABELS and "1234567890" not in ALLOWED_LABELS


def test_an_entry_present_in_both_saves_but_dated_inside_the_interval_is_read_by_date() -> None:
    both = entry(0, "Crackdown")
    events = run((both,), (both, entry(1, "Crackdown", "2031-05-01T00:00:00")))
    assert [event.id for event in events] == [
        "faction.transaction_recorded/faction:15/Crackdown/0",
        "faction.transaction_recorded/faction:15/Crackdown/1",
    ]


def test_an_unchanged_ledger_or_an_unknown_snapshot_date_yields_nothing() -> None:
    both = entry(0, "Crackdown")
    assert run((both,), (both,)) == []
    assert run((), (entry(0, "Coup"),), after_date=Unknown()) == []


def test_every_resource_of_one_charge_is_its_own_event() -> None:
    events = run((), (entry(0, "Ship Construction", amount=-100.0), entry(1, "Ship Construction", amount=-50.0)))
    assert [event.id for event in events] == [
        "faction.transaction_recorded/faction:15/Ship Construction/0",
        "faction.transaction_recorded/faction:15/Ship Construction/1",
    ]
