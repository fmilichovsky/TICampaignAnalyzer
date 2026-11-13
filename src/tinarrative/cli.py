"""Command-line entry point for the analyzer."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from collections.abc import Callable, Sequence
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from . import __version__
from .benchmarking import metrics as benchmark_metrics
from .benchmarking import runtime as benchmark_runtime
from .benchmarking.manifest import MANIFEST, sample_files, update_samples, verify_samples
from .benchmarking.samples import SampleImportError, import_sample_campaign
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
from .grouping import CampaignGroup, group_saves, listing_document, render_listing, select_campaign
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
from .model.events import SIGNIFICANCE_ORDER, Event, Significance
from .model.records import record_counts
from .model.snapshot import NORMALIZED_COLLECTION_LABELS, SaveSnapshot
from .model.values import Observed, to_jsonable
from .narrative import build_dossier, narrative_rules
from .narrator.assembly import KEPT_FINISHES, assemble, parse_plan, stored_chapter
from .narrator.chapters import ChapterPlan, OverBudget, base_options, plan_chapters, validate
from .narrator.councilors import article_requests, assemble_articles, missing, request_sha256
from .narrator.providers import CompletionRequest, Endpoint, ProviderError, complete, completion_request, endpoint
from .narrator.rate_limit import RateLimiter, estimate_tokens
from .narrator.request import AUDIENCES, CITATIONS, STYLES, render_request
from .narrator.transport import Transport, UrllibTransport
from .parsing.continuity import CampaignProfile
from .parsing.errors import SaveLoadError
from .parsing.normalization import normalize
from .parsing.unknowns import UnknownCollector
from .picker import pick_campaign
from .rendering.json_report import build_document
from .rendering.listing import CONSTITUENTS, Constituents
from .rendering.markdown import PERIODS, Period, render_sequence
from .sequence import (
    IntervalResult,
    SaveRef,
    SequencePlan,
    SkippedSave,
    SurveyFailure,
    event_stream,
    narrative_events,
    plan_sequence,
    run_sequence,
    survey_all,
)
from .workers import default_jobs, memory_line

logger = get_logger(__name__)

EXIT_SUCCESS = 0
EXIT_USAGE_ERROR = 2
EXIT_NOT_IMPLEMENTED = 3
"""Reserved for commands registered before they are implemented; none is at present."""
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
BENCHMARK_ROOT = Path.cwd() / "benchmarks"
BENCHMARK_SAMPLES_DIR = BENCHMARK_ROOT / "samples"

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


def _survey_failed(command: str, failure: SurveyFailure) -> int:
    """Print why a path named on the command line could not be surveyed and return the exit code."""
    if failure.content:
        print(f"tinarrative {command}: {failure.source}: {failure.reason}", file=sys.stderr)
        return EXIT_UNSUPPORTED_INPUT
    print(f"tinarrative {command}: cannot read {failure.source}: {failure.reason}", file=sys.stderr)
    return EXIT_INPUT_ERROR


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


def _survey_inputs(
    command: str, inputs: Sequence[SaveInput], progress: _ProgressTracker | None = None, jobs: int = 1
) -> tuple[list[SaveRef], list[SkippedSave]] | int:
    """Survey every input; only a path named on the command line can fail the run (exit 4 beats nothing found).

    Outcomes are judged in input order, so the failure reported is the same whatever ``jobs`` is.
    """
    surveyed: list[SaveRef] = []
    skipped: list[SkippedSave] = []
    usable: dict[Path, int] = {}
    done = 0

    def on_save(path: Path) -> None:
        nonlocal done
        done += 1
        if progress is not None:
            progress.update("Scanning saves", done, filename=path.name)

    paths = [item.path for item in inputs if not item.empty_directory]
    with closing(survey_all(paths, jobs=jobs, on_save=on_save)) as outcomes:
        for item in inputs:
            if item.empty_directory:
                print(f"tinarrative {command}: {item.path}: the directory holds no files", file=sys.stderr)
                return EXIT_INPUT_ERROR
            found = next(outcomes)
            if item.directory is None:
                if isinstance(found, SurveyFailure):
                    return _survey_failed(command, found)
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
            print(f"tinarrative {command}: {directory}: the directory holds no usable save", file=sys.stderr)
            return EXIT_INPUT_ERROR
    return surveyed, skipped


def _jobs(requested: int | None, settings: Settings, sources: Sequence[str | Path]) -> int:
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
        total = len(sample_files(samples)) * sum(len(entries) for entries in matrix.values())
        progress_tracker = _ProgressTracker("benchmark metrics measure", total)
        progress = progress_tracker
        metrics = benchmark_metrics.measure(
            python=cast(str, args.python),
            samples=samples,
            matrix_path=cast(Path, args.matrix),
            config=cast(Path, args.config),
            out=cast(Path, args.out),
            label=cast(str, args.label),
            chars_per_token=cast(float, args.chars_per_token),
            jobs=cast(int, args.jobs),
            on_progress=lambda amount: progress_tracker.advance("Measuring runs", amount),
            on_campaign_complete=progress_tracker.report,
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


def _run_benchmark_runtime(args: argparse.Namespace) -> int:
    """Measure the runtime of ``events`` on one or two revisions, or write the report of a measurement."""
    command = f"tinarrative benchmark runtime {args.runtime_command}"
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
    sides = [benchmark_runtime.Side("head", cast(str, args.python), cast(str, args.label))]
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


@dataclass(frozen=True)
class _SequenceRun:
    """The analyzed campaign of a save-input command: what ``events`` reports and ``narrate`` packages."""

    plan: SequencePlan
    intervals: list[IntervalResult]
    campaign: CampaignGroup
    surveyed: int
    narrative: list[Event] | None


def _run_saves(
    command: str,
    paths: list[Path],
    selector: str | None,
    settings: Settings,
    *,
    inferred: bool,
    changes: bool,
    narrative: bool,
    jobs: int | None = None,
) -> _SequenceRun | int:
    """Survey the inputs, choose the campaign and analyze its saves in order; a failure is printed and returned as
    the exit code. ``jobs`` is ``--jobs``; unset falls back to the settings, then to ``workers.default_jobs``."""
    inputs = expand_inputs(paths)
    if len(inputs) < 2:
        print(f"tinarrative {command}: at least two saves are required", file=sys.stderr)
        return EXIT_USAGE_ERROR
    logger.info("%s start %s", command, fields(inputs=len(paths), candidates=len(inputs)))
    progress = _ProgressTracker(command, len(inputs))
    survey_jobs = _jobs(jobs, settings, [item.path for item in inputs if not item.empty_directory])
    outcome = _survey_inputs(command, inputs, progress, survey_jobs)
    if isinstance(outcome, int):
        progress.finish()
        return outcome
    surveyed, skipped = outcome
    if len(surveyed) < 2:
        print(
            f"tinarrative {command}: at least two saves are required ({len(surveyed)} usable, {len(skipped)} skipped)",
            file=sys.stderr,
        )
        progress.finish()
        return EXIT_USAGE_ERROR
    campaign = _choose_campaign(command, group_saves(surveyed), selector)
    if isinstance(campaign, int):
        progress.finish()
        return campaign
    if len(campaign.members) < 2:
        print(
            f"tinarrative {command}: at least two saves are required (campaign {campaign.key} has "
            f"{len(campaign.members)})",
            file=sys.stderr,
        )
        progress.finish()
        return EXIT_USAGE_ERROR
    plan = plan_sequence(campaign.members, skipped)
    interval_jobs = _jobs(jobs, settings, [save.source for save in plan.saves])
    logger.debug("%s jobs %s", command, fields(survey=survey_jobs, intervals=interval_jobs))
    progress.update("Processing saves", 0, len(plan.saves))
    loaded_saves = 0

    def on_save() -> None:
        nonlocal loaded_saves
        loaded_saves += 1
        progress.update("Processing saves", loaded_saves, len(plan.saves))

    try:
        intervals = list(
            run_sequence(
                plan,
                inferred=inferred or narrative,
                changes=changes,
                load=_SnapshotLoader(command),
                significance=settings.narrative.significance,
                jobs=interval_jobs,
                on_save=on_save,
            )
        )
    except _LoadFailed as failure:
        print(failure.message, file=sys.stderr)
        progress.finish()
        return failure.code
    events = narrative_events(intervals, narrative_rules(settings.narrative)) if narrative else None
    memory_line()
    progress.finish()
    return _SequenceRun(plan, intervals, campaign, len(surveyed), events)


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
    inputs = expand_inputs(paths)
    career: list[Event] = []
    profile: CampaignProfile | None = None
    if len(inputs) == 1:
        latest = inputs[0].path
    else:
        run = _run_saves(
            "councilors",
            paths,
            cast("str | None", args.campaign),
            settings,
            inferred=False,
            changes=False,
            narrative=False,
            jobs=cast("int | None", args.jobs),
        )
        if isinstance(run, int):
            return run
        career = event_stream(run.intervals)
        newest = run.plan.saves[-1]
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
    items = [
        _SendItem(index, f"article {index}", request, request_sha256(request), note=f" ({entry['name']})")
        for (index, request), entry in zip(article_requests(dossier), dossier["councilors"], strict=True)
    ]
    sys.stdout.write(_dossier_summary(dossier))
    if output is not None:
        try:
            output.mkdir(parents=True, exist_ok=True)
            text = json.dumps(dossier, indent=2, ensure_ascii=False) + "\n"
            (output / "dossier.json").write_text(text, encoding="utf-8", newline="\n")
            _write_requests(output, items)
        except OSError as error:
            return _output_failed(output, error, "councilors")
        sys.stdout.write(f"Wrote dossier.json and {_count(len(items), 'request')} to {output}.\n")
    else:
        sys.stdout.write("Nothing written; give --output DIR for the dossier and the requests.\n")
    sys.stdout.flush()
    code = EXIT_SUCCESS
    outcomes: list[_Outcome] = []
    if target is not None and output is not None:
        outcomes, code = _send(
            items,
            narrator,
            target,
            output,
            command="councilors",
            noun="article",
            force=bool(args.force),
            stop_on_failure=False,
        )
        if code != EXIT_OUTPUT_ERROR:
            assembled = _write_articles(output, dossier, outcomes, narrator, target)
            if assembled != EXIT_SUCCESS:
                code = assembled
    logger.info(
        "councilors done %s",
        fields(
            saves=len(inputs),
            selected=len(dossier["councilors"]),
            written=output is not None,
            sent=sum(outcome.record is not None and not outcome.kept for outcome in outcomes) if target else None,
            kept=sum(outcome.kept for outcome in outcomes) if target else None,
            failed=sum(outcome.record is None for outcome in outcomes) if target else None,
            exit=code,
        ),
    )
    return code


def _write_articles(
    directory: Path,
    dossier: dict[str, Any],
    outcomes: Sequence[_Outcome],
    narrator: NarratorSettings,
    target: Endpoint,
) -> int:
    """Assemble ``councilors.md`` and ``manifest.json`` from the run's outcomes; a failed article is listed in the
    manifest with its finish and the reason, and the missing ones are summed up in one stderr line."""
    sent_with = {
        "provider": target.provider,
        "model": narrator.model,
        "max_output_tokens": narrator.max_output_tokens,
        "temperature": narrator.temperature,
    }
    stored: dict[int, dict[str, Any]] = {}
    for outcome in outcomes:
        if outcome.record is not None:
            stored[outcome.item.index] = outcome.record
        elif outcome.error is not None:
            stored[outcome.item.index] = {**sent_with, "finish": outcome.finish, "error": outcome.error}
    markdown, manifest = assemble_articles(dossier, stored, generated=_now(), version=__version__, sent_with=sent_with)
    for name, text in (
        ("councilors.md", markdown),
        ("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"),
    ):
        try:
            (directory / name).write_text(text, encoding="utf-8", newline="\n")
        except OSError as error:
            return _output_failed(directory / name, error, "councilors")
    absent = missing(manifest)
    total = len(manifest["articles"])
    logger.info("councilors assembled %s", fields(articles=total, written=total - len(absent), missing=len(absent)))
    sys.stdout.write(f"Wrote councilors.md and manifest.json to {directory}.\n")
    sys.stdout.flush()
    if absent:
        print(
            f"tinarrative councilors: {len(absent)} of {_count(total, 'article')} missing; see "
            f"{directory / 'manifest.json'}",
            file=sys.stderr,
        )
    return EXIT_SUCCESS


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
    run = _run_saves(
        "events",
        cast(list[Path], args.saves),
        cast("str | None", args.campaign),
        settings,
        inferred=args.inferred,
        changes=args.changes,
        narrative=args.narrative,
        jobs=cast("int | None", args.jobs),
    )
    if isinstance(run, int):
        return run
    plan, intervals, campaign, narrative = run.plan, run.intervals, run.campaign, run.narrative
    minimum = Significance(cast(str, args.min_significance))
    constituents = cast(Constituents, args.constituents)
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
        rendered = json.dumps(document, indent=2, ensure_ascii=True) + "\n"
    else:
        left_out = run.surveyed - len(campaign.members)
        rendered = render_sequence(
            plan,
            intervals,
            min_significance=minimum,
            constituents=constituents,
            campaign=campaign,
            left_out=left_out,
            narrative=narrative,
            changed_settings={
                key: value for key, value in settings.differences(DEFAULT_SETTINGS).items() if key.startswith("events.")
            },
            period=cast(Period, args.period),
        )
    sys.stdout.write(rendered)
    sys.stdout.flush()
    logger.info(
        "events done %s",
        fields(
            saves=len(plan.saves),
            intervals=len(intervals),
            skipped=len(plan.skipped),
            events=len(event_stream(intervals)),
            narrative=None if narrative is None else len(narrative),
            exit=EXIT_SUCCESS,
        ),
    )
    return EXIT_SUCCESS


def _run_narrate(args: argparse.Namespace) -> int:
    """Cut a narrator package into chapters under the token budget and build each chapter's request; with ``--send``,
    send the requests to the configured provider and assemble the history; with ``--assemble``, only assemble."""
    assembled = cast("Path | None", args.assemble)
    if assembled is not None:
        given = [flag for flag, key in _ASSEMBLE_EXCLUDED if getattr(args, key) not in (None, False, [])]
        if given:
            print(f"tinarrative narrate: --assemble reads DIR only; drop {', '.join(given)}", file=sys.stderr)
            return EXIT_USAGE_ERROR
        return _assemble(assembled)
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
    if output is not None:
        try:
            _write_narration(output, plan)
        except OSError as error:
            return _output_failed(output, error)
    sys.stdout.write(_render_plan(plan, output))
    sys.stdout.flush()
    sent = kept = 0
    code = EXIT_SUCCESS
    if target is not None and output is not None:
        outcomes, code = _send(
            _chapter_items(plan),
            narrator,
            target,
            output,
            command="narrate",
            noun="chapter",
            force=bool(args.force),
            stop_on_failure=True,
        )
        sent = sum(outcome.record is not None and not outcome.kept for outcome in outcomes)
        kept = sum(outcome.kept for outcome in outcomes)
        if code == EXIT_SUCCESS:
            code = _assemble(output)
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


def _transport() -> Transport:
    """The HTTP transport of ``narrate --send``; tests replace it with a fake."""
    return UrllibTransport()


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


class _RateLimitStatus:
    """Show and clear the expected retry time on one terminal line."""

    def __init__(self) -> None:
        self.width = 0

    def wait(self, seconds: float) -> None:
        if not sys.stderr.isatty():
            return
        expected = (datetime.now().astimezone() + timedelta(seconds=seconds)).strftime("%H:%M:%S")
        label = f"tinarrative: rate limit wait; next attempt expected at {expected}"
        sys.stderr.write("\r" + label + " " * max(self.width - len(label), 0))
        sys.stderr.flush()
        self.width = len(label)

    def clear(self) -> None:
        if not sys.stderr.isatty():
            return
        sys.stderr.write("\r" + " " * self.width + "\r")
        sys.stderr.flush()
        self.width = 0


def _now() -> datetime:
    """The generation time of an assembled history; tests replace it."""
    return datetime.now(UTC)


@dataclass(frozen=True)
class _SendItem:
    """One request of a ``--send`` run: ``label`` names it in messages, ``note`` ends its stdout line and ``extra``
    members follow ``finish`` in its response record."""

    index: int
    label: str
    request: dict[str, Any]
    request_sha256: str
    extra: dict[str, Any] = field(default_factory=dict)
    note: str = ""


@dataclass(frozen=True)
class _Outcome:
    """``record`` is the stored or new response; without one, ``finish`` and ``error`` say why."""

    item: _SendItem
    record: dict[str, Any] | None
    kept: bool
    finish: str | None
    error: str | None


def _chapter_items(plan: ChapterPlan) -> list[_SendItem]:
    return [
        _SendItem(
            planned.index,
            f"chapter {planned.index}",
            planned.request,
            planned.request_sha256,
            {"estimate": planned.estimate},
            f" (estimate {planned.estimate})",
        )
        for planned in plan.chapters
    ]


def _send(
    items: Sequence[_SendItem],
    settings: NarratorSettings,
    target: Endpoint,
    directory: Path,
    *,
    command: str,
    noun: str,
    force: bool,
    stop_on_failure: bool,
) -> tuple[list[_Outcome], int]:
    """Send the items in order and write each completed one to ``responses/NN.json``; an item whose stored
    response was made from the same request is kept unless ``force``. A failure stops the run when
    ``stop_on_failure``, else the next item is sent. Returns the outcomes and the exit code."""
    responses = directory / "responses"
    count = len(items)
    try:
        responses.mkdir(exist_ok=True)
        _remove_stale(responses, {_chapter_file(item.index, count) for item in items})
    except OSError as error:
        return [], _output_failed(responses, error, command)
    transport = _transport()
    outcomes: list[_Outcome] = []
    stopped = False
    prepared: list[tuple[_SendItem, CompletionRequest, Path, dict[str, Any] | None, int]] = []
    impossible: list[tuple[_SendItem, int]] = []
    for item in items:
        request = completion_request(item.request, settings)
        path = responses / _chapter_file(item.index, count)
        stored = None if force else _stored(path, item.request_sha256, request, target.provider)
        reserved = estimate_tokens(request.system, request.user, settings.chars_per_token, request.max_output_tokens)
        if stored is None and settings.tokens_per_minute is not None and reserved > settings.tokens_per_minute:
            impossible.append((item, reserved))
        prepared.append((item, request, path, stored, reserved))

    if impossible:
        offending = {item.index: reserved for item, reserved in impossible}
        for item, _, _, stored, _ in prepared:
            if stored is not None:
                outcomes.append(_Outcome(item, stored, True, stored["finish"], None))
                continue
            if item.index in offending:
                reason = (
                    f"estimated request reservation {offending[item.index]} tokens exceeds "
                    f"tokens_per_minute {settings.tokens_per_minute}"
                )
            else:
                reason = "not sent because another request exceeds tokens_per_minute"
            outcomes.append(_Outcome(item, None, False, "error", reason))
            print(f"tinarrative {command}: {item.label}: {target.provider}: {reason}", file=sys.stderr)
        return outcomes, EXIT_PROVIDER_ERROR

    status = _RateLimitStatus()
    limiter = RateLimiter(
        settings.requests_per_minute,
        settings.tokens_per_minute,
        sleep=_sleep,
        on_wait=status.wait,
        on_ready=status.clear,
    )
    for item, request, path, stored, reserved in prepared:
        if stored is not None:
            outcomes.append(_Outcome(item, stored, True, stored["finish"], None))
            logger.info(
                "%s kept %s", command, fields(**{noun: item.index}, provider=target.provider, finish=stored["finish"])
            )
            sys.stdout.write(
                _render_sent(item, "kept", stored["finish"], stored.get("input_tokens"), stored.get("output_tokens"))
            )
            sys.stdout.flush()
            continue
        failure: tuple[str, str] | None = None
        try:

            def before_attempt(reservation: int = reserved) -> None:
                limiter.acquire(reservation)

            completion = complete(
                request,
                target,
                transport,
                sleep=_sleep,
                before_attempt=before_attempt,
                chapter=item.index,
            )
        except ProviderError as error:
            logger.info(
                "%s send failed %s",
                command,
                fields(**{noun: item.index}, provider=target.provider, kind=error.kind, status=error.status),
            )
            failure = ("error", str(error))
        else:
            if completion.finish in ("length", "refused", "empty"):
                logger.info(
                    "%s send failed %s",
                    command,
                    fields(**{noun: item.index}, provider=target.provider, finish=completion.finish),
                )
                reason = {
                    "length": f"the completion stopped at max_output_tokens {request.max_output_tokens}; raise "
                    "llm.max_output_tokens or give --max-output-tokens",
                    "refused": "the model refused the request",
                    "empty": "the completion has no text; run the command again to send it again",
                }[completion.finish]
                failure = (completion.finish, reason)
        if failure is not None:
            print(f"tinarrative {command}: {item.label}: {target.provider}: {failure[1]}", file=sys.stderr)
            outcomes.append(_Outcome(item, None, False, failure[0], failure[1]))
            if stop_on_failure:
                stopped = True
                break
            continue
        record = {
            "index": item.index,
            "request_sha256": item.request_sha256,
            "provider": target.provider,
            "model": request.model,
            "max_output_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "reported_model": completion.model,
            "finish": completion.finish,
            **item.extra,
            "input_tokens": completion.input_tokens,
            "output_tokens": completion.output_tokens,
            "text": completion.text,
        }
        try:
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        except OSError as error:
            return outcomes, _output_failed(path, error, command)
        outcomes.append(_Outcome(item, record, False, completion.finish, None))
        logger.info(
            "%s sent %s",
            command,
            fields(
                **{noun: item.index},
                provider=target.provider,
                finish=completion.finish,
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
                **item.extra,
                characters=len(completion.text),
            ),
        )
        sys.stdout.write(
            _render_sent(item, "sent", completion.finish, completion.input_tokens, completion.output_tokens)
        )
        sys.stdout.flush()
    failed = any(outcome.record is None for outcome in outcomes)
    if not stopped:
        sent = sum(outcome.record is not None and not outcome.kept for outcome in outcomes)
        kept = sum(outcome.kept for outcome in outcomes)
        stored_line = f", kept {kept} stored" if kept else ""
        sys.stdout.write(f"Wrote {_count(sent, 'response')} to {responses}{stored_line}.\n")
        sys.stdout.flush()
    return outcomes, EXIT_PROVIDER_ERROR if failed else EXIT_SUCCESS


def _stored(path: Path, request_sha256: str, request: CompletionRequest, provider: str) -> dict[str, Any] | None:
    """The response stored at ``path`` when it was made from the same request: the same request file and the same
    provider, model, output limit and temperature, with a finish that is kept and a non-blank text."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    sent_with = {
        "request_sha256": request_sha256,
        "provider": provider,
        "model": request.model,
        "max_output_tokens": request.max_output_tokens,
        "temperature": request.temperature,
    }
    if (
        not isinstance(record, dict)
        or any(record.get(key) != value for key, value in sent_with.items())
        or record.get("finish") not in KEPT_FINISHES
        or not isinstance(record.get("text"), str)
        or not record["text"].strip()
    ):
        return None
    return record


