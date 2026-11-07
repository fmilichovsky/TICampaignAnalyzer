"""Ordered save sequences: the per-interval pipeline run over every pair of consecutive saves (architecture 15).

Saves are ordered by serialized game time only, never by file name or modification time
(``docs/game-data-notes/chronology-and-deduplication.md``); byte-identical saves are merged. Consecutive intervals
share their boundary snapshot, so every change is reported in exactly one interval, and event IDs are qualified by
the interval key to stay unique. Rules see one interval: evidence straddling a boundary is not combined.
"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from collections.abc import Callable, Generator, Iterable, Iterator, Sequence
from concurrent.futures import Future
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .analyzers import ALL_ANALYZERS, FIRST_INTERVAL_ANALYZERS, run_analyzers
from .config import DEFAULT_SETTINGS, SignificanceSettings
from .diff import diff_states
from .io.save_loader import load_raw_save, load_save
from .log import TIMING_LOGGER, fields, get_logger, safe_path
from .model.changes import StateChange, StateDiff
from .model.events import Event
from .model.snapshot import SaveSnapshot
from .narrative import NARRATIVE_RULES, NarrativeRule, SituationReport, aggregate, assign_significance, build_situation
from .narrative.chronology import TIE_SEPARATOR, chronological, interval_keys, qualify
from .narrative.situation import SPACEPORTS
from .parsing.continuity import CampaignProfile
from .parsing.errors import SaveLoadError
from .parsing.normalization import normalize
from .parsing.survey import survey_metadata
from .reconstruction import infer_events
from .workers import memory_line, pool, tick

logger = get_logger(__name__)
timing = get_logger(TIMING_LOGGER)

MIN_CHUNK_INTERVALS = 2
"""A worker's chunk has at least this many intervals, because each chunk normalizes its boundary save once more."""


class UnknownChronologyError(SaveLoadError):
    """A save has no parseable ``TITimeState.currentDateTime``, so its place in a sequence is unknown."""


@dataclass(frozen=True)
class SaveRef:
    """One distinct snapshot of a sequence, with the paths of its byte-identical aliases."""

    source: str
    sha256: str
    timestamp: datetime
    aliases: tuple[str, ...] = ()
    profile: CampaignProfile | None = None
    """The campaign continuity signals; not part of ``to_dict`` (the campaign group reports them)."""

    @property
    def date(self) -> str:
        return self.timestamp.isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "aliases": list(self.aliases), "sha256": self.sha256, "date": self.date}


@dataclass(frozen=True)
class SkippedSave:
    """A file found inside a given directory that could not be used: its path and why, never its content."""

    source: str
    error_class: str
    error: str

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "error_class": self.error_class, "error": self.error}


@dataclass(frozen=True)
class SequencePlan:
    """The distinct saves in chronological order, each with its key, and the number of paths given.

    A key is the save's game time, followed by ``#n`` for the n-th (n >= 2) distinct save with the same time; the
    first keeps the bare time, so the key of a save does not change when saves are added around it.
    """

    saves: tuple[SaveRef, ...]
    keys: tuple[str, ...]
    inputs: int
    skipped: tuple[SkippedSave, ...] = ()
    """Files found inside given directories that were skipped; they are not counted in ``inputs``."""

    @property
    def duplicates(self) -> int:
        """Paths merged into another save's ``SaveRef`` because their bytes are identical."""
        return self.inputs - len(self.saves)

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputs": self.inputs,
            "duplicates": self.duplicates,
            "skipped": [skipped.to_dict() for skipped in self.skipped],
            "saves": [{"key": key, **save.to_dict()} for key, save in zip(self.keys, self.saves, strict=True)],
        }


@dataclass(frozen=True)
class IntervalAnalysis:
    """What the pipeline derives from one pair of snapshots; ``inferred`` is ``None`` when it was not requested."""

    diff: StateDiff
    objective: tuple[Event, ...]
    inferred: tuple[Event, ...] | None
    seconds: dict[str, float] = field(default_factory=dict, compare=False)
    """Wall time per stage (``diff``, ``analyzers``, ``reconstruction``, ``significance``), for the timing log."""


