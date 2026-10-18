"""Ordered save sequences: the per-interval pipeline run over every pair of consecutive saves (architecture 15, Mode B).

The saves are assumed to belong to one campaign; nothing here groups them. Ordering follows
``docs/game-data-notes/chronology-and-deduplication.md``:

1. ``survey`` reads each save once for its SHA-256 and serialized game time (``TITimeState``); a save without one has
   unknown chronology and is rejected, never placed by its file name or modification time.
2. ``plan_sequence`` merges byte-identical saves into one ``SaveRef`` (every path kept as provenance) and sorts the
   rest by game time, then path. Equal times with different bytes are both kept. Argument order never matters.
3. ``run_sequence`` normalizes the saves in that order, holding two snapshots at a time, and runs
   ``analyze_interval`` (diff, analyzers, significance and, when asked, reconstruction) on each consecutive pair.

Consecutive intervals share their boundary snapshot, so every change is reported in exactly one interval and a
save-carried log entry once. The events of an interval are qualified by its key (``narrative.chronology``) so that
IDs stay unique across the sequence. Rules still see one interval: evidence that straddles a boundary is not
combined (that is narrative aggregation).
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .analyzers import ALL_ANALYZERS, run_analyzers
from .diff import diff_states
from .io.save_loader import load_raw_save, load_save
from .log import fields, get_logger
from .model.changes import StateChange, StateDiff
from .model.events import Event
from .model.snapshot import SaveSnapshot
from .narrative import assign_significance
from .narrative.chronology import chronological, qualify
from .parsing.errors import SaveLoadError
from .parsing.normalization import normalize, save_timestamp
from .parsing.raw_save import parse_raw_save
from .reconstruction import infer_events

logger = get_logger(__name__)

TIE_SEPARATOR = "#"
"""Joins a game time and the position of a save among distinct saves with the same time (``...T00:00:00#2``)."""


class UnknownChronologyError(SaveLoadError):
    """A save has no parseable ``TITimeState.currentDateTime``, so its place in a sequence is unknown."""


@dataclass(frozen=True)
class SaveRef:
    """One distinct snapshot of a sequence: its path, its byte-identical aliases, its hash and its game time."""

    source: str
    sha256: str
    timestamp: datetime
    aliases: tuple[str, ...] = ()

    @property
    def date(self) -> str:
        return self.timestamp.isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "aliases": list(self.aliases), "sha256": self.sha256, "date": self.date}


@dataclass(frozen=True)
class SequencePlan:
    """The distinct saves in chronological order, each with its key, and the number of paths given.

    A key is the save's game time, followed by ``#n`` for the n-th (n >= 2) distinct save with the same time; the
    first keeps the bare time, so the key of a save does not change when saves are added around it.
    """

    saves: tuple[SaveRef, ...]
    keys: tuple[str, ...]
    inputs: int

    @property
    def duplicates(self) -> int:
        """Paths merged into another save's ``SaveRef`` because their bytes are identical."""
        return self.inputs - len(self.saves)

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputs": self.inputs,
            "duplicates": self.duplicates,
            "saves": [{"key": key, **save.to_dict()} for key, save in zip(self.keys, self.saves, strict=True)],
        }


@dataclass(frozen=True)
class IntervalAnalysis:
    """What the pipeline derives from one pair of snapshots; ``inferred`` is ``None`` when it was not requested."""

    diff: StateDiff
    objective: tuple[Event, ...]
    inferred: tuple[Event, ...] | None


@dataclass(frozen=True)
class IntervalResult:
    """The events of one interval of a sequence, qualified by its key.

    The snapshots are not kept. The diff's changes are kept in ``state_changes`` only when they were requested
    (``None`` otherwise), because a long sequence would hold every interval's evidence values.
    """

    index: int
    key: str
    before: SaveRef
    after: SaveRef
    changes: int
    objective: tuple[Event, ...]
    inferred: tuple[Event, ...] | None
    state_changes: tuple[StateChange, ...] | None = None

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