def _render_sent(item: _SendItem, verb: str, finish: str, input_tokens: int | None, output_tokens: int | None) -> str:
    used = (
        f"{'?' if input_tokens is None else input_tokens} input and "
        f"{'?' if output_tokens is None else output_tokens} output tokens"
    )
    return f"- {item.index} {verb}: {finish}, {used}{item.note}\n"


_FINDINGS = {
    "unmatched": ("unmatched citation", "unmatched citations"),
    "uncited": ("uncited narrative event at major and above", "uncited narrative events at major and above"),
    "undefined": ("footnote without definition", "footnotes without definition"),
    "unreferenced": ("definition without reference", "definitions without reference"),
}


def _assemble(directory: Path) -> int:
    """Assemble ``history.md`` and ``manifest.json`` from the plan, requests and responses written to ``directory``;
    audit findings are summed up in one stderr line."""
    try:
        plan = parse_plan((directory / "plan.json").read_bytes())
        count = len(plan["chapters"])
        chapters = []
        for entry in plan["chapters"]:
            name = _chapter_file(entry["index"], count)
            chapters.append(
                stored_chapter(
                    entry, _read_optional(directory / "requests" / name), _read_optional(directory / "responses" / name)
                )
            )
    except OSError as error:
        logger.debug("read failed %s", fields(output=safe_path(directory), error=type(error).__name__))
        print(f"tinarrative narrate: cannot read {directory}: {error.strerror or error}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except ValueError as error:
        print(f"tinarrative narrate: {directory}: {error}", file=sys.stderr)
        return EXIT_UNSUPPORTED_INPUT
    assembly = assemble(chapters, plan, generated=_now(), version=__version__)
    for name, text in (
        ("history.md", assembly.history),
        ("manifest.json", json.dumps(assembly.manifest, ensure_ascii=False, indent=2) + "\n"),
    ):
        try:
            (directory / name).write_text(text, encoding="utf-8", newline="\n")
        except OSError as error:
            return _output_failed(directory / name, error)
    findings = assembly.findings
    audit = assembly.manifest["audit"]
    logger.info(
        "narrate assembled %s",
        fields(
            chapters=count,
            footnotes=audit["footnotes"],
            cited_ids=audit["cited_ids"],
            **{kind: len(audit[kind] or ()) for kind in _FINDINGS},
        ),
    )
    sys.stdout.write(f"Wrote history.md and manifest.json to {directory}.\n")
    sys.stdout.flush()
    if findings:
        summary = ", ".join(f"{number} {_FINDINGS[kind][number != 1]}" for kind, number in findings.items())
        print(f"tinarrative narrate: citation audit: {summary}; see {directory / 'manifest.json'}", file=sys.stderr)
    return EXIT_SUCCESS


def _read_optional(path: Path) -> bytes | None:
    """The bytes of ``path``, or ``None`` when it does not exist."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _output_failed(path: Path, error: OSError, command: str = "narrate") -> int:
    logger.debug("output failed %s", fields(output=safe_path(path), error=type(error).__name__))
    print(f"tinarrative {command}: cannot write {path}: {error.strerror or error}", file=sys.stderr)
    return EXIT_OUTPUT_ERROR


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
    run = _run_saves(
        "narrate",
        saves,
        cast("str | None", args.campaign),
        settings,
        inferred=True,
        changes=False,
        narrative=True,
        jobs=cast("int | None", args.jobs),
    )
    if isinstance(run, int):
        return run
    document = build_document(
        run.plan,
        run.intervals,
        campaign=run.campaign,
        settings=settings,
        narrative=run.narrative,
        min_significance=Significance(cast("str | None", args.min_significance) or Significance.MAJOR.value),
        constituents=cast("Constituents | None", args.constituents) or "evidence",
    )
    package: object = json.loads(json.dumps(document))
    return package


def _write_narration(directory: Path, plan: ChapterPlan) -> None:
    """``plan.json`` and ``requests/NN.json``."""
    _write_requests(directory, _chapter_items(plan))
    text = json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n"
    (directory / "plan.json").write_text(text, encoding="utf-8", newline="\n")


def _write_requests(directory: Path, items: Sequence[_SendItem]) -> None:
    """``requests/NN.json``; numbered requests left from a longer run are removed."""
    requests = directory / "requests"
    requests.mkdir(parents=True, exist_ok=True)
    written: set[str] = set()
    for item in items:
        name = _chapter_file(item.index, len(items))
        (requests / name).write_text(render_request(item.request), encoding="utf-8", newline="\n")
        written.add(name)
    _remove_stale(requests, written)


def _chapter_file(index: int, count: int) -> str:
    """A chapter's request or response file name: two digits, more when there are more chapters."""
    return f"{index:0{max(2, len(str(count)))}d}.json"


def _remove_stale(directory: Path, kept: set[str]) -> None:
    """Remove the numbered files of ``directory`` that are not ``kept``; other files are left alone."""
    for stale in sorted(directory.glob("*.json")):
        if stale.stem.isdigit() and stale.name not in kept:
            stale.unlink()


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


def _file_time(path: str) -> float:
    """A file's modification time for ``--campaign latest``; an unreadable file counts as oldest."""
    try:
        return os.stat(path).st_mtime
    except OSError:
        return float("-inf")


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
    """The campaign to analyze; several without a selector, or a selector that matches none, opens the picker in a
    terminal and is a usage error otherwise (or when the picker is cancelled)."""
    if selector is None:
        if len(groups) == 1:
            return groups[0]
        message = f"the input holds {len(groups)} campaigns; choose one with --campaign"
    else:
        selected = select_campaign(groups, selector, _file_time)
        if isinstance(selected, CampaignGroup):
            logger.info("campaign selected %s", fields(index=selected.index, of=len(groups)))
            return selected
        message = selected
    if not _interactive():
        print(f"tinarrative {command}: {message}\n\n{render_listing(groups)}", end="", file=sys.stderr)
        return EXIT_USAGE_ERROR
    if selector is not None:
        _write_stderr(f"tinarrative {command}: {message}\n")
    picked = pick_campaign(groups, read=_prompt, write=_write_stderr, file_time=_file_time, initial=selector)
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
    outcome = _survey_inputs("campaigns", inputs)
    if isinstance(outcome, int):
        return outcome
    surveyed, skipped = outcome
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


def _add_parse_parser(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    summary = "Load and validate a save file as a supported raw save."
    parser = subcommands.add_parser(
        "parse",
        help=summary,
        description=(
            f"{summary} Reports the validated envelope and a summary of the normalized "
            "snapshot: game date, campaign day, player faction, and entity counts."
        ),
        epilog=(
            "Exit codes: 0 success; 2 usage error (including --record-unknowns without a registry); "
            "4 file cannot be read; 5 malformed data or unsupported shape, format, or game version; "
            "7 the unknowns registry cannot be read, is invalid, or cannot be written."
        ),
    )
    parser.add_argument("save", type=Path, help="Path to a single save file.")
    parser.add_argument(
        "--record-unknowns",
        action="store_true",
        help="Also fold the unknown structures met in this save into the registry (see 'tinarrative unknowns').",
    )
    _add_registry_argument(parser)
    parser.set_defaults(handler=_run_parse)


def _add_registry_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            f"Unknowns registry JSON file to update; created when missing. Overrides the {REGISTRY_ENV_VAR} "
            "environment variable."
        ),
    )


