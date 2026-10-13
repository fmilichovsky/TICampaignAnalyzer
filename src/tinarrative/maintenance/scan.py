"""Scan one or more saves for unknown structures and merge what they report."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from ..io.save_discovery import discover_saves
from ..io.save_loader import load_raw_save
from ..log import fields as log_fields
from ..log import get_logger, safe_path
from ..parsing.errors import SaveLoadError
from ..parsing.normalization import normalize
from ..parsing.unknowns import UnknownCollector, UnknownFinding, UnknownReport

logger = get_logger(__name__)

EMPTY_DIRECTORY = "EmptyDirectory"
"""``ScanResult.error_class`` for an explicit directory that holds no files."""


@dataclass(frozen=True)
class ScanInput:
    """One candidate file: given on the command line (``explicit``) or found inside a given directory."""

    path: Path
    explicit: bool
    empty_directory: bool = False


@dataclass(frozen=True)
class ScanResult:
    """What scanning one input produced: a report, or why it was skipped."""

    path: Path
    explicit: bool
    report: UnknownReport | None = None
    game_version: str | None = None
    error: str | None = None
    error_class: str | None = None
    input_error: bool = False
    """The input could not be read at all (as opposed to being readable but not a supported save)."""

    @property
    def scanned(self) -> bool:
        return self.report is not None


@dataclass(frozen=True)
class MergedFinding:
    """A finding summed over the scanned saves, with the number of saves it appeared in."""

    finding: UnknownFinding
    saves: int


def merge_reports(reports: Iterable[UnknownReport]) -> tuple[MergedFinding, ...]:
    """Union the findings of several saves by key: occurrences add up, shapes merge, saves are counted."""
    merged: dict[tuple[str, str, str, str], MergedFinding] = {}
    for report in reports:
        for finding in report.findings:
            current = merged.get(finding.key)
            if current is None:
                merged[finding.key] = MergedFinding(finding, 1)
                continue
            previous = current.finding
            if previous.shape is None or finding.shape is None:
                shape = previous.shape if finding.shape is None else finding.shape
            else:
                shape = previous.shape.merge(finding.shape)
            merged[finding.key] = MergedFinding(
                UnknownFinding(
                    kind=finding.kind,
                    state_type=finding.state_type,
                    field=finding.field,
                    detail=finding.detail,
                    occurrences=previous.occurrences + finding.occurrences,
                    shape=shape,
                ),
                current.saves + 1,
            )
    return tuple(merged[key] for key in sorted(merged))


@dataclass(frozen=True)
class ScanRun:
    results: tuple[ScanResult, ...]
    findings: tuple[MergedFinding, ...] = field(init=False)

    def __post_init__(self) -> None:
        reports = [result.report for result in self.results if result.report is not None]
        object.__setattr__(self, "findings", merge_reports(reports))

    @property
    def scanned(self) -> tuple[ScanResult, ...]:
        return tuple(result for result in self.results if result.scanned)

    def scans(self) -> list[tuple[UnknownReport, str | None]]:
        """``(report, game_version)`` per scanned save, in input order, for the registry."""
        return [(result.report, result.game_version) for result in self.results if result.report is not None]


def expand_inputs(paths: Sequence[Path]) -> tuple[ScanInput, ...]:
    """Files stay as given; a directory contributes its files in ``discover_saves`` order, one level deep."""
    inputs: list[ScanInput] = []
    for path in paths:
        if path.is_dir():
            try:
                files = discover_saves(path)
            except OSError:
                inputs.append(ScanInput(path, explicit=True))
                continue
            if not files:
                inputs.append(ScanInput(path, explicit=True, empty_directory=True))
            inputs.extend(ScanInput(file, explicit=False) for file in files)
        else:
            inputs.append(ScanInput(path, explicit=True))
    return tuple(inputs)


def scan_save(path: Path) -> tuple[UnknownReport, str | None]:
    """Normalize one save with a collector and return its findings and serialized game version."""
    raw = load_raw_save(path)
    collector = UnknownCollector()
    normalize(raw, collector=collector)
    return collector.report(), raw.game_version


def scan_inputs(inputs: Sequence[ScanInput]) -> ScanRun:
    """Scan every input, recording per-file failures instead of stopping."""
    results: list[ScanResult] = []
    for item in inputs:
        name = safe_path(item.path)
        if item.empty_directory:
            results.append(
                ScanResult(
                    item.path,
                    item.explicit,
                    error="the directory holds no files",
                    error_class=EMPTY_DIRECTORY,
                    input_error=True,
                )
            )
            logger.info("unknowns skipped %s", log_fields(save=name, error=EMPTY_DIRECTORY))
            continue
        try:
            report, game_version = scan_save(item.path)
        except OSError as error:
            results.append(
                ScanResult(
                    item.path,
                    item.explicit,
                    error=error.strerror or str(error),
                    error_class=type(error).__name__,
                    input_error=True,
                )
            )
            logger.info("unknowns skipped %s", log_fields(save=name, error=type(error).__name__))
            continue
        except SaveLoadError as error:
            results.append(ScanResult(item.path, item.explicit, error=str(error), error_class=type(error).__name__))
            logger.info("unknowns skipped %s", log_fields(save=name, error=type(error).__name__))
            continue
        results.append(ScanResult(item.path, item.explicit, report=report, game_version=game_version))
        logger.info("unknowns scanned %s", log_fields(save=name, findings=report.total))
    return ScanRun(tuple(results))
