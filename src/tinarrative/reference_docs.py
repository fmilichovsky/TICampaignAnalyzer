"""The generated regions of the command pages: synopsis, options and exit codes, rendered from the CLI parser.

``make docs`` rewrites them; ``--check`` fails when a page is stale. Everything outside the markers is hand-written.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from .cli import EXIT_CODES, build_parser

COMMANDS_DIR = Path("docs/commands")
KINDS = ("synopsis", "options", "exit-codes")
USAGE_WIDTH = 100
ROOT = "tinarrative"
_REGION = re.compile(
    r"<!-- generated: (?P<kind>[a-z-]+) (?P<command>[a-z ]+) -->\n(?P<body>.*?)<!-- end generated -->",
    re.DOTALL,
)
_MARKER = re.compile(r"<!-- (?:generated:|end generated)")


class DocsError(ValueError):
    """A page or the parser breaks a rule of the generated regions; the message names what to fix."""


@dataclass(frozen=True)
class Region:
    kind: str
    command: str


def parsers(parser: argparse.ArgumentParser) -> Iterator[argparse.ArgumentParser]:
    """``parser`` and every parser below it."""
    yield parser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for child in dict.fromkeys(action.choices.values()):
                yield from parsers(child)


def _is_leaf(parser: argparse.ArgumentParser) -> bool:
    return not any(isinstance(action, argparse._SubParsersAction) for action in parser._actions)


def _documented(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    return [
        action
        for action in parser._actions
        if not isinstance(action, (argparse._HelpAction, argparse._SubParsersAction))
    ]


def _check_help(command: str, action: argparse.Action) -> None:
    name = "/".join(action.option_strings) or action.dest
    text = action.help
    if not text or text == argparse.SUPPRESS:
        raise DocsError(f"{command} {name}: every option needs a help string")
    static = action.default not in (None, False, [], argparse.SUPPRESS)
    if static and "%(default)s" not in text:
        raise DocsError(f"{command} {name}: a static default is shown with %(default)s, not restated")
    if not static and "%(default)s" in text:
        raise DocsError(f"{command} {name}: %(default)s needs a static default; name the setting instead")


def synopsis(parser: argparse.ArgumentParser) -> str:
    formatter = argparse.HelpFormatter(prog=parser.prog, width=USAGE_WIDTH)
    actions = [action for action in parser._actions if not isinstance(action, argparse._HelpAction)]
    formatter.add_usage(parser.usage, actions, parser._mutually_exclusive_groups, prefix="")
    return f"```\n{formatter.format_help().strip()}\n```"


def _option(action: argparse.Action) -> str:
    if action.choices is not None and not isinstance(action, argparse._SubParsersAction):
        value = "|".join(str(choice) for choice in action.choices)
    elif action.nargs == 0:
        value = ""
    else:
        metavar = action.metavar if isinstance(action.metavar, str) else action.dest.upper()
        value = f"{metavar}..." if action.nargs in ("+", "*") else metavar
    if not action.option_strings:
        return f"`{value}`"
    flags = ", ".join(action.option_strings)
    return f"`{flags} {value}`" if value else f"`{flags}`"


def options(command: str, parser: argparse.ArgumentParser) -> str:
    formatter = argparse.HelpFormatter(prog=parser.prog)
    rows = ["| Option | Meaning |", "| --- | --- |"]
    for action in _documented(parser):
        _check_help(command, action)
        meaning = formatter._expand_help(action)
        rows.append(f"| {_cell(_option(action))} | {_cell(meaning)} |")
    return "\n".join(rows)


def exit_codes(command: str) -> str:
    rows = ["| Code | When |", "| --- | --- |"]
    for code, meaning in EXIT_CODES[command]:
        rows.append(f"| {code} | {_cell(meaning[0].upper() + meaning[1:])} |")
    return "\n".join(rows)


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def render(region: Region, by_command: dict[str, argparse.ArgumentParser]) -> str:
    parser = by_command.get(region.command)
    if parser is None:
        raise DocsError(f"generated region names an unknown command: {region.command!r}")
    if region.kind not in KINDS:
        raise DocsError(f"{region.command}: unknown region kind {region.kind!r}; use one of {', '.join(KINDS)}")
    if region.command == ROOT:
        if region.kind != "options":
            raise DocsError(f"{ROOT}: only the global options are generated")
        return options(ROOT, parser)
    if not _is_leaf(parser):
        raise DocsError(f"{region.command}: a command group has no generated regions; document its commands")
    if region.kind == "synopsis":
        return synopsis(parser)
    if region.kind == "options":
        return options(region.command, parser)
    return exit_codes(region.command)


def _commands() -> dict[str, argparse.ArgumentParser]:
    by_command = {}
    for parser in parsers(build_parser()):
        command = parser.prog.removeprefix(f"{ROOT} ") if parser.prog != ROOT else ROOT
        by_command[command] = parser
    leaves = {command for command, parser in by_command.items() if command != ROOT and _is_leaf(parser)}
    if leaves != set(EXIT_CODES):
        raise DocsError(
            f"EXIT_CODES must list exactly the leaf commands; differs by {sorted(leaves ^ set(EXIT_CODES))}"
        )
    return by_command


def generate(directory: Path) -> dict[Path, str]:
    """Every page in ``directory`` with its generated regions rendered; raises ``DocsError`` on any broken rule."""
    by_command = _commands()
    seen: dict[Region, Path] = {}
    pages = {}
    for page in sorted(directory.glob("*.md")):
        text = page.read_text(encoding="utf-8")

        def replace(match: re.Match[str], page: Path = page) -> str:
            region = Region(match["kind"], match["command"])
            if region in seen:
                raise DocsError(f"{page}: {region.kind} {region.command} is already generated in {seen[region]}")
            seen[region] = page
            opening = f"<!-- generated: {region.kind} {region.command} -->"
            return f"{opening}\n{render(region, by_command)}\n<!-- end generated -->"

        rendered = _REGION.sub(replace, text)
        if len(_MARKER.findall(text)) != 2 * len(_REGION.findall(text)):
            raise DocsError(f"{page}: a generated marker is malformed or unclosed")
        pages[page] = rendered
    required = {Region(kind, command) for command in EXIT_CODES for kind in KINDS} | {Region("options", ROOT)}
    missing = sorted(f"{region.kind} {region.command}" for region in required - set(seen))
    if missing:
        raise DocsError(f"no page generates: {', '.join(missing)}")
    return pages


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="make docs", description="Rewrite the generated regions of the docs.")
    parser.add_argument("--check", action="store_true", help="Fail when a page is stale instead of rewriting it.")
    parser.add_argument("--dir", type=Path, default=COMMANDS_DIR, help="The command pages (default %(default)s).")
    args = parser.parse_args(argv)
    try:
        pages = generate(args.dir)
    except DocsError as error:
        print(f"make docs: {error}", file=sys.stderr)
        return 1
    stale = [page for page, text in pages.items() if page.read_text(encoding="utf-8") != text]
    if args.check:
        for page in stale:
            print(f"{page} is stale; run make docs", file=sys.stderr)
        return 1 if stale else 0
    for page in stale:
        page.write_text(pages[page], encoding="utf-8", newline="\n")
        print(f"updated {page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
