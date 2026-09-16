"""Command-line entry point for the analyzer."""

from __future__ import annotations

import argparse
import functools
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from .inspection import RenderLimits, inspect_bytes, render_json, render_text
from .io.save_loader import load_save

EXIT_SUCCESS = 0
EXIT_USAGE_ERROR = 2
EXIT_NOT_IMPLEMENTED = 3
EXIT_INPUT_ERROR = 4
"""The save path could not be read (missing, unreadable, or a directory)."""
EXIT_UNSUPPORTED_INPUT = 5
"""Bytes were read but could not be decoded as UTF-8 JSON; a report is printed."""
EXIT_PATH_NOT_FOUND = 6
"""At least one ``--path`` did not resolve; the full report is still printed."""

Handler = Callable[[argparse.Namespace], int]


def _not_implemented(command: str, args: argparse.Namespace) -> int:
    """Report a pipeline stage that has not been implemented yet."""
    print(
        f"tinarrative {command} is not implemented yet.",
        file=sys.stderr,
    )
    return EXIT_NOT_IMPLEMENTED


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
    try:
        data = load_save(save_path)
    except OSError as error:
        reason = error.strerror or str(error)
        print(f"tinarrative inspect: cannot read {save_path}: {reason}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    limits = RenderLimits(
        max_items=args.max_items,
        max_string=args.max_string,
        max_depth=args.max_depth,
    )
    report = inspect_bytes(data, save_path.name, args.path, limits)
    rendered = render_json(report) if args.format == "json" else render_text(report)
    sys.stdout.write(rendered)
    sys.stdout.flush()

    if report.status == "unsupported_input":
        return EXIT_UNSUPPORTED_INPUT
    if report.status == "path_not_found":
        return EXIT_PATH_NOT_FOUND
    return EXIT_SUCCESS


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tinarrative",
        description="Reconstruct Terra Invicta campaign history from save files.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    subcommands = parser.add_subparsers(
        dest="command",
        title="commands",
        metavar="COMMAND",
        description="Use 'tinarrative COMMAND --help' for command-specific help.",
    )
    _add_inspect_parser(subcommands)
    for command, summary in (
        ("parse", "Parse a save file into a normalized campaign snapshot."),
        ("diff", "Compare two campaign snapshots and report state changes."),
    ):
        subcommand = subcommands.add_parser(command, help=summary, description=summary)
        subcommand.set_defaults(handler=functools.partial(_not_implemented, command))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface and return a stable process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return EXIT_SUCCESS
    handler = cast(Handler, args.handler)
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
