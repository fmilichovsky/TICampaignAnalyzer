"""The campaign-wide singletons: ``TIGlobalValuesState`` and the game's notification log.

Notification log types are named by the game's template (``notification.<templateName>``), so one prefix kind covers
them; the fixed types of the analyzer are exact kinds. Of the campaign types, only the milestone record is narrator
evidence; every notification line is, since the log dates and places a battle or a destroyed hab.
"""

from __future__ import annotations

import re
from dataclasses import replace

from ..diff.render import render_value
from ..model.events import Event, Role, Significance
from ..model.kinds import EventKind, EvidenceRole
from ..model.values import Observed, Unknown
from .text import (
    TRANSITION,
    attribute_label,
    attribute_text,
    plain,
    render_event_value,
    role_label,
    subject_label,
    transition_label,
)

_ABSENT = "is absent from the after snapshot"
_PRESENT = "is present only in the after snapshot"


def _presence(event: Event) -> str:
    return f"{subject_label(event)} {_PRESENT if event.attribute('side') == 'after' else _ABSENT}"


def _milestone_recorded(event: Event) -> str:
    return (
        f"{subject_label(event)} records global milestone {attribute_text(event, 'milestone')} "
        f"for {attribute_label(event, 'faction')}"
    )


def _milestone_changed(event: Event) -> str:
    label = f"global milestone {attribute_text(event, 'milestone')} faction"
    return f"{subject_label(event)} {transition_label(event, label)}"


def _sea_level_rise(event: Event) -> str:
    return f"{subject_label(event)} sea level rise {attribute_label(event, 'stage')} flag set"


def _narrative_event_triggered(event: Event) -> str:
    name = attribute_text(event, "narrative_event")
    if event.attribute("scope") == "target":
        return (
            f"{subject_label(event)} lists narrative event {name} as triggered for {attribute_label(event, 'targets')}"
        )
    return f"{subject_label(event)} lists narrative event {name} as triggered once per campaign"


def _global_value_changed(event: Event) -> str:
    field = attribute_text(event, "field")
    if isinstance(event.attribute("transition"), Unknown):
        return (
            f"{subject_label(event)} {field} records changed: {attribute_label(event, 'added')} added, "
            f"{attribute_label(event, 'removed')} removed, {attribute_label(event, 'changed')} changed"
        )
    return f"{subject_label(event)} {transition_label(event, field)}"


SIDE = frozenset({"side"})

GLOBAL_VALUES_APPEARED = EventKind(
    "campaign.global_values_appeared", _presence, Significance.MINOR, EvidenceRole.BOOKKEEPING, required=SIDE
)
GLOBAL_VALUES_DISAPPEARED = EventKind(
    "campaign.global_values_disappeared", _presence, Significance.MINOR, EvidenceRole.BOOKKEEPING, required=SIDE
)
MILESTONE_RECORDED = EventKind(
    "campaign.global_milestone_recorded",
    _milestone_recorded,
    Significance.CAMPAIGN_DEFINING,
    EvidenceRole.EVIDENCE,
    required=frozenset({"milestone", "faction"}),
)
MILESTONE_CHANGED = EventKind(
    "campaign.global_milestone_changed",
    _milestone_changed,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION | {"milestone"},
)
NUCLEAR_STRIKES_CHANGED = EventKind(
    "campaign.nuclear_strikes_changed",
    plain("nuclear strikes"),
    Significance.CAMPAIGN_DEFINING,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION,
)
SEA_LEVEL_RISE_TRIGGERED = EventKind(
    "campaign.sea_level_rise_triggered",
    _sea_level_rise,
    Significance.CAMPAIGN_DEFINING,
    EvidenceRole.BOOKKEEPING,
    required=TRANSITION | {"stage"},
)
NARRATIVE_EVENT_TRIGGERED = EventKind(
    "campaign.narrative_event_triggered",
    _narrative_event_triggered,
    Significance.MAJOR,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"narrative_event", "scope"}),
    optional=frozenset({"targets"}),
)
VALUE_CHANGED = EventKind(
    "campaign.global_value_changed",
    _global_value_changed,
    Significance.MINOR,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"field", "before", "after"}),
    optional=frozenset({"transition", "added", "removed", "changed"}),
)

# --- The notification log -------------------------------------------------------------------------------------

NOTIFICATION_PREFIX = "notification."
"""The types whose names come from the game's log templates."""