@dataclass(frozen=True)
class IntervalResult:
    """The events of one interval of a sequence, qualified by its key.

    The snapshots are not kept; their situation reports are, and consecutive intervals share the boundary save's
    report. The diff's changes are kept in ``state_changes`` only when they were requested (``None`` otherwise),
    because a long sequence would hold every interval's evidence values.
    """

    index: int
    key: str
    before: SaveRef
    after: SaveRef
    changes: int
    objective: tuple[Event, ...]
    inferred: tuple[Event, ...] | None
    state_changes: tuple[StateChange, ...] | None = None
    before_situation: SituationReport | None = None
    after_situation: SituationReport | None = None
    """The situation reports of ``before`` and ``after``; not part of ``to_dict`` (the saves carry them)."""

    def events(self) -> tuple[Event, ...]:
        return self.objective + (self.inferred or ())

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "key": self.key,
            "before": self.before.source,
            "after": self.after.source,
            "not_before": self.before.date,
            "date": self.after.date,
            "changes": self.changes,
            "events": [event.to_dict() for event in self.objective],
            "inferred": None if self.inferred is None else [event.to_dict() for event in self.inferred],
            "state_changes": None
            if self.state_changes is None
            else [change.to_dict() for change in self.state_changes],
        }


def analyze_interval(
    before: SaveSnapshot,
    after: SaveSnapshot,
    *,
    inferred: bool,
    first: bool = False,
    significance: SignificanceSettings = DEFAULT_SETTINGS.narrative.significance,
) -> IntervalAnalysis:
    """Diff two snapshots, run every analyzer and, when asked, reconstruction; every event gets its significance.

    ``first`` marks the first interval of a sequence, which also runs ``FIRST_INTERVAL_ANALYZERS``.
    """
    clock = time.perf_counter()
    seconds = dict.fromkeys(("diff", "analyzers", "reconstruction", "significance"), 0.0)

    def lap(stage: str) -> None:
        nonlocal clock
        now = time.perf_counter()
        seconds[stage] += now - clock
        clock = now

    diff = diff_states(before, after)
    lap("diff")
    analyzers = ALL_ANALYZERS + FIRST_INTERVAL_ANALYZERS if first else ALL_ANALYZERS
    found = run_analyzers(analyzers, before, after, diff)
    lap("analyzers")
    objective = assign_significance(found, before, after, significance)
    lap("significance")
    reconstructed = None
    if inferred:
        events = infer_events(objective, before, after, diff)
        lap("reconstruction")
        reconstructed = assign_significance(events, before, after, significance, evidence=objective)
        lap("significance")
    return IntervalAnalysis(diff, objective, reconstructed, seconds)


def survey(path: Path) -> SaveRef:
    """Hash a save and read its game time and campaign profile; ``OSError`` for the path, ``SaveLoadError`` for the
    content."""
    started = time.perf_counter()
    data = load_save(path)
    timestamp, profile = survey_metadata(data, source=str(path))
    if timestamp is None:
        raise UnknownChronologyError("no parseable TITimeState.currentDateTime; the save cannot be ordered")
    surveyed = SaveRef(
        source=str(path),
        sha256=hashlib.sha256(data).hexdigest(),
        timestamp=timestamp,
        profile=profile,
    )
    timing.info("survey %s", fields(seconds=_seconds(started)))
    return surveyed


@dataclass(frozen=True)
class SurveyFailure:
    """Why one path could not be surveyed: unreadable (``content`` false) or not a usable save."""

    source: str
    content: bool
    error_class: str
    reason: str


def survey_outcome(path: Path) -> SaveRef | SurveyFailure:
    """``survey``, with a read or content failure returned instead of raised, so a worker can hand it back."""
    try:
        return survey(path)
    except OSError as error:
        logger.debug("read failed %s", fields(save=safe_path(path), errno=error.errno, error=type(error).__name__))
        return SurveyFailure(str(path), False, type(error).__name__, error.strerror or str(error))
    except SaveLoadError as error:
        logger.debug("survey failed %s", fields(save=safe_path(path), error=type(error).__name__), exc_info=True)
        return SurveyFailure(str(path), True, type(error).__name__, str(error))


