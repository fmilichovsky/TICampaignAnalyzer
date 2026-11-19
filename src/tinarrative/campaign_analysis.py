"""Campaign analysis: save inputs to an analysed campaign in three steps (survey, choice, analysis).

Each step returns a failure value; the module never prints, prompts or picks an exit code."""

from __future__ import annotations

import os
from collections.abc import Sequence
from contextlib import closing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from .config import Settings
from .grouping import CampaignGroup, select_campaign
from .io.save_discovery import SaveInput
from .io.save_loader import load_raw_save
from .log import fields, get_logger, safe_path
from .model.events import Event
from .model.snapshot import SaveSnapshot
from .narrative import narrative_rules
from .parsing.errors import SaveLoadError
from .parsing.normalization import normalize
from .sequence import (
    IntervalResult,
    SaveRef,
    SequencePlan,
    SkippedSave,
    SurveyFailure,
    narrative_events,
    plan_sequence,
    run_sequence,
    survey_all,
)
from .workers import default_jobs, memory_line

logger = get_logger(__name__)


class ProgressReporter(Protocol):
    """What the analysis reports to while it works; the command line supplies a terminal tracker."""

    def update(self, phase: str, completed: int, total: int | None = None, filename: str | None = None) -> None: ...

    def finish(self, activity: str = "parsing and processing") -> None: ...


@dataclass(frozen=True)
class UnreadableInput:
    """A named path could not be read."""

    source: str
    reason: str

    @property
    def message(self) -> str:
        return f"cannot read {self.source}: {self.reason}"


@dataclass(frozen=True)
class UnsupportedSave:
    """A named file was read but is not a supported save."""

    source: str
    reason: str

    @property
    def message(self) -> str:
        return f"{self.source}: {self.reason}"


@dataclass(frozen=True)
class EmptyDirectory:
    """A named directory holds no files."""

    directory: str

    @property
    def message(self) -> str:
        return f"{self.directory}: the directory holds no files"


@dataclass(frozen=True)
class NoUsableSave:
    """A named directory holds files, but none is a usable save."""

    directory: str

    @property
    def message(self) -> str:
        return f"{self.directory}: the directory holds no usable save"


SurveyFailed = UnreadableInput | UnsupportedSave | EmptyDirectory | NoUsableSave
"""Every way the survey can fail."""


@dataclass(frozen=True)
class Survey:
    """The usable saves of the inputs, and the files skipped inside given directories."""

    saves: list[SaveRef]
    skipped: list[SkippedSave]


def resolve_jobs(requested: int | None, settings: Settings, sources: Sequence[str | Path]) -> int:
    """``--jobs`` wins over ``processing.jobs``; neither gives the default for these files' sizes."""
    if requested is not None:
        return requested
    if settings.processing.jobs is not None:
        return settings.processing.jobs
    sizes: list[int] = []
    for source in sources:
        try:
            sizes.append(os.stat(source).st_size)
        except OSError:
            continue  # the survey reports it
    return default_jobs(sizes)


def survey_inputs(
    inputs: Sequence[SaveInput],
    settings: Settings,
    *,
    command: str,
    jobs: int | None = None,
    progress: ProgressReporter | None = None,
) -> Survey | SurveyFailed:
    """Survey every input; only a path the user named can fail (the first failure in input order is returned, so it
    is the same whatever ``jobs`` is). There is no minimum count of saves. ``command`` labels the log lines."""
    paths = [item.path for item in inputs if not item.empty_directory]
    workers = resolve_jobs(jobs, settings, paths)
    logger.debug("%s survey jobs %s", command, fields(jobs=workers))
    surveyed: list[SaveRef] = []
    skipped: list[SkippedSave] = []
    usable: dict[Path, int] = {}
    done = 0

    def on_save(path: Path) -> None:
        nonlocal done
        done += 1
        if progress is not None:
            progress.update("Scanning saves", done, filename=path.name)

    with closing(survey_all(paths, jobs=workers, on_save=on_save)) as outcomes:
        for item in inputs:
            if item.empty_directory:
                return EmptyDirectory(str(item.path))
            found = next(outcomes)
            if item.directory is None:
                if isinstance(found, SurveyFailure):
                    return _named_failure(found)
                surveyed.append(found)
                continue
            usable.setdefault(item.directory, 0)
            if isinstance(found, SurveyFailure):
                logger.debug("%s skipped %s", command, fields(save=safe_path(item.path), error=found.error_class))
                skipped.append(SkippedSave(str(item.path), found.error_class, found.reason))
            else:
                surveyed.append(found)
                usable[item.directory] += 1
    for directory, count in usable.items():
        if count == 0:
            return NoUsableSave(str(directory))
    return Survey(surveyed, skipped)


def _named_failure(failure: SurveyFailure) -> UnreadableInput | UnsupportedSave:
    if failure.content:
        return UnsupportedSave(failure.source, failure.reason)
    return UnreadableInput(failure.source, failure.reason)


