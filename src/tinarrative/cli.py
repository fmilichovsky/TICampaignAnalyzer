"""Command-line entry point for the analyzer."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import cast

from . import __version__
from .diff import diff_states
from .diff import render_json as render_diff_json
from .diff import render_text as render_diff_text
from .inspection import RenderLimits, inspect_bytes, render_json, render_text
from .io.save_loader import load_raw_save, load_save
from .log import DEFAULT_LEVEL, ENV_VAR, LEVELS, configure_logging, fields, get_logger, safe_path
from .maintenance import REGISTRY_ENV_VAR
from .maintenance.registry import RegistryError, RegistryUpdate, record
from .maintenance.render import render_json as render_unknowns_json
from .maintenance.render import render_text as render_unknowns_text
from .maintenance.scan import ScanRun, expand_inputs, scan_inputs
from .model.snapshot import NORMALIZED_COLLECTION_LABELS, SaveSnapshot
from .model.values import Observed, to_jsonable
from .parsing.errors import SaveLoadError
from .parsing.normalization import normalize
from .parsing.unknowns import UnknownCollector

logger = get_logger(__name__)

EXIT_SUCCESS = 0
EXIT_USAGE_ERROR = 2
EXIT_NOT_IMPLEMENTED = 3
"""Reserved for commands registered before they are implemented; none is at present."""
EXIT_INPUT_ERROR = 4
"""The save path could not be read (missing, unreadable, or a directory)."""
EXIT_UNSUPPORTED_INPUT = 5
"""Bytes were read but are not decodable JSON (``inspect``, report printed) or not a
supported save: malformed, wrong shape, or unsupported format/version (``parse``)."""
EXIT_PATH_NOT_FOUND = 6
"""At least one ``--path`` did not resolve; the full report is still printed."""
EXIT_REGISTRY_ERROR = 7
"""The unknowns registry could not be read, is not a registry document, or could not be written; the report
or summary is still printed."""

Handler = Callable[[argparse.Namespace], int]


def _non_negative_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected an integer, got {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError(f"expected a value >= 0, got {value}")
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
        print(f"tinarrative inspect: cannot read {save_path}: {reason}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    logger.info("inspect start %s", fields(save=save_name, bytes=len(data), pointers=len(args.path)))
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
    logger.info("inspect done %s", fields(save=save_name, status=report.status, exit=code))
    return code


def _run_parse(args: argparse.Namespace) -> int:
    """Load and validate one save, then summarize it; failures never raise a traceback."""
    save_path = cast(Path, args.save)
    save_name = safe_path(save_path)
    logger.info("parse start %s", fields(save=save_name))
    collector = UnknownCollector()
    try:
        raw = load_raw_save(save_path)
        snapshot = normalize(raw, collector=collector)
    except OSError as error:
        reason = error.strerror or str(error)
        logger.debug("read failed %s", fields(save=save_name, errno=error.errno, error=type(error).__name__))
        print(f"tinarrative parse: cannot read {save_path}: {reason}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except SaveLoadError as error:
        logger.debug("parse failed %s", fields(save=save_name, error=type(error).__name__), exc_info=True)
        print(f"tinarrative parse: {save_path}: {error}", file=sys.stderr)
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
    print(f"unknown structures: {report.total}")

    code = EXIT_SUCCESS
    if args.record_unknowns:
        registry = _resolve_registry(args.registry)
        if registry is None:
            print(f"tinarrative parse: --record-unknowns needs --registry PATH or {REGISTRY_ENV_VAR}", file=sys.stderr)
            code = EXIT_USAGE_ERROR
        else:
            try:
                update = record(registry, [(report, raw.game_version)], format=raw.format, today=date.today())
            except RegistryError as error:
                logger.debug("registry failed %s", fields(registry=safe_path(registry)), exc_info=True)
                print(f"tinarrative parse: cannot update registry {registry}: {error}", file=sys.stderr)
                code = EXIT_REGISTRY_ERROR
            else:
                print(_registry_line(registry, update))
    logger.info(
        "parse done %s",
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
    logger.info("diff start %s", fields(before=before_name, after=after_name))
    before = _load_snapshot("diff", before_path)
    if isinstance(before, int):
        return before
    after = _load_snapshot("diff", after_path)
    if isinstance(after, int):
        return after
    diff = diff_states(before, after)
    rendered = render_diff_json(diff) if args.format == "json" else render_diff_text(diff)
    sys.stdout.write(rendered)
    sys.stdout.flush()
    logger.info(
        "diff done %s",
        fields(before=before_name, after=after_name, changes=len(diff.changes), exit=EXIT_SUCCESS),
    )
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
            f"{summary} Each save is normalized exactly as 'parse' does, and every state type, field, "
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
            f"{summary} Both saves are normalized exactly as 'parse' does, entities are matched by "
            "their in-save ID (technologies by name), and every differing field is listed with its "
            "before and after value and its location in each save. Entities present in only one save "
            "are reported as appeared or disappeared; no cause is inferred."
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
    _add_inspect_parser(subcommands)
    _add_parse_parser(subcommands)
    _add_unknowns_parser(subcommands)
    _add_diff_parser(subcommands)
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
