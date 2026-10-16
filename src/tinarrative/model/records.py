"""Save-carried records: dated logs and cumulative counters the game appends to an entity.

A record is neither objective snapshot state (it cannot be re-derived from other fields of the same save)
nor an inferred event (the save literally carries it). Each :class:`RecordSet` belongs to one entity and one
serialized field; its entries keep serialized order and their index, so every entry is addressable as
state type + map ID + field + index. A set whose field is absent or has an undocumented shape has
``entries = Unknown(...)``, never an empty tuple. See ``docs/architecture.md`` section 4.3.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable
from dataclasses import dataclass, replace
from dataclasses import fields as dataclass_fields
from enum import StrEnum
from typing import Any

from .entities import EntityRef
from .evidence import SourceLocation, pointer_path
from .values import Observed, Unknown, to_jsonable


class RecordKind(StrEnum):
    """The serialized shape of a record field; decides the entry type and how the diff compares entries."""

    LEDGER = "ledger"
    """``Transactions``: an object label -> list of ``{Resource, Amount, Date}``; ``LedgerEntry``."""
    DESTRUCTION_LOG = "destruction_log"
    """``HabDestructionLog``: a list of ``{HabType, SpaceBody, Date, Destroyer}``; ``DestructionEntry``."""
    NAME_LOG = "name_log"
    """``milestones``: a list of names; ``ItemEntry`` per element."""
    DATED_REFERENCES = "dated_references"
    """A pair map reference -> componentized date of the last update (``knownAlienSites``, ``lostControlPoints``)."""
    REFERENCE_VALUES = "reference_values"
    """A pair map reference -> value (``Kills``, ``factionAssassinations``, ``factionHate``); ``KeyedEntry``."""
    LABEL_VALUES = "label_values"
    """An object label -> value (``numAtrocitiesByCause``, ``armiesLost``, ``objectiveNames``); ``KeyedEntry``."""
    DATED_LABELS = "dated_labels"
    """An object label -> componentized date or null (``boostAccounts``); ``KeyedEntry``."""
    EXECUTIVE_CHANGE = "executive_change"
    """``lastExecutiveChange``: ``{cause, date, newExecutive}``; one ``KeyedEntry`` per member."""
    COUNTER = "counter"
    """A cumulative number; one ``ItemEntry``."""
    DATE = "date"
    """A componentized date or null; one ``ItemEntry``."""
    REFERENCE_LIST = "reference_list"
    """A list of references (``intelSharingFactions``); one ``ItemEntry`` holding the resolved list."""
    LABELLED_REFERENCES = "labelled_references"
    """An object label -> reference or list of references (``globalMilestones``, ``triggeredOncePerTargetEvents``);
    ``KeyedEntry`` whose value is the resolved reference or list."""
    NOTIFICATION_LOG = "notification_log"
    """``notificationSummaryQueue``: a list of dated typed entries (the game's own event log);
    ``NotificationEntry``."""


LOG_KINDS = frozenset((RecordKind.LEDGER, RecordKind.DESTRUCTION_LOG, RecordKind.NAME_LOG, RecordKind.NOTIFICATION_LOG))
"""Logs: entries are compared as multisets of their ``diff_key``, index aside (most grow by appending; see the
field map)."""
KEYED_KINDS = frozenset(
    (
        RecordKind.DATED_REFERENCES,
        RecordKind.REFERENCE_VALUES,
        RecordKind.LABEL_VALUES,
        RecordKind.DATED_LABELS,
        RecordKind.EXECUTIVE_CHANGE,
        RecordKind.LABELLED_REFERENCES,
    )
)
"""Maps: entries are matched by key, so a changed value is reported against its key."""
SCALAR_KINDS = frozenset((RecordKind.COUNTER, RecordKind.DATE, RecordKind.REFERENCE_LIST))
"""One ``ItemEntry`` whose value is compared like an ordinary field."""
PAIR_MAP_KINDS = frozenset((RecordKind.DATED_REFERENCES, RecordKind.REFERENCE_VALUES))
"""Keyed kinds serialized as a ``Key``/``Value`` array; entries are addressed by index."""


@dataclass(frozen=True)
class LedgerEntry:
    """``Transactions[label][index]``; ``label`` is an opaque cause, mission or hashed label."""

    index: int
    label: str
    resource: Observed
    amount: Observed
    date: Observed


@dataclass(frozen=True)
class DestructionEntry:
    """``HabDestructionLog[index]``; the references are ``EntityRef``, ``None`` or unresolved ``Unknown``."""

    index: int
    hab_type: Observed
    space_body: Observed
    date: Observed
    destroyer: Observed


@dataclass(frozen=True)
class KeyedEntry:
    """One member of a pair map or label map; ``key`` is a label, an ``EntityRef`` or an unresolved ``Unknown``."""

    index: int
    key: Observed
    value: Observed


@dataclass(frozen=True)
class ItemEntry:
    """One element of a plain list, or the single value of a scalar record kind."""

    index: int
    value: Observed


@dataclass(frozen=True)
class NotificationEntry:
    """``notificationSummaryQueue[index]``: one entry of the game's notification log.

    ``template`` is the log template identifier, ``date`` the ISO-8601 entry date and ``summary`` the localized
    free text (campaign content: never logged). ``subject`` is the resolved ``gotoGameState`` (``EntityRef``,
    ``None`` or unresolved ``Unknown``); the faction lists are resolved reference tuples.
    """

    index: int
    template: Observed
    date: Observed
    summary: Observed
    outcome: Observed
    subject: Observed
    alien_related: Observed
    news_feed_factions: Observed
    summary_log_factions: Observed


RecordEntry = LedgerEntry | DestructionEntry | KeyedEntry | ItemEntry | NotificationEntry


def diff_key(entry: RecordEntry) -> Hashable:
    """What identifies a log entry across two saves, index aside.

    A notification is identified by template, date and summary, so an entry whose other members differ is the
    same entry changed: the game was observed to rewrite ``gotoGameState`` of kept entries (to ``null`` or to
    another entity) between saves. Any other entry is identified by its whole content.
    """
    if isinstance(entry, NotificationEntry):
        return (entry.template, entry.date, entry.summary)
    return replace(entry, index=0)


def entry_to_dict(entry: RecordEntry) -> dict[str, Any]:
    return {item.name: to_jsonable(getattr(entry, item.name)) for item in dataclass_fields(entry)}


@dataclass(frozen=True)
class RecordSet:
    """Every record of one kind carried by one entity's serialized field.

    ``location`` points at the field (``<entity Value path>/<field>``); :meth:`entry_location` extends it
    to one entry. ``entries`` is ``Unknown`` when the field is absent (``missing``) or does not have the
    documented shape (``unparseable``, raw attached).
    """

    owner: EntityRef
    field: str
    kind: RecordKind
    location: SourceLocation
    entries: tuple[RecordEntry, ...] | Unknown = Unknown()

    @property
    def sort_key(self) -> tuple[tuple[str, int, int, str], str]:
        return (self.owner.entity_id.sort_key, self.field)

    def entry_location(self, entry: RecordEntry) -> SourceLocation:
        """Provenance of one entry: state type, map ID and the pointer into the serialized field."""
        base = self.location.path or ""
        if isinstance(entry, LedgerEntry):
            path = pointer_path(base, entry.label, entry.index)
        elif self.kind in SCALAR_KINDS:
            path = base
        elif isinstance(entry, KeyedEntry) and self.kind not in PAIR_MAP_KINDS and isinstance(entry.key, str):
            path = pointer_path(base, entry.key)
        else:
            path = pointer_path(base, entry.index)
        return SourceLocation(self.location.save_id, self.location.state_type, self.location.map_id, path)

    def to_dict(self) -> dict[str, Any]:
        entries: Any
        if isinstance(self.entries, Unknown):
            entries = to_jsonable(self.entries)
        else:
            entries = [entry_to_dict(entry) for entry in self.entries]
        return {
            "owner": str(self.owner.entity_id),
            "state_type": self.owner.state_type,
            "field": self.field,
            "kind": self.kind.value,
            "location": self.location.to_dict(),
            "entries": entries,
        }


def record_counts(records: Iterable[RecordSet]) -> tuple[int, int]:
    """``(known sets, entries)``: sets whose entries are known, and the entries they hold in total."""
    sets = 0
    entries = 0
    for record in records:
        if not isinstance(record.entries, Unknown):
            sets += 1
            entries += len(record.entries)
    return sets, entries
