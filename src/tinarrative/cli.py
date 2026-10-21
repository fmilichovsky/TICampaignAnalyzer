"""Command-line entry point for the analyzer."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

from . import __version__
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
from .log import DEFAULT_LEVEL, ENV_VAR, LEVELS, configure_logging, fields, get_logger, safe_path
from .maintenance import REGISTRY_ENV_VAR
from .maintenance.registry import RegistryError, RegistryUpdate, record
from .maintenance.render import render_json as render_unknowns_json
from .maintenance.render import render_text as render_unknowns_text
from .maintenance.scan import ScanRun, scan_inputs
from .model.events import SIGNIFICANCE_ORDER, Event, Significance
from .model.records import record_counts
from .model.snapshot import NORMALIZED_COLLECTION_LABELS, SaveSnapshot
from .model.values import Observed, to_jsonable
from .narrative import narrative_rules
from .narrator.chapters import ChapterPlan, OverBudget, PlannedChapter, base_options, plan_chapters, validate
from .narrator.providers import Endpoint, ProviderError, complete, completion_request, endpoint
from .narrator.request import AUDIENCES, CITATIONS, STYLES, render_request
from .narrator.transport import Transport, UrllibTransport
from .parsing.errors import SaveLoadError
from .parsing.normalization import normalize
from .parsing.unknowns import UnknownCollector
from .picker import pick_campaign
from .rendering.json_report import build_document
from .rendering.markdown import PERIODS, Period, render_sequence
from .sequence import (
    IntervalResult,
    SaveRef,
    SequencePlan,
    SkippedSave,
    event_stream,
    narrative_events,
    plan_sequence,
    run_sequence,
    survey,
)

logger = get_logger(__name__)

EXIT_SUCCESS = 0
EXIT_USAGE_ERROR = 2
EXIT_NOT_IMPLEMENTED = 3
"""Reserved for commands registered before they are implemented; none is at present."""
EXIT_INPUT_ERROR = 4
"""The save path could not be read (missing, unreadable, or a directory)."""
EXIT_UNSUPPORTED_INPUT = 5
"""Bytes were read but are not decodable JSON (``save inspect``, report printed) or not a
supported save: malformed, wrong shape, or unsupported format/version (``save parse``)."""
EXIT_PATH_NOT_FOUND = 6
"""At least one ``--path`` did not resolve; the full report is still printed."""
EXIT_REGISTRY_ERROR = 7
"""The unknowns registry could not be read, is not a registry document, or could not be written; the report
or summary is still printed."""
EXIT_CONFIG_ERROR = 8
"""The settings file (``--config`` or ``TINARRATIVE_CONFIG``) could not be read or is not valid settings; nothing is
printed on stdout."""
EXIT_OUTPUT_ERROR = 9
"""``narrate --output`` could not write its directory; the plan is not printed."""
EXIT_PROVIDER_ERROR = 10
"""``narrate --send``: a chapter request failed (authentication, network, an HTTP error, an invalid response) or its
completion stopped at the output limit or was refused; the chapters completed before it are kept."""

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


def _load_snapshot(command: str, save_path: Path) -> SaveSnapshot | int:
    """Load and normalize one save, or print the failure and return the exit code."""
    save_name = safe_path(save_path)
    try:
        return normalize(load_raw_save(save_path))
    except OSError as error:
        reason = error.strerror or str(error)
        logger.debug("read failed %s", fields(save=save_name, errno=error.errno, error=type(error).__name__))
        print(f"tinarrative {command}: cannot read {save_path}: {reason}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except SaveLoadError as error:
        logger.debug("parse failed %s", fields(save=save_name, error=type(error).__name__), exc_info=True)
        print(f"tinarrative {command}: {save_path}: {error}", file=sys.stderr)
        return EXIT_UNSUPPORTED_INPUT


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


class _LoadFailed(Exception):
    """A save of a sequence failed to load after ``_load_snapshot`` reported it; carries the exit code."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


