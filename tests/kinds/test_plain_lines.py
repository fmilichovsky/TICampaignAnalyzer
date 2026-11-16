"""The plain rendering of the catalog: names without IDs, dates without times, no raw payloads, no glue containers."""

from __future__ import annotations

from tests.narrative.support import atomic, nation, ref
from tinarrative.kinds import describe_event
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Event
from tinarrative.model.values import Observed, Unknown, UnknownReason

K = "2032-01-01T00:00:00"
NORTH = nation("20", "Northland")
QUEUE = ref(EntityDomain.NOTIFICATION_QUEUE, "5771")


def nation_line(event_type: str, *attributes: tuple[str, Observed], who=NORTH) -> Event:
    return atomic(f"{event_type}/nation:20", K, entities=(who,), attributes=attributes)


def test_a_named_entity_reads_as_its_name_only() -> None:
    event = nation_line("nation.appeared", ("side", "after"))

    assert describe_event(event, plain=True) == "Northland appeared"
    assert describe_event(event) == "Northland (nation:20) appeared"


def test_an_unnamed_entity_keeps_its_bare_id() -> None:
    event = nation_line("nation.appeared", ("side", "after"), who=nation("20"))

    assert describe_event(event, plain=True) == "nation:20 appeared"


def test_a_reference_inside_a_list_is_named_too() -> None:
    kabul = ref(EntityDomain.REGION, "40", "Kabul")
    event = nation_line("nation.claims_changed", ("added", (kabul,)), ("removed", ()))

    assert "[Kabul]" in describe_event(event, plain=True)
    assert "[Kabul (region:40)]" in describe_event(event)


def test_an_unresolved_reference_is_unknown_without_its_payload() -> None:
    event = nation_line(
        "nation.claims_changed",
        ("transition", "unresolved"),
        ("before", Unknown(UnknownReason.UNRESOLVED_REFERENCE, 5773)),
        ("after", Unknown()),
    )

    plain = describe_event(event, plain=True)
    assert "unknown" in plain
    assert "raw" not in plain and "5773" not in plain
    assert "raw=5773" in describe_event(event)


def test_a_notification_drops_the_timestamp_time_and_the_queue_id() -> None:
    event = atomic(
        "notification.research_completed/notification_queue:5771",
        K,
        entities=(QUEUE,),
        attributes=(
            ("template", "ResearchCompleted"),
            ("summary", None),
            ("outcome", None),
            ("subject", None),
            ("alien_related", False),
            ("news_feed_factions", ()),
            ("summary_log_factions", ()),
        ),
    )

    assert describe_event(event).endswith("(in notification queue:5771)")
    plain = describe_event(event, plain=True)
    assert plain == "ResearchCompleted logged, dated 2032-01-01"
