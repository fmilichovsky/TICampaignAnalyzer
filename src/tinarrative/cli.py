"""Command-line entry point for the analyzer."""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import threading
import time
import webbrowser
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, TypeAlias, assert_never, cast

from . import __version__
from .benchmarking import metrics as benchmark_metrics
from .benchmarking import runtime as benchmark_runtime
from .benchmarking.calibration import cache as calibration_cache
from .benchmarking.calibration import readout as calibration_readout
from .benchmarking.calibration import replay as calibration_replay
from .benchmarking.calibration import server as calibration_server
from .benchmarking.calibration.table import CalibrationTableError
from .benchmarking.manifest import MANIFEST, sample_files, sha256_file, update_samples, verify_samples
from .benchmarking.samples import SampleImportError, import_sample_campaign
from .campaign_analysis import (
    CampaignAnalysis,
    Depth,
    EmptyDirectory,
    LoadFailed,
    NoUsableSave,
    Survey,
    SurveyFailed,
    UnreadableInput,
    UnsupportedSave,
    analyze_campaign,
    choose_campaign,
    file_time,
    survey_inputs,
)
from .config import (
    CONFIG_ENV_VAR,
    DEFAULT_SETTINGS,
    PROVIDERS,
    ConfigError,
    NarratorSettings,
    Settings,
    load_settings,
    override,
)
from .diff import diff_states
from .diff import render_json as render_diff_json
from .diff import render_text as render_diff_text
from .grouping import CampaignGroup, group_saves, listing_document, render_listing
from .host import Host
from .inspection import RenderLimits, inspect_bytes, render_json, render_text
from .io.save_discovery import SaveInput, expand_inputs
from .io.save_loader import load_raw_save, load_save
from .log import DEFAULT_LEVEL, ENV_VAR, LEVELS, TIMING_ENV_VAR, configure_logging, fields, get_logger, safe_path
from .maintenance import REGISTRY_ENV_VAR
from .maintenance.registry import RegistryError, RegistryUpdate, record
from .maintenance.render import render_json as render_unknowns_json
from .maintenance.render import render_text as render_unknowns_text
from .maintenance.scan import ScanRun, scan_inputs
from .model.entities import EntityDomain, EntityId
from .model.events import SIGNIFICANCE_ORDER, Significance
from .model.records import record_counts
from .model.snapshot import NORMALIZED_COLLECTION_LABELS, SaveSnapshot
from .model.values import Observed, to_jsonable
from .narrative import build_dossier
from .narrator.assembly import Assembly
from .narrator.chapters import ChapterPlan, OverBudget, base_options, plan_chapters, validate
from .narrator.councilors import article_requests, missing
from .narrator.providers import Endpoint, endpoint
from .narrator.request import AUDIENCES, CITATIONS, STYLES
from .narrator.run_directory import RunDirectory, RunDirectoryWriteError
from .narrator.runs import (
    HistoryReadError,
    RunReporter,
    assemble_history,
    chapter_items,
    narrate_history,
    write_articles,
)
from .narrator.send_run import SendItem, SendOutcome
from .parsing.continuity import CampaignProfile
from .parsing.errors import SaveLoadError
from .parsing.normalization import normalize
from .parsing.unknowns import UnknownCollector
from .picker import pick_campaign
from .rendering.json_report import build_document
from .rendering.listing import CONSTITUENTS, Constituents
from .rendering.markdown import PERIODS, Period, render_sequence
from .sequence import (
    event_stream,
)

logger = get_logger(__name__)

EXIT_SUCCESS = 0
EXIT_USAGE_ERROR = 2
EXIT_INPUT_ERROR = 4
"""The save path could not be read (missing, unreadable, or a directory)."""
EXIT_UNSUPPORTED_INPUT = 5
"""Bytes were read but are not decodable JSON (``save inspect``) or not a supported save (``save parse``)."""
EXIT_PATH_NOT_FOUND = 6
"""At least one ``--path`` did not resolve; the full report is still printed."""
EXIT_REGISTRY_ERROR = 7
"""The unknowns registry could not be read, parsed or written; the report is still printed."""
EXIT_CONFIG_ERROR = 8
"""The settings file could not be read or is not valid settings; nothing is printed on stdout."""
EXIT_OUTPUT_ERROR = 9
"""``--output`` could not be written."""
EXIT_PROVIDER_ERROR = 10
"""``--send``: a request failed, hit the output limit or was refused. ``narrate`` stops at the first failed chapter
and keeps the earlier ones; ``councilors`` skips the failed articles and reports at the end."""

ExitCodes = tuple[tuple[int, str], ...]
_USAGE: ExitCodes = ((EXIT_USAGE_ERROR, "usage error."),)
_SAVE_INPUT: ExitCodes = (
    (EXIT_INPUT_ERROR, "a named path cannot be read, or a named directory holds no usable save."),
    (EXIT_UNSUPPORTED_INPUT, "a named file is not a supported save or has no game time."),
)
_CONFIG: ExitCodes = ((EXIT_CONFIG_ERROR, "the settings file cannot be read or is not valid settings."),)
EXIT_CODES: dict[str, ExitCodes] = {
    "campaigns": ((EXIT_SUCCESS, "the listing was printed."), *_USAGE, *_SAVE_INPUT),
    "events": (
        (EXIT_SUCCESS, "the report was printed, or every --output file was written."),
        (
            EXIT_USAGE_ERROR,
            "usage error, no campaign chosen, or --output with --min-significance or --constituents.",
        ),
        *_SAVE_INPUT,
        *_CONFIG,
        (EXIT_OUTPUT_ERROR, "an --output file cannot be written; the files before it are kept."),
    ),
    "narrate": (
        (EXIT_SUCCESS, "the plan was printed; with --send, the history was assembled."),
        (
            EXIT_USAGE_ERROR,
            "usage error, no campaign chosen, the package holds no interval (one save), a single interval over "
            "llm.max_input_tokens, or --send without --output, a provider, a model or an API key.",
        ),
        (EXIT_INPUT_ERROR, "a save, the --package file or the --assemble directory cannot be read."),
        (
            EXIT_UNSUPPORTED_INPUT,
            "a save is not a supported save, the package is not a narrator package, or a run directory does not "
            "match its plan.",
        ),
        *_CONFIG,
        (EXIT_OUTPUT_ERROR, "--output cannot be written."),
        (
            EXIT_PROVIDER_ERROR,
            "a chapter request failed, or its completion was cut off, refused or empty; earlier chapters are kept.",
        ),
    ),
    "councilors": (
        (EXIT_SUCCESS, "the summary was printed; with --send, every article was written."),
        (
            EXIT_USAGE_ERROR,
            "usage error, no campaign chosen, or --send without --output, a provider, a model or an API key.",
        ),
        (EXIT_INPUT_ERROR, "a save cannot be read."),
        (EXIT_UNSUPPORTED_INPUT, "a save is not a supported save."),
        *_CONFIG,
        (EXIT_OUTPUT_ERROR, "--output cannot be written."),
        (
            EXIT_PROVIDER_ERROR,
            "an article request failed, or its completion was cut off, refused or empty; the other articles are "
            "written.",
        ),
    ),
    "save inspect": (
        (EXIT_SUCCESS, "the report was printed."),
        (EXIT_USAGE_ERROR, "usage error, including a negative limit."),
        (EXIT_INPUT_ERROR, "the save cannot be read."),
        (EXIT_UNSUPPORTED_INPUT, "the bytes are not decodable JSON; file facts and diagnostics are still printed."),
        (EXIT_PATH_NOT_FOUND, "a --path did not resolve; the report is still printed. 5 wins over 6."),
    ),
    "save parse": (
        (EXIT_SUCCESS, "the save was loaded."),
        (EXIT_USAGE_ERROR, "usage error, including --record-unknowns without a registry."),
        (EXIT_INPUT_ERROR, "the save cannot be read."),
        (EXIT_UNSUPPORTED_INPUT, "the file is not a supported save."),
        (EXIT_REGISTRY_ERROR, "the registry cannot be read, is invalid or cannot be written; the summary is printed."),
    ),
    "save diff": (
        (EXIT_SUCCESS, "both saves were compared."),
        *_USAGE,
        (EXIT_INPUT_ERROR, "a save cannot be read."),
        (EXIT_UNSUPPORTED_INPUT, "a save is not a supported save."),
    ),
    "unknowns": (
        (EXIT_SUCCESS, "every named path was scanned; findings are not failures."),
        *_USAGE,
        (EXIT_INPUT_ERROR, "a named path cannot be read, or a named directory holds no files."),
        (EXIT_UNSUPPORTED_INPUT, "a named file is not a supported save."),
        (
            EXIT_REGISTRY_ERROR,
            "the registry cannot be read, is invalid or cannot be written; the report is printed. 7 wins over 4 and 5.",
        ),
    ),
    "benchmark sample": (
        (EXIT_SUCCESS, f"the sample and {MANIFEST} were updated."),
        (EXIT_USAGE_ERROR, "usage error, or a campaign selector that cannot be resolved without a terminal."),
        *_SAVE_INPUT,
        (EXIT_OUTPUT_ERROR, f"the sample directory or {MANIFEST} cannot be written."),
    ),
    "benchmark metrics samples": (
        (EXIT_SUCCESS, f"every sample matches {MANIFEST}."),
        (EXIT_USAGE_ERROR, f"usage error, or a sample does not match {MANIFEST}."),
        (EXIT_OUTPUT_ERROR, f"the samples or {MANIFEST} cannot be read or written."),
    ),
    "benchmark metrics measure": (
        (EXIT_SUCCESS, "metrics.json was written; failed runs are recorded in it."),
        (
            EXIT_USAGE_ERROR,
            f"usage error, a sample that does not match {MANIFEST}, an invalid matrix or an unknown --campaign.",
        ),
        (EXIT_OUTPUT_ERROR, "the outputs cannot be written."),
    ),
    "benchmark metrics merge": (
        (EXIT_SUCCESS, "the merged metrics.json was written."),
        (EXIT_USAGE_ERROR, "usage error, metrics files that differ in their metadata, or a campaign in two of them."),
        (EXIT_INPUT_ERROR, "a metrics file cannot be read or is not a metrics file."),
        (EXIT_OUTPUT_ERROR, "the merged file cannot be written."),
    ),
    "benchmark metrics compare": (
        (EXIT_SUCCESS, "the report was written."),
        *_USAGE,
        (EXIT_INPUT_ERROR, "a metrics file cannot be read or is not a metrics file, or the report cannot be written."),
    ),
    "benchmark runtime measure": (
        (EXIT_SUCCESS, "the runtime JSON was written; failed runs are recorded in it."),
        (EXIT_USAGE_ERROR, f"usage error, a sample that does not match {MANIFEST}, or a --run the matrix lacks."),
        (EXIT_INPUT_ERROR, "--samples is not a directory."),
        (EXIT_OUTPUT_ERROR, "the runtime JSON cannot be written."),
    ),
    "benchmark calibrate report": (
        (EXIT_SUCCESS, "the readout was printed."),
        (
            EXIT_USAGE_ERROR,
            f"usage error, a sample that does not match {MANIFEST}, an unknown measure, campaign or type, a base "
            "level that is not a level, an invalid --state, a measure or switched type given twice, a table at "
            "another schema version (run with --rebuild), or a failed extraction (status.js says failed; the old "
            "table stays).",
        ),
        (EXIT_INPUT_ERROR, f"--samples is not a directory or its {MANIFEST} cannot be read."),
        (EXIT_OUTPUT_ERROR, "--out cannot be written."),
    ),
    "benchmark calibrate open": (
        (
            EXIT_SUCCESS,
            "the page was served with a current table until interrupted; a browser that cannot be opened only warns.",
        ),
        (
            EXIT_USAGE_ERROR,
            f"usage error, a sample that does not match {MANIFEST}, or a failed extraction (status.js says failed). "
            "With no old table the command stops at once; an old table is served until interrupted.",
        ),
        (EXIT_INPUT_ERROR, f"--samples is not a directory or its {MANIFEST} cannot be read."),
        (EXIT_OUTPUT_ERROR, "--out cannot be written, or the port cannot be served on."),
    ),
    "benchmark runtime merge": (
        (EXIT_SUCCESS, "the merged runtime JSON was written."),
        (EXIT_USAGE_ERROR, "usage error, runtime files that differ in their metadata, or a campaign in two of them."),
        (EXIT_INPUT_ERROR, f"a runtime file cannot be read or is not a runtime file, or --samples has no {MANIFEST}."),
        (EXIT_OUTPUT_ERROR, "the merged file cannot be written."),
    ),
    "benchmark runtime report": (
        (EXIT_SUCCESS, "the report was written."),
        *_USAGE,
        (
            EXIT_INPUT_ERROR,
            "the runtime JSON cannot be read or is not a runtime file, or the report cannot be written.",
        ),
    ),
}
"""Each leaf command's exit codes and when they occur; ``--help`` and the command pages are rendered from these."""