ENTRY = frozenset(
    {
        "template",
        "summary",
        "outcome",
        "subject",
        "alien_related",
        "news_feed_factions",
        "summary_log_factions",
    }
)
"""What every logged entry carries; the summary text is campaign content, carried and never rendered."""
BEFORE_ENTRY = frozenset(
    {
        "before_subject",
        "before_outcome",
        "before_alien_related",
        "before_news_feed_factions",
        "before_summary_log_factions",
    }
)


def _notification_subject(event: Event) -> str:
    """The resolved subject, ``null`` for none, or the literal unresolved value; never the summary text."""
    return render_event_value(event.attribute("subject"))


def _notification_logged(event: Event) -> str:
    date = event.date if isinstance(event.date, str) else render_value(event.date)
    return (
        f"{subject_label(event)} logs {attribute_text(event, 'template')} dated {date} "
        f"about {_notification_subject(event)}"
    )


def _notification_removed(event: Event) -> str:
    return (
        f"{subject_label(event)} no longer lists {attribute_text(event, 'template')} "
        f"dated {attribute_text(event, 'logged_on')} about {_notification_subject(event)}"
    )


def _notification_changed(event: Event) -> str:
    before = render_event_value(event.attribute("before_subject"))
    return (
        f"{subject_label(event)} entry {attribute_text(event, 'template')} "
        f"dated {attribute_text(event, 'logged_on')} changed: "
        f"subject {before} -> {_notification_subject(event)}, "
        f"outcome {attribute_label(event, 'before_outcome')} -> {attribute_label(event, 'outcome')}"
    )


NOTIFICATION = EventKind(
    NOTIFICATION_PREFIX,
    _notification_logged,
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    required=ENTRY,
    prefix=True,
)
QUEUE_APPEARED = EventKind(
    "notification.queue_appeared", _presence, Significance.MINOR, EvidenceRole.EVIDENCE, required=SIDE
)
QUEUE_DISAPPEARED = EventKind(
    "notification.queue_disappeared", _presence, Significance.MINOR, EvidenceRole.EVIDENCE, required=SIDE
)
QUEUE_VALUE_CHANGED = EventKind(
    "notification.queue_value_changed",
    _global_value_changed,
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    required=TRANSITION | {"field"},
)
ENTRY_REMOVED = EventKind(
    "notification.entry_removed",
    _notification_removed,
    Significance.TRIVIAL,
    EvidenceRole.EVIDENCE,
    required=ENTRY | {"logged_on"},
)
ENTRY_CHANGED = EventKind(
    "notification.entry_changed",
    _notification_changed,
    Significance.TRIVIAL,
    EvidenceRole.EVIDENCE,
    required=ENTRY | BEFORE_ENTRY | {"logged_on"},
)
UNKNOWN_TEMPLATE = EventKind(
    "notification.unknown_template",
    _notification_logged,
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    required=ENTRY,
)

FIXED = (QUEUE_APPEARED, QUEUE_DISAPPEARED, QUEUE_VALUE_CHANGED, ENTRY_REMOVED, ENTRY_CHANGED, UNKNOWN_TEMPLATE)
"""The notification types of the analyzer that are not a log template; templates are CamelCase, these are not."""

_TEMPLATE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def entry_kind(template: Observed) -> EventKind:
    """The kind of a logged entry: the prefix kind named ``notification.<templateName>`` for an identifier-like
    template, else ``notification.unknown_template``."""
    fixed = {kind.event_type for kind in FIXED}
    if isinstance(template, str) and _TEMPLATE.match(template) and NOTIFICATION_PREFIX + template not in fixed:
        return replace(NOTIFICATION, event_type=NOTIFICATION_PREFIX + template, prefix=False)
    return UNKNOWN_TEMPLATE


KINDS = (
    GLOBAL_VALUES_APPEARED,
    GLOBAL_VALUES_DISAPPEARED,
    MILESTONE_RECORDED,
    MILESTONE_CHANGED,
    NUCLEAR_STRIKES_CHANGED,
    SEA_LEVEL_RISE_TRIGGERED,
    NARRATIVE_EVENT_TRIGGERED,
    VALUE_CHANGED,
    NOTIFICATION,
    *FIXED,
)


# --- Narrative events (#325) ---------------------------------------------------------------------------------------


def _first_milestone(event: Event) -> str:
    return f"{role_label(event, Role.ACTOR)} recorded the campaign milestone {attribute_text(event, 'milestone')}"


FIRST_MILESTONE = EventKind(
    "campaign.first_milestone",
    _first_milestone,
    None,
    EvidenceRole.BOOKKEEPING,
    required=frozenset({"milestone", "faction"}),
)

NARRATIVE_KINDS = (FIRST_MILESTONE,)
