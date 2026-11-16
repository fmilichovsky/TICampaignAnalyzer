"""Campaign-wide facts, the game's notification log, and the campaign's first milestones."""

from __future__ import annotations

from ..diff.render import render_value
from ..model.entities import EntityDomain
from ..model.events import Event, Role, Significance
from ..model.kinds import EventKind, EvidenceRole
from ..model.plain import is_plain, plain_timestamp
from ..model.values import Unknown
from .narrative import narrative_kind, role
from .text import (
    attribute_label,
    attribute_text,
    render_event_value,
    subject_label,
    transition_label,
)


def _side_presence(event: Event) -> str:
    status = "appeared" if event.attribute("side") == "after" else "disappeared"
    return f"{subject_label(event)} {status}"


def _in(event: Event) -> str:
    """The singleton or queue the line is about, last: it names the container, not what happened."""
    if is_plain() and event.entities and event.entities[0].entity_id.domain is EntityDomain.NOTIFICATION_QUEUE:
        return ""  # the queue is glue: an ID with no content of its own
    return f" (in {subject_label(event)})"


def _milestone_recorded(event: Event) -> str:
    milestone = attribute_text(event, "milestone")
    faction = attribute_label(event, "faction")
    return f"{milestone} global milestone for {faction}{_in(event)}"


def _milestone_changed(event: Event) -> str:
    label = f"global milestone {attribute_text(event, 'milestone')} faction"
    return f"{transition_label(event, label)}{_in(event)}"


def _nuclear_strikes(event: Event) -> str:
    return f"{transition_label(event, 'nuclear strikes')}{_in(event)}"


def _sea_level_rise(event: Event) -> str:
    return f"sea level rise stage {attribute_label(event, 'stage')} flag set{_in(event)}"


def _narrative_event(event: Event) -> str:
    name = attribute_text(event, "narrative_event")
    if event.attribute("scope") == "target":
        return f"narrative event {name} listed as triggered for {attribute_label(event, 'targets')}{_in(event)}"
    return f"narrative event {name} listed as triggered once per campaign{_in(event)}"


def _global_value(event: Event) -> str:
    if isinstance(event.attribute("transition"), Unknown):
        return (
            f"{attribute_text(event, 'field')} records changed: "
            f"{event.attribute('added')} added, {event.attribute('removed')} removed, "
            f"{event.attribute('changed')} changed{_in(event)}"
        )
    field = attribute_text(event, "field")
    return f"{transition_label(event, field)}{_in(event)}"


def _interstate_wars(event: Event) -> str:
    field = event.sources[0].change.field if event.sources else "list"
    transition = event.attribute("transition")
    if transition == "unresolved":
        return f"{transition_label(event, f'{field} list')}{_in(event)}"
    sign = "+" if transition == "added" else "-"
    return f"{field} list: {sign}{attribute_label(event, 'member')}{_in(event)}"


def _about(event: Event) -> str:
    """`` about <subject>``; a null subject says nothing and is left out."""
    subject = event.attribute("subject")
    return "" if subject is None else f" about {render_event_value(subject)}"


def _date(event: Event) -> str:
    return plain_timestamp(event.date) if isinstance(event.date, str) else render_value(event.date)


def _notification(event: Event) -> str:
    template = attribute_text(event, "template")
    return f"{template} logged{_about(event)}, dated {_date(event)}{_in(event)}"


def _notification_removed(event: Event) -> str:
    template = attribute_text(event, "template")
    date = attribute_text(event, "logged_on")
    return f"{template} no longer listed{_about(event)}, dated {date}{_in(event)}"


def _notification_changed(event: Event) -> str:
    # Fields that changed lead; unchanged pairs and null-to-null ones follow or are left out.
    pairs = [
        ("outcome", event.attribute("before_outcome"), event.attribute("outcome")),
        ("subject", event.attribute("before_subject"), event.attribute("subject")),
    ]
    shown = [
        (name, render_event_value(before), render_event_value(after))
        for name, before, after in pairs
        if not (before is None and after is None)
    ]
    shown.sort(key=lambda item: item[1] == item[2])
    parts = ", ".join(f"{name} {before} -> {after}" for name, before, after in shown)
    parts = f": {parts}" if parts else ""
    template = attribute_text(event, "template")
    date = attribute_text(event, "logged_on")
    return f"{template} entry changed{parts}; dated {date}{_in(event)}"