NARRATE_MIN_SIGNIFICANCE = Significance.MAJOR
NARRATE_CONSTITUENTS: Constituents = "evidence"
EVENTS_MIN_SIGNIFICANCE = Significance.TRIVIAL
EVENTS_CONSTITUENTS: Constituents = "none"
SIGNIFICANCE_LEVELS = tuple(level.value for level in SIGNIFICANCE_ORDER)
BENCHMARK_ROOT = Path("benchmarks")
BENCHMARK_SAMPLES_DIR = BENCHMARK_ROOT / "samples"
CALIBRATION_OUT_DIR = Path("build") / "calibration"

Handler = Callable[[argparse.Namespace], int]


def _non_negative_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected an integer, got {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError(f"expected a value >= 0, got {value}")
    return value


def _positive_int(text: str) -> int:
    value = _non_negative_int(text)
    if value == 0:
        raise argparse.ArgumentTypeError("expected a value >= 1, got 0")
    return value


def _positive_float(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a number, got {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"expected a value >= 1, got {value}")
    return value


@dataclass(frozen=True)
class _EventsOutput:
    """One ``events --output`` value: the significance cut and constituents of one report, and where it goes."""

    min_significance: Significance
    constituents: Constituents
    path: Path


def _events_output(text: str) -> _EventsOutput:
    """Parse ``MIN_SIGNIFICANCE:CONSTITUENTS:PATH``; the path may itself hold colons."""
    parts = text.split(":", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(f"expected MIN_SIGNIFICANCE:CONSTITUENTS:PATH, got {text!r}")
    minimum, constituents, path = parts
    if minimum not in SIGNIFICANCE_LEVELS:
        raise argparse.ArgumentTypeError(
            f"unknown significance {minimum!r} in {text!r}; expected one of {', '.join(SIGNIFICANCE_LEVELS)}"
        )
    if constituents not in CONSTITUENTS:
        raise argparse.ArgumentTypeError(
            f"unknown constituents {constituents!r} in {text!r}; expected one of {', '.join(CONSTITUENTS)}"
        )
    if not path:
        raise argparse.ArgumentTypeError(f"no path in {text!r}")
    return _EventsOutput(Significance(minimum), constituents, Path(path))


def _run_inspect(args: argparse.Namespace) -> int:
    """Print a raw structural report for one save without interpreting it."""
    save_path = cast(Path, args.save)
    save_name = safe_path(save_path)
    try:
        data = load_save(save_path)
    except OSError as error:
        reason = error.strerror or str(error)
        logger.debug("read failed %s", fields(save=save_name, errno=error.errno, error=type(error).__name__))
        print(f"tinarrative save inspect: cannot read {save_path}: {reason}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    logger.info("save inspect start %s", fields(save=save_name, bytes=len(data), pointers=len(args.path)))
    limits = RenderLimits(
        max_items=args.max_items,
        max_string=args.max_string,
        max_depth=args.max_depth,
    )
    logger.debug(
        "render limits %s",
        fields(
            max_items=limits.max_items, max_string=limits.max_string, max_depth=limits.max_depth, format=args.format
        ),
    )
    report = inspect_bytes(data, save_name, args.path, limits)
    rendered = render_json(report) if args.format == "json" else render_text(report)
    sys.stdout.write(rendered)
    sys.stdout.flush()

    if report.status == "unsupported_input":
        code = EXIT_UNSUPPORTED_INPUT
    elif report.status == "path_not_found":
        code = EXIT_PATH_NOT_FOUND
    else:
        code = EXIT_SUCCESS
    logger.info("save inspect done %s", fields(save=save_name, status=report.status, exit=code))
    return code


def _run_parse(args: argparse.Namespace) -> int:
    """Load and validate one save, then summarize it; failures never raise a traceback."""
    save_path = cast(Path, args.save)
    save_name = safe_path(save_path)
    logger.info("save parse start %s", fields(save=save_name))
    collector = UnknownCollector()
    try:
        raw = load_raw_save(save_path)
        snapshot = normalize(raw, collector=collector)
    except OSError as error:
        reason = error.strerror or str(error)
        logger.debug("read failed %s", fields(save=save_name, errno=error.errno, error=type(error).__name__))
        print(f"tinarrative save parse: cannot read {save_path}: {reason}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except SaveLoadError as error:
        logger.debug("parse failed %s", fields(save=save_name, error=type(error).__name__), exc_info=True)
        print(f"tinarrative save parse: {save_path}: {error}", file=sys.stderr)
        return EXIT_UNSUPPORTED_INPUT

    report = collector.report()
    print(f"source: {snapshot.source}")
    print(f"format: {raw.format}")
    print(f"game version: {raw.game_version or 'not serialized'}")
    print(f"size: {raw.size_bytes} bytes")
    print(f"top-level keys: {', '.join(raw.root)}")
    print(f"state types: {len(raw.root['gamestates'])}")
    print(f"date: {_render_observed(snapshot.date)}")
    print(f"campaign day: {_render_observed(snapshot.campaign_day)}")
    print(f"player faction: {_render_observed(snapshot.campaign.player_faction_name)}")
    for attribute, label in NORMALIZED_COLLECTION_LABELS:
        print(f"{label}: {len(getattr(snapshot, attribute))}")
    record_sets, record_entries = record_counts(snapshot.records)
    print(f"records: {record_sets} fields, {record_entries} entries")
    print(f"unknown structures: {report.total}")

    code = EXIT_SUCCESS
    if args.record_unknowns:
        registry = _resolve_registry(args.registry)
        if registry is None:
            print(
                f"tinarrative save parse: --record-unknowns needs --registry PATH or {REGISTRY_ENV_VAR}",
                file=sys.stderr,
            )
            code = EXIT_USAGE_ERROR
        else:
            try:
                update = record(registry, [(report, raw.game_version)], format=raw.format, today=date.today())
            except RegistryError as error:
                logger.debug("registry failed %s", fields(registry=safe_path(registry)), exc_info=True)
                print(f"tinarrative save parse: cannot update registry {registry}: {error}", file=sys.stderr)
                code = EXIT_REGISTRY_ERROR
            else:
                print(_registry_line(registry, update))
    logger.info(
        "save parse done %s",
        fields(
            save=save_name,
            state_types=len(raw.root["gamestates"]),
            game_version=raw.game_version,
            unknowns=report.total,
            exit=code,
        ),
    )
    return code


def _registry_line(registry: Path, update: RegistryUpdate) -> str:
    return (
        f"registry: {registry}: {update.added} added, {update.updated} updated, {update.pruned} pruned, "
        f"{update.total} total"
    )


def _resolve_registry(flag: Path | None) -> Path | None:
    """``--registry`` wins over ``TINARRATIVE_UNKNOWNS_REGISTRY``; an empty variable counts as unset."""
    if flag is not None:
        return flag
    from_env = os.environ.get(REGISTRY_ENV_VAR, "").strip()
    return Path(from_env) if from_env else None


def _run_unknowns(args: argparse.Namespace) -> int:
    """Scan saves for structures outside the schema; optionally fold them into the registry."""
    paths = cast(list[Path], args.paths)
    inputs = expand_inputs(paths)
    logger.info("unknowns start %s", fields(inputs=len(paths), saves=len(inputs)))
    run = scan_inputs(inputs)
    registry = _resolve_registry(args.registry)
    update: RegistryUpdate | None = None
    code = _unknowns_exit_code(run)
    if registry is not None and run.scanned:
        try:
            update = record(registry, run.scans(), today=date.today())
        except RegistryError as error:
            logger.debug("registry failed %s", fields(registry=safe_path(registry)), exc_info=True)
            print(f"tinarrative unknowns: cannot update registry {registry}: {error}", file=sys.stderr)
            code = EXIT_REGISTRY_ERROR
    rendered = (
        render_unknowns_json(run, update, registry)
        if args.format == "json"
        else render_unknowns_text(run, update, registry)
    )
    sys.stdout.write(rendered)
    sys.stdout.flush()
    logger.info(
        "unknowns done %s",
        fields(
            saves=len(run.results),
            scanned=len(run.scanned),
            skipped=len(run.results) - len(run.scanned),
            findings=len(run.findings),
            registry=safe_path(registry) if registry is not None else None,
            exit=code,
        ),
    )
    return code


def _unknowns_exit_code(run: ScanRun) -> int:
    """Only inputs named on the command line decide the code: 4 beats 5 beats 0; findings are not failures."""
    explicit_failures = [result for result in run.results if result.explicit and not result.scanned]
    if any(result.input_error for result in explicit_failures):
        return EXIT_INPUT_ERROR
    if explicit_failures:
        return EXIT_UNSUPPORTED_INPUT
    return EXIT_SUCCESS


class _LoadFailed(Exception):
    """A save could not be loaded; carries the exit code and the stderr message, and survives pickling."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(code, message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class _SnapshotLoader:
    """Load and normalize one save of ``command``; picklable, so a worker process can run it."""

    command: str

    def __call__(self, source: str) -> SaveSnapshot:
        save_path = Path(source)
        save_name = safe_path(save_path)
        try:
            return normalize(load_raw_save(save_path))
        except OSError as error:
            reason = error.strerror or str(error)
            logger.debug("read failed %s", fields(save=save_name, errno=error.errno, error=type(error).__name__))
            message = f"tinarrative {self.command}: cannot read {save_path}: {reason}"
            raise _LoadFailed(EXIT_INPUT_ERROR, message) from None
        except SaveLoadError as error:
            logger.debug("parse failed %s", fields(save=save_name, error=type(error).__name__), exc_info=True)
            raise _LoadFailed(EXIT_UNSUPPORTED_INPUT, f"tinarrative {self.command}: {save_path}: {error}") from None


def _load_snapshot(command: str, save_path: Path) -> SaveSnapshot | int:
    """Load and normalize one save, or print the failure and return the exit code."""
    try:
        return _SnapshotLoader(command)(str(save_path))
    except _LoadFailed as failure:
        print(failure.message, file=sys.stderr)
        return failure.code


def _run_diff(args: argparse.Namespace) -> int:
    """Compare two saves and report every literal state change between them."""
    before_path, after_path = cast(Path, args.before), cast(Path, args.after)
    before_name, after_name = safe_path(before_path), safe_path(after_path)
    logger.info("save diff start %s", fields(before=before_name, after=after_name))
    before = _load_snapshot("save diff", before_path)
    if isinstance(before, int):
        return before
    after = _load_snapshot("save diff", after_path)
    if isinstance(after, int):
        return after
    diff = diff_states(before, after)
    rendered = render_diff_json(diff) if args.format == "json" else render_diff_text(diff)
    sys.stdout.write(rendered)
    sys.stdout.flush()
    logger.info(
        "save diff done %s",
        fields(before=before_name, after=after_name, changes=len(diff.changes), exit=EXIT_SUCCESS),
    )
    return EXIT_SUCCESS


class _ProgressTracker:
    """Show save work on one terminal line and report its total elapsed time on stderr."""

    def __init__(self, command: str, total: int) -> None:
        self.command = command
        self.total = total
        self.started = time.perf_counter()
        self.terminal = sys.stderr.isatty()
        self.width = 0
        self.completed = 0
        self.label = ""
        self.lock = threading.Lock()

    def update(self, phase: str, completed: int, total: int | None = None, filename: str | None = None) -> None:
        if not self.terminal:
            return
        with self.lock:
            self._write_update(phase, completed, total, filename)

    def advance(self, phase: str, amount: int = 1) -> None:
        """Advance aggregate progress safely when workers finish concurrently."""
        if not self.terminal:
            return
        with self.lock:
            self.completed += amount
            self._write_update(phase, self.completed, None, None)

    def _write_update(self, phase: str, completed: int, total: int | None, filename: str | None) -> None:
        count = self.total if total is None else total
        current = "" if filename is None else f": {filename}"
        label = f"tinarrative {self.command}: {phase} {completed}/{count}{current}"
        self.label = label
        sys.stderr.write("\r" + label + " " * max(self.width - len(label), 0))
        sys.stderr.flush()
        self.width = len(label)

    def report(self, lines: Sequence[str]) -> None:
        """Write a completed work group without colliding with the live progress line."""
        with self.lock:
            if self.terminal:
                sys.stderr.write("\r" + " " * self.width + "\r")
            sys.stderr.write("\n".join(lines) + "\n")
            if self.terminal and self.label:
                sys.stderr.write("\r" + self.label + " " * max(self.width - len(self.label), 0))
            sys.stderr.flush()

    def finish(self, activity: str = "parsing and processing") -> None:
        elapsed = time.perf_counter() - self.started
        with self.lock:
            if self.terminal:
                sys.stderr.write("\r" + " " * self.width + "\r")
            sys.stderr.write(f"tinarrative {self.command}: {activity} took {elapsed:.1f}s\n")
            sys.stderr.flush()


def _load_failed(command: str, failure: LoadFailed) -> int:
    """Print the load failure behind its command prefix and return its exit code."""
    print(f"tinarrative {command}: {failure.message}", file=sys.stderr)
    return EXIT_INPUT_ERROR if isinstance(failure.cause, UnreadableInput) else EXIT_UNSUPPORTED_INPUT


def _survey_failed(command: str, failure: SurveyFailed) -> int:
    """Print the survey failure behind its command prefix and return its exit code; exhaustive over the failures."""
    print(f"tinarrative {command}: {failure.message}", file=sys.stderr)
    match failure:
        case UnreadableInput() | EmptyDirectory() | NoUsableSave():
            return EXIT_INPUT_ERROR
        case UnsupportedSave():
            return EXIT_UNSUPPORTED_INPUT
        case _:
            assert_never(failure)


def _survey_command_inputs(
    command: str,
    inputs: Sequence[SaveInput],
    settings: Settings,
    jobs: int | None = None,
    progress: _ProgressTracker | None = None,
) -> Survey | int:
    """Survey the inputs for ``command``, or print the failure and return its exit code."""
    outcome = survey_inputs(inputs, settings, command=command, jobs=jobs, progress=progress)
    if isinstance(outcome, Survey):
        return outcome
    return _survey_failed(command, outcome)


def _run_benchmark_sample(args: argparse.Namespace) -> int:
    """Import one benchmark campaign and render its CLI-facing result."""
    name = cast(str, args.name)

    def progress_factory(total: int) -> _ProgressTracker:
        return _ProgressTracker("benchmark sample", total)

    try:
        result = import_sample_campaign(
            name,
            cast(list[Path], args.paths),
            description=cast("str | None", args.description),
            selector=cast("str | None", args.campaign),
            samples_dir=BENCHMARK_SAMPLES_DIR,
            progress_factory=progress_factory,
            choose_campaign=lambda groups, selector: _choose_campaign("benchmark sample", groups, selector),
        )
    except SampleImportError as error:
        if not error.reported:
            print(f"tinarrative benchmark sample: {error}", file=sys.stderr)
        return error.exit_code

    for skipped in result.skipped:
        print(
            f"tinarrative benchmark sample: skipped {skipped.source}: {skipped.error_class}: {skipped.error}",
            file=sys.stderr,
        )
    print(f"Imported {result.files} saves into benchmarks/samples/{result.name}/.")
    if not result.description.strip():
        print(f"Add a description for {name!r} in benchmarks/samples/samples.json.")
    print("Review benchmarks/matrix.toml and add runs for this campaign if needed.")
    return EXIT_SUCCESS


def _run_benchmark_metrics(args: argparse.Namespace) -> int:
    """Verify samples, measure narrator packages, or compare two metrics files."""
    operation = cast(str, args.metrics_command)
    if operation == "samples":
        samples = cast(Path, args.samples)
        try:
            if args.update:
                updated = update_samples(samples)
                (samples / MANIFEST).write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8", newline="\n")
            errors = verify_samples(samples)
        except (OSError, json.JSONDecodeError) as exception:
            print(f"tinarrative benchmark metrics samples: {exception}", file=sys.stderr)
            return EXIT_OUTPUT_ERROR
        for sample_error in errors:
            print(f"tinarrative benchmark metrics samples: {sample_error}", file=sys.stderr)
        return EXIT_USAGE_ERROR if errors else EXIT_SUCCESS

    if operation == "merge":
        return _merge_metrics(args)

    if operation == "compare":
        try:
            report = benchmark_metrics.compare(
                json.loads(cast(Path, args.base).read_text(encoding="utf-8")),
                json.loads(cast(Path, args.head).read_text(encoding="utf-8")),
                threshold=cast(float, args.threshold),
                run_url=cast("str | None", args.run_url),
            )
            output = cast("Path | None", args.out)
            if output is None:
                sys.stdout.write(report)
            else:
                output.write_text(report, encoding="utf-8")
            return EXIT_SUCCESS
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exception:
            print(f"tinarrative benchmark metrics compare: {exception}", file=sys.stderr)
            return EXIT_INPUT_ERROR

    samples = cast(Path, args.samples)
    progress: _ProgressTracker | None = None
    try:
        errors = verify_samples(samples)
        for sample_error in errors:
            print(f"tinarrative benchmark metrics measure: {sample_error}", file=sys.stderr)
        if errors:
            return EXIT_USAGE_ERROR
        matrix = benchmark_metrics.load_matrix(cast(Path, args.matrix))
        named = cast("list[str] | None", args.campaign)
        selected = benchmark_metrics.select_campaigns(sample_files(samples), named)
        total = len(selected) * sum(len(entries) for entries in matrix.values())
        progress_tracker = _ProgressTracker("benchmark metrics measure", total)
        progress = progress_tracker
        metrics = benchmark_metrics.measure(
            python=cast("str | None", args.python) or sys.executable,
            samples=samples,
            matrix_path=cast(Path, args.matrix),
            config=cast(Path, args.config),
            out=cast(Path, args.out),
            label=cast(str, args.label),
            chars_per_token=cast(float, args.chars_per_token),
            jobs=cast("int | None", args.jobs) or os.cpu_count() or 1,
            on_progress=lambda amount: progress_tracker.advance("Measuring runs", amount),
            on_campaign_complete=progress_tracker.report,
            campaigns=named,
        )
        output = cast(Path, args.out)
        output.mkdir(parents=True, exist_ok=True)
        (output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8", newline="\n")
        return EXIT_SUCCESS
    except ValueError as error:
        print(f"tinarrative benchmark metrics measure: {error}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    except OSError as error:
        print(f"tinarrative benchmark metrics measure: {error}", file=sys.stderr)
        return EXIT_OUTPUT_ERROR
    finally:
        if progress is not None:
            progress.finish("measurement")


def _merge_metrics(args: argparse.Namespace) -> int:
    """Combine per-campaign metrics files into one."""
    try:
        documents = [json.loads(path.read_text(encoding="utf-8")) for path in cast("list[Path]", args.inputs)]
        if not all(
            isinstance(document, dict) and isinstance(document.get("campaigns"), dict) for document in documents
        ):
            raise ValueError("an input is not a metrics file")
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"tinarrative benchmark metrics merge: {error}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    try:
        merged = benchmark_metrics.merge(documents)
    except ValueError as error:
        print(f"tinarrative benchmark metrics merge: {error}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    output = cast(Path, args.out)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8", newline="\n")
    except OSError as error:
        print(f"tinarrative benchmark metrics merge: {error}", file=sys.stderr)
        return EXIT_OUTPUT_ERROR
    return EXIT_SUCCESS


def _calibration_samples_error(command: str, samples: Path) -> int | None:
    """The exit code when ``samples`` cannot be calibrated against, after printing why; None when it can."""
    try:
        if not samples.is_dir():
            raise OSError(f"{samples}: not a directory")
        (samples / MANIFEST).read_bytes()
    except OSError as error:
        print(f"{command}: {error}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    errors = verify_samples(samples)
    for sample_error in errors:
        print(f"{command}: {sample_error}", file=sys.stderr)
    return EXIT_USAGE_ERROR if errors else None


def _run_benchmark_calibrate_open(args: argparse.Namespace) -> int:
    """Serve the calibration page on 127.0.0.1, open it, keep its table current, and serve until interrupted.

    A stale table is shown at once and rebuilt while it is served; the page polls ``status.js``. With no table, the
    table is built first. A failed rebuild of an old table keeps that table served.
    """
    command = "tinarrative benchmark calibrate open"
    samples = cast(Path, args.samples)
    out = cast(Path, args.out)
    failed = _calibration_samples_error(command, samples)
    if failed is not None:
        return failed
    try:
        server = calibration_server.bind(calibration_server.Calibration(out), cast(int, args.port))
    except OSError as error:
        print(f"{command}: cannot serve on {calibration_server.HOST}:{args.port}: {error}", file=sys.stderr)
        return EXIT_OUTPUT_ERROR
    thread = threading.Thread(target=server.serve_forever, name="calibration-server", daemon=True)
    thread.start()
    page = calibration_server.url(server)
    shown = False

    def show() -> None:
        nonlocal shown
        if shown:
            return
        shown = True
        print(page, flush=True)
        if not args.no_open:
            _open_page(command, page)

    def stale(found: calibration_cache.CacheCheck) -> None:
        if found.existing is not None:
            show()
            print(
                f"{command}: Rebuilding the calibration table in {out}; the page shows the old one...", file=sys.stderr
            )
        else:
            print(f"{command}: Extracting the calibration table in {out}...", file=sys.stderr)

    code = EXIT_SUCCESS
    try:
        try:
            calibration_cache.refresh(samples, out, rebuild=cast(bool, args.rebuild), on_stale=stale)
        except calibration_cache.CalibrationCacheError as error:
            print(f"{command}: {error}", file=sys.stderr)
            if not shown:
                return EXIT_USAGE_ERROR
            code = EXIT_USAGE_ERROR
        except OSError as error:
            print(f"{command}: {error}", file=sys.stderr)
            return EXIT_OUTPUT_ERROR
        show()
        print(f"{command}: Serving {page}; press Ctrl-C to stop.", file=sys.stderr, flush=True)
        _wait_for_interrupt()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
    return code


def _wait_for_interrupt() -> None:
    """Block until Ctrl-C; the server answers from its own thread meanwhile."""
    threading.Event().wait()


def _open_page(command: str, page: str) -> None:
    """Open ``page`` in the default browser; a browser that cannot be opened is a warning, not a failure."""
    try:
        opened = webbrowser.open(page)
    except webbrowser.Error:
        opened = False
    if not opened:
        print(f"{command}: warning: cannot open a browser; open {page} by hand.", file=sys.stderr)


def _run_benchmark_calibrate(args: argparse.Namespace) -> int:
    """Refresh the calibration cache, replay it for the requested state and print the readout."""
    command = "tinarrative benchmark calibrate report"
    samples = cast(Path, args.samples)
    out = cast(Path, args.out)
    failed = _calibration_samples_error(command, samples)
    if failed is not None:
        return failed

    def stale(found: calibration_cache.CacheCheck) -> None:
        what = "Rebuilding" if found.existing is not None else "Extracting"
        print(f"{command}: {what} the calibration table in {out}...", file=sys.stderr)

    try:
        calibration_cache.refresh(samples, out, rebuild=cast(bool, args.rebuild), on_stale=stale)
    except calibration_cache.CalibrationCacheError as error:
        print(f"{command}: {error}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    except OSError as error:
        print(f"{command}: {error}", file=sys.stderr)
        return EXIT_OUTPUT_ERROR
    try:
        index, tables, drafts = calibration_replay.load(out)
        state = (
            calibration_replay.decode_state(cast(str, args.state), index)
            if args.state is not None
            else calibration_replay.default_state(index)
        )
        state = calibration_readout.override_state(
            state,
            index,
            references=cast("list[str] | None", args.reference) or [],
            campaigns=cast("list[str] | None", args.campaign) or [],
            types=cast("list[str] | None", args.type) or [],
            bases=cast("list[str] | None", args.base) or [],
        )
        result = calibration_replay.replay(index, tables, state, drafts)
    except (calibration_replay.ReplayError, CalibrationTableError) as error:
        print(f"{command}: {error}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    state_hash = calibration_replay.encode_state(state, index)
    if args.format == "json":
        document = calibration_readout.render_json(index, tables, result, state_hash=state_hash, drafts=drafts)
        sys.stdout.write(json.dumps(document, indent=2) + "\n")
    else:
        sys.stdout.write(calibration_readout.render_text(index, result, state_hash=state_hash, drafts=drafts))
    return EXIT_SUCCESS


def _run_benchmark_runtime(args: argparse.Namespace) -> int:
    """Measure the runtime of ``events`` on one or two revisions, or report or merge measurements."""
    command = f"tinarrative benchmark runtime {args.runtime_command}"
    if args.runtime_command == "merge":
        return _merge_runtime(args)
    if args.runtime_command == "report":
        try:
            report = benchmark_runtime.report(
                json.loads(cast(Path, args.runtime).read_text(encoding="utf-8")),
                run_url=cast("str | None", args.run_url),
            )
            output = cast("Path | None", args.out)
            if output is None:
                sys.stdout.write(report)
            else:
                output.write_text(report, encoding="utf-8")
            return EXIT_SUCCESS
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, StopIteration) as exception:
            print(f"{command}: {exception}", file=sys.stderr)
            return EXIT_INPUT_ERROR

    samples = cast(Path, args.samples)
    sides = [benchmark_runtime.Side("head", cast("str | None", args.python) or sys.executable, cast(str, args.label))]
    if args.base_python is not None:
        sides.insert(0, benchmark_runtime.Side("base", cast(str, args.base_python), cast(str, args.base_label)))
    progress: _ProgressTracker | None = None
    try:
        if not samples.is_dir():
            print(f"{command}: {samples}: not a directory", file=sys.stderr)
            return EXIT_INPUT_ERROR
        errors = verify_samples(samples) if (samples / MANIFEST).exists() else []
        for sample_error in errors:
            print(f"{command}: {sample_error}", file=sys.stderr)
        if errors:
            return EXIT_USAGE_ERROR
        campaigns = len(sample_files(samples)) if (samples / MANIFEST).exists() else 1
        progress_tracker = _ProgressTracker("benchmark runtime measure", campaigns * len(sides) * args.repeats)
        progress = progress_tracker

        def completed(line: str) -> None:
            progress_tracker.report([line])
            progress_tracker.advance("Measuring runs")

        runtime = benchmark_runtime.measure(
            sides=sides,
            samples=samples,
            matrix_path=cast(Path, args.matrix),
            run_id=cast(str, args.run),
            config=cast(Path, args.config),
            repeats=cast(int, args.repeats),
            campaign=cast("str | None", args.campaign),
            on_run_complete=completed,
        )
        output = cast(Path, args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(runtime, indent=2) + "\n", encoding="utf-8", newline="\n")
        return EXIT_SUCCESS
    except ValueError as error:
        print(f"{command}: {error}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    except OSError as error:
        print(f"{command}: {error}", file=sys.stderr)
        return EXIT_OUTPUT_ERROR
    finally:
        if progress is not None:
            progress.finish("measurement")


def _merge_runtime(args: argparse.Namespace) -> int:
    """Combine per-campaign runtime files into one, with the samples hash of the manifest given."""
    command = "tinarrative benchmark runtime merge"
    try:
        documents = [json.loads(path.read_text(encoding="utf-8")) for path in cast("list[Path]", args.inputs)]
        samples_sha256 = sha256_file(cast(Path, args.samples) / MANIFEST)
        for document in documents:
            if not (
                isinstance(document, dict)
                and all(key in document for key in benchmark_runtime.MERGE_METADATA)
                and isinstance(document.get("sides"), dict)
                and all(
                    isinstance(side, dict) and isinstance(side.get("campaigns"), dict) and "label" in side
                    for side in document["sides"].values()
                )
            ):
                raise ValueError("an input is not a runtime file")
        if len({tuple(document["sides"]) for document in documents}) > 1:
            raise ValueError("the runtime files differ in their sides")
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"{command}: {error}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    try:
        merged = benchmark_runtime.merge(documents, samples_sha256=samples_sha256)
    except ValueError as error:
        print(f"{command}: {error}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    output = cast(Path, args.out)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8", newline="\n")
    except OSError as error:
        print(f"{command}: {error}", file=sys.stderr)
        return EXIT_OUTPUT_ERROR
    return EXIT_SUCCESS


def _resolve_settings(command: str, flag: Path | None) -> Settings | int:
    """``--config`` wins over ``TINARRATIVE_CONFIG``; an empty variable counts as unset, and neither gives the
    defaults."""
    from_env = os.environ.get(CONFIG_ENV_VAR, "").strip()
    path = flag if flag is not None else (Path(from_env) if from_env else None)
    source = "flag" if flag is not None else ("env" if from_env else "default")
    shown = None if path is None else safe_path(path)
    try:
        settings = load_settings(path)
    except OSError as error:
        logger.debug("settings failed %s", fields(source=source, path=shown), exc_info=True)
        print(f"tinarrative {command}: cannot read settings {path}: {error.strerror or error}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    except ConfigError as error:
        logger.debug("settings invalid %s", fields(source=source, path=shown))
        print(f"tinarrative {command}: settings {path}: {error}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    logger.debug(
        "settings resolved %s",
        fields(
            source=source,
            path=None if path is None else safe_path(path),
            changed=len(settings.differences(DEFAULT_SETTINGS)),
        ),
    )
    return settings


def _analyze_inputs(
    command: str,
    paths: list[Path],
    selector: str | None,
    settings: Settings,
    *,
    depth: Depth,
    state_changes: bool,
    jobs: int | None = None,
) -> tuple[Survey, CampaignAnalysis] | int:
    """Survey the inputs, choose the campaign and analyze it; a failure is printed and returned as the exit code.
    ``jobs`` is ``--jobs``; unset falls back to the settings, then to ``workers.default_jobs``."""
    inputs = expand_inputs(paths)
    logger.info("%s start %s", command, fields(inputs=len(paths), candidates=len(inputs)))
    progress = _ProgressTracker(command, len(inputs))
    try:
        survey = _survey_command_inputs(command, inputs, settings, jobs, progress)
        if isinstance(survey, int):
            return survey
        campaign = _choose_campaign(command, group_saves(survey.saves), selector)
        if isinstance(campaign, int):
            return campaign
        analysis = analyze_campaign(
            campaign,
            settings,
            command=command,
            depth=depth,
            state_changes=state_changes,
            skipped=survey.skipped,
            jobs=jobs,
            progress=progress,
        )
        if isinstance(analysis, LoadFailed):
            return _load_failed(command, analysis)
        return survey, analysis
    finally:
        progress.finish()


def _run_councilors(args: argparse.Namespace) -> int:
    """Select the notable councilors of a campaign's latest save, write their dossier and one article request per
    councilor; with ``--send``, send the requests and assemble the articles."""
    output = cast("Path | None", args.output)
    if args.force and not args.send:
        print("tinarrative councilors: --force re-sends articles, so it needs --send", file=sys.stderr)
        return EXIT_USAGE_ERROR
    if args.send and output is None:
        print("tinarrative councilors: --send needs --output DIR to write the responses to", file=sys.stderr)
        return EXIT_USAGE_ERROR
    settings = _resolve_settings("councilors", cast("Path | None", args.config))
    if isinstance(settings, int):
        return settings
    narrator = _resolve_narrator(args, settings.narrator, command="councilors")
    if isinstance(narrator, int):
        return narrator
    target: Endpoint | None = None
    if args.send:
        try:
            target = endpoint(narrator, os.environ)
        except ValueError as error:
            print(f"tinarrative councilors: {error}", file=sys.stderr)
            return EXIT_USAGE_ERROR
    paths = cast(list[Path], args.saves)
    run = _analyze_inputs(
        "councilors",
        paths,
        cast("str | None", args.campaign),
        settings,
        depth=Depth.OBJECTIVE,
        state_changes=False,
        jobs=cast("int | None", args.jobs),
    )
    if isinstance(run, int):
        return run
    survey, analysis = run
    career = event_stream(analysis.intervals)
    newest = analysis.plan.saves[-1]
    latest, profile = Path(newest.source), newest.profile
    snapshot = _load_snapshot("councilors", latest)
    if isinstance(snapshot, int):
        return snapshot
    dossier = build_dossier(
        snapshot,
        _player_faction(snapshot, profile),
        career,
        settings.councilors,
        latest.name,
        player_only=args.player_only,
        tier_exponent=settings.narrative.significance.tier_exponent,
    )
    count = len(dossier["councilors"])
    reporter = _CliSendReporter(
        "councilors",
        "article",
        args.host,
        lambda: _write_out(f"Wrote dossier.json and {_count(count, 'request')} to {output}.\n"),
    )
    sys.stdout.write(_dossier_summary(dossier))
    code = EXIT_SUCCESS
    outcomes: list[SendOutcome] = []
    try:
        if target is not None and output is not None:
            articles = write_articles(
                dossier,
                narrator,
                target,
                output,
                host=args.host,
                reporter=reporter,
                force=bool(args.force),
                version=__version__,
            )
            outcomes = articles.outcomes
            code = EXIT_PROVIDER_ERROR if any(outcome.record is None for outcome in outcomes) else EXIT_SUCCESS
            _report_articles(output, articles.manifest)
        elif output is not None:
            RunDirectory(output).write_dossier(dossier, article_requests(dossier))
            reporter.written()
        else:
            sys.stdout.write("Nothing written; give --output DIR for the dossier and the requests.\n")
    except RunDirectoryWriteError as error:
        return _run_directory_write_failed(error, "councilors", output=None if reporter.is_written else output)
    sys.stdout.flush()
    logger.info(
        "councilors done %s",
        fields(
            saves=len(survey.saves),
            selected=len(dossier["councilors"]),
            written=output is not None,
            sent=sum(outcome.record is not None and not outcome.kept for outcome in outcomes) if target else None,
            kept=sum(outcome.kept for outcome in outcomes) if target else None,
            failed=sum(outcome.record is None for outcome in outcomes) if target else None,
            exit=code,
        ),
    )
    return code


def _write_out(text: str) -> None:
    sys.stdout.write(text)


def _report_articles(directory: Path, manifest: dict[str, Any]) -> None:
    """The one stdout line about ``councilors.md`` and, when articles are missing, the one stderr line."""
    absent = missing(manifest)
    total = len(manifest["articles"])
    sys.stdout.write(f"Wrote councilors.md and manifest.json to {directory}.\n")
    sys.stdout.flush()
    if absent:
        print(
            f"tinarrative councilors: {len(absent)} of {_count(total, 'article')} missing; see "
            f"{RunDirectory(directory).manifest_path}",
            file=sys.stderr,
        )


def _player_faction(snapshot: SaveSnapshot, profile: CampaignProfile | None) -> EntityId | None:
    """The human faction of the campaign: the profile's, else the one named by the save's metadata."""
    if profile is not None and profile.human_faction is not None:
        return EntityId(EntityDomain.FACTION, str(profile.human_faction))
    name = snapshot.campaign.player_faction_name
    matches = [state.ref.entity_id for state in snapshot.factions if isinstance(name, str) and state.ref.name == name]
    return matches[0] if len(matches) == 1 else None


def _dossier_summary(dossier: dict[str, Any]) -> str:
    chosen = dossier["councilors"]
    lines = [
        f"as of {dossier['as_of']}, player faction {dossier['player_faction'] or 'unknown'}: "
        f"{len(chosen)} councilors selected"
    ]
    for entry in chosen:
        marker = "player" if entry["player"] else "rival"
        lines.append(
            f"  {entry['name']} ({entry['faction']}, {marker}, rank {entry['prominence']['rank_in_faction']}, "
            f"{entry['tenure_years']} years)"
        )
    return "\n".join(lines) + "\n"


def _run_events(args: argparse.Namespace) -> int:
    """Order saves by game time and report the analyzer results of every consecutive pair."""
    outputs = cast("list[_EventsOutput]", args.output)
    single = [flag for flag, key in _EVENTS_PER_OUTPUT if getattr(args, key) is not None]
    if outputs and single:
        print(
            f"tinarrative events: {' and '.join(single)} with --output is ambiguous; give each report its own "
            "MIN_SIGNIFICANCE:CONSTITUENTS in --output",
            file=sys.stderr,
        )
        return EXIT_USAGE_ERROR
    settings = _resolve_settings("events", cast("Path | None", args.config))
    if isinstance(settings, int):
        return settings
    if args.format == "json" and args.narrative and args.changes:
        print(
            "tinarrative events: the JSON narrator package (--narrative) carries no state changes; "
            "drop --changes, or --narrative for the audit report",
            file=sys.stderr,
        )
        return EXIT_USAGE_ERROR
    run = _analyze_inputs(
        "events",
        cast(list[Path], args.saves),
        cast("str | None", args.campaign),
        settings,
        depth=Depth.NARRATIVE if args.narrative else Depth.INFERRED if args.inferred else Depth.OBJECTIVE,
        state_changes=args.changes,
        jobs=cast("int | None", args.jobs),
    )
    if isinstance(run, int):
        return run
    survey, analysis = run
    if outputs:
        for output in outputs:
            rendered = _events_report(args, settings, survey, analysis, output.min_significance, output.constituents)
            try:
                output.path.parent.mkdir(parents=True, exist_ok=True)
                output.path.write_text(rendered, encoding="utf-8", newline="\n")
            except OSError as error:
                print(f"tinarrative events: cannot write {output.path}: {error.strerror or error}", file=sys.stderr)
                return EXIT_OUTPUT_ERROR
    else:
        given = cast("str | None", args.min_significance)
        minimum = EVENTS_MIN_SIGNIFICANCE if given is None else Significance(given)
        constituents = cast("Constituents | None", args.constituents) or EVENTS_CONSTITUENTS
        sys.stdout.write(_events_report(args, settings, survey, analysis, minimum, constituents))
        sys.stdout.flush()
    plan, intervals, narrative = analysis.plan, analysis.intervals, analysis.narrative
    logger.info(
        "events done %s",
        fields(
            saves=len(plan.saves),
            intervals=len(intervals),
            skipped=len(plan.skipped),
            events=len(event_stream(intervals)),
            narrative=None if narrative is None else len(narrative),
            outputs=len(outputs) or None,
            exit=EXIT_SUCCESS,
        ),
    )
    return EXIT_SUCCESS


_EVENTS_PER_OUTPUT = (("--min-significance", "min_significance"), ("--constituents", "constituents"))
"""The ``events`` options that ``--output`` sets per report, so they cannot be given with it."""


def _events_report(
    args: argparse.Namespace,
    settings: Settings,
    survey: Survey,
    analysis: CampaignAnalysis,
    minimum: Significance,
    constituents: Constituents,
) -> str:
    """One ``events`` report of an analyzed campaign, cut at ``minimum`` and listing ``constituents``."""
    plan, intervals, campaign, narrative = analysis.plan, analysis.intervals, analysis.campaign, analysis.narrative
    if args.format == "json":
        document = build_document(
            plan,
            intervals,
            campaign=campaign,
            settings=settings,
            narrative=narrative,
            min_significance=minimum,
            constituents=constituents,
        )
        return json.dumps(document, indent=2, ensure_ascii=True) + "\n"
    return render_sequence(
        plan,
        intervals,
        min_significance=minimum,
        constituents=constituents,
        campaign=campaign,
        left_out=len(survey.saves) - len(campaign.members),
        narrative=narrative,
        changed_settings={
            key: value for key, value in settings.differences(DEFAULT_SETTINGS).items() if key.startswith("events.")
        },
        period=cast(Period, args.period),
    )


def _run_narrate(args: argparse.Namespace) -> int:
    """Cut a narrator package into chapters under the token budget and build each chapter's request; with ``--send``,
    send the requests to the configured provider and assemble the history; with ``--assemble``, only assemble."""
    assembled = cast("Path | None", args.assemble)
    if assembled is not None:
        given = [flag for flag, key in _ASSEMBLE_EXCLUDED if getattr(args, key) not in (None, False, [])]
        if given:
            print(f"tinarrative narrate: --assemble reads DIR only; drop {', '.join(given)}", file=sys.stderr)
            return EXIT_USAGE_ERROR
        return _assemble(assembled, host=args.host)
    if args.force and not args.send:
        print("tinarrative narrate: --force re-sends chapters, so it needs --send", file=sys.stderr)
        return EXIT_USAGE_ERROR
    settings = _resolve_settings("narrate", cast("Path | None", args.config))
    if isinstance(settings, int):
        return settings
    narrator = _resolve_narrator(args, settings.narrator)
    if isinstance(narrator, int):
        return narrator
    output = cast("Path | None", args.output)
    target: Endpoint | None = None
    if args.send:
        if output is None:
            print("tinarrative narrate: --send needs --output DIR to write the responses to", file=sys.stderr)
            return EXIT_USAGE_ERROR
        try:
            target = endpoint(narrator, os.environ)
        except ValueError as error:
            print(f"tinarrative narrate: {error}", file=sys.stderr)
            return EXIT_USAGE_ERROR
    saves = cast(list[Path], args.saves)
    source = cast("str | None", args.package)
    if source is not None and (
        saves
        or args.campaign is not None
        or args.min_significance is not None
        or args.constituents is not None
        or args.jobs is not None
    ):
        print(
            "tinarrative narrate: --package is narrated as it was built; drop the save paths, --campaign, "
            "--min-significance, --constituents and --jobs",
            file=sys.stderr,
        )
        return EXIT_USAGE_ERROR
    if source is None and not saves:
        print("tinarrative narrate: give save paths or --package FILE", file=sys.stderr)
        return EXIT_USAGE_ERROR
    loaded = _read_package(source) if source is not None else _build_package(args, saves, settings)
    if isinstance(loaded, int):
        return loaded
    try:
        package = validate(loaded)
        if not package["intervals"]:
            print("tinarrative narrate: the package holds no interval, so there is nothing to narrate", file=sys.stderr)
            return EXIT_USAGE_ERROR
        options = base_options(
            package,
            narrator,
            period=cast("str | None", args.period),
            audience=cast("str | None", args.audience),
            citations=cast("str | None", args.citations),
            style=cast("str | None", args.style),
            focus=cast("str | None", args.focus),
        )
        plan = plan_chapters(
            package, options, narrator, length=cast("int | None", args.length), requested=args.period is not None
        )
    except ValueError as error:
        logger.debug("package invalid %s", fields(error=type(error).__name__))
        print(f"tinarrative narrate: {error}", file=sys.stderr)
        return EXIT_UNSUPPORTED_INPUT
    if isinstance(plan, OverBudget):
        if plan.kind == "output":
            problem = (
                f"interval {plan.interval} asks for a length that needs about {plan.needed} max_output_tokens, over "
                f"max_output_tokens {plan.budget}; raise llm.max_output_tokens or give a smaller --length"
            )
        else:
            problem = (
                f"interval {plan.interval} needs about {plan.needed} input tokens without its atomic stream, over "
                f"max_input_tokens {plan.budget}; raise llm.max_input_tokens"
            )
        print(f"tinarrative narrate: {problem}", file=sys.stderr)
        logger.info(
            "narrate over budget %s",
            fields(kind=plan.kind, needed=plan.needed, budget=plan.budget, exit=EXIT_USAGE_ERROR),
        )
        return EXIT_USAGE_ERROR
    if plan.sparse:
        period = plan.options["period"]
        print(
            f"tinarrative narrate: warning: the saves are further apart than a {period} in "
            f"{', '.join(plan.sparse)}; --period {period} is kept, so those sections may divide what the saves cannot",
            file=sys.stderr,
        )
    reporter = _CliSendReporter("narrate", "chapter", args.host, lambda: _write_out(_render_plan(plan, output)))
    sent = kept = 0
    code = EXIT_SUCCESS
    try:
        if target is not None and output is not None:
            history = narrate_history(
                plan,
                narrator,
                target,
                output,
                host=args.host,
                reporter=reporter,
                force=bool(args.force),
                version=__version__,
            )
            outcomes = history.outcomes
            sent = sum(outcome.record is not None and not outcome.kept for outcome in outcomes)
            kept = sum(outcome.kept for outcome in outcomes)
            if history.assembly is None:
                code = EXIT_PROVIDER_ERROR
            else:
                _report_history(output, history.assembly)
        else:
            if output is not None:
                RunDirectory(output).write_plan(
                    plan.to_dict(), [(item.index, item.request) for item in chapter_items(plan)]
                )
            reporter.written()
    except RunDirectoryWriteError as error:
        return _run_directory_write_failed(error, output=None if reporter.is_written else output)
    except HistoryReadError as error:
        return _history_unreadable(error, cast(Path, output))
    logger.info(
        "narrate done %s",
        fields(
            chapters=len(plan.chapters),
            narrative_events=sum(planned.narrative_events for planned in plan.chapters),
            largest_estimate=max(planned.estimate for planned in plan.chapters),
            reduced=sum(planned.chapter.reduction is not None for planned in plan.chapters),
            coarsened=sum(planned.period_basis == "save_spacing" for planned in plan.chapters),
            sparse=len(plan.sparse),
            written=output is not None,
            sent=sent if target is not None else None,
            kept=kept if target is not None else None,
            exit=code,
        ),
    )
    return code


_ASSEMBLE_EXCLUDED = (
    ("PATH", "saves"),
    ("--package", "package"),
    ("--campaign", "campaign"),
    ("--min-significance", "min_significance"),
    ("--constituents", "constituents"),
    ("--period", "period"),
    ("--audience", "audience"),
    ("--citations", "citations"),
    ("--style", "style"),
    ("--length", "length"),
    ("--focus", "focus"),
    ("--output", "output"),
    ("--send", "send"),
    ("--force", "force"),
    ("--profile", "profile"),
    ("--provider", "provider"),
    ("--model", "model"),
    ("--base-url", "base_url"),
    ("--max-input-tokens", "max_input_tokens"),
    ("--max-output-tokens", "max_output_tokens"),
    ("--temperature", "temperature"),
    ("--config", "config"),
    ("--jobs", "jobs"),
)
"""The options ``narrate --assemble`` refuses: it reads the plan, requests and responses of DIR and nothing else."""

_NARRATOR_FLAGS = (
    ("--provider", "provider"),
    ("--model", "model"),
    ("--base-url", "base_url"),
    ("--max-input-tokens", "max_input_tokens"),
    ("--max-output-tokens", "max_output_tokens"),
    ("--temperature", "temperature"),
)


def _resolve_narrator(
    args: argparse.Namespace, narrator: NarratorSettings, *, command: str = "narrate"
) -> NarratorSettings | int:
    """The ``[narrator]`` settings, then the ``--profile`` over them, then the flags over both."""
    profile = cast("str | None", args.profile)
    if profile is not None:
        try:
            narrator = narrator.with_profile(profile)
        except KeyError:
            known = ", ".join(sorted(narrator.profiles)) or "none"
            print(f"tinarrative {command}: unknown profile {profile!r} (the settings define: {known})", file=sys.stderr)
            return EXIT_USAGE_ERROR
    overridden = 0
    for flag, key in _NARRATOR_FLAGS:
        value = getattr(args, key, None)
        if value is None:
            continue
        try:
            narrator = override(narrator, key, value)
        except ConfigError as error:
            print(f"tinarrative {command}: {flag}: {error}", file=sys.stderr)
            return EXIT_USAGE_ERROR
        overridden += 1
    logger.debug(
        "narrator resolved %s", fields(profile=profile is not None, provider=narrator.provider, flags=overridden)
    )
    return narrator


class _CliSendReporter(RunReporter):
    def __init__(self, command: str, noun: str, host: Host, on_written: Callable[[], None]) -> None:
        self.command = command
        self.noun = noun
        self.host = host
        self.on_written = on_written
        self.width = 0
        self.is_written = False

    def written(self) -> None:
        self.is_written = True
        self.on_written()
        sys.stdout.flush()

    def kept(self, outcome: SendOutcome, tokens: tuple[int | None, int | None]) -> None:
        item = outcome.item
        sys.stdout.write(_render_sent(item, "kept", outcome.finish or "", *tokens))
        sys.stdout.flush()

    def sent(self, outcome: SendOutcome) -> None:
        item, record = outcome.item, outcome.record
        assert record is not None
        sys.stdout.write(
            _render_sent(item, "sent", outcome.finish or "", record["input_tokens"], record["output_tokens"])
        )
        sys.stdout.flush()

    def failed(self, outcome: SendOutcome, provider: str) -> None:
        reason = outcome.error or "request failed"
        if outcome.finish == "length":
            reason += "; raise llm.max_output_tokens or give --max-output-tokens"
        elif outcome.finish == "empty":
            reason += "; run the command again to send it again"
        print(
            f"tinarrative {self.command}: {self.noun} {outcome.item.index}: {provider}: {reason}",
            file=sys.stderr,
        )

    def waiting(self, seconds: float) -> None:
        if not sys.stderr.isatty():
            return
        expected = (self.host.now().astimezone() + timedelta(seconds=seconds)).strftime("%H:%M:%S")
        label = f"tinarrative: rate limit wait; next attempt expected at {expected}"
        sys.stderr.write("\r" + label + " " * max(self.width - len(label), 0))
        sys.stderr.flush()
        self.width = len(label)

    def ready(self) -> None:
        if sys.stderr.isatty():
            sys.stderr.write("\r" + " " * self.width + "\r")
            sys.stderr.flush()
            self.width = 0

    def summary(self, outcomes: Sequence[SendOutcome], responses: Path, stopped: bool) -> None:
        if stopped:
            return
        sent = sum(outcome.record is not None and not outcome.kept for outcome in outcomes)
        kept = sum(outcome.kept for outcome in outcomes)
        stored_line = f", kept {kept} stored" if kept else ""
        sys.stdout.write(f"Wrote {_count(sent, 'response')} to {responses}{stored_line}.\n")
        sys.stdout.flush()


def _render_sent(item: SendItem, verb: str, finish: str, input_tokens: int | None, output_tokens: int | None) -> str:
    used = (
        f"{'?' if input_tokens is None else input_tokens} input and "
        f"{'?' if output_tokens is None else output_tokens} output tokens"
    )
    note = f" (estimate {item.subject})" if item.tag == "chapter" else (f" ({item.subject})" if item.subject else "")
    return f"- {item.index} {verb}: {finish}, {used}{note}\n"


_FINDINGS = {
    "unmatched": ("unmatched citation", "unmatched citations"),
    "uncited": ("uncited narrative event at major and above", "uncited narrative events at major and above"),
    "undefined": ("footnote without definition", "footnotes without definition"),
    "unreferenced": ("definition without reference", "definitions without reference"),
}


def _assemble(directory: Path, *, host: Host) -> int:
    """``narrate --assemble``: the history from what ``directory`` holds."""
    try:
        assembled = assemble_history(directory, host=host, version=__version__)
    except HistoryReadError as error:
        return _history_unreadable(error, directory)
    except RunDirectoryWriteError as error:
        return _run_directory_write_failed(error)
    _report_history(directory, assembled.assembly)
    return EXIT_SUCCESS


def _history_unreadable(failure: HistoryReadError, directory: Path) -> int:
    error = failure.error
    if isinstance(error, OSError):
        logger.debug("read failed %s", fields(output=safe_path(directory), error=type(error).__name__))
        print(f"tinarrative narrate: cannot read {directory}: {error.strerror or error}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    print(f"tinarrative narrate: {directory}: {error}", file=sys.stderr)
    return EXIT_UNSUPPORTED_INPUT


def _report_history(directory: Path, assembly: Assembly) -> None:
    """The one stdout line about ``history.md`` and, when the audit found something, the one stderr line."""
    sys.stdout.write(f"Wrote history.md and manifest.json to {directory}.\n")
    sys.stdout.flush()
    if assembly.findings:
        summary = ", ".join(f"{number} {_FINDINGS[kind][number != 1]}" for kind, number in assembly.findings.items())
        print(
            f"tinarrative narrate: citation audit: {summary}; see {RunDirectory(directory).manifest_path}",
            file=sys.stderr,
        )


def _output_failed(path: Path, error: OSError, command: str = "narrate") -> int:
    logger.debug("output failed %s", fields(output=safe_path(path), error=type(error).__name__))
    print(f"tinarrative {command}: cannot write {path}: {error.strerror or error}", file=sys.stderr)
    return EXIT_OUTPUT_ERROR


def _run_directory_write_failed(
    error: RunDirectoryWriteError, command: str = "narrate", *, output: Path | None = None
) -> int:
    """A write failure names the file, except before the plan or dossier is written, when it names the directory."""
    return _output_failed(output or error.path, error.error, command)


def _read_package(source: str) -> object | int:
    """A finished narrator package from a file, or from stdin for ``-``."""
    shown = "stdin" if source == "-" else safe_path(source)
    try:
        text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    except OSError as error:
        logger.debug("read failed %s", fields(package=shown, errno=error.errno, error=type(error).__name__))
        print(f"tinarrative narrate: cannot read {source}: {error.strerror or error}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except UnicodeDecodeError:
        print(f"tinarrative narrate: {source}: not UTF-8 text", file=sys.stderr)
        return EXIT_UNSUPPORTED_INPUT
    try:
        package: object = json.loads(text)
    except json.JSONDecodeError as error:
        print(f"tinarrative narrate: {source}: not valid JSON: {error}", file=sys.stderr)
        return EXIT_UNSUPPORTED_INPUT
    logger.info("narrate package %s", fields(package=shown, characters=len(text)))
    return package


def _build_package(args: argparse.Namespace, saves: list[Path], settings: Settings) -> object | int:
    """The narrator package as ``events --narrative --format json`` builds it, round-tripped through JSON so it is
    the same value a ``--package`` file gives."""
    run = _analyze_inputs(
        "narrate",
        saves,
        cast("str | None", args.campaign),
        settings,
        depth=Depth.NARRATIVE,
        state_changes=False,
        jobs=cast("int | None", args.jobs),
    )
    if isinstance(run, int):
        return run
    _, analysis = run
    document = build_document(
        analysis.plan,
        analysis.intervals,
        campaign=analysis.campaign,
        settings=settings,
        narrative=analysis.narrative,
        min_significance=Significance(cast("str | None", args.min_significance) or NARRATE_MIN_SIGNIFICANCE.value),
        constituents=cast("Constituents | None", args.constituents) or NARRATE_CONSTITUENTS,
    )
    package: object = json.loads(json.dumps(document))
    return package


def _render_plan(plan: ChapterPlan, output: Path | None) -> str:
    settings = plan.settings
    count = len(plan.chapters)
    lines = [
        f"{_count(count, 'chapter')} by {plan.options.get('period', 'year')}, max_input_tokens "
        f"{settings.max_input_tokens} at {settings.chars_per_token:g} characters per token:"
    ]
    reductions = {"atomic_dropped": "; atomic stream left out", "split": "; period split at saves"}
    coarsened = {"save_spacing": f" (saves too far apart for a {plan.options.get('period', 'year')})"}
    for planned in plan.chapters:
        lines.append(
            f"- {planned.index} ({planned.part}) {planned.covers[0][:10]} to {planned.covers[1][:10]}, "
            f"{', '.join(planned.periods)}{coarsened.get(planned.period_basis, '')}: "
            f"{_count(planned.narrative_events, 'narrative event')}, "
            f"{planned.continuing} continuing, {planned.recalled} recalled; ~{planned.estimate} input tokens"
            f"{reductions.get(planned.chapter.reduction or '', '')}"
            f"{', no atomic stream' if planned.chapter.reduction == 'split' and not planned.chapter.atomic else ''}"
        )
    if output is not None:
        lines.append(f"Wrote plan.json and {_count(count, 'request')} to {output}.")
    else:
        lines.append("Nothing written; give --output DIR for the plan and the requests.")
    return "\n".join(lines) + "\n"


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}{'' if number == 1 else 's'}"


def _interactive() -> bool:
    """Whether a person can answer the campaign picker: stdin and stderr are both terminals (stdout may be a file)."""
    return sys.stdin.isatty() and sys.stderr.isatty()


def _write_stderr(text: str) -> None:
    sys.stderr.write(text)
    sys.stderr.flush()


def _prompt(text: str) -> str:
    """``input`` that writes its prompt to stderr, so that a redirected report never holds it."""
    _write_stderr(text)
    line = sys.stdin.readline()
    if not line:
        raise EOFError
    return line.rstrip("\n")


def _choose_campaign(command: str, groups: Sequence[CampaignGroup], selector: str | None) -> CampaignGroup | int:
    """The campaign to analyze; ``choose_campaign`` not choosing one opens the picker in a terminal and is a usage
    error with the listing otherwise (or when the picker is cancelled)."""
    chosen = choose_campaign(groups, selector)
    if isinstance(chosen, CampaignGroup):
        return chosen
    if not _interactive():
        print(f"tinarrative {command}: {chosen.reason}\n\n{render_listing(groups)}", end="", file=sys.stderr)
        return EXIT_USAGE_ERROR
    if selector is not None:
        _write_stderr(f"tinarrative {command}: {chosen.reason}\n")
    picked = pick_campaign(groups, read=_prompt, write=_write_stderr, file_time=file_time, initial=selector)
    if picked is None:
        print(f"tinarrative {command}: no campaign chosen", file=sys.stderr)
        return EXIT_USAGE_ERROR
    logger.info("campaign selected %s", fields(index=picked.index, of=len(groups), interactive=True))
    return picked


def _run_campaigns(args: argparse.Namespace) -> int:
    """List the campaigns the saves belong to, without analyzing them."""
    paths = cast(list[Path], args.saves)
    inputs = expand_inputs(paths)
    logger.info("campaigns start %s", fields(inputs=len(paths), candidates=len(inputs)))
    outcome = _survey_command_inputs("campaigns", inputs, DEFAULT_SETTINGS, jobs=1)
    if isinstance(outcome, int):
        return outcome
    surveyed, skipped = outcome.saves, outcome.skipped
    groups = group_saves(surveyed)
    if args.format == "json":
        rendered = json.dumps(listing_document(groups, skipped), indent=2, ensure_ascii=True) + "\n"
    else:
        rendered = render_listing(groups)
        if skipped:
            rendered += f"\n{len(skipped)} skipped (inside a given directory, not a usable save):\n"
            rendered += "".join(f"- {save.source}: {save.error_class}: {save.error}\n" for save in skipped)
    sys.stdout.write(rendered)
    sys.stdout.flush()
    logger.info("campaigns done %s", fields(campaigns=len(groups), skipped=len(skipped), exit=EXIT_SUCCESS))
    return EXIT_SUCCESS


def _render_observed(value: Observed) -> str:
    """One-line text for a normalized value; unknown values say why."""
    rendered = to_jsonable(value)
    if isinstance(rendered, dict) and "unknown" in rendered:
        return f"unknown ({rendered['unknown']})"
    return str(rendered)


Subcommands: TypeAlias = "argparse._SubParsersAction[argparse.ArgumentParser]"

SAVES_HELP = "Save files or directories, in any order; a directory is read one level deep."
CAMPAIGN_HELP = (
    "The campaign to use when the saves hold several: a key, a unique key prefix, a listing number or 'latest'."
)
FORMAT_HELP = "Report format (default %(default)s)."
CONFIG_HELP = f"TOML settings file (default: ${CONFIG_ENV_VAR}, else the built-in settings)."
JOBS_HELP = "Worker processes; 1 runs everything in one process; the output is the same (default: processing.jobs)."


class _HelpFormatter(argparse.HelpFormatter):
    """Wraps each line of a description or epilog on its own, so the exit codes stay one per line."""

    def _fill_text(self, text: str, width: int, indent: str) -> str:
        lines = []
        for line in text.splitlines():
            hanging = len(line) - len(line.lstrip(" 0123456789"))
            lines.append(textwrap.fill(line, width, initial_indent=indent, subsequent_indent=indent + " " * hanging))
        return "\n".join(lines)


def _epilog(command: str) -> str:
    return "exit codes:\n" + "\n".join(f"  {code:<3} {meaning}" for code, meaning in EXIT_CODES[command])


def _add_command(subcommands: Subcommands, name: str, summary: str, command: str) -> argparse.ArgumentParser:
    """A leaf command whose ``--help`` shows ``summary`` and its exit codes from ``EXIT_CODES[command]``."""
    return subcommands.add_parser(
        name, help=summary, description=summary, epilog=_epilog(command), formatter_class=_HelpFormatter
    )


def _add_format_argument(parser: argparse.ArgumentParser, choices: tuple[str, ...] = ("text", "json")) -> None:
    parser.add_argument("--format", choices=choices, default=choices[0], help=FORMAT_HELP)


def _add_config_and_jobs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, metavar="FILE", help=CONFIG_HELP)
    parser.add_argument("--jobs", type=_positive_int, metavar="N", help=JOBS_HELP)


def _add_provider_arguments(parser: argparse.ArgumentParser, *, input_budget: bool) -> None:
    parser.add_argument("--profile", metavar="NAME", help="Apply the settings profile llm.profiles.NAME.")
    parser.add_argument("--provider", choices=PROVIDERS, help="Override llm.provider.")
    parser.add_argument("--model", help="Override llm.model; there is no default model.")
    parser.add_argument("--base-url", metavar="URL", help="Override llm.base_url.")
    if input_budget:
        parser.add_argument("--max-input-tokens", type=int, metavar="TOKENS", help="Override llm.max_input_tokens.")
    parser.add_argument("--max-output-tokens", type=int, metavar="TOKENS", help="Override llm.max_output_tokens.")
    parser.add_argument("--temperature", type=float, help="Override llm.temperature.")


def _add_parse_parser(subcommands: Subcommands) -> None:
    parser = _add_command(subcommands, "parse", "Check that a save loads and summarize what it holds.", "save parse")
    parser.add_argument("save", type=Path, help="Path to a single save file.")
    parser.add_argument(
        "--record-unknowns",
        action="store_true",
        help="Also fold the unknown structures in this save into the unknowns registry.",
    )
    _add_registry_argument(parser)
    parser.set_defaults(handler=_run_parse)


def _add_registry_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        metavar="PATH",
        help=f"Unknowns registry JSON file to update, created when missing (default: ${REGISTRY_ENV_VAR}).",
    )


def _add_unknowns_parser(subcommands: Subcommands) -> None:
    parser = _add_command(
        subcommands,
        "unknowns",
        "Scan saves for structures the parser does not describe and, with a registry, record them for triage.",
        "unknowns",
    )
    parser.add_argument("paths", type=Path, nargs="+", metavar="PATH", help=SAVES_HELP)
    _add_registry_argument(parser)
    _add_format_argument(parser)
    parser.set_defaults(handler=_run_unknowns)


def _add_inspect_parser(subcommands: Subcommands) -> None:
    parser = _add_command(
        subcommands, "inspect", "Report one save file's raw structure without interpreting it.", "save inspect"
    )
    parser.add_argument("save", type=Path, help="Path to a single save file.")
    parser.add_argument(
        "-p",
        "--path",
        action="append",
        default=[],
        metavar="POINTER",
        help="RFC 6901 JSON pointer to print, such as /gamestates/Some.State/0/Value; may be repeated.",
    )
    parser.add_argument(
        "--max-items",
        type=_non_negative_int,
        default=RenderLimits.max_items,
        metavar="N",
        help="Maximum array items or object keys shown per container in a selected path (default %(default)s).",
    )
    parser.add_argument(
        "--max-string",
        type=_non_negative_int,
        default=RenderLimits.max_string,
        metavar="N",
        help="Maximum characters shown per string in a selected path (default %(default)s).",
    )
    parser.add_argument(
        "--max-depth",
        type=_non_negative_int,
        default=RenderLimits.max_depth,
        metavar="N",
        help="Maximum nesting depth shown in a selected path (default %(default)s).",
    )
    _add_format_argument(parser)
    parser.set_defaults(handler=_run_inspect)


def _add_diff_parser(subcommands: Subcommands) -> None:
    parser = _add_command(
        subcommands, "diff", "List every literal difference between two saves, without inferring causes.", "save diff"
    )
    parser.add_argument("before", type=Path, help="The earlier save file.")
    parser.add_argument("after", type=Path, help="The later save file; the saves are compared in argument order.")
    _add_format_argument(parser)
    parser.set_defaults(handler=_run_diff)


def _add_councilors_parser(subcommands: Subcommands) -> None:
    parser = _add_command(
        subcommands,
        "councilors",
        "Write public-perception articles about a campaign's notable councilors with an LLM.",
        "councilors",
    )
    parser.add_argument(
        "saves",
        type=Path,
        nargs="+",
        metavar="PATH",
        help="One save, or saves and directories of one campaign; a directory is read one level deep.",
    )
    parser.add_argument("--campaign", metavar="SELECTOR", help=CAMPAIGN_HELP)
    parser.add_argument("--player-only", action="store_true", help="Select only the player's councilors.")
    parser.add_argument(
        "--output", type=Path, metavar="DIR", help="Write dossier.json and one request per councilor here."
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help=(
            "Send the requests to the provider and write councilors.md; needs --output. Hands the dossier to a "
            "third party unless the provider runs locally."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --send, send every article again, even one with a matching stored response.",
    )
    _add_provider_arguments(parser, input_budget=False)
    _add_config_and_jobs(parser)
    parser.set_defaults(handler=_run_councilors)


def _add_events_parser(subcommands: Subcommands) -> None:
    parser = _add_command(
        subcommands,
        "events",
        "Report what happened between every pair of consecutive saves of one campaign.",
        "events",
    )
    parser.add_argument("saves", type=Path, nargs="+", metavar="PATH", help=SAVES_HELP)
    parser.add_argument("--campaign", metavar="SELECTOR", help=CAMPAIGN_HELP)
    _add_format_argument(parser, ("markdown", "json"))
    parser.add_argument(
        "--min-significance",
        choices=SIGNIFICANCE_LEVELS,
        help="Lowest significance listed; with --narrative, of the narrative events "
        f"(default {EVENTS_MIN_SIGNIFICANCE.value}).",
    )
    parser.add_argument(
        "--constituents",
        choices=CONSTITUENTS,
        help="With --narrative, which events behind the listed narrative events to list "
        f"(default {EVENTS_CONSTITUENTS}).",
    )
    parser.add_argument(
        "--output",
        type=_events_output,
        action="append",
        default=[],
        metavar="MIN_SIGNIFICANCE:CONSTITUENTS:PATH",
        help="Write the report to PATH with this significance cut and constituents instead of printing it; "
        "repeatable, the campaign is analyzed once. Not with --min-significance or --constituents.",
    )
    parser.add_argument(
        "--period",
        choices=PERIODS,
        default="year",
        help="How the Markdown narrative section is grouped (default %(default)s).",
    )
    parser.add_argument(
        "--inferred",
        action="store_true",
        help="Also list the events inferred in each interval, with the results they rest on.",
    )
    parser.add_argument(
        "--changes",
        action="store_true",
        help="Also list every literal state change under its interval; not with --narrative --format json.",
    )
    parser.add_argument(
        "--narrative",
        action="store_true",
        help="Also join the whole campaign's events into narrative events; implies --inferred.",
    )
    _add_config_and_jobs(parser)
    parser.set_defaults(handler=_run_events)


def _add_narrate_parser(subcommands: Subcommands) -> None:
    parser = _add_command(subcommands, "narrate", "Turn a campaign into a written history told by an LLM.", "narrate")
    parser.add_argument("saves", type=Path, nargs="*", metavar="PATH", help=SAVES_HELP)
    parser.add_argument(
        "--package",
        metavar="FILE",
        help="A narrator package from 'events --narrative --format json' to narrate instead; '-' reads stdin.",
    )
    parser.add_argument("--campaign", metavar="SELECTOR", help=CAMPAIGN_HELP)
    parser.add_argument(
        "--min-significance",
        choices=SIGNIFICANCE_LEVELS,
        default=None,
        help=f"Lowest significance of a narrative event told, from saves (default {NARRATE_MIN_SIGNIFICANCE.value}).",
    )
    parser.add_argument(
        "--constituents",
        choices=CONSTITUENTS,
        default=None,
        help=f"Which events behind the narrative events the model also gets (default {NARRATE_CONSTITUENTS}).",
    )
    parser.add_argument(
        "--period", choices=PERIODS, help="The sections the history is told in (default: from the campaign's span)."
    )
    parser.add_argument(
        "--audience",
        choices=AUDIENCES,
        help=f"Who the history is for; insider centres on the player faction (default {AUDIENCES[0]}).",
    )
    parser.add_argument(
        "--citations", choices=CITATIONS, help=f"Footnotes citing event IDs, or none (default {CITATIONS[0]})."
    )
    parser.add_argument("--style", choices=STYLES, help=f"Running prose or headlines (default {STYLES[0]}).")
    parser.add_argument(
        "--length",
        type=_positive_int,
        metavar="WORDS",
        help="Target length of the whole history (default: from how much happened).",
    )
    parser.add_argument(
        "--focus",
        metavar="NAME",
        help="A faction or nation to centre the account on (default: the player faction with --audience insider).",
    )
    parser.add_argument("--output", type=Path, metavar="DIR", help="Write the plan and one request per chapter here.")
    parser.add_argument(
        "--send",
        action="store_true",
        help=(
            "Send the requests to the provider and assemble history.md; needs --output. Hands the campaign to a "
            "third party unless the provider runs locally."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --send, send every chapter again, even one with a matching stored response.",
    )
    parser.add_argument(
        "--assemble",
        type=Path,
        metavar="DIR",
        help="Assemble history.md from a directory written earlier, sending nothing; takes no other option.",
    )
    _add_provider_arguments(parser, input_budget=True)
    _add_config_and_jobs(parser)
    parser.set_defaults(handler=_run_narrate)


def _add_campaigns_parser(subcommands: Subcommands) -> None:
    parser = _add_command(
        subcommands,
        "campaigns",
        "List the campaigns that saves belong to, with the selector that --campaign accepts.",
        "campaigns",
    )
    parser.add_argument("saves", type=Path, nargs="+", metavar="PATH", help=SAVES_HELP)
    _add_format_argument(parser)
    parser.set_defaults(handler=_run_campaigns)


def _add_benchmark_parser(subcommands: Subcommands) -> None:
    summary = "Maintain the benchmark samples, measure package size and runtime, and calibrate shares."
    parser = subcommands.add_parser("benchmark", help=summary, description=summary)
    commands = parser.add_subparsers(dest="benchmark_command", metavar="COMMAND", required=True)
    sample = _add_command(
        commands, "sample", "Import or refresh a campaign in benchmarks/samples/ and samples.json.", "benchmark sample"
    )
    sample.add_argument("name", help="The sample campaign's directory name under benchmarks/samples/.")
    sample.add_argument("paths", type=Path, nargs="+", metavar="PATH", help="One directory, or save files.")
    sample.add_argument(
        "--description", metavar="TEXT", help="Campaign description for samples.json (default: keep the existing one)."
    )
    sample.add_argument(
        "--campaign", metavar="SELECTOR", help="The campaign to import from a directory that holds several."
    )
    sample.set_defaults(handler=_run_benchmark_sample)

    summary = "Measure and compare narrator package sizes."
    metrics = commands.add_parser("metrics", help=summary, description=summary)
    metric_commands = metrics.add_subparsers(dest="metrics_command", metavar="OPERATION", required=True)
    samples = _add_command(
        metric_commands,
        "samples",
        f"Verify the sample files against {MANIFEST}, or rewrite it.",
        "benchmark metrics samples",
    )
    _add_samples_argument(samples)
    samples.add_argument("--update", action="store_true", help=f"Rewrite {MANIFEST} from the files.")
    samples.set_defaults(handler=_run_benchmark_metrics)

    measure = _add_command(
        metric_commands,
        "measure",
        "Run the package-size matrix on every sample campaign and write metrics.json.",
        "benchmark metrics measure",
    )
    _add_python_argument(measure)
    _add_samples_argument(measure)
    _add_matrix_and_config_arguments(measure)
    measure.add_argument(
        "--out", type=Path, required=True, metavar="PATH", help="Directory for the packages, plans and metrics.json."
    )
    _add_label_argument(measure)
    measure.add_argument(
        "--campaign",
        action="append",
        metavar="NAME",
        help="Measure only this sample campaign; repeat for several (default: every campaign).",
    )
    measure.add_argument(
        "--chars-per-token",
        type=_positive_float,
        default=2.4,
        metavar="FLOAT",
        help="Characters per estimated token (default %(default)s).",
    )
    measure.add_argument(
        "--jobs", type=_positive_int, metavar="N", help="Commands run at once (default: the CPU count)."
    )
    measure.set_defaults(handler=_run_benchmark_metrics)

    merge = _add_command(
        metric_commands,
        "merge",
        "Combine per-campaign metrics.json files into one.",
        "benchmark metrics merge",
    )
    merge.add_argument("inputs", type=Path, nargs="+", metavar="METRICS", help="A per-campaign metrics.json.")
    merge.add_argument("--out", type=Path, required=True, metavar="PATH", help="Write the merged metrics.json here.")
    merge.set_defaults(handler=_run_benchmark_metrics)

    compare = _add_command(
        metric_commands, "compare", "Write the Markdown comparison of two metrics files.", "benchmark metrics compare"
    )
    compare.add_argument("base", type=Path, help="The base metrics.json.")
    compare.add_argument("head", type=Path, help="The head metrics.json.")
    _add_report_arguments(compare)
    compare.add_argument(
        "--threshold",
        type=float,
        default=1.0,
        metavar="PERCENT",
        help="Highlight size changes of at least this percentage (default %(default)s).",
    )
    compare.set_defaults(handler=_run_benchmark_metrics)

    summary = "Measure and report the processing runtime of events."
    runtime = commands.add_parser("runtime", help=summary, description=summary)
    runtime_commands = runtime.add_subparsers(dest="runtime_command", metavar="OPERATION", required=True)
    timed = _add_command(
        runtime_commands,
        "measure",
        "Time one events run per campaign and write the runtime JSON.",
        "benchmark runtime measure",
    )
    timed.add_argument("--out", type=Path, required=True, metavar="FILE", help="The runtime JSON file to write.")
    _add_python_argument(timed)
    _add_label_argument(timed)
    timed.add_argument(
        "--base-python", metavar="PYTHON", help="A second interpreter measured as the base, alternating with --python."
    )
    timed.add_argument(
        "--base-label", default="base", metavar="TEXT", help="What the base is, such as a commit (default %(default)s)."
    )
    timed.add_argument(
        "--samples",
        type=Path,
        default=BENCHMARK_SAMPLES_DIR,
        metavar="PATH",
        help=f"Benchmark samples (a directory with {MANIFEST}) or one directory of saves (default %(default)s).",
    )
    timed.add_argument(
        "--campaign", metavar="SELECTOR", help="Passed to events --campaign, for a directory of several campaigns."
    )
    _add_matrix_and_config_arguments(timed)
    timed.add_argument(
        "--run", default="major", metavar="ID", help="The matrix's events run to time (default %(default)s)."
    )
    timed.add_argument(
        "--repeats",
        type=_positive_int,
        default=1,
        metavar="N",
        help="Runs per side; the fastest is kept (default %(default)s).",
    )
    timed.set_defaults(handler=_run_benchmark_runtime)

    merged = _add_command(
        runtime_commands,
        "merge",
        "Combine per-campaign runtime JSON files into one.",
        "benchmark runtime merge",
    )
    merged.add_argument("inputs", type=Path, nargs="+", metavar="FILE", help="A per-campaign runtime JSON file.")
    merged.add_argument(
        "--out", type=Path, required=True, metavar="FILE", help="The merged runtime JSON file to write."
    )
    _add_samples_argument(merged)
    merged.set_defaults(handler=_run_benchmark_runtime)

    reported = _add_command(
        runtime_commands, "report", "Write the Markdown report of a runtime JSON file.", "benchmark runtime report"
    )
    reported.add_argument("runtime", type=Path, metavar="FILE", help="The runtime JSON file.")
    _add_report_arguments(reported)
    reported.set_defaults(handler=_run_benchmark_runtime)

    summary = "Replay the share calibration table for other references."
    calibrate = commands.add_parser("calibrate", help=summary, description=summary)
    calibrate_commands = calibrate.add_subparsers(dest="calibrate_command", metavar="OPERATION", required=True)
    opened = _add_command(
        calibrate_commands,
        "open",
        "Serve the share calibration page, open it in the browser and keep its table current until interrupted.",
        "benchmark calibrate open",
    )
    _add_calibration_cache_arguments(opened)
    opened.add_argument(
        "--port",
        type=int,
        default=calibration_server.DEFAULT_PORT,
        metavar="PORT",
        help="The port on 127.0.0.1 to serve the page on (default %(default)s).",
    )
    opened.add_argument("--no-open", action="store_true", help="Print the page's URL without opening a browser.")
    opened.set_defaults(handler=_run_benchmark_calibrate_open)

    report = _add_command(
        calibrate_commands,
        "report",
        "Refresh the calibration cache and print the readout of a calibration state.",
        "benchmark calibrate report",
    )
    _add_calibration_cache_arguments(report)
    report.add_argument(
        "--reference",
        action="append",
        metavar="MEASURE=VALUE",
        help="A measure's reference share; comma-separated, repeatable (default: the code's).",
    )
    report.add_argument(
        "--campaign",
        action="append",
        metavar="NAME",
        help="Replay only these sample campaigns; comma-separated, repeatable (default: every one).",
    )
    report.add_argument(
        "--type",
        action="append",
        metavar="EVENT_TYPE",
        help="Count only these event types; comma-separated, repeatable (default: every type).",
    )
    report.add_argument(
        "--base",
        action="append",
        metavar="TYPE=LEVEL",
        help="Try a base level on an event type; comma-separated, repeatable (default: the code's).",
    )
    report.add_argument(
        "--state", metavar="HASH", help="A calibration page's URL hash; the other flags override what it sets."
    )
    _add_format_argument(report)
    report.set_defaults(handler=_run_benchmark_calibrate)


def _add_calibration_cache_arguments(parser: argparse.ArgumentParser) -> None:
    _add_samples_argument(parser)
    parser.add_argument(
        "--out",
        type=Path,
        default=CALIBRATION_OUT_DIR,
        metavar="PATH",
        help="The calibration cache directory (default %(default)s).",
    )
    parser.add_argument("--rebuild", action="store_true", help="Rebuild the cache even when it is fresh.")


def _add_python_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--python", metavar="PYTHON", help="The interpreter whose tinarrative is measured (default: this one)."
    )


def _add_label_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--label",
        default="working tree",
        metavar="TEXT",
        help="What is measured, such as a commit (default %(default)s).",
    )


def _add_samples_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--samples",
        type=Path,
        default=BENCHMARK_SAMPLES_DIR,
        metavar="PATH",
        help="Benchmark samples directory (default %(default)s).",
    )


def _add_matrix_and_config_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--matrix",
        type=Path,
        default=BENCHMARK_ROOT / "matrix.toml",
        metavar="PATH",
        help="The run matrix (default %(default)s).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=BENCHMARK_ROOT / "config.toml",
        metavar="PATH",
        help="Settings file for the measured runs (default %(default)s).",
    )


def _add_report_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", type=Path, metavar="PATH", help="Write the report here (default: stdout).")
    parser.add_argument("--run-url", metavar="URL", help="Link the report to this CI run.")


def _add_save_parser(subcommands: Subcommands) -> None:
    summary = "Inspect, parse or diff individual save files."
    parser = subcommands.add_parser("save", help=summary, description=summary)
    save_commands = parser.add_subparsers(
        dest="save_command",
        title="commands",
        metavar="COMMAND",
        required=True,
        description="Use 'tinarrative save COMMAND --help' for command-specific help.",
    )
    _add_inspect_parser(save_commands)
    _add_parse_parser(save_commands)
    _add_diff_parser(save_commands)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tinarrative",
        description="Reconstruct Terra Invicta campaign history from save files.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}", help="Print the version.")
    parser.add_argument(
        "--log-level",
        choices=tuple(LEVELS),
        default=None,
        metavar="LEVEL",
        help=(
            f"Diagnostic log level on stderr: {', '.join(LEVELS)}; must precede COMMAND (default: ${ENV_VAR}, "
            f"else {DEFAULT_LEVEL})."
        ),
    )

    subcommands = parser.add_subparsers(
        dest="command",
        title="commands",
        metavar="COMMAND",
        description="Use 'tinarrative COMMAND --help' for command-specific help.",
    )
    _add_campaigns_parser(subcommands)
    _add_benchmark_parser(subcommands)
    _add_councilors_parser(subcommands)
    _add_events_parser(subcommands)
    _add_narrate_parser(subcommands)
    _add_save_parser(subcommands)
    _add_unknowns_parser(subcommands)
    return parser


def main(argv: Sequence[str] | None = None, *, host: Host | None = None) -> int:
    """Run the command-line interface and return a stable process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    args.host = Host.real() if host is None else host
    level = _resolve_log_level(parser, args)
    configure_logging(level, timing=os.environ.get(TIMING_ENV_VAR, "").strip() not in ("", "0"))
    if not hasattr(args, "handler"):
        parser.print_help()
        return EXIT_SUCCESS
    handler = cast(Handler, args.handler)
    return handler(args)


def _resolve_log_level(parser: argparse.ArgumentParser, args: argparse.Namespace) -> str:
    """``--log-level`` wins over ``TINARRATIVE_LOG_LEVEL``; an invalid variable is a usage error."""
    if args.log_level is not None:
        return cast(str, args.log_level)
    from_env = os.environ.get(ENV_VAR)
    if from_env is None or from_env == "":
        return DEFAULT_LEVEL
    level = from_env.strip().lower()
    if level not in LEVELS:
        parser.error(f"{ENV_VAR}={from_env!r} is not one of: {', '.join(LEVELS)}")
    return level


if __name__ == "__main__":
    raise SystemExit(main())