def analyze_interval(before: SaveSnapshot, after: SaveSnapshot, *, inferred: bool) -> IntervalAnalysis:
    """Diff two snapshots, run every analyzer and, when asked, reconstruction; every event gets its significance."""
    diff = diff_states(before, after)
    objective = assign_significance(run_analyzers(ALL_ANALYZERS, before, after, diff), before, after)
    reconstructed = (
        assign_significance(infer_events(objective, before, after, diff), before, after) if inferred else None
    )
    return IntervalAnalysis(diff, objective, reconstructed)


def survey(path: Path) -> SaveRef:
    """Hash a save and read its game time; ``OSError`` for the path, ``SaveLoadError`` for the content."""
    data = load_save(path)
    raw = parse_raw_save(data, source=str(path))
    timestamp = save_timestamp(raw)
    if timestamp is None:
        raise UnknownChronologyError("no parseable TITimeState.currentDateTime; the save cannot be ordered")
    return SaveRef(source=str(path), sha256=hashlib.sha256(data).hexdigest(), timestamp=timestamp)


def plan_sequence(saves: Iterable[SaveRef]) -> SequencePlan:
    """Merge byte-identical saves (the first path in sort order is the source) and sort by game time, then path."""
    surveyed = list(saves)
    by_hash: dict[str, list[SaveRef]] = defaultdict(list)
    for save in surveyed:
        by_hash[save.sha256].append(save)
    distinct: list[SaveRef] = []
    for group in by_hash.values():
        paths = sorted({save.source for save in group})
        distinct.append(SaveRef(paths[0], group[0].sha256, group[0].timestamp, tuple(paths[1:])))
    distinct.sort(key=lambda save: (save.timestamp, save.source))
    keys: list[str] = []
    for position, save in enumerate(distinct):
        tied = sum(1 for earlier in distinct[:position] if earlier.timestamp == save.timestamp)
        keys.append(save.date if tied == 0 else f"{save.date}{TIE_SEPARATOR}{tied + 1}")
    plan = SequencePlan(tuple(distinct), tuple(keys), len(surveyed))
    logger.info(
        "sequence planned %s",
        fields(
            inputs=plan.inputs,
            saves=len(plan.saves),
            duplicates=plan.duplicates,
            tied=sum(TIE_SEPARATOR in key for key in plan.keys),
            intervals=max(len(plan.saves) - 1, 0),
        ),
    )
    return plan


def load_snapshot(source: str) -> SaveSnapshot:
    return normalize(load_raw_save(Path(source)))


def run_sequence(
    plan: SequencePlan,
    *,
    inferred: bool,
    changes: bool = False,
    load: Callable[[str], SaveSnapshot] = load_snapshot,
) -> Iterator[IntervalResult]:
    """The results of every interval in order; each save is normalized once and at most two are held at a time.

    With ``changes`` every result also keeps its literal state changes.
    """
    if len(plan.saves) < 2:
        return
    before = load(plan.saves[0].source)
    for index in range(1, len(plan.saves)):
        after = load(plan.saves[index].source)
        analysis = analyze_interval(before, after, inferred=inferred)
        key = plan.keys[index]
        result = IntervalResult(
            index=index - 1,
            key=key,
            before=plan.saves[index - 1],
            after=plan.saves[index],
            changes=len(analysis.diff.changes),
            objective=tuple(qualify(event, key) for event in analysis.objective),
            inferred=None if analysis.inferred is None else tuple(qualify(event, key) for event in analysis.inferred),
            state_changes=analysis.diff.changes if changes else None,
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
        yield result
        before = after


def event_stream(intervals: Iterable[IntervalResult]) -> list[Event]:
    """Every event of every interval in one chronological stream; IDs are unique because they are qualified."""
    return chronological(event for interval in intervals for event in interval.events())
