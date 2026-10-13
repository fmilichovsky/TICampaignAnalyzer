"""The committed unknowns registry: findings accumulated across saves and scans, awaiting triage.

The registry is a JSON document (``docs/game-data-notes/unknowns/registry.json`` in this repository) that
records, per finding key, how often and when a structure outside the parser's schema was observed. It holds
schema-level facts only; :data:`SAFE_STRING` rejects anything that could be a value, a name or a path. The
scanner owns every member except ``triage``, which is written by hand and preserved verbatim. Entries leave
the registry only when the code tables learn the structure (:func:`prune_known`); a scan that does not meet
an entry never removes it, because absence from one save set is not resolution.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from ..log import fields as log_fields
from ..log import get_logger, safe_path
from ..parsing.game_version import DEFAULT_FORMAT
from ..parsing.unknowns import FindingKey, ShapeSummary, UnknownKind, UnknownReport, is_known

logger = get_logger(__name__)

SCHEMA_VERSION = 1
NO_GAME_VERSION = "not-serialized"
"""Recorded for a save without a serialized ``game_version``, so that fact survives later versioned saves."""
PRIVACY_NOTE = (
    "Schema-level facts only: state-type names, field names, JSON shapes, counts and dates. "
    "Never values, player or file names, paths or hashes."
)
SAFE_STRING = re.compile(r"^[A-Za-z0-9_$][A-Za-z0-9_$.:=-]*$")
"""Every state type, field, detail, shape key and game version must match this: no spaces, quotes or slashes."""
MAX_STRING = 120

_KINDS = frozenset(kind.value for kind in UnknownKind)
_TYPE_LABELS = frozenset(("null", "boolean", "number", "string", "array", "object"))
_DOCUMENT_KEYS = ("schema_version", "format", "last_scan", "privacy_note", "entries")
_ENTRY_KEYS = (
    "kind",
    "state_type",
    "field",
    "detail",
    "shape",
    "max_occurrences",
    "saves_seen",
    "first_seen",
    "last_seen",
    "game_versions",
    "triage",
)
_SHAPE_KEYS = ("types", "object_keys", "object_keys_omitted", "array_item_types", "array_item_keys")
_TRIAGE_KEYS = ("status", "notes", "ref")


class RegistryError(ValueError):
    """The registry file is not a valid registry document, or cannot be read or written."""


class TriageStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    NEEDS_EVIDENCE = "needs_evidence"


@dataclass(frozen=True)
class EntryKey:
    """Identity of a registry entry: the same four parts as ``UnknownFinding.key``."""

    kind: str
    state_type: str
    field: str | None
    detail: str | None

    @property
    def sort_key(self) -> FindingKey:
        return (self.kind, self.state_type, self.field or "", self.detail or "")

    @classmethod
    def from_finding_key(cls, key: FindingKey) -> EntryKey:
        kind, state_type, field, detail = key
        return cls(kind, state_type, field or None, detail or None)

    def __str__(self) -> str:
        subject = f"{self.state_type}.{self.field}" if self.state_type and self.field else self.state_type or self.field
        return f"{self.kind} {subject}" + (f" [{self.detail}]" if self.detail else "")


@dataclass(frozen=True)
class Triage:
    """Hand-written triage state; the only free text in the registry."""

    status: TriageStatus = TriageStatus.OPEN
    notes: str = ""
    ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"status": self.status.value, "notes": self.notes}
        if self.ref is not None:
            data["ref"] = self.ref
        return data


@dataclass(frozen=True)
class RegistryEntry:
    key: EntryKey
    shape: ShapeSummary | None
    max_occurrences: int
    saves_seen: int
    first_seen: date
    last_seen: date
    game_versions: tuple[str, ...]
    triage: Triage | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "kind": self.key.kind,
            "state_type": self.key.state_type,
            "field": self.key.field,
            "detail": self.key.detail,
            "shape": self.shape.to_dict() if self.shape is not None else None,
            "max_occurrences": self.max_occurrences,
            "saves_seen": self.saves_seen,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "game_versions": list(self.game_versions),
        }
        if self.triage is not None:
            data["triage"] = self.triage.to_dict()
        return data


@dataclass(frozen=True)
class Registry:
    format: str = DEFAULT_FORMAT
    last_scan: date | None = None
    entries: tuple[RegistryEntry, ...] = ()

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.entries, key=lambda entry: entry.key.sort_key))
        keys = [entry.key for entry in ordered]
        if len(set(keys)) != len(keys):
            raise RegistryError("registry entries repeat a key")
        object.__setattr__(self, "entries", ordered)

    def to_document(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "format": self.format,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "privacy_note": PRIVACY_NOTE,
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True)
class RegistryDelta:
    """What one scan did to the registry; counts and dates alone never make a delta."""

    added: tuple[EntryKey, ...] = ()
    updated: tuple[EntryKey, ...] = ()
    pruned: tuple[EntryKey, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.added or self.pruned)


@dataclass(frozen=True)
class RegistryUpdate:
    """Summary of a :func:`record` call for the command output."""

    added: int
    updated: int
    pruned: int
    total: int


def empty_registry(format: str = DEFAULT_FORMAT) -> Registry:
    return Registry(format=format)


def _is_safe(value: object) -> bool:
    return isinstance(value, str) and 0 < len(value) <= MAX_STRING and SAFE_STRING.match(value) is not None


def _parse_date(text: object) -> date:
    if not isinstance(text, str):
        raise ValueError("not a string")
    return date.fromisoformat(text)


def _validate_string_list(values: object, what: str, prefix: str, *, labels: bool = False) -> list[str]:
    if not isinstance(values, list):
        return [f"{prefix}: {what} is not a list"]
    problems: list[str] = []
    if values != sorted(set(values), key=str):
        problems.append(f"{prefix}: {what} is not sorted and unique")
    for item in values:
        if labels:
            if item not in _TYPE_LABELS:
                problems.append(f"{prefix}: {what} has an unknown type label")
        elif not _is_safe(item):
            problems.append(f"{prefix}: {what} contains an unsafe string")
    return problems


def _validate_shape(shape: object, prefix: str) -> list[str]:
    if shape is None:
        return []
    if not isinstance(shape, dict):
        return [f"{prefix}: shape is not an object"]
    if tuple(shape) != _SHAPE_KEYS:
        return [f"{prefix}: shape keys are not {', '.join(_SHAPE_KEYS)}"]
    problems = _validate_string_list(shape["types"], "types", prefix, labels=True)
    problems += _validate_string_list(shape["object_keys"], "object_keys", prefix)
    problems += _validate_string_list(shape["array_item_types"], "array_item_types", prefix, labels=True)
    problems += _validate_string_list(shape["array_item_keys"], "array_item_keys", prefix)
    if not isinstance(shape["object_keys_omitted"], bool):
        problems.append(f"{prefix}: object_keys_omitted is not a boolean")
    return problems


def _validate_triage(triage: object, prefix: str) -> list[str]:
    if not isinstance(triage, dict):
        return [f"{prefix}: triage is not an object"]
    problems: list[str] = []
    if set(triage) - set(_TRIAGE_KEYS) or "status" not in triage or "notes" not in triage:
        problems.append(f"{prefix}: triage keys are not status, notes and optional ref")
    if triage.get("status") not in {status.value for status in TriageStatus}:
        problems.append(f"{prefix}: triage status is not one of {', '.join(status.value for status in TriageStatus)}")
    if not isinstance(triage.get("notes"), str):
        problems.append(f"{prefix}: triage notes is not a string")
    if "ref" in triage and not isinstance(triage["ref"], str):
        problems.append(f"{prefix}: triage ref is not a string")
    return problems


def _is_count(value: object, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _validate_entry(entry: object, index: int) -> list[str]:
    prefix = f"entries[{index}]"
    if not isinstance(entry, dict):
        return [f"{prefix}: not an object"]
    expected = _ENTRY_KEYS if "triage" in entry else _ENTRY_KEYS[:-1]
    if tuple(entry) != expected:
        return [f"{prefix}: keys are not {', '.join(_ENTRY_KEYS)} in that order"]
    problems: list[str] = []
    kind = entry["kind"]
    if kind not in _KINDS:
        problems.append(f"{prefix}: unknown kind")
    state_type = entry["state_type"]
    if kind == UnknownKind.ENVELOPE_KEY.value:
        if state_type != "":
            problems.append(f"{prefix}: an envelope-key entry has an empty state_type")
    elif not _is_safe(state_type):
        problems.append(f"{prefix}: state_type is not a safe string")
    for name in ("field", "detail"):
        if entry[name] is not None and not _is_safe(entry[name]):
            problems.append(f"{prefix}: {name} is neither null nor a safe string")
    problems += _validate_shape(entry["shape"], prefix)
    if not _is_count(entry["max_occurrences"], 0):
        problems.append(f"{prefix}: max_occurrences is not a non-negative integer")
    if not _is_count(entry["saves_seen"], 1):
        problems.append(f"{prefix}: saves_seen is not a positive integer")
    for name in ("first_seen", "last_seen"):
        try:
            _parse_date(entry[name])
        except ValueError:
            problems.append(f"{prefix}: {name} is not an ISO date")
    problems += _validate_string_list(entry["game_versions"], "game_versions", prefix)
    if isinstance(entry["game_versions"], list) and not entry["game_versions"]:
        problems.append(f"{prefix}: game_versions is empty")
    if "triage" in entry:
        problems += _validate_triage(entry["triage"], prefix)
    return problems


def validate_document(document: object) -> list[str]:
    """Every way the decoded JSON fails to be a registry; ``[]`` when it is one."""
    if not isinstance(document, dict):
        return ["document is not a JSON object"]
    problems: list[str] = []
    if tuple(document) != _DOCUMENT_KEYS:
        problems.append(f"document keys are not {', '.join(_DOCUMENT_KEYS)} in that order")
        return problems
    if document["schema_version"] != SCHEMA_VERSION:
        problems.append(f"schema_version is not {SCHEMA_VERSION}")
    if not _is_safe(document["format"]):
        problems.append("format is not a safe string")
    if document["last_scan"] is not None:
        try:
            _parse_date(document["last_scan"])
        except ValueError:
            problems.append("last_scan is neither null nor an ISO date")
    if document["privacy_note"] != PRIVACY_NOTE:
        problems.append("privacy_note is missing or altered")
    entries = document["entries"]
    if not isinstance(entries, list):
        problems.append("entries is not a list")
        return problems
    keys: list[FindingKey] = []
    for index, entry in enumerate(entries):
        entry_problems = _validate_entry(entry, index)
        problems += entry_problems
        if not entry_problems:
            keys.append((entry["kind"], entry["state_type"], entry["field"] or "", entry["detail"] or ""))
    if keys != sorted(keys):
        problems.append("entries are not sorted by kind, state_type, field, detail")
    if len(set(keys)) != len(keys):
        problems.append("entries repeat a key")
    return problems


def _entry_from_dict(data: dict[str, Any]) -> RegistryEntry:
    triage_data = data.get("triage")
    triage = (
        Triage(TriageStatus(triage_data["status"]), triage_data["notes"], triage_data.get("ref"))
        if triage_data is not None
        else None
    )
    return RegistryEntry(
        key=EntryKey(data["kind"], data["state_type"], data["field"], data["detail"]),
        shape=ShapeSummary.from_dict(data["shape"]) if data["shape"] is not None else None,
        max_occurrences=data["max_occurrences"],
        saves_seen=data["saves_seen"],
        first_seen=date.fromisoformat(data["first_seen"]),
        last_seen=date.fromisoformat(data["last_seen"]),
        game_versions=tuple(data["game_versions"]),
        triage=triage,
    )


def registry_from_document(document: object) -> Registry:
    """Build a registry from decoded JSON; raises ``RegistryError`` listing what is wrong."""
    problems = validate_document(document)
    if problems:
        shown = "; ".join(problems[:5]) + (f"; and {len(problems) - 5} more" if len(problems) > 5 else "")
        raise RegistryError(f"not a valid unknowns registry: {shown}")
    assert isinstance(document, dict)
    return Registry(
        format=document["format"],
        last_scan=date.fromisoformat(document["last_scan"]) if document["last_scan"] else None,
        entries=tuple(_entry_from_dict(entry) for entry in document["entries"]),
    )


def load_registry(path: Path) -> Registry:
    """Read and validate the registry at ``path``; ``OSError`` propagates, bad content is a ``RegistryError``."""
    text = path.read_text(encoding="utf-8")
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise RegistryError(f"not valid JSON: {error.msg} (line {error.lineno}, column {error.colno})") from None
    registry = registry_from_document(document)
    logger.debug("registry loaded %s", log_fields(registry=safe_path(path), entries=len(registry.entries)))
    return registry


def load_or_empty(path: Path, format: str = DEFAULT_FORMAT) -> Registry:
    """The registry at ``path``, or an empty one when the file does not exist yet."""
    if not path.exists():
        return empty_registry(format)
    return load_registry(path)


def _version_label(game_version: str | None) -> str:
    if game_version is None:
        return NO_GAME_VERSION
    return game_version if _is_safe(game_version) else "unrepresentable"


def merge(registry: Registry, report: UnknownReport, *, game_version: str | None, today: date) -> Registry:
    """Fold one save's findings into the registry.

    An entry seen again keeps the larger per-save occurrence count (so re-scanning a save changes nothing),
    counts one more save, unions its shape and game versions and moves ``last_seen``; a new entry starts from
    this save. Entries the report does not mention are untouched.
    """
    version = _version_label(game_version)
    entries = {entry.key: entry for entry in registry.entries}
    for finding in report.findings:
        key = EntryKey.from_finding_key(finding.key)
        existing = entries.get(key)
        if existing is None:
            entries[key] = RegistryEntry(
                key=key,
                shape=finding.shape,
                max_occurrences=finding.occurrences,
                saves_seen=1,
                first_seen=today,
                last_seen=today,
                game_versions=(version,),
            )
            continue
        if existing.shape is None or finding.shape is None:
            shape = existing.shape if finding.shape is None else finding.shape
        else:
            shape = existing.shape.merge(finding.shape)
        entries[key] = RegistryEntry(
            key=key,
            shape=shape,
            max_occurrences=max(existing.max_occurrences, finding.occurrences),
            saves_seen=existing.saves_seen + 1,
            first_seen=existing.first_seen,
            last_seen=today,
            game_versions=tuple(sorted(set(existing.game_versions) | {version})),
            triage=existing.triage,
        )
    return Registry(registry.format, registry.last_scan, tuple(entries.values()))


def prune_known(
    registry: Registry, known: Callable[[FindingKey], bool] = is_known
) -> tuple[Registry, tuple[EntryKey, ...]]:
    """Drop entries the current schema can no longer produce; returns the registry and the dropped keys."""
    kept = tuple(entry for entry in registry.entries if not known(entry.key.sort_key))
    pruned = tuple(entry.key for entry in registry.entries if known(entry.key.sort_key))
    return Registry(registry.format, registry.last_scan, kept), pruned


def delta(before: Registry, after: Registry) -> RegistryDelta:
    """Keys added, seen again (``saves_seen`` grew) and pruned between two registry states."""
    old = {entry.key: entry for entry in before.entries}
    new = {entry.key: entry for entry in after.entries}
    return RegistryDelta(
        added=tuple(key for key in new if key not in old),
        updated=tuple(key for key in new if key in old and new[key].saves_seen > old[key].saves_seen),
        pruned=tuple(key for key in old if key not in new),
    )


def _compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(", ", ": "))


def dump(registry: Registry) -> str:
    """Canonical text: fixed key order, one entry member per line with nested values compact, ASCII only.

    Equivalent to ``json.dumps`` of :meth:`Registry.to_document` but keeps every entry at one line per member,
    so a 400-entry registry stays reviewable and a change to one entry is a local diff.
    """
    document = registry.to_document()
    lines = ["{"]
    for key in _DOCUMENT_KEYS[:-1]:
        lines.append(f"  {_compact(key)}: {_compact(document[key])},")
    entries = document["entries"]
    if not entries:
        lines.append('  "entries": []')
    else:
        lines.append('  "entries": [')
        for index, entry in enumerate(entries):
            lines.append("    {")
            members = list(entry.items())
            for position, (name, value) in enumerate(members):
                comma = "," if position < len(members) - 1 else ""
                lines.append(f"      {_compact(name)}: {_compact(value)}{comma}")
            lines.append("    }" + ("," if index < len(entries) - 1 else ""))
        lines.append("  ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def write_registry(path: Path, registry: Registry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(registry), encoding="utf-8")


def record(
    path: Path,
    scans: Sequence[tuple[UnknownReport, str | None]],
    *,
    format: str = DEFAULT_FORMAT,
    today: date,
) -> RegistryUpdate:
    """Load the registry at ``path`` (or start one), merge every scanned save, prune, stamp and write it back.

    Raises ``RegistryError`` when the file cannot be read, is not a registry, belongs to another format, or
    cannot be written.
    """
    try:
        before = load_or_empty(path, format)
    except OSError as error:
        raise RegistryError(f"cannot read registry: {error.strerror or error}") from error
    if before.format != format:
        raise RegistryError(f"registry format {before.format!r} does not match the scanned format {format!r}")
    after = before
    for report, game_version in scans:
        after = merge(after, report, game_version=game_version, today=today)
    after, _pruned = prune_known(after)
    after = Registry(after.format, today, after.entries)
    changes = delta(before, after)
    try:
        write_registry(path, after)
    except OSError as error:
        raise RegistryError(f"cannot write registry: {error.strerror or error}") from error
    update = RegistryUpdate(len(changes.added), len(changes.updated), len(changes.pruned), len(after.entries))
    logger.debug(
        "registry updated %s",
        log_fields(
            registry=safe_path(path),
            saves=len(scans),
            added=update.added,
            updated=update.updated,
            pruned=update.pruned,
            total=update.total,
        ),
    )
    return update
