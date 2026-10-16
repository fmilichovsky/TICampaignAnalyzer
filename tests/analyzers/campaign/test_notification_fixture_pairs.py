"""Acceptance over the notification fixture pair: one event per log entry, record dates, provenance, wording."""

import pytest

from tests.analyzers.support import fixture_pair
from tinarrative.analyzers import ALL_ANALYZERS, CAMPAIGN_ANALYZERS, run_analyzers
from tinarrative.analyzers.render import describe_event
from tinarrative.model.events import Confidence, DateBasis, Event
from tinarrative.model.values import Unknown, UnknownReason

PAIR = ("notifications_before.json", "notifications_after.json")
QUEUE = "notification queue:80"
LOG_PATH = "/gamestates/PavonisInteractive.TerraInvicta.TINotificationQueueState/0/Value/notificationSummaryQueue"
FORBIDDEN = ("pruned", "expired", "dismissed")


def run() -> tuple[Event, ...]:
    return run_analyzers(CAMPAIGN_ANALYZERS, *fixture_pair(*PAIR))


def by_id(events: tuple[Event, ...]) -> dict[str, Event]:
    return {event.id: event for event in events}


@pytest.mark.fixture
def test_notification_pair_yields_one_event_per_added_removed_and_changed_entry() -> None:
    assert [event.id for event in run()] == [
        f"notification.LogSpaceBattleTakesPlace/{QUEUE}/2",
        f"notification.LogXenoformingDetected/{QUEUE}/3",
        f"notification.LogXenoformingDetected/{QUEUE}/4",
        f"notification.LogHabDestroyed/{QUEUE}/5",
        f"notification.LogProjectComplete/{QUEUE}/6",
        f"notification.LogNationJoinsWar/{QUEUE}/7",
        f"notification.entry_changed/{QUEUE}/1",
        f"notification.entry_removed/{QUEUE}/1",
    ]


@pytest.mark.fixture
def test_an_added_entry_is_dated_by_the_entry_and_cites_it() -> None:
    event = by_id(run())[f"notification.LogSpaceBattleTakesPlace/{QUEUE}/2"]
    assert (event.date, event.date_basis, event.not_before) == (
        "2032-01-15T00:00:00",
        DateBasis.RECORD,
        "2032-01-01T00:00:00",
    )
    (source,) = event.sources
    assert source.entry is not None and source.entry.path == f"{LOG_PATH}/2"
    assert source.member == "LogSpaceBattleTakesPlace"
    assert [str(ref.entity_id) for ref in event.entities] == [QUEUE, "fleet:50"]
    assert event.attribute("summary") == "Fixture summary: fleets engage."
    assert [str(ref.entity_id) for ref in event.attribute("news_feed_factions")] == ["faction:15", "faction:16"]
    assert event.confidence is Confidence.HIGH


@pytest.mark.fixture
def test_duplicate_entries_are_two_events_and_an_unresolved_subject_is_kept_with_low_confidence() -> None:
    events = by_id(run())
    twins = [events[f"notification.LogXenoformingDetected/{QUEUE}/{index}"] for index in (3, 4)]
    assert twins[0].attributes == twins[1].attributes
    for event_id in (f"notification.LogHabDestroyed/{QUEUE}/5", f"notification.LogProjectComplete/{QUEUE}/6"):
        event = events[event_id]
        subject = event.attribute("subject")
        assert isinstance(subject, Unknown) and subject.reason is UnknownReason.UNRESOLVED_REFERENCE
        assert [str(ref.entity_id) for ref in event.entities] == [QUEUE]
        assert event.confidence is Confidence.LOW


@pytest.mark.fixture
def test_a_removed_entry_is_reported_literally_and_dated_by_the_interval() -> None:
    event = by_id(run())[f"notification.entry_removed/{QUEUE}/1"]
    assert (event.date, event.date_basis) == ("2032-03-01T00:00:00", DateBasis.INTERVAL)
    assert event.attribute("logged_on") == "2031-12-25T00:00:00"
    assert event.attribute("template") == "LogMyCouncilorDetained"
    (source,) = event.sources
    assert source.entry is not None and source.entry.path == f"{LOG_PATH}/1"
    assert source.entry.save_id.endswith("notifications_before.json")


@pytest.mark.fixture
def test_a_changed_entry_keeps_both_outcomes() -> None:
    event = by_id(run())[f"notification.entry_changed/{QUEUE}/1"]
    assert (event.attribute("before_outcome"), event.attribute("outcome")) == ("None", "Success")


@pytest.mark.fixture
def test_lines_name_the_template_and_subject_but_never_the_summary() -> None:
    events = run_analyzers(ALL_ANALYZERS, *fixture_pair(*PAIR))
    lines = {describe_event(event) for event in events}
    assert lines == {
        f"{QUEUE} logs LogSpaceBattleTakesPlace dated 2032-01-15T00:00:00 about fleet:50",
        f"{QUEUE} logs LogXenoformingDetected dated 2032-02-01T00:00:00 about region:40",
        f"{QUEUE} logs LogHabDestroyed dated 2032-02-10T00:00:00 about unknown "
        '(unresolved_reference, raw={"$type": "PavonisInteractive.TerraInvicta.TIHabState", "value": 999})',
        f"{QUEUE} logs LogProjectComplete dated 2032-02-20T00:00:00 about unknown "
        '(unresolved_reference, raw={"$type": "PavonisInteractive.TerraInvicta.TIMissionPhaseState", "value": 300})',
        f"{QUEUE} logs LogNationJoinsWar dated 2032-02-25T00:00:00 about null",
        f"{QUEUE} entry LogMissionOutcome dated 2031-12-28T00:00:00 changed: "
        'subject region:40 -> region:40, outcome "None" -> "Success"',
        f"{QUEUE} no longer lists LogMyCouncilorDetained dated 2031-12-25T00:00:00 about null",
    }
    text = " ".join(lines)
    assert "Fixture summary" not in text
    for word in FORBIDDEN:
        assert word not in text.lower()