def _survey(command: str, save_path: Path) -> SaveRef | int:
    """Hash one save and read its game time and profile, or print the failure and return the exit code."""
    save_name = safe_path(save_path)
    try:
        return survey(save_path)
    except OSError as error:
        reason = error.strerror or str(error)
        logger.debug("read failed %s", fields(save=save_name, errno=error.errno, error=type(error).__name__))
        print(f"tinarrative {command}: cannot read {save_path}: {reason}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except SaveLoadError as error:
        logger.debug("survey failed %s", fields(save=save_name, error=type(error).__name__), exc_info=True)
        print(f"tinarrative {command}: {save_path}: {error}", file=sys.stderr)
        return EXIT_UNSUPPORTED_INPUT


def _survey_found(command: str, item: SaveInput) -> SaveRef | SkippedSave:
    """Survey a file found inside a given directory; a failure skips it instead of stopping the run."""
    try:
        return survey(item.path)
    except OSError as error:
        reason, error_class = error.strerror or str(error), type(error).__name__
    except SaveLoadError as error:
        reason, error_class = str(error), type(error).__name__
    logger.debug("%s skipped %s", command, fields(save=safe_path(item.path), error=error_class))
    return SkippedSave(str(item.path), error_class, reason)


def _survey_inputs(command: str, inputs: Sequence[SaveInput]) -> tuple[list[SaveRef], list[SkippedSave]] | int:
    """Survey every input; only a path named on the command line can fail the run (exit 4 beats nothing found)."""
    surveyed: list[SaveRef] = []
    skipped: list[SkippedSave] = []
    usable: dict[Path, int] = {}
    for item in inputs:
        if item.empty_directory:
            print(f"tinarrative {command}: {item.path}: the directory holds no files", file=sys.stderr)
            return EXIT_INPUT_ERROR
        if item.directory is None:
            save = _survey(command, item.path)
            if isinstance(save, int):
                return save
            surveyed.append(save)
            continue
        usable.setdefault(item.directory, 0)
        found = _survey_found(command, item)
        if isinstance(found, SkippedSave):
            skipped.append(found)
        else:
            surveyed.append(found)
            usable[item.directory] += 1
    for directory, count in usable.items():
        if count == 0:
            print(f"tinarrative {command}: {directory}: the directory holds no usable save", file=sys.stderr)
            return EXIT_INPUT_ERROR
    return surveyed, skipped


def _resolve_settings(command: str, flag: Path | None) -> Settings | int:
    """``--config`` wins over ``TINARRATIVE_CONFIG``; an empty variable counts as unset, and neither gives the
    defaults. An unreadable or invalid file is ``EXIT_CONFIG_ERROR``."""
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
) -> _SequenceRun | int:
    """Survey the inputs, choose the campaign and analyze its saves in order; a failure is printed and returned as
    the exit code."""
    inputs = expand_inputs(paths)
    if len(inputs) < 2:
        print(f"tinarrative {command}: at least two saves are required", file=sys.stderr)
        return EXIT_USAGE_ERROR
    logger.info("%s start %s", command, fields(inputs=len(paths), candidates=len(inputs)))
    outcome = _survey_inputs(command, inputs)
    if isinstance(outcome, int):
        return outcome
    surveyed, skipped = outcome
    if len(surveyed) < 2:
        print(
            f"tinarrative {command}: at least two saves are required ({len(surveyed)} usable, {len(skipped)} skipped)",
            file=sys.stderr,
        )
        return EXIT_USAGE_ERROR
    campaign = _choose_campaign(command, group_saves(surveyed), selector)
    if isinstance(campaign, int):
        return campaign
    if len(campaign.members) < 2:
        print(
            f"tinarrative {command}: at least two saves are required (campaign {campaign.key} has "
            f"{len(campaign.members)})",
            file=sys.stderr,
        )
        return EXIT_USAGE_ERROR
    plan = plan_sequence(campaign.members, skipped)

    def load(source: str) -> SaveSnapshot:
        loaded = _load_snapshot(command, Path(source))
        if isinstance(loaded, int):
            raise _LoadFailed(loaded)
        return loaded

    try:
        intervals = list(run_sequence(plan, inferred=inferred or narrative, changes=changes, load=load))
    except _LoadFailed as failure:
        return failure.code
    events = narrative_events(intervals, narrative_rules(settings.narrative)) if narrative else None
    return _SequenceRun(plan, intervals, campaign, len(surveyed), events)


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
    )
    if isinstance(run, int):
        return run
    plan, intervals, campaign, narrative = run.plan, run.intervals, run.campaign, run.narrative
    minimum = Significance(cast(str, args.min_significance))
    include_constituents = cast(bool, args.include_constituents)
    if args.format == "json":
        document = build_document(
            plan,
            intervals,
            campaign=campaign,
            settings=settings,
            narrative=narrative,
            min_significance=minimum,
            include_constituents=include_constituents,
        )
        rendered = json.dumps(document, indent=2, ensure_ascii=True) + "\n"
    else:
        left_out = run.surveyed - len(campaign.members)
        rendered = render_sequence(
            plan,
            intervals,
            min_significance=minimum,
            include_constituents=include_constituents,
            campaign=campaign,
            left_out=left_out,
            narrative=narrative,
            changed_settings={
                key: value
                for key, value in settings.differences(DEFAULT_SETTINGS).items()
                if key.startswith("narrative.")
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
    send the requests to the configured provider."""
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
    if source is not None and (saves or args.campaign is not None or args.min_significance is not None):
        print(
            "tinarrative narrate: --package is narrated as it was built; drop the save paths, --campaign and "
            "--min-significance",
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
        plan = plan_chapters(package, options, narrator, length=cast("int | None", args.length))
    except ValueError as error:
        logger.debug("package invalid %s", fields(error=type(error).__name__))
        print(f"tinarrative narrate: {error}", file=sys.stderr)
        return EXIT_UNSUPPORTED_INPUT
    if isinstance(plan, OverBudget):
        print(
            f"tinarrative narrate: interval {plan.interval} needs about {plan.needed} input tokens without its atomic "
            f"stream, over max_input_tokens {plan.budget}; raise narrator.max_input_tokens",
            file=sys.stderr,
        )
        logger.info("narrate over budget %s", fields(needed=plan.needed, budget=plan.budget, exit=EXIT_USAGE_ERROR))
        return EXIT_USAGE_ERROR
    if output is not None:
        try:
            _write_narration(output, plan)
        except OSError as error:
            return _output_failed(output, error)
    sys.stdout.write(_render_plan(plan, output))
    sys.stdout.flush()
    sent = 0
    code = EXIT_SUCCESS
    if target is not None and output is not None:
        sent, code = _send(plan, narrator, target, output)
    logger.info(
        "narrate done %s",
        fields(
            chapters=len(plan.chapters),
            developments=sum(planned.developments for planned in plan.chapters),
            largest_estimate=max(planned.estimate for planned in plan.chapters),
            reduced=sum(planned.chapter.reduction is not None for planned in plan.chapters),
            written=output is not None,
            sent=sent if target is not None else None,
            exit=code,
        ),
    )
    return code


_NARRATOR_FLAGS = (
    ("--provider", "provider"),
    ("--model", "model"),
    ("--base-url", "base_url"),
    ("--max-input-tokens", "max_input_tokens"),
    ("--max-output-tokens", "max_output_tokens"),
    ("--temperature", "temperature"),
)


def _resolve_narrator(args: argparse.Namespace, narrator: NarratorSettings) -> NarratorSettings | int:
    """The ``[narrator]`` settings, then the ``--profile`` over them, then the flags over both."""
    profile = cast("str | None", args.profile)
    if profile is not None:
        try:
            narrator = narrator.with_profile(profile)
        except KeyError:
            known = ", ".join(sorted(narrator.profiles)) or "none"
            print(f"tinarrative narrate: unknown profile {profile!r} (the settings define: {known})", file=sys.stderr)
            return EXIT_USAGE_ERROR
    overridden = 0
    for flag, key in _NARRATOR_FLAGS:
        value = getattr(args, key)
        if value is None:
            continue
        try:
            narrator = override(narrator, key, value)
        except ConfigError as error:
            print(f"tinarrative narrate: {flag}: {error}", file=sys.stderr)
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


def _send(plan: ChapterPlan, settings: NarratorSettings, target: Endpoint, directory: Path) -> tuple[int, int]:
    """Send the chapters in order and write each completed one to ``responses/NN.json``; the first failure stops the
    run. Returns the number of chapters completed and the exit code."""
    responses = directory / "responses"
    count = len(plan.chapters)
    try:
        responses.mkdir(exist_ok=True)
        _remove_stale(responses, {_chapter_file(planned.index, count) for planned in plan.chapters})
    except OSError as error:
        return 0, _output_failed(responses, error)
    transport = _transport()
    for planned in plan.chapters:
        request = completion_request(planned.request, settings)
        try:
            completion = complete(request, target, transport, sleep=_sleep, chapter=planned.index)
        except ProviderError as error:
            logger.info(
                "narrate send failed %s",
                fields(chapter=planned.index, provider=target.provider, kind=error.kind, status=error.status),
            )
            print(f"tinarrative narrate: chapter {planned.index}: {target.provider}: {error}", file=sys.stderr)
            return planned.index - 1, EXIT_PROVIDER_ERROR
        if completion.finish in ("length", "refused"):
            reason = (
                f"the completion stopped at max_output_tokens {request.max_output_tokens}; raise "
                "narrator.max_output_tokens or give --max-output-tokens"
                if completion.finish == "length"
                else "the model refused the request"
            )
            logger.info(
                "narrate send failed %s",
                fields(chapter=planned.index, provider=target.provider, finish=completion.finish),
            )
            print(f"tinarrative narrate: chapter {planned.index}: {target.provider}: {reason}", file=sys.stderr)
            return planned.index - 1, EXIT_PROVIDER_ERROR
        record = {
            "index": planned.index,
            "request_sha256": planned.request_sha256,
            "provider": target.provider,
            "model": request.model,
            "max_output_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "reported_model": completion.model,
            "finish": completion.finish,
            "estimate": planned.estimate,
            "input_tokens": completion.input_tokens,
            "output_tokens": completion.output_tokens,
            "text": completion.text,
        }
        path = responses / _chapter_file(planned.index, count)
        try:
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        except OSError as error:
            return planned.index - 1, _output_failed(path, error)
        logger.info(
            "narrate sent %s",
            fields(
                chapter=planned.index,
                provider=target.provider,
                finish=completion.finish,
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
                estimate=planned.estimate,
                characters=len(completion.text),
            ),
        )
        sys.stdout.write(_render_sent(planned, completion.finish, completion.input_tokens, completion.output_tokens))
        sys.stdout.flush()
    sys.stdout.write(f"Wrote {_count(count, 'response')} to {responses}.\n")
    sys.stdout.flush()
    return count, EXIT_SUCCESS


def _render_sent(planned: PlannedChapter, finish: str, input_tokens: int | None, output_tokens: int | None) -> str:
    used = (
        f"{'?' if input_tokens is None else input_tokens} input and "
        f"{'?' if output_tokens is None else output_tokens} output tokens"
    )
    return f"- {planned.index} sent: {finish}, {used} (estimate {planned.estimate})\n"


def _output_failed(path: Path, error: OSError) -> int:
    logger.debug("output failed %s", fields(output=safe_path(path), error=type(error).__name__))
    print(f"tinarrative narrate: cannot write {path}: {error.strerror or error}", file=sys.stderr)
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
    """The narrator package of the saves, as ``events --narrative --include-constituents --format json`` builds it,
    through JSON so that it is the same value a ``--package`` file gives."""
    run = _run_saves(
        "narrate",
        saves,
        cast("str | None", args.campaign),
        settings,
        inferred=True,
        changes=False,
        narrative=True,
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
        include_constituents=True,
    )
    package: object = json.loads(json.dumps(document))
    return package


def _write_narration(directory: Path, plan: ChapterPlan) -> None:
    """``plan.json`` and ``requests/NN.json``; numbered requests left from a longer plan are removed."""
    requests = directory / "requests"
    requests.mkdir(parents=True, exist_ok=True)
    written: set[str] = set()
    for planned in plan.chapters:
        name = _chapter_file(planned.index, len(plan.chapters))
        (requests / name).write_text(render_request(planned.request), encoding="utf-8", newline="\n")
        written.add(name)
    _remove_stale(requests, written)
    text = json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n"
    (directory / "plan.json").write_text(text, encoding="utf-8", newline="\n")


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
        f"{settings.max_input_tokens} at {settings.chars_per_token} characters per token:"
    ]
    reductions = {"atomic_dropped": "; atomic stream left out", "split": "; period split at saves, no atomic stream"}
    for planned in plan.chapters:
        lines.append(
            f"- {planned.index} ({planned.part}) {planned.covers[0][:10]} to {planned.covers[1][:10]}, "
            f"{', '.join(planned.periods)}: {_count(planned.developments, 'development')}, "
            f"{planned.continuing} continuing, {planned.recalled} recalled; ~{planned.estimate} input tokens"
            f"{reductions.get(planned.chapter.reduction or '', '')}"
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
            "follow --include-constituents instead; applies to the markdown and the JSON report, and omitted events "
            "are counted."
        ),
    )
    parser.add_argument(
        "--include-constituents",
        action="store_true",
        help=(
            "With --narrative, also list the objective and inferred events the listed narrative events are built "
            "from, transitively and whatever their significance, and the lower-order narrative events they cite; "
            "without it the narrative report lists no objective or inferred event. Ignored without --narrative."
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
    parser.set_defaults(handler=_run_events)


def _add_narrate_parser(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    summary = (
        "Cut a campaign's narrator package into chapters under a token budget, build their LLM requests and send them."
    )
    parser = subcommands.add_parser(
        "narrate",
        help=summary,
        description=(
            f"{summary} The package is built from the saves exactly as 'events --narrative --include-constituents "
            "--format json' builds it, or read with --package. Each chapter is a run of whole periods whose "
            "estimated request stays within narrator.max_input_tokens; it carries the developments that start in "
            "it, its opening and closing situation and a continuity member, and is the same schema as the package. "
            "With --output the plan and one request per chapter are written. Nothing is sent without --send; with "
            "it, the requests (and so the campaign) go to the configured provider, a third party unless it runs "
            "locally."
        ),
        epilog=(
            "Exit codes: 0 success; 2 usage error (including --package with save paths, --campaign or "
            "--min-significance, a package with no interval, a single interval over the token budget, an unknown "
            "--profile, or --send without --output, provider, model or API key, or over the context window); "
            "4 a save or the package cannot be read; 5 a save is not a supported save, or the package is not "
            "valid JSON or not a narrator package; 8 the settings file is invalid; 9 --output cannot be written; "
            "10 a provider request failed, or a completion stopped at its output limit or was refused."
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
            "Lowest significance of a listed development when building from saves (default major); the atomic "
            "stream keeps only the constituents of the listed developments."
        ),
    )
    parser.add_argument(
        "--period",
        choices=PERIODS,
        help=(
            "The sections of the history and the unit chapters are cut by (default: from the campaign span, see "
            "narrator.quarter_span_days and narrator.half_span_days)."
        ),
    )
    parser.add_argument("--audience", choices=AUDIENCES, help="Who the history is for (prompt default public).")
    parser.add_argument("--citations", choices=CITATIONS, help="Footnotes citing event IDs (prompt default) or none.")
    parser.add_argument("--style", choices=STYLES, help="Chronicle (prompt default) or headlines.")
    parser.add_argument(
        "--length",
        type=_positive_int,
        metavar="WORDS",
        help="A target length for the whole history, shared out across chapters by their developments.",
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
        "--profile",
        metavar="NAME",
        help="Apply the settings profile [narrator.profiles.NAME] over the [narrator] keys.",
    )
    parser.add_argument("--provider", choices=PROVIDERS, help="Override narrator.provider.")
    parser.add_argument("--model", help="Override narrator.model (there is no default model).")
    parser.add_argument("--base-url", metavar="URL", help="Override narrator.base_url.")
    parser.add_argument("--max-input-tokens", type=int, metavar="TOKENS", help="Override narrator.max_input_tokens.")
    parser.add_argument("--max-output-tokens", type=int, metavar="TOKENS", help="Override narrator.max_output_tokens.")
    parser.add_argument("--temperature", type=float, help="Override narrator.temperature.")
    parser.add_argument(
        "--config",
        type=Path,
        metavar="FILE",
        help=(
            f"A TOML settings file: the narrative rules, and the [narrator] budget, provider and profiles (default: "
            f"${CONFIG_ENV_VAR} if set, else the built-in defaults; see docs/configuration.md)."
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
    configure_logging(level)
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
