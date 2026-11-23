"""The per-event calibration table of the sample campaigns, written as ``.js`` files the page loads as scripts."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from tinarrative.benchmarking.calibration import drafts as draft_shares
from tinarrative.benchmarking.calibration.drafts import (
    DraftShare,
    draft_base,
    draft_row_id,
    draft_scalings,
    validate_drafts,
)
from tinarrative.benchmarking.calibration.progress import CampaignProgress, ExtractionProgress, ProgressSnapshot
from tinarrative.benchmarking.manifest import decompress_samples, extractable_campaigns, raw_sizes
from tinarrative.kinds.describe import describe_event
from tinarrative.kinds.registry import kind_for
from tinarrative.model.entities import EntityId
from tinarrative.model.events import (
    SCORE_BANDS,
    SCORE_MAX,
    SCORE_MIN,
    SIGNIFICANCE_ORDER,
    Event,
    Role,
    Significance,
)
from tinarrative.narrative import NARRATIVE_RULES, default_member_gates, rule_layers
from tinarrative.narrative.aggregation import interval_shares
from tinarrative.narrative.chronology import interval_of
from tinarrative.narrative.geopolitics import TERRITORY_GAINED, readings
from tinarrative.narrative.measures import MEASURES
from tinarrative.narrative.nation_metrics import BAND_CROSSED, band_explainers, explainer_of
from tinarrative.narrative.scalings import DEFAULT_WIDTH, SCALINGS, ScalingSpec
from tinarrative.narrative.significance import IntervalShares, decide, score_event
from tinarrative.narrative.situation import SituationReport
from tinarrative.sequence import (
    IntervalResult,
    SaveRef,
    SurveyFailure,
    narrative_events,
    plan_sequence,
    run_sequence,
    save_shares,
    situations,
    survey_all,
)

SCHEMA_VERSION: Final = 6
CAMPAIGN_PREFIX: Final = 'window.TI_CALIBRATION.campaigns["'
INDEX_PREFIX: Final = "window.TI_CALIBRATION.index = "
STATUS_PREFIX: Final = "window.TI_CALIBRATION.status = "
SUFFIX: Final = ";"
NEIGHBOURS: Final = 5
"""Events the calibration page lists on each side of a cut-off."""
PACKAGE_LEVEL: Final = Significance.MAJOR.value
"""The lowest level of a narrative event the narrator package carries."""


class CalibrationTableError(ValueError):
    """A calibration table file that does not follow the wrapper contract, or a campaign that cannot be extracted."""


def declared_drafts(drafts: Sequence[DraftShare] | None = None) -> tuple[DraftShare, ...]:
    """``drafts``, else the declared ``DRAFT_SHARES``, validated (``DraftShareError``)."""
    chosen = tuple(draft_shares.DRAFT_SHARES if drafts is None else drafts)
    validate_drafts(chosen)
    return chosen


def extract_campaign(
    saves: Sequence[Path], drafts: Sequence[DraftShare] | None = None, progress: CampaignProgress | None = None
) -> dict[str, Any]:
    """The campaign document from a separate in-process run at code defaults: one row per finished event, one
    shadow row per draft share and event of its types (``drafts``, by default the declared ones), and the
    ``names`` of the entities that were renamed (``name_history``). ``progress`` is told each phase and each save
    a phase finishes."""
    chosen = declared_drafts(drafts)
    paths = list(saves)
    if progress is not None:
        progress.phase("survey")
    outcomes: list[SaveRef | SurveyFailure] = []
    for path, outcome in zip(paths, survey_all(paths), strict=True):
        outcomes.append(outcome)
        if progress is not None:
            progress.saves_done([path.name])
    failures = [outcome for outcome in outcomes if isinstance(outcome, SurveyFailure)]
    if failures:
        raise CalibrationTableError(f"cannot survey {len(failures)} save(s): {failures[0]}")
    refs = [outcome for outcome in outcomes if isinstance(outcome, SaveRef)]
    plan = plan_sequence(refs)
    if progress is not None:
        progress.phase("sequence")
    intervals: list[IntervalResult] = []
    for interval in run_sequence(plan, inferred=True):
        intervals.append(interval)
        if progress is not None:
            # The first interval finishes the first two saves; each later one finishes its second save.
            finished = plan.saves[:2] if len(intervals) == 1 else plan.saves[len(intervals) : len(intervals) + 1]
            progress.saves_done(Path(path).name for save in finished for path in (save.source, *save.aliases))
    if progress is not None:
        progress.phase("narrative")
    narrative = narrative_events(intervals)
    dates = {interval.key: (interval.before.date, interval.after.date) for interval in intervals}
    explainers = explained_by((event for interval in intervals for event in interval.objective), narrative)
    rows = [_row(event, "atomic", dates, explainers) for interval in intervals for event in interval.objective]
    rows.extend(
        _row(event, "reconstructed", dates, explainers) for interval in intervals for event in interval.inferred or ()
    )
    rows.extend(_row(event, "narrative", dates, explainers) for event in narrative)
    by_id = {event.id: event for interval in intervals for event in interval.events()}
    by_id.update((event.id, event) for event in narrative)
    shares = interval_shares(situations(intervals), save_shares(intervals))
    shadows = [
        _draft_row(draft, event, by_id, shares, dates)
        for draft in chosen
        for event in narrative
        if event.event_type in draft.event_types
    ]
    return {"events": rows, "drafts": shadows, "names": name_history(situations(intervals))}


def _draft_row(
    draft: DraftShare,
    event: Event,
    by_id: Mapping[str, Event],
    shares: Mapping[str, IntervalShares],
    dates: Mapping[str, tuple[str, str]],
) -> dict[str, Any]:
    """The event scored by the draft's candidates, each as the pipeline would score it; the score is the highest
    of the candidates with a share, as the replay takes it."""
    kind = kind_for(event.event_type)
    if kind is None:
        raise CalibrationTableError(f"event type {event.event_type} is declared by no kind")
    cited = [by_id[item] for item in event.constituents]
    first, last = shares.get(event.intervals[0]), shares.get(event.intervals[-1])
    base = draft_base(draft)
    scalings = draft_scalings(draft)
    results = [
        score_event(
            kind,
            event,
            cited,
            reading=reading,
            scaling=scalings[reading.measure][1],
            base=base,
            shares=first,
            last=last,
        )
        for reading in draft.readings
    ]
    scored = [result for result in results if result.basis is not None]
    score = max(result.score for result in scored) if scored else results[0].score
    return {
        **_row(event, "narrative", dates, {}),
        "id": draft_row_id(draft.name, event.id),
        "base": results[0].level.base,
        "shares": [
            {"measure": result.basis.measure.value, "share": result.basis.share}
            for result in scored
            if result.basis is not None
        ],
        "score": score,
        "rule": None if results[0].rule is None else results[0].rule.value,
        "level": Significance.of(score).value,
        "ruled": results[0].ruled,
    }


def explained_by(atomic: Iterable[Event], narrative: Sequence[Event]) -> dict[str, str]:
    """The ID of the narrative event that explains each atomic event the narrative rules leave out for it, by the
    rules' own tests: a band crossing is explained by a shift covering its nation and interval, a territory gain by
    a reading of its nation and interval."""
    covering = readings(narrative)
    found: dict[str, str] = {}
    for event in atomic:
        if not event.entities:
            continue
        nation = event.entities[0].entity_id
        if event.event_type == TERRITORY_GAINED:
            reading = covering.get((nation, interval_of(event.id)))
            if reading is not None:
                found[event.id] = reading.id
        elif event.event_type == BAND_CROSSED:
            statistic = event.attribute("statistic")
            explainers = [
                item
                for item in narrative
                if isinstance(statistic, str) and item.event_type in band_explainers(statistic)
            ]
            explainer = explainer_of(event, nation, explainers)
            if explainer is not None:
                found[event.id] = explainer.id
    return found


def _row(
    event: Event,
    tier: str,
    dates: Mapping[str, tuple[str, str]] | None = None,
    explainers: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """One row of a campaign file. Beside the id, type, tier, scores and citations, it carries:

    - ``entities[].role`` and ``targets``: a narrative event's role for each entity (``actor``, ``target``, ...) and
      its number of target entities; both ``None`` for an atomic or reconstructed event, which has no roles;
    - ``explained_by``: the ID of the narrative event that explains the event without citing it, ``None`` for an
      event nothing explains (the rules' own tests, see ``explained_by`` above);
    - ``intervals``: the key, start and end date (the dates of its two saves) of each interval the event spans.

    A renamed entity's names are in the index (``name_history``), not repeated in the rows.
    """
    basis = event.significance_basis
    narrative = tier == "narrative"
    roles = _roles(event) if narrative else {}
    dates, explainers = dates or {}, explainers or {}
    return {
        "id": event.id,
        "type": event.event_type,
        "tier": tier,
        "interval": event.intervals[0] if narrative else interval_of(event.id),
        "date": event.date if isinstance(event.date, str) else None,
        "label": describe_event(event, plain=True),
        "base": basis.base if basis is not None else _own_base(event, narrative),
        "rule": None if event.context_rule is None else event.context_rule.value,
        "shares": [{"measure": basis.measure.value, "share": basis.share}] if basis is not None else [],
        "entities": [
            {"id": str(ref.entity_id), "name": ref.name or None, "role": roles.get(ref.entity_id)}
            for ref in event.entities
        ],
        "targets": sum(1 for role in roles.values() if role == Role.TARGET.value) if narrative else None,
        "explained_by": explainers.get(event.id),
        "intervals": [
            {"key": key, "start": dates[key][0], "end": dates[key][1]}
            for key in (event.intervals if narrative else (interval_of(event.id),))
            if key in dates
        ],
        "cited": list(event.constituents) if narrative else [],
        "score": event.score,
        "level": event.significance.value,
    }


def _roles(event: Event) -> dict[EntityId, str]:
    """The role of each entity of a narrative event, the highest ranking one where it holds several."""
    found: dict[EntityId, Role] = {}
    for role, ref in event.roles:
        if ref.entity_id not in found or role.rank < found[ref.entity_id].rank:
            found[ref.entity_id] = role
    return {entity: role.value for entity, role in found.items()}


def name_history(reports: Sequence[SituationReport]) -> dict[str, list[dict[str, str]]]:
    """Every name each renamed entity held, in order, with the first and last save date showing it; an entity that
    kept one name is not listed, as a row's own entity names resolve it."""
    held: dict[str, list[dict[str, str]]] = {}
    for report in reports:
        if not isinstance(report.date, str):
            continue
        refs = (
            *(item.nation for item in report.nations),
            *(item.federation for item in report.federations),
            *(item.war for item in report.wars),
            *(item.faction for item in report.factions),
        )
        for ref in refs:
            if not ref.name:
                continue
            names = held.setdefault(str(ref.entity_id), [])
            if names and names[-1]["name"] == ref.name:
                names[-1]["last"] = report.date
            else:
                names.append({"name": ref.name, "first": report.date, "last": report.date})
    return {entity: names for entity, names in sorted(held.items()) if len({item["name"] for item in names}) > 1}


def _own_base(event: Event, narrative: bool) -> int:
    """The base of a row without a basis; a narrative event's level may have been raised by the events it cites."""
    if not narrative:
        return event.significance.base
    kind = kind_for(event.event_type)
    if kind is None:
        raise CalibrationTableError(f"event type {event.event_type} is declared by no kind")
    return decide(kind, event)[0].base


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
    """The ``kinds`` map of the index: each distinct type's code base level, context rule and scaling (``None`` for
    none), sorted by type; ``CalibrationTableError`` for a type no kind declares."""
    kinds: dict[str, dict[str, Any]] = {}
    for event_type in sorted(set(types)):
        kind = kind_for(event_type)
        if kind is None:
            raise CalibrationTableError(f"event type {event_type} is declared by no kind")
        kinds[event_type] = {
            "base": kind.base.value,
            "rule": None if kind.rule is None else kind.rule.value,
            "scaling": None if kind.scaling is None else kind.scaling.value,
        }
    return kinds


def build_index(
    campaigns: Sequence[str],
    *,
    key: str,
    extracted_at: str,
    kinds: Mapping[str, Mapping[str, Any]],
    drafts: Sequence[DraftShare] | None = None,
    names: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """The ``index.js`` document: what the rows cannot say about themselves, from the registry, the rules and the
    draft shares (``drafts``, by default the declared ones).

    ``kinds`` is the ``type_kinds`` map of the types the campaigns' rows hold; ``names`` is each campaign's
    ``name_history``. ``scalings`` holds every declared scaling, then each draft's own, in draft order.
    """
    chosen = declared_drafts(drafts)
    scalings = {scaling.value: _scaling(spec) for scaling, spec in SCALINGS.items()}
    for draft in chosen:
        scalings.update((name, _scaling(spec)) for name, spec in draft_scalings(draft).values() if name not in scalings)
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
            "default_width": DEFAULT_WIDTH,
            "score_min": SCORE_MIN,
            "score_max": SCORE_MAX,
            "neighbours": NEIGHBOURS,
            "package_level": PACKAGE_LEVEL,
        },
        "measures": {
            measure.value: {"label": spec.label, "description": spec.description} for measure, spec in MEASURES.items()
        },
        "scalings": scalings,
        "kinds": {event_type: dict(kind) for event_type, kind in kinds.items()},
        "names": {campaign: dict(history) for campaign, history in (names or {}).items()},
        "drafts": [
            {
                "name": draft.name,
                "label": draft.label,
                "issue": draft.issue,
                "base": draft_base(draft).value,
                "measures": list(dict.fromkeys(reading.measure.value for reading in draft.readings)),
                "scalings": {measure.value: name for measure, (name, _) in draft_scalings(draft).items()},
            }
            for draft in chosen
        ],
    }