GLOBAL_VALUES_APPEARED = EventKind(
    "campaign.global_values_appeared",
    _side_presence,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"side"}),
    base=Significance.MINOR,
)
GLOBAL_VALUES_DISAPPEARED = EventKind(
    "campaign.global_values_disappeared",
    _side_presence,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"side"}),
    base=Significance.MINOR,
)
# Campaign-wide firsts, nuclear use and climate stages are what a history reports.
GLOBAL_MILESTONE_RECORDED = EventKind(
    "campaign.global_milestone_recorded",
    _milestone_recorded,
    EvidenceRole.EVIDENCE,
    required=frozenset({"milestone", "faction"}),
    base=Significance.CAMPAIGN_DEFINING,
)
GLOBAL_MILESTONE_CHANGED = EventKind(
    "campaign.global_milestone_changed",
    _milestone_changed,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"milestone", "transition", "before", "after"}),
    base=Significance.MINOR,
)
NUCLEAR_STRIKES_CHANGED = EventKind(
    "campaign.nuclear_strikes_changed",
    _nuclear_strikes,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"transition", "before", "after"}),
    base=Significance.CAMPAIGN_DEFINING,
)
SEA_LEVEL_RISE_TRIGGERED = EventKind(
    "campaign.sea_level_rise_triggered",
    _sea_level_rise,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"stage", "transition", "before", "after"}),
    base=Significance.CAMPAIGN_DEFINING,
)
# A once-per-campaign narrative event.
NARRATIVE_EVENT_TRIGGERED = EventKind(
    "campaign.narrative_event_triggered",
    _narrative_event,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"narrative_event", "scope"}),
    optional=frozenset({"targets"}),
    base=Significance.MAJOR,
)
GLOBAL_VALUE_CHANGED = EventKind(
    "campaign.global_value_changed",
    _global_value,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"field"}),
    optional=frozenset({"transition", "before", "after", "added", "removed", "changed"}),
    base=Significance.MINOR,
)
INTERSTATE_WARS_CHANGED = EventKind(
    "campaign.interstate_wars_changed",
    _interstate_wars,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
    base=Significance.MINOR,
)

_BEFORE_ENTRY = frozenset(
    {
        "before_subject",
        "before_outcome",
        "before_alien_related",
        "before_news_feed_factions",
        "before_summary_log_factions",
    }
)
"""What a changed log entry carries of its earlier state."""

NOTIFICATION_ENTRY = EventKind(
    "notification.*",
    _notification,
    EvidenceRole.EVIDENCE,
    required=frozenset(
        {"template", "summary", "outcome", "subject", "alien_related", "news_feed_factions", "summary_log_factions"}
    ),
    base=Significance.MINOR,
)
NOTIFICATION_UNKNOWN_TEMPLATE = EventKind(
    "notification.unknown_template",
    _notification,
    EvidenceRole.EVIDENCE,
    required=NOTIFICATION_ENTRY.required,
    base=Significance.MINOR,
)
NOTIFICATION_QUEUE_APPEARED = EventKind(
    "notification.queue_appeared",
    _side_presence,
    EvidenceRole.EVIDENCE,
    required=frozenset({"side"}),
    base=Significance.MINOR,
)
NOTIFICATION_QUEUE_DISAPPEARED = EventKind(
    "notification.queue_disappeared",
    _side_presence,
    EvidenceRole.EVIDENCE,
    required=frozenset({"side"}),
    base=Significance.MINOR,
)
NOTIFICATION_QUEUE_VALUE_CHANGED = EventKind(
    "notification.queue_value_changed",
    _global_value,
    EvidenceRole.EVIDENCE,
    required=frozenset({"field"}),
    optional=GLOBAL_VALUE_CHANGED.optional,
    base=Significance.MINOR,
)
NOTIFICATION_ENTRY_REMOVED = EventKind(
    "notification.entry_removed",
    _notification_removed,
    EvidenceRole.EVIDENCE,
    required=NOTIFICATION_ENTRY.required | {"logged_on"},
    base=Significance.TRIVIAL,
)
NOTIFICATION_ENTRY_CHANGED = EventKind(
    "notification.entry_changed",
    _notification_changed,
    EvidenceRole.EVIDENCE,
    required=NOTIFICATION_ENTRY.required | {"logged_on"} | _BEFORE_ENTRY,
    base=Significance.TRIVIAL,
)


def _first_milestone(event: Event) -> str:
    return f"{attribute_text(event, 'milestone')} campaign milestone for {role(event, Role.ACTOR)}"


FIRST_MILESTONE = narrative_kind(
    "campaign.first_milestone",
    _first_milestone,
    required=frozenset({"milestone", "faction"}),
    base=Significance.CAMPAIGN_DEFINING,
)

KINDS = (
    GLOBAL_VALUES_APPEARED,
    GLOBAL_VALUES_DISAPPEARED,
    GLOBAL_MILESTONE_RECORDED,
    GLOBAL_MILESTONE_CHANGED,
    NUCLEAR_STRIKES_CHANGED,
    SEA_LEVEL_RISE_TRIGGERED,
    NARRATIVE_EVENT_TRIGGERED,
    GLOBAL_VALUE_CHANGED,
    INTERSTATE_WARS_CHANGED,
    NOTIFICATION_ENTRY,
    NOTIFICATION_UNKNOWN_TEMPLATE,
    NOTIFICATION_QUEUE_APPEARED,
    NOTIFICATION_QUEUE_DISAPPEARED,
    NOTIFICATION_QUEUE_VALUE_CHANGED,
    NOTIFICATION_ENTRY_REMOVED,
    NOTIFICATION_ENTRY_CHANGED,
    FIRST_MILESTONE,
)