@dataclass(frozen=True)
class CampaignNotChosen:
    """No single campaign was selected; ``reason`` says why."""

    reason: str

    @property
    def message(self) -> str:
        return self.reason


def file_time(path: str) -> float:
    """A file's modification time for the ``latest`` selector; an unreadable file counts as oldest."""
    try:
        return os.stat(path).st_mtime
    except OSError:
        return float("-inf")


def choose_campaign(groups: Sequence[CampaignGroup], selector: str | None = None) -> CampaignGroup | CampaignNotChosen:
    """The campaign to analyze: the only one when there is no selector, else the one the selector names. Several
    campaigns without a selector, or a selector that matches none, is ``CampaignNotChosen``.

    The choice sits outside the analysis because it may need a person; this never prompts, so the command line
    decides whether to open a picker."""
    if selector is None:
        if len(groups) == 1:
            return groups[0]
        return CampaignNotChosen(f"the input holds {len(groups)} campaigns; choose one with --campaign")
    selected = select_campaign(groups, selector, file_time)
    if isinstance(selected, CampaignGroup):
        logger.info("campaign selected %s", fields(index=selected.index, of=len(groups)))
        return selected
    return CampaignNotChosen(selected)


class Depth(Enum):
    """How far the analysis goes; each depth includes the one before it."""

    OBJECTIVE = "objective"
    INFERRED = "inferred"
    NARRATIVE = "narrative"


@dataclass(frozen=True)
class LoadFailed:
    """A save of the chosen campaign could not be loaded while its intervals were analyzed."""

    cause: UnreadableInput | UnsupportedSave

    @property
    def message(self) -> str:
        return self.cause.message


class _LoadError(Exception):
    """Carries a load failure out of a worker process; picklable, and turned into a ``LoadFailed`` value."""

    def __init__(self, cause: UnreadableInput | UnsupportedSave) -> None:
        super().__init__(cause)
        self.cause = cause


@dataclass(frozen=True)
class _SnapshotLoader:
    """Load and normalize one save; picklable, so a worker process can run it."""

    command: str

    def __call__(self, source: str) -> SaveSnapshot:
        save_path = Path(source)
        save_name = safe_path(save_path)
        try:
            return normalize(load_raw_save(save_path))
        except OSError as error:
            reason = error.strerror or str(error)
            logger.debug(
                "%s read failed %s", self.command, fields(save=save_name, errno=error.errno, error=type(error).__name__)
            )
            raise _LoadError(UnreadableInput(str(save_path), reason)) from None
        except SaveLoadError as error:
            logger.debug(
                "%s parse failed %s", self.command, fields(save=save_name, error=type(error).__name__), exc_info=True
            )
            raise _LoadError(UnsupportedSave(str(save_path), str(error))) from None


@dataclass(frozen=True)
class CampaignAnalysis:
    """The analyzed campaign: what ``events`` reports and ``narrate`` packages."""

    plan: SequencePlan
    intervals: list[IntervalResult]
    campaign: CampaignGroup
    narrative: list[Event] | None
    """The narrative events, at ``Depth.NARRATIVE`` only."""


def analyze_campaign(
    campaign: CampaignGroup,
    settings: Settings,
    *,
    command: str,
    depth: Depth = Depth.OBJECTIVE,
    state_changes: bool = False,
    skipped: Sequence[SkippedSave] = (),
    jobs: int | None = None,
    progress: ProgressReporter | None = None,
) -> CampaignAnalysis | LoadFailed:
    """Plan the campaign's sequence and analyze its intervals in order; with ``state_changes`` every interval keeps
    its literal state changes. ``skipped`` are the survey's skipped saves, which the plan records. ``jobs`` is the
    ``--jobs`` flag (see ``resolve_jobs``)."""
    plan = plan_sequence(campaign.members, skipped)
    workers = resolve_jobs(jobs, settings, [save.source for save in plan.saves])
    logger.debug("%s jobs %s", command, fields(intervals=workers))
    if progress is not None:
        progress.update("Processing saves", 0, len(plan.saves))
    loaded = 0

    def on_save() -> None:
        nonlocal loaded
        loaded += 1
        if progress is not None:
            progress.update("Processing saves", loaded, len(plan.saves))

    try:
        intervals = list(
            run_sequence(
                plan,
                inferred=depth is not Depth.OBJECTIVE,
                changes=state_changes,
                load=_SnapshotLoader(command),
                narrative=settings.narrative,
                jobs=workers,
                on_save=on_save,
            )
        )
    except _LoadError as failure:
        return LoadFailed(failure.cause)
    events = (
        narrative_events(intervals, narrative_rules(settings.narrative), settings.narrative.significance)
        if depth is Depth.NARRATIVE
        else None
    )
    memory_line()
    return CampaignAnalysis(plan, intervals, campaign, events)