def _add_unknowns_parser(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    summary = "Scan saves for structures the parser does not describe and record them for triage."
    parser = subcommands.add_parser(
        "unknowns",
        help=summary,
        description=(
            f"{summary} Each save is normalized exactly as 'save parse' does, and every state type, field, "
            "envelope key, field shape or reference target outside the documented schema is reported with "
            "a content-free shape summary (type labels and member names only). With a registry, the findings "
            "are merged into it; entries the schema has since learned are pruned."
        ),
        epilog=(
            "Exit codes: 0 every given path was scanned (findings are not failures); 2 usage error; "
            "4 a given path cannot be read or a given directory holds no files; 5 a given file is not a "
            "supported save; 7 the registry cannot be read, is invalid, or cannot be written (report still "
            "printed). Files found inside a given directory that fail are listed as skipped and never change "
            "the exit code. 7 takes precedence over 4, and 4 over 5."
        ),
    )
    parser.add_argument(
        "paths",
        type=Path,
        nargs="+",
        metavar="PATH",
        help="Save files or directories; a directory is scanned one level deep.",
    )
    _add_registry_argument(parser)
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Report format (default %(default)s).",
    )
    parser.set_defaults(handler=_run_unknowns)


def _add_inspect_parser(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    summary = "Inspect one save file's raw structure without interpreting it."
    parser = subcommands.add_parser(
        "inspect",
        help=summary,
        description=(
            f"{summary} Reports byte-level facts, the JSON root type, top-level "
            "keys with their types and lengths, one further level of keys, and "
            "any selected JSON-pointer paths with bounded output."
        ),
        epilog=(
            "Exit codes: 0 success; 2 usage error; 4 file cannot be read; "
            "5 bytes are not decodable JSON (report still printed); "
            "6 a --path did not resolve (report still printed)."
        ),
    )
    parser.add_argument("save", type=Path, help="Path to a single save file.")
    parser.add_argument(
        "-p",
        "--path",
        action="append",
        default=[],
        metavar="POINTER",
        help=("RFC 6901 JSON pointer to print, e.g. /gamestates/Some.State/0/Value. May be repeated."),
    )
    parser.add_argument(
        "--max-items",
        type=_non_negative_int,
        default=RenderLimits.max_items,
        metavar="N",
        help="Maximum array items or object keys shown per container (default %(default)s).",
    )
    parser.add_argument(
        "--max-string",
        type=_non_negative_int,
        default=RenderLimits.max_string,
        metavar="N",
        help="Maximum string characters shown (default %(default)s).",
    )
    parser.add_argument(
        "--max-depth",
        type=_non_negative_int,
        default=RenderLimits.max_depth,
        metavar="N",
        help="Maximum nesting depth rendered for selected paths (default %(default)s).",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Report format (default %(default)s).",
    )
    parser.set_defaults(handler=_run_inspect)


def _add_diff_parser(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    summary = "Compare two campaign snapshots and report state changes."
    parser = subcommands.add_parser(
        "diff",
        help=summary,
        description=(
            f"{summary} Both saves are normalized exactly as 'save parse' does, entities are matched by "
            "their in-save ID (technologies by name), and every differing field is listed with its "
            "before and after value and its location in each save. Entities present in only one save "
            "are reported as appeared or disappeared; no cause is inferred. The saves are compared in argument "
            "order, whatever their game dates. Analyzer results and inferred events are reported by 'events'."
        ),
        epilog=(
            "Exit codes: 0 success; 2 usage error; 4 a save cannot be read; "
            "5 a save is malformed or has an unsupported shape, format, or game version."
        ),
    )
    parser.add_argument("before", type=Path, help="Path to the earlier save file.")
    parser.add_argument("after", type=Path, help="Path to the later save file.")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Report format (default %(default)s).",
    )
    parser.set_defaults(handler=_run_diff)


def _add_councilors_parser(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    summary = (
        "Select a campaign's notable councilors, build the dossier and one article request per councilor, and "
        "send them."
    )
    parser = subcommands.add_parser(
        "councilors",
        help=summary,
        description=(
            f"{summary} The dossier lists every player councilor employed long enough, plus the most prominent "
            "councilors of each other human faction (councilors.rivals_per_faction), from the latest save; with "
            "several saves it adds each councilor's career from the events between them. Stdout gets a selection "
            "summary and --output writes dossier.json and requests/NN.json. Nothing is sent without --send; with "
            "it, the requests (and so the dossier) go to the configured provider, a third party unless it runs "
            "locally, and the responses are assembled into councilors.md with a manifest.json. An article whose "
            "stored response was made from the same request is not sent again."
        ),
        epilog=(
            "Exit codes: 0 success; 2 usage error (including several campaigns without --campaign, an unknown "
            "--profile, --force without --send, or --send without --output, provider, model or API key); 4 a save "
            "cannot be read; 5 a save is not a supported save; 8 the settings file is invalid; 9 --output cannot "
            "be written; 10 an article request failed, or its completion stopped at its output limit or was "
            "refused; the other articles are written."
        ),
    )
    parser.add_argument(
        "saves",
        type=Path,
        nargs="+",
        metavar="PATH",
        help="One save, or saves and directories of one campaign, any order; a directory is read one level deep.",
    )
    parser.add_argument("--campaign", metavar="SELECTOR", help="The campaign to use when the saves hold several.")
    parser.add_argument("--player-only", action="store_true", help="Select the player's councilors only.")
    parser.add_argument(
        "--output",
        type=Path,
        metavar="DIR",
        help=(
            "Write dossier.json and requests/NN.json here; with --send also responses/NN.json, councilors.md and "
            "manifest.json."
        ),
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help=(
            "Send each article request to the provider and write responses/NN.json under --output. This hands the "
            "dossier to the provider, a third party unless it runs locally."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --send, send every article again, even one whose stored response matches its request.",
    )
    parser.add_argument(
        "--profile",
        metavar="NAME",
        help="Apply the settings profile [llm.profiles.NAME] over the [llm] keys.",
    )
    parser.add_argument("--provider", choices=PROVIDERS, help="Override llm.provider.")
    parser.add_argument("--model", help="Override llm.model (there is no default model).")
    parser.add_argument("--base-url", metavar="URL", help="Override llm.base_url.")
    parser.add_argument("--max-output-tokens", type=int, metavar="TOKENS", help="Override llm.max_output_tokens.")
    parser.add_argument("--temperature", type=float, help="Override llm.temperature.")
    parser.add_argument(
        "--config",
        type=Path,
        metavar="FILE",
        help=(
            f"A TOML settings file: the [councilors] selection and the [narrator] provider and profiles (default: "
            f"${CONFIG_ENV_VAR} if set, see docs/configuration.md)."
        ),
    )
    parser.add_argument(
        "--jobs",
        type=_positive_int,
        metavar="N",
        help=(
            "Worker processes for surveying the saves and analyzing the intervals; 1 runs everything in one process "
            "(default: processing.jobs, else bounded by the CPUs and the memory the saves need)."
        ),
    )
    parser.set_defaults(handler=_run_councilors)


def _add_events_parser(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    summary = "Order the saves of a campaign by game time and report the events of every consecutive pair."
    parser = subcommands.add_parser(
        "events",
        help=summary,
        description=(
            f"{summary} Each save is normalized exactly as 'save parse' does. Saves are ordered by their serialized "
            "game time, never by file name or argument order; byte-identical saves are merged. Every pair of "
            "consecutive saves is diffed, run through every objective analyzer and the significance rules and, "
            "with --inferred, the reconstruction rules; every event ID is qualified by its interval so that IDs "
            "are unique across the sequence. Saves are grouped by campaign first (see 'tinarrative campaigns'); "
            "when they hold more than one campaign, --campaign chooses which one to report."
        ),
        epilog=(
            "In a terminal, several campaigns without --campaign, or a --campaign that matches none or several, "
            "open a picker that takes a listing number, a key or fuzzy search text. "
            "Exit codes: 0 success; 2 usage error (including fewer than two usable saves in the chosen campaign, "
            "several campaigns without --campaign or a --campaign that matches none when stdin or stderr is not a "
            "terminal, or a cancelled picker); 4 a given path cannot be "
            "read, or a given directory holds no files or no usable save; "
            "5 a given file is malformed, has an unsupported shape, format, or game version, or has no game time. "
            "Files found inside a given directory that fail are listed as skipped and never change the exit code."
        ),
    )
    parser.add_argument(
        "saves",
        type=Path,
        nargs="+",
        metavar="PATH",
        help="Save files or directories, any order; a directory is read one level deep.",
    )
    parser.add_argument(
        "--campaign",
        metavar="SELECTOR",
        help=(
            "The campaign to report when the saves hold several: a key or unique key prefix from "
            "'tinarrative campaigns', its listing index, or 'latest' (the campaign of the most recently "
            "modified file). In a terminal, a missing or unmatched selector opens a picker instead of failing."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Report format (default %(default)s).",
    )
    parser.add_argument(
        "--min-significance",
        choices=tuple(level.value for level in SIGNIFICANCE_ORDER),
        default=Significance.TRIVIAL.value,
        help=(
            "Lowest significance an event needs to be listed (default %(default)s, which lists every event): an "
            "objective or inferred event, or with --narrative a narrative event, whose objective and inferred events "
            "follow --constituents instead; applies to the markdown and the JSON report, and omitted events are "
            "counted."
        ),
    )
    parser.add_argument(
        "--constituents",
        choices=CONSTITUENTS,
        default="none",
        help=(
            "With --narrative, which of the objective and inferred events the listed narrative events are built "
            "from (transitively and whatever their significance) to list: all of them, the narrator evidence among "
            "them, or none (default %(default)s); with all and evidence, the lower-order narrative events they cite "
            "are listed too. Ignored without --narrative."
        ),
    )
    parser.add_argument(
        "--period",
        choices=PERIODS,
        default="year",
        help=(
            "The period the markdown narrative section groups events by: year, half (H1, H2) or quarter "
            "(default %(default)s); the JSON report is not grouped."
        ),
    )
    parser.add_argument(
        "--inferred",
        action="store_true",
        help="Also reconstruct inferred events in every interval and report them with the results they rest on.",
    )
    parser.add_argument(
        "--changes",
        action="store_true",
        help="Also list every literal state change of each interval under that interval.",
    )
    parser.add_argument(
        "--narrative",
        action="store_true",
        help=(
            "Also aggregate the events of the whole sequence into narrative events and list them by period above "
            "the intervals; implies --inferred."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        metavar="FILE",
        help=(
            f"A TOML settings file for the narrative rules' thresholds and windows (default: ${CONFIG_ENV_VAR} if "
            "set, else the built-in defaults; see docs/configuration.md)."
        ),
    )
    parser.add_argument(
        "--jobs",
        type=_positive_int,
        metavar="N",
        help=(
            "Worker processes for surveying the saves and analyzing the intervals; 1 runs everything in one process "
            "(default: processing.jobs, else bounded by the CPUs and the memory the saves need)."
        ),
    )
    parser.set_defaults(handler=_run_events)


def _add_narrate_parser(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    summary = (
        "Cut a campaign's narrator package into chapters under a token budget, build their LLM requests and send them."
    )
    parser = subcommands.add_parser(
        "narrate",
        help=summary,
        description=(
            f"{summary} The package is built from the saves exactly as 'events --narrative --constituents evidence "
            "--format json' builds it, or read with --package. Each chapter is a run of whole periods whose "
            "estimated request stays within llm.max_input_tokens; it carries the narrative events that start in "
            "it, its opening and closing situation and a continuity member, and is the same schema as the package. "
            "With --output the plan and one request per chapter are written. Nothing is sent without --send; with "
            "it, the requests (and so the campaign) go to the configured provider, a third party unless it runs "
            "locally, and the responses are assembled into history.md with a citation audit in manifest.json. A "
            "chapter whose stored response was made from the same request is not sent again."
        ),
        epilog=(
            "Exit codes: 0 success; 2 usage error (including --package with save paths, --campaign, "
            "--min-significance or --constituents, a package with no interval, a single interval over the token "
            "budget, an unknown --profile, or --send without --output, provider, model or API key, or over the "
            "context window); 4 a save or the package cannot be read; 5 a save is not a supported save, or the "
            "package is not valid JSON or not a narrator package; 8 the settings file is invalid; 9 --output cannot "
            "be written; 10 a provider request failed, or a completion stopped at its output limit or was refused. "
            "With --assemble: 2 another option was given; 4 DIR or its plan.json cannot be read; 5 a request or "
            "response is missing, invalid or does not match the plan; 9 the history cannot be written."
        ),
    )
    parser.add_argument(
        "saves",
        type=Path,
        nargs="*",
        metavar="PATH",
        help="Save files or directories, any order; a directory is read one level deep.",
    )
    parser.add_argument(
        "--package",
        metavar="FILE",
        help="A narrator package ('events --narrative --format json') to narrate as built; '-' reads stdin.",
    )
    parser.add_argument(
        "--campaign",
        metavar="SELECTOR",
        help="The campaign to narrate when the saves hold several (as 'events --campaign').",
    )
    parser.add_argument(
        "--min-significance",
        choices=tuple(level.value for level in SIGNIFICANCE_ORDER),
        default=None,
        help=(
            "Lowest significance of a listed narrative event when building from saves (default major); the atomic "
            "stream keeps only the constituents of the listed narrative events."
        ),
    )
    parser.add_argument(
        "--constituents",
        choices=CONSTITUENTS,
        default=None,
        help=(
            "Which constituents of the listed narrative events the atomic stream keeps when building from saves, as "
            "'events --constituents' does (default evidence)."
        ),
    )
    parser.add_argument(
        "--period",
        choices=PERIODS,
        help=(
            "The sections of the history and the unit chapters are cut by (default: from the campaign span, using "
            "the built-in quarter and half-year spans, made coarser chapter by chapter where the "
            "saves are further apart than the period runs). A given period is kept, with a warning where the "
            "saves are too sparse for it."
        ),
    )
    parser.add_argument("--audience", choices=AUDIENCES, help="Who the history is for (prompt default public).")
    parser.add_argument("--citations", choices=CITATIONS, help="Footnotes citing event IDs (prompt default) or none.")
    parser.add_argument("--style", choices=STYLES, help="Chronicle (prompt default) or headlines.")
    parser.add_argument(
        "--length",
        type=_positive_int,
        metavar="WORDS",
        help=(
            "A target length for the whole history, shared out across chapters by their narrative weight "
            "(default: from the narrative weight)."
        ),
    )
    parser.add_argument(
        "--focus",
        help="A faction or nation to centre the account on (default: the player faction for an insider audience).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        metavar="DIR",
        help="Write plan.json and requests/NN.json here; without it only the plan summary is printed.",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help=(
            "Send each chapter request to the provider and write responses/NN.json under --output. This hands the "
            "campaign to the provider, a third party unless it runs locally."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --send, send every chapter again, even one whose stored response matches its request.",
    )
    parser.add_argument(
        "--assemble",
        type=Path,
        metavar="DIR",
        help=(
            "Assemble history.md and manifest.json from the plan, requests and responses already in DIR; sends "
            "nothing and takes no other option."
        ),
    )
    parser.add_argument(
        "--profile",
        metavar="NAME",
        help="Apply the settings profile [llm.profiles.NAME] over the [llm] keys.",
    )
    parser.add_argument("--provider", choices=PROVIDERS, help="Override llm.provider.")
    parser.add_argument("--model", help="Override llm.model (there is no default model).")
    parser.add_argument("--base-url", metavar="URL", help="Override llm.base_url.")
    parser.add_argument("--max-input-tokens", type=int, metavar="TOKENS", help="Override llm.max_input_tokens.")
    parser.add_argument("--max-output-tokens", type=int, metavar="TOKENS", help="Override llm.max_output_tokens.")
    parser.add_argument("--temperature", type=float, help="Override llm.temperature.")
    parser.add_argument(
        "--config",
        type=Path,
        metavar="FILE",
        help=(
            f"A TOML settings file: the narrative rules, and the [narrator] budget, provider and profiles (default: "
            f"${CONFIG_ENV_VAR} if set, else the built-in defaults; see docs/configuration.md)."
        ),
    )
    parser.add_argument(
        "--jobs",
        type=_positive_int,
        metavar="N",
        help=(
            "Worker processes for surveying the saves and analyzing the intervals; 1 runs everything in one process "
            "(default: processing.jobs, else bounded by the CPUs and the memory the saves need)."
        ),
    )
    parser.set_defaults(handler=_run_narrate)


def _add_campaigns_parser(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    summary = "List the campaigns that saves belong to, with the selector for 'events --campaign'."
    parser = subcommands.add_parser(
        "campaigns",
        help=summary,
        description=(
            f"{summary} Saves belong to one campaign when the human player's faction, the faction name, the "
            "scenario and the real-world campaign start all match; a save without exactly one resolvable human "
            "player is listed on its own. Only the time and identity of each save are read; nothing is analyzed."
        ),
        epilog=(
            "Exit codes: 0 success; 2 usage error; 4 a given path cannot be read, or a given directory holds no "
            "files or no usable save; 5 a given file is malformed, has an unsupported shape, format, or game "
            "version, or has no game time. Files found inside a given directory that fail are listed as skipped "
            "and never change the exit code."
        ),
    )
    parser.add_argument(
        "saves",
        type=Path,
        nargs="+",
        metavar="PATH",
        help="Save files or directories, any order; a directory is read one level deep.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Report format (default %(default)s).",
    )
    parser.set_defaults(handler=_run_campaigns)


def _add_benchmark_parser(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subcommands.add_parser("benchmark", help="Manage benchmark samples.")
    commands = parser.add_subparsers(dest="benchmark_command", metavar="COMMAND", required=True)
    sample = commands.add_parser(
        "sample",
        help="Import or refresh a campaign in benchmarks/samples/.",
        description=(
            "Import save files into benchmarks/samples/ and refresh samples.json. A single directory is grouped by "
            "campaign; choose one with --campaign or the interactive picker. Refresh replaces the named campaign."
        ),
        epilog=(
            "Progress is written to stderr in a terminal. After import, review samples.json and matrix.toml; "
            "add a campaign description if one is not already present."
        ),
    )
    sample.add_argument("name", help="Name of the campaign directory to create or replace.")
    sample.add_argument("paths", type=Path, nargs="+", metavar="PATH", help="One directory or save file paths.")
    sample.add_argument("--description", help="Campaign description to write to samples.json.")
    sample.add_argument("--campaign", metavar="SELECTOR", help="Campaign to import from a directory input.")
    sample.set_defaults(handler=_run_benchmark_sample)

    metrics = commands.add_parser("metrics", help="Measure and compare narrator package sizes.")
    metric_commands = metrics.add_subparsers(dest="metrics_command", metavar="OPERATION", required=True)
    samples = metric_commands.add_parser("samples", help=f"Verify the sample files against {MANIFEST}, or rewrite it.")
    samples.add_argument("--samples", type=Path, default=BENCHMARK_SAMPLES_DIR)
    samples.add_argument("--update", action="store_true", help="Rewrite the manifest from the files.")
    samples.set_defaults(handler=_run_benchmark_metrics)

    measure = metric_commands.add_parser("measure", help="Run the matrix and write metrics.json.")
    measure.add_argument("--python", default=sys.executable, help="The interpreter with the tinarrative to measure.")
    measure.add_argument("--samples", type=Path, default=BENCHMARK_SAMPLES_DIR)
    measure.add_argument("--matrix", type=Path, default=BENCHMARK_ROOT / "matrix.toml")
    measure.add_argument("--config", type=Path, default=BENCHMARK_ROOT / "config.toml")
    measure.add_argument("--out", type=Path, required=True)
    measure.add_argument("--label", default="working tree", help="What is measured, for example a commit.")
    measure.add_argument("--chars-per-token", type=_positive_float, default=2.4)
    measure.add_argument("--jobs", type=_positive_int, default=os.cpu_count() or 1, help="Commands to run at once.")
    measure.set_defaults(handler=_run_benchmark_metrics)

    compare = metric_commands.add_parser("compare", help="Write the Markdown report of two metrics files.")
    compare.add_argument("base", type=Path)
    compare.add_argument("head", type=Path)
    compare.add_argument("--out", type=Path, help="Where to write the report (default: stdout).")
    compare.add_argument("--threshold", type=float, default=1.0, help="Highlight changes of at least this per cent.")
    compare.add_argument("--run-url", help="The CI run whose artifact holds the outputs.")
    compare.set_defaults(handler=_run_benchmark_metrics)

    runtime = commands.add_parser("runtime", help="Measure and report the processing runtime of events.")
    runtime_commands = runtime.add_subparsers(dest="runtime_command", metavar="OPERATION", required=True)
    timed = runtime_commands.add_parser("measure", help="Time one events run per campaign and write runtime JSON.")
    timed.add_argument("--python", default=sys.executable, help="The interpreter with the tinarrative to measure.")
    timed.add_argument("--label", default="working tree", help="What is measured, for example a commit.")
    timed.add_argument("--base-python", help="A second interpreter to measure as the base, alternating with --python.")
    timed.add_argument("--base-label", default="base", help="What the base is, for example a commit.")
    timed.add_argument(
        "--samples",
        type=Path,
        default=BENCHMARK_SAMPLES_DIR,
        help=f"Benchmark samples (a directory with {MANIFEST}), or one directory of saves.",
    )
    timed.add_argument("--campaign", help="Passed to events as --campaign, for a directory of several campaigns.")
    timed.add_argument("--matrix", type=Path, default=BENCHMARK_ROOT / "matrix.toml")
    timed.add_argument("--run", default="major", help="The events run of the matrix to time (default major).")
    timed.add_argument("--config", type=Path, default=BENCHMARK_ROOT / "config.toml")
    timed.add_argument("--repeats", type=_positive_int, default=1, help="Runs per side; the fastest is kept.")
    timed.add_argument("--out", type=Path, required=True, help="The runtime JSON file to write.")
    timed.set_defaults(handler=_run_benchmark_runtime)

    reported = runtime_commands.add_parser("report", help="Write the Markdown report of a runtime JSON file.")
    reported.add_argument("runtime", type=Path)
    reported.add_argument("--out", type=Path, help="Where to write the report (default: stdout).")
    reported.add_argument("--run-url", help="The CI run whose artifact holds the measurements.")
    reported.set_defaults(handler=_run_benchmark_runtime)


def _add_save_parser(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    summary = "Inspect, parse or diff individual save files."
    parser = subcommands.add_parser(
        "save",
        help=summary,
        description=(
            f"{summary} These commands report the evidence of one save, or the literal changes between two, "
            "without analyzing anything; campaign history is reported by 'events'."
        ),
        epilog="Exit codes: 2 usage error (including a missing COMMAND); each command documents its own codes.",
    )
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
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--log-level",
        choices=tuple(LEVELS),
        default=None,
        metavar="LEVEL",
        help=(
            f"Diagnostic log level written to stderr: {', '.join(LEVELS)}. Overrides the "
            f"{ENV_VAR} environment variable; default {DEFAULT_LEVEL}. Must precede COMMAND."
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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface and return a stable process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
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
