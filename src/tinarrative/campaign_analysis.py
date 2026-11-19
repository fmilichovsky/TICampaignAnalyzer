"""Campaign analysis: the survey of save inputs into surveyed and skipped saves, or a returned failure.

It never prints and never picks an exit code; the command line maps each failure to its code and prefix."""

from __future__ import annotations

import os
from collections.abc import Sequence
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import Settings
from .io.save_discovery import SaveInput
from .log import fields, get_logger, safe_path
from .sequence import SaveRef, SkippedSave, SurveyFailure, survey_all
from .workers import default_jobs

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