def survey_all(
    paths: Sequence[Path], *, jobs: int = 1, on_save: Callable[[Path], None] | None = None
) -> Generator[SaveRef | SurveyFailure, None, None]:
    """The survey outcome of every path, in order; ``on_save`` follows each survey.

    With one job each path is surveyed when its outcome is asked for, so a consumer that stops early stops the work.
    """
    if jobs <= 1 or len(paths) < 2:
        for path in paths:
            outcome = survey_outcome(path)
            if on_save is not None:
                on_save(path)
            yield outcome
        return
    with pool(min(jobs, len(paths))) as executor:
        futures = [executor.submit(survey_outcome, path) for path in paths]
        if on_save is not None:
            for path, future in zip(paths, futures, strict=True):
                future.add_done_callback(_reporter(on_save, path))
        for future in futures:
            yield future.result()


def _reporter(on_save: Callable[[Path], None], path: Path) -> Callable[[Future[SaveRef | SurveyFailure]], None]:
    return lambda _: on_save(path)


def _seconds(started: float) -> float:
    return round(time.perf_counter() - started, 4)


def merge_identical(saves: Iterable[SaveRef]) -> list[SaveRef]:
    """Merge byte-identical saves (the first path in sort order is the source) and sort by game time, then path."""
    by_hash: dict[str, list[SaveRef]] = defaultdict(list)
    for save in saves:
        by_hash[save.sha256].append(save)
    distinct: list[SaveRef] = []
    for group in by_hash.values():
        paths = sorted({path for save in group for path in (save.source, *save.aliases)})
        distinct.append(SaveRef(paths[0], group[0].sha256, group[0].timestamp, tuple(paths[1:]), group[0].profile))
    distinct.sort(key=lambda save: (save.timestamp, save.source))
    return distinct


def plan_sequence(saves: Iterable[SaveRef], skipped: Iterable[SkippedSave] = ()) -> SequencePlan:
    """Merge byte-identical saves (see ``merge_identical``) and key each distinct save by its game time."""
    surveyed = list(saves)
    distinct = merge_identical(surveyed)
    keys = interval_keys([save.date for save in distinct])
    plan = SequencePlan(tuple(distinct), tuple(keys), len(surveyed), tuple(skipped))
    logger.info(
        "sequence planned %s",
        fields(
            inputs=plan.inputs,
            saves=len(plan.saves),
            duplicates=plan.duplicates,
            skipped=len(plan.skipped),
            tied=sum(TIE_SEPARATOR in key for key in plan.keys),
            intervals=max(len(plan.saves) - 1, 0),
        ),
    )
    return plan


def load_snapshot(source: str) -> SaveSnapshot:
    return normalize(load_raw_save(Path(source)))


@dataclass(frozen=True)
class _Options:
    inferred: bool
    changes: bool
    spaceports: int
    load: Callable[[str], SaveSnapshot]
    significance: SignificanceSettings = DEFAULT_SETTINGS.narrative.significance


@dataclass(frozen=True)
class _Chunk:
    """Consecutive saves of a plan, the first of which is save ``start``: the work of one worker."""

    start: int
    saves: tuple[SaveRef, ...]
    keys: tuple[str, ...]
    options: _Options


def run_sequence(
    plan: SequencePlan,
    *,
    inferred: bool,
    changes: bool = False,
    load: Callable[[str], SaveSnapshot] = load_snapshot,
    spaceports: int = SPACEPORTS,
    significance: SignificanceSettings = DEFAULT_SETTINGS.narrative.significance,
    jobs: int = 1,
    on_save: Callable[[], None] | None = None,
) -> Iterator[IntervalResult]:
    """The results of every interval in order; each save is normalized once and at most two are held at a time.

    With ``changes`` every result also keeps its literal state changes. With ``jobs`` above one the intervals are cut
    into contiguous chunks run by worker processes (``load`` must then be picklable); each chunk normalizes its first
    save once more, and the results are the same. ``on_save`` is called once per save of the plan.
    """
    if len(plan.saves) < 2:
        return
    options = _Options(inferred, changes, spaceports, load, significance)
    chunks = [
        _Chunk(start, plan.saves[start : end + 1], plan.keys[start : end + 1], options)
        for start, end in _chunks(len(plan.saves) - 1, jobs)
    ]
    if len(chunks) == 1:
        yield from _interval_results(chunks[0], on_save)
        return
    logger.info("sequence parallel %s", fields(workers=len(chunks)))
    with pool(len(chunks), on_save, tasks_per_child=1) as executor:  # one chunk per process: its memory line is its own
        futures: list[Future[list[IntervalResult]]] = [executor.submit(_run_chunk, chunk) for chunk in chunks]
        for future in futures:
            yield from future.result()


