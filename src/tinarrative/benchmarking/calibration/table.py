"""The per-event calibration table of the sample campaigns, written as ``file://``-loadable ``.js`` files."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from tinarrative.benchmarking.manifest import decompress_samples, extractable_campaigns
from tinarrative.config import DEFAULT_SETTINGS
from tinarrative.kinds.describe import describe_event
from tinarrative.kinds.registry import kind_for
from tinarrative.model.events import SCORE_BANDS, SIGNIFICANCE_ORDER, Event, Significance
from tinarrative.narrative import NARRATIVE_RULES, default_member_gates, rule_layers
from tinarrative.narrative.chronology import interval_of
from tinarrative.narrative.measures import MEASURES, SCALE_MAX, SCALE_MIN
from tinarrative.narrative.significance import narrative_level
from tinarrative.sequence import (
    SaveRef,
    SurveyFailure,
    narrative_events,
    plan_sequence,
    run_sequence,
    survey_all,
)

SCHEMA_VERSION: Final = 2
CAMPAIGN_PREFIX: Final = 'window.TI_CALIBRATION.campaigns["'
INDEX_PREFIX: Final = "window.TI_CALIBRATION.index = "
STATUS_PREFIX: Final = "window.TI_CALIBRATION.status = "
SUFFIX: Final = ";"
SCORE_MIN: Final = 0
SCORE_MAX: Final = 100
NEIGHBOURS: Final = 5
"""Events the calibration page lists on each side of a cut-off."""
PACKAGE_LEVEL: Final = Significance.MAJOR.value
"""The lowest level of a narrative event the narrator package carries."""


class CalibrationTableError(ValueError):
    """A calibration table file that does not follow the wrapper contract, or a campaign that cannot be extracted."""


def extract_campaign(saves: Sequence[Path]) -> list[dict[str, Any]]:
    """One row per finished event of a campaign, from a separate in-process run at code defaults."""
    outcomes = list(survey_all(list(saves)))
    failures = [outcome for outcome in outcomes if isinstance(outcome, SurveyFailure)]
    if failures:
        raise CalibrationTableError(f"cannot survey {len(failures)} save(s): {failures[0]}")
    refs = [outcome for outcome in outcomes if isinstance(outcome, SaveRef)]
    plan = plan_sequence(refs)
    intervals = list(run_sequence(plan, inferred=True))
    rows = [_row(event, "atomic") for interval in intervals for event in interval.objective]
    rows.extend(_row(event, "reconstructed") for interval in intervals for event in interval.inferred or ())
    rows.extend(_row(event, "narrative") for event in narrative_events(intervals))
    return rows


def _row(event: Event, tier: str) -> dict[str, Any]:
    basis = event.significance_basis
    narrative = tier == "narrative"
    return {
        "id": event.id,
        "type": event.event_type,
        "tier": tier,
        "interval": event.intervals[0] if narrative else interval_of(event.id),
        "date": event.date if isinstance(event.date, str) else None,
        "label": describe_event(event, plain=True),
        "base": basis.base if basis is not None else _own_base(event, narrative),
        "rule": None if event.context_rule is None else event.context_rule.value,
        "stakes": [{"measure": basis.measure.value, "share": basis.share}] if basis is not None else [],
        "entities": [{"id": str(ref.entity_id), "name": ref.name or None} for ref in event.entities],
        "cited": list(event.constituents) if narrative else [],
        "score": event.score,
        "level": event.significance.value,
    }


def _own_base(event: Event, narrative: bool) -> int:
    """The base of a row without a basis; a narrative event's level may have been raised by the events it cites."""
    if not narrative:
        return event.significance.base
    kind = kind_for(event.event_type)
    if kind is None:
        raise CalibrationTableError(f"event type {event.event_type} is declared by no kind")
    return narrative_level(kind, event, DEFAULT_SETTINGS.narrative.geopolitics).base


def layers() -> dict[str, int]:
    """The layer of each narrative event type of the default rule set; atomic and reconstructed rows are layer 0."""
    exclusive = frozenset(
        event_type
        for rule in NARRATIVE_RULES
        for event_type in rule.emitted_types
        if (kind := kind_for(event_type)) is not None and kind.exclusive_constituents
    )
    return {
        event_type: number
        for number, layer in enumerate(rule_layers(NARRATIVE_RULES, exclusive), start=1)
        for rule in layer
        for event_type in sorted(rule.emitted_types)
    }


def type_kinds(types: Iterable[str]) -> dict[str, dict[str, Any]]:
    """The ``kinds`` map of the index: each distinct type's code base level and context rule (``None`` for none),
    sorted by type; ``CalibrationTableError`` for a type no kind declares."""
    kinds: dict[str, dict[str, Any]] = {}
    for event_type in sorted(set(types)):
        kind = kind_for(event_type)
        if kind is None:
            raise CalibrationTableError(f"event type {event_type} is declared by no kind")
        kinds[event_type] = {"base": kind.base.value, "rule": None if kind.rule is None else kind.rule.value}
    return kinds


