"""Campaign-wide facts, the game's notification log, and the campaign's first milestones."""

from __future__ import annotations

from ..diff.render import render_value
from ..model.events import Event, Role, Significance
from ..model.kinds import EventKind, EvidenceRole
from ..model.values import Unknown
from .narrative import narrative_kind, role
from .text import (
    attribute_label,
    attribute_text,
    list_changed,
    plain,
    render_event_value,
    subject_label,
    transition_label,
)


def _side_presence(event: Event) -> str:
    status = (
        "is present only in the after snapshot"
        if event.attribute("side") == "after"
        else "is absent from the after snapshot"
    )
    return f"{subject_label(event)} {status}"


def _milestone_recorded(event: Event) -> str:
    milestone = attribute_text(event, "milestone")
    faction = attribute_label(event, "faction")
    return f"{subject_label(event)} records global milestone {milestone} for {faction}"


def _milestone_changed(event: Event) -> str:
    label = f"global milestone {attribute_text(event, 'milestone')} faction"
    return f"{subject_label(event)} {transition_label(event, label)}"


def _sea_level_rise(event: Event) -> str:
    return f"{subject_label(event)} sea level rise {attribute_label(event, 'stage')} flag set"


def _narrative_event(event: Event) -> str:
    name = attribute_text(event, "narrative_event")
    if event.attribute("scope") == "target":
        return (
            f"{subject_label(event)} lists narrative event {name} as triggered for {attribute_label(event, 'targets')}"
        )
    return f"{subject_label(event)} lists narrative event {name} as triggered once per campaign"


def _global_value(event: Event) -> str:
    if isinstance(event.attribute("transition"), Unknown):
        return (
            f"{subject_label(event)} {attribute_text(event, 'field')} records changed: "
            f"{event.attribute('added')} added, {event.attribute('removed')} removed, "
            f"{event.attribute('changed')} changed"
        )
    field = attribute_text(event, "field")
    return f"{subject_label(event)} {transition_label(event, field)}"


def _notification(event: Event) -> str:
    date = event.date if isinstance(event.date, str) else render_value(event.date)
    subject = render_event_value(event.attribute("subject"))
    return f"{subject_label(event)} logs {attribute_text(event, 'template')} dated {date} about {subject}"


def _notification_removed(event: Event) -> str:
    subject = render_event_value(event.attribute("subject"))
    template = attribute_text(event, "template")
    date = attribute_text(event, "logged_on")
    return f"{subject_label(event)} no longer lists {template} dated {date} about {subject}"


def _notification_changed(event: Event) -> str:
    before = render_event_value(event.attribute("before_subject"))
    subject = render_event_value(event.attribute("subject"))
    template = attribute_text(event, "template")
    date = attribute_text(event, "logged_on")
    before_outcome = attribute_label(event, "before_outcome")
    outcome = attribute_label(event, "outcome")
    return (
        f"{subject_label(event)} entry {template} dated {date} changed: subject {before} -> {subject}, "
        f"outcome {before_outcome} -> {outcome}"
    )


GLOBAL_VALUES_APPEARED = EventKind(
    "campaign.global_values_appeared",
    _side_presence,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"side"}),
)
GLOBAL_VALUES_DISAPPEARED = EventKind(
    "campaign.global_values_disappeared",
    _side_presence,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"side"}),
)
# Campaign-wide firsts, nuclear use and climate stages are what a history reports.
GLOBAL_MILESTONE_RECORDED = EventKind(
    "campaign.global_milestone_recorded",
    _milestone_recorded,
    Significance.CAMPAIGN_DEFINING,
    EvidenceRole.EVIDENCE,
    required=frozenset({"milestone", "faction"}),
)
GLOBAL_MILESTONE_CHANGED = EventKind(
    "campaign.global_milestone_changed",
    _milestone_changed,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"milestone", "transition", "before", "after"}),
)
NUCLEAR_STRIKES_CHANGED = EventKind(
    "campaign.nuclear_strikes_changed",
    plain("nuclear strikes"),
    Significance.CAMPAIGN_DEFINING,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"transition", "before", "after"}),
)
SEA_LEVEL_RISE_TRIGGERED = EventKind(
    "campaign.sea_level_rise_triggered",
    _sea_level_rise,
    Significance.CAMPAIGN_DEFINING,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"stage", "transition", "before", "after"}),
)
# A once-per-campaign narrative event.
NARRATIVE_EVENT_TRIGGERED = EventKind(
    "campaign.narrative_event_triggered",
    _narrative_event,
    Significance.MAJOR,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"narrative_event", "scope"}),
    optional=frozenset({"targets"}),
)
GLOBAL_VALUE_CHANGED = EventKind(
    "campaign.global_value_changed",
    _global_value,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"field"}),
    optional=frozenset({"transition", "before", "after", "added", "removed", "changed"}),
)
INTERSTATE_WARS_CHANGED = EventKind(
    "campaign.interstate_wars_changed",
    list_changed,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"transition"}),
    optional=frozenset({"member", "before", "after"}),
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
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    required=frozenset(
        {"template", "summary", "outcome", "subject", "alien_related", "news_feed_factions", "summary_log_factions"}
    ),
)
NOTIFICATION_UNKNOWN_TEMPLATE = EventKind(
    "notification.unknown_template",
    _notification,
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    required=NOTIFICATION_ENTRY.required,
)
NOTIFICATION_QUEUE_APPEARED = EventKind(
    "notification.queue_appeared",
    _side_presence,
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    required=frozenset({"side"}),
)
NOTIFICATION_QUEUE_DISAPPEARED = EventKind(
    "notification.queue_disappeared",
    _side_presence,
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    required=frozenset({"side"}),
)
NOTIFICATION_QUEUE_VALUE_CHANGED = EventKind(
    "notification.queue_value_changed",
    _global_value,
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    required=frozenset({"field"}),
    optional=GLOBAL_VALUE_CHANGED.optional,
)
NOTIFICATION_ENTRY_REMOVED = EventKind(
    "notification.entry_removed",
    _notification_removed,
    Significance.TRIVIAL,
    EvidenceRole.EVIDENCE,
    required=NOTIFICATION_ENTRY.required | {"logged_on"},
)
NOTIFICATION_ENTRY_CHANGED = EventKind(
    "notification.entry_changed",
    _notification_changed,
    Significance.TRIVIAL,
    EvidenceRole.EVIDENCE,
    required=NOTIFICATION_ENTRY.required | {"logged_on"} | _BEFORE_ENTRY,
)


def _first_milestone(event: Event) -> str:
    return f"{role(event, Role.ACTOR)} recorded the campaign milestone {attribute_text(event, 'milestone')}"


FIRST_MILESTONE = narrative_kind(
    "campaign.first_milestone", _first_milestone, required=frozenset({"milestone", "faction"})
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