def _chunks(intervals: int, jobs: int) -> list[tuple[int, int]]:
    """Contiguous, near-equal ranges of saves (first and last index) covering ``intervals`` intervals once."""
    count = max(1, min(jobs, intervals // MIN_CHUNK_INTERVALS))
    size, extra = divmod(intervals, count)
    ranges: list[tuple[int, int]] = []
    start = 0
    for chunk in range(count):
        end = start + size + (chunk < extra)
        ranges.append((start, end))
        start = end
    return ranges


def _run_chunk(chunk: _Chunk) -> list[IntervalResult]:
    """A worker's chunk; the snapshots stay in the worker, only the results go back."""
    results = list(_interval_results(chunk, tick))
    memory_line()
    return results


def _interval_results(chunk: _Chunk, on_save: Callable[[], None] | None) -> Iterator[IntervalResult]:
    """The intervals of one chunk; the first save of a later chunk is not reported to ``on_save`` again."""
    options = chunk.options

    def prepared(offset: int) -> tuple[SaveSnapshot, SituationReport]:
        if on_save is not None and (offset > 0 or chunk.start == 0):
            on_save()
        index = chunk.start + offset
        started = time.perf_counter()
        snapshot = options.load(chunk.saves[offset].source)
        loaded = time.perf_counter()
        situation = build_situation(snapshot, spaceports=options.spaceports)
        timing.info("save %s", fields(index=index, load=round(loaded - started, 4), situation=_seconds(loaded)))
        return snapshot, situation

    before, before_situation = prepared(0)
    for offset in range(1, len(chunk.saves)):
        index = chunk.start + offset
        after, after_situation = prepared(offset)
        analysis = analyze_interval(
            before, after, inferred=options.inferred, first=index == 1, significance=options.significance
        )
        timing.info(
            "interval %s",
            fields(index=index - 1, **{stage: round(value, 4) for stage, value in analysis.seconds.items()}),
        )
        key = chunk.keys[offset]
        result = IntervalResult(
            index=index - 1,
            key=key,
            before=chunk.saves[offset - 1],
            after=chunk.saves[offset],
            changes=len(analysis.diff.changes),
            objective=tuple(qualify(event, key) for event in analysis.objective),
            inferred=None if analysis.inferred is None else tuple(qualify(event, key) for event in analysis.inferred),
            state_changes=analysis.diff.changes if options.changes else None,
            before_situation=before_situation,
            after_situation=after_situation,
        )
        logger.info(
            "interval done %s",
            fields(
                interval=result.index,
                changes=result.changes,
                events=len(result.objective),
                inferred=None if result.inferred is None else len(result.inferred),
            ),
        )
        del analysis  # its diff holds both snapshots; the next load must find only ``after`` alive
        yield result
        before, before_situation = after, after_situation


def event_stream(intervals: Iterable[IntervalResult]) -> list[Event]:
    """Every event of every interval in one chronological stream; IDs are unique because they are qualified."""
    return chronological(event for interval in intervals for event in interval.events())


def situations(intervals: Iterable[IntervalResult]) -> tuple[SituationReport, ...]:
    """One situation report per save of the sequence, in its order; empty when no interval ran."""
    reports: list[SituationReport] = []
    for interval in intervals:
        if not reports and interval.before_situation is not None:
            reports.append(interval.before_situation)
        if interval.after_situation is not None:
            reports.append(interval.after_situation)
    return tuple(reports)


def narrative_events(
    intervals: Sequence[IntervalResult], rules: Sequence[NarrativeRule] = NARRATIVE_RULES
) -> list[Event]:
    """The narrative events the rules build over the stream and situation reports (``narrative.aggregate``)."""
    return aggregate(event_stream(intervals), situations(intervals), rules)