def build_index(
    campaigns: Sequence[str], *, key: str, extracted_at: str, kinds: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """The ``index.js`` document: what the rows cannot say about themselves, from the registry and the rules.

    ``kinds`` is the ``type_kinds`` map of the types the campaigns' rows hold.
    """
    rules = {rule.name: rule for rule in NARRATIVE_RULES}
    return {
        "schema_version": SCHEMA_VERSION,
        "campaigns": list(campaigns),
        "key": key,
        "extracted_at": extracted_at,
        "layers": layers(),
        "member_gates": [
            {
                "rule": name,
                "group_types": sorted(rules[name].emitted_types),
                "member_type": gate.member_type,
                "admitted_levels": [level.value for level in SIGNIFICANCE_ORDER if level in gate.admitted_levels],
                "minimum": gate.minimum,
            }
            for name, gate in sorted(default_member_gates().items())
        ],
        "constants": {
            "level_bands": {level.value: list(SCORE_BANDS[level]) for level in SIGNIFICANCE_ORDER},
            "scale_min": SCALE_MIN,
            "scale_max": SCALE_MAX,
            "score_min": SCORE_MIN,
            "score_max": SCORE_MAX,
            "neighbours": NEIGHBOURS,
            "package_level": PACKAGE_LEVEL,
        },
        "measures": {
            measure.value: {"reference": spec.reference, "label": spec.label, "description": spec.description}
            for measure, spec in MEASURES.items()
        },
        "kinds": {event_type: dict(kind) for event_type, kind in kinds.items()},
        "drafts": [],
    }


def write_campaign(directory: Path, name: str, rows: Sequence[dict[str, Any]]) -> Path:
    """Write ``tables/<name>.js`` under ``directory``: JSON in the one-line wrapper."""
    path = directory / "tables" / f"{name}.js"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {"events": list(rows), "drafts": []}
    path.write_text(f'{CAMPAIGN_PREFIX}{name}"] = {_dumps(document)}{SUFFIX}\n', encoding="utf-8")
    return path


def read_campaign(path: Path) -> dict[str, Any]:
    """The document of a campaign file, by stripping the wrapper; ``CalibrationTableError`` for any other shape."""
    text = path.read_text(encoding="utf-8").rstrip("\n")
    name = path.stem
    prefix = f'{CAMPAIGN_PREFIX}{name}"] = '
    return _unwrap(text, prefix, path)


def write_index(directory: Path, index: dict[str, Any]) -> Path:
    path = directory / "index.js"
    path.write_text(f"{INDEX_PREFIX}{_dumps(index)}{SUFFIX}\n", encoding="utf-8")
    return path


def read_index(path: Path) -> dict[str, Any]:
    return _unwrap(path.read_text(encoding="utf-8").rstrip("\n"), INDEX_PREFIX, path)


def write_status(directory: Path, status: dict[str, Any]) -> Path:
    """Write ``status.js`` under ``directory``, in place: the page polls it and tolerates a torn read."""
    path = directory / "status.js"
    path.write_text(f"{STATUS_PREFIX}{_dumps(status)}{SUFFIX}\n", encoding="utf-8")
    return path


def read_status(path: Path) -> dict[str, Any]:
    return _unwrap(path.read_text(encoding="utf-8").rstrip("\n"), STATUS_PREFIX, path)


def extract_all(samples: Path, directory: Path, *, key: str, now: datetime | None = None) -> list[str]:
    """Extract every campaign that is not a ``prefix_of`` another into ``directory``; the campaigns extracted."""
    stamp = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    names: list[str] = []
    types: set[str] = set()
    for name, files in extractable_campaigns(samples).items():
        with tempfile.TemporaryDirectory(prefix="calibration-") as scratch:
            decompress_samples(files, Path(scratch))
            rows = extract_campaign(sorted(Path(scratch).iterdir()))
        write_campaign(directory, name, rows)
        names.append(name)
        types.update(row["type"] for row in rows)
    write_index(directory, build_index(names, key=key, extracted_at=stamp, kinds=type_kinds(types)))
    return names


def _dumps(document: Any) -> str:
    return json.dumps(document, ensure_ascii=True, separators=(",", ":"))


def _unwrap(text: str, prefix: str, path: Path) -> dict[str, Any]:
    if not text.startswith(prefix) or not text.endswith(SUFFIX) or "\n" in text:
        raise CalibrationTableError(f"{path.name}: not a calibration wrapper (expected `{prefix.strip()}{{...}};`)")
    try:
        document = json.loads(text[len(prefix) : -len(SUFFIX)])
    except json.JSONDecodeError as error:
        raise CalibrationTableError(f"{path.name}: the wrapped document is not valid JSON: {error}") from error
    if not isinstance(document, dict):
        raise CalibrationTableError(f"{path.name}: the wrapped document is not an object")
    return document
