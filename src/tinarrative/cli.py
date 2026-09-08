"""Command-line entry point for the analyzer."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from typing import cast

EXIT_SUCCESS = 0
EXIT_USAGE_ERROR = 2
EXIT_NOT_IMPLEMENTED = 3


def _not_implemented(command: str) -> int:
    """Report a pipeline stage that has not been implemented yet."""
    print(
        f"tinarrative {command} is not implemented yet.",
        file=sys.stderr,
    )
    return EXIT_NOT_IMPLEMENTED


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
    for command, summary in (
        ("inspect", "Inspect a save file and report its basic metadata."),
        ("parse", "Parse a save file into a normalized campaign snapshot."),
        ("diff", "Compare two campaign snapshots and report state changes."),
    ):
        subcommand = subcommands.add_parser(command, help=summary, description=summary)
        subcommand.set_defaults(handler=lambda name=command: _not_implemented(name))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface and return a stable process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return EXIT_SUCCESS
    handler = cast(Callable[[], int], args.handler)
    return handler()


if __name__ == "__main__":
    raise SystemExit(main())