def _scaling(spec: ScalingSpec) -> dict[str, Any]:
    return {"measure": spec.measure.value, "rise": spec.rise, "drop": spec.drop, "reason": spec.reason}


def write_campaign(directory: Path, name: str, document: Mapping[str, Any]) -> Path:
    """Write ``tables/<name>.js`` under ``directory``: the campaign document (``events``, ``drafts``) as JSON in the
    one-line wrapper."""
    path = directory / "tables" / f"{name}.js"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {"events": list(document["events"]), "drafts": list(document["drafts"])}
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


def extract_all(
    samples: Path,
    directory: Path,
    *,
    key: str,
    now: datetime | None = None,
    on_progress: Callable[[ProgressSnapshot], None] | None = None,
) -> list[str]:
    """Extract every campaign that is not a ``prefix_of`` another into ``directory``; the campaigns extracted.

    ``on_progress`` is called with the extraction's progress after every change, from the extracting thread.
    """
    stamp = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    chosen = declared_drafts()
    names: list[str] = []
    types: set[str] = set()
    histories: dict[str, Mapping[str, Any]] = {}
    campaigns = extractable_campaigns(samples)
    progress = ExtractionProgress(
        {name: raw_sizes(samples, name, files) for name, files in campaigns.items()}, on_change=on_progress
    )
    for name, files in campaigns.items():
        campaign = progress.campaign(name)
        with tempfile.TemporaryDirectory(prefix="calibration-") as scratch:
            campaign.phase("decompress")
            decompress_samples(files, Path(scratch))
            document = extract_campaign(sorted(Path(scratch).iterdir()), chosen, campaign)
        write_campaign(directory, name, document)
        campaign.phase("done")
        names.append(name)
        histories[name] = document["names"]
        types.update(row["type"] for row in document["events"])
    write_index(
        directory,
        build_index(names, key=key, extracted_at=stamp, kinds=type_kinds(types), drafts=chosen, names=histories),
    )
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
