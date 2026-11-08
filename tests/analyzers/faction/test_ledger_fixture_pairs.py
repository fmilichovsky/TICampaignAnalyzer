"""Acceptance for the faction family over the ledger fixture pair."""

import json

from tests.analyzers.support import fixture_pair
from tinarrative.analyzers import FACTION_ANALYZERS, run_analyzers
from tinarrative.analyzers.render import describe_event
from tinarrative.model.events import Confidence, DateBasis, EventStatus, SourceRole

PAIR = ("ledger_before.json", "ledger_after.json")


def test_ledger_pair_yields_the_allow_listed_entries_inside_the_interval() -> None:
    before, after, diff = fixture_pair(*PAIR)
    events = run_analyzers(FACTION_ANALYZERS, before, after, diff)
    assert [event.id for event in events] == [
        "faction.transaction_recorded/faction:15/Stabilize/0",
        "faction.transaction_recorded/faction:15/Ship Construction/0",
    ]
    assert [event.date for event in events] == [
        "2031-04-15T00:00:00",
        "2031-06-01T00:00:00",
    ]
    assert {describe_event(event) for event in events} == {
        "Fixture Resistance (faction:15) ledger records a Stabilize charge: -16.0 Influence "
        "(dated 2031-04-15T00:00:00)",
        "Fixture Resistance (faction:15) ledger records a Ship Construction charge: -100.0 Metals "
        "(dated 2031-06-01T00:00:00)",
    }
    # Operation charges, the pruned Coup list, and the earlier-day Crackdown charge are not events; the
    # pruned entry stays visible in the diff.
    (change,) = [c for c in diff.changes if c.field == "Transactions" and str(c.entity_id) == "faction:15"]
    assert any(getattr(entry, "label", None) == "Coup" for entry in change.detail.removed)  # type: ignore[union-attr]


def test_every_ledger_event_is_evidenced_objective_and_deterministic() -> None:
    before, after, diff = fixture_pair(*PAIR)
    events = run_analyzers(FACTION_ANALYZERS, before, after, diff)
    assert events and len({e.id for e in events}) == len(events)
    assert json.dumps([e.to_dict() for e in events]) == json.dumps(
        [e.to_dict() for e in run_analyzers(FACTION_ANALYZERS, before, after, diff)]
    )
    changes = set(diff.changes)
    for event in events:
        assert event.status is EventStatus.OBJECTIVE
        assert event.sources and any(source.role is SourceRole.PRIMARY for source in event.sources)
        assert all(source.change in changes for source in event.sources)
        assert event.entities
        assert event.not_before == before.date
        assert event.confidence is Confidence.HIGH
        assert event.date_basis is DateBasis.RECORD
        assert str(before.date) < str(event.date) <= str(after.date)
        json.loads(json.dumps(event.to_dict()))
