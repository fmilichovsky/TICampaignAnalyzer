"""Read the calibration registry: the `calibration` issues and PRs, their kind and what they touch.

Standard library plus the `gh` CLI; the two machine-readable lines are described in ``calibration_registry.md``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

LABEL = "calibration"
PARENT_TITLE = "Calibration reviews"
KINDS = ("review", "value proposal", "scoring proposal", "structural finding")
GROUPS = ("types", "measures", "scalings", "themes", "principles")
FILTER_OPTIONS = {
    "types": "type",
    "measures": "measure",
    "scalings": "scaling",
    "themes": "theme",
    "principles": "principle",
}
DEFAULT_SINCE_DAYS = 90
LIST_LIMIT = 1000

EXIT_OK = 0
EXIT_GH_FAILED = 2

KIND_LINE = re.compile(r"^Calibration:(.*)$")
TOUCHES_LINE = re.compile(r"^Touches:(.*)$")
FENCE = re.compile(r"^\s*(```|~~~)")

Touches = dict[str, tuple[str, ...]]
Runner = Callable[[Sequence[str]], str]


@dataclass(frozen=True)
class Item:
    """One registry member as the tracker holds it, with whatever its two lines say."""

    number: int
    title: str
    url: str
    state: str
    is_pr: bool
    closed_at: datetime | None
    kind: str | None
    touches: Touches | None
    problems: tuple[str, ...] = field(default=())

    @property
    def complete(self) -> bool:
        return not self.problems

    def to_json(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "title": self.title,
            "url": self.url,
            "state": self.state,
            "pr": self.is_pr,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "kind": self.kind,
            "touches": {group: list(values) for group, values in self.touches.items()} if self.touches else None,
            "problems": list(self.problems),
        }


def parse_touches(text: str) -> Touches:
    """The groups of a Touches line's value; raises ``ValueError`` on a malformed one."""
    touches: Touches = {}
    for raw_group in text.split(";"):
        group_text = raw_group.strip()
        if not group_text:
            continue
        name, separator, values_text = group_text.partition("=")
        name = name.strip()
        if not separator:
            raise ValueError(f"group {group_text!r} has no '='")
        if name not in GROUPS:
            raise ValueError(f"unknown group {name!r}; expected one of {', '.join(GROUPS)}")
        if name in touches:
            raise ValueError(f"group {name!r} appears twice")
        values = tuple(value.strip().strip("`").strip() for value in values_text.split(","))
        if not values or any(not value for value in values):
            raise ValueError(f"group {name!r} has an empty value")
        touches[name] = values
    if not touches:
        raise ValueError("no group")
    return touches


def _machine_lines(body: str) -> Iterable[str]:
    """The body's lines outside fenced code blocks, so a quoted example is never read as the item's own line."""
    fenced = False
    for line in body.splitlines():
        if FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            yield line.strip()


def parse_body(body: str) -> tuple[str | None, Touches | None, tuple[str, ...]]:
    """The kind, the Touches groups and the problems found in an issue or PR body."""
    kinds: list[str] = []
    touches_texts: list[str] = []
    for line in _machine_lines(body or ""):
        if kind_match := KIND_LINE.match(line):
            kinds.append(kind_match.group(1).strip())
        elif touches_match := TOUCHES_LINE.match(line):
            touches_texts.append(touches_match.group(1))
    problems: list[str] = []

    kind: str | None = None
    if not kinds:
        problems.append("no Calibration line")
    elif len(kinds) > 1:
        problems.append("more than one Calibration line")
    elif kinds[0] not in KINDS:
        problems.append(f"unknown kind {kinds[0]!r}; expected one of {', '.join(KINDS)}")
    else:
        kind = kinds[0]

    touches: Touches | None = None
    if not touches_texts:
        problems.append("no Touches line")
    elif len(touches_texts) > 1:
        problems.append("more than one Touches line")
    else:
        try:
            touches = parse_touches(touches_texts[0])
        except ValueError as error:
            problems.append(f"malformed Touches line: {error}")
    return kind, touches, tuple(problems)


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def item_from_gh(record: Mapping[str, Any], *, is_pr: bool) -> Item:
    """An item from one record of ``gh issue list``/``gh pr list`` JSON or of the REST sub-issues listing."""
    kind, touches, problems = parse_body(str(record.get("body") or ""))
    return Item(
        number=int(record["number"]),
        title=str(record["title"]),
        url=str(record.get("url") or record.get("html_url") or ""),
        state=str(record["state"]).lower(),
        is_pr=is_pr,
        closed_at=_timestamp(record.get("closedAt", record.get("closed_at"))),
        kind=kind,
        touches=touches,
        problems=problems,
    )


def normalize_filters(raw: Mapping[str, Iterable[str]]) -> dict[str, frozenset[str]]:
    """Filter values per group, split on commas and case-folded; groups without values are dropped."""
    filters: dict[str, frozenset[str]] = {}
    for group, values in raw.items():
        folded = frozenset(part.strip().casefold() for value in values for part in value.split(",") if part.strip())
        if folded:
            filters[group] = folded
    return filters


def matches(touches: Touches | None, filters: Mapping[str, frozenset[str]]) -> bool:
    """Whether any Touches group overlaps its filter; everything matches when no filter is given."""
    if not filters:
        return True
    if touches is None:
        return False
    return any(not filters[group].isdisjoint(value.casefold() for value in touches.get(group, ())) for group in filters)


def recent(item: Item, cutoff: datetime) -> bool:
    """Open, or closed (merged included) at or after ``cutoff``."""
    if item.state == "open":
        return True
    return item.closed_at is not None and item.closed_at >= cutoff


@dataclass(frozen=True)
class Registry:
    """What one read of the tracker yields, already filtered."""

    cutoff: datetime
    filters: Mapping[str, frozenset[str]]
    parent: Item | None
    items: tuple[Item, ...]
    reviews: tuple[Item, ...]
    needs_lines: tuple[Item, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "since": self.cutoff.isoformat(),
            "filters": {group: sorted(values) for group, values in self.filters.items()},
            "parent": None
            if self.parent is None
            else {"number": self.parent.number, "title": self.parent.title, "url": self.parent.url},
            "items": [item.to_json() for item in self.items],
            "reviews": [item.to_json() for item in self.reviews],
            "needs_lines": [item.to_json() for item in self.needs_lines],
        }


def find_parent(issues: Iterable[Item]) -> Item | None:
    """The open issue titled exactly "Calibration reviews"."""
    return next((item for item in issues if item.title == PARENT_TITLE and item.state == "open"), None)


def build_registry(
    members: Iterable[Item],
    sub_issues: Iterable[Item],
    parent: Item | None,
    *,
    cutoff: datetime,
    filters: Mapping[str, frozenset[str]],
) -> Registry:
    """Split the tracker's members into complete items, open reviews and items that still need their lines.

    An item without usable lines is listed whatever the filter, since it may touch anything.
    """
    in_window = sorted(
        (item for item in members if recent(item, cutoff) and (parent is None or item.number != parent.number)),
        key=lambda item: item.number,
    )
    items = tuple(item for item in in_window if item.complete and matches(item.touches, filters))
    needs_lines = tuple(item for item in in_window if not item.complete)
    reviews = tuple(
        sorted(
            (
                item
                for item in sub_issues
                if item.state == "open" and (item.touches is None or matches(item.touches, filters))
            ),
            key=lambda item: item.number,
        )
    )
    return Registry(cutoff, filters, parent, items, reviews, needs_lines)


def gh_runner(arguments: Sequence[str]) -> str:
    """Run ``gh`` and return its standard output; raises ``RuntimeError`` with its error output on failure."""
    try:
        completed = subprocess.run(["gh", *arguments], capture_output=True, text=True, check=False)
    except FileNotFoundError as error:
        raise RuntimeError("gh is not installed or not on PATH") from error
    if completed.returncode != 0:
        raise RuntimeError(f"gh {' '.join(arguments[:2])} failed: {completed.stderr.strip()}")
    return completed.stdout


def _repo_arguments(repo: str | None) -> list[str]:
    return ["--repo", repo] if repo else []


def fetch(run: Runner, repo: str | None) -> tuple[list[Item], list[Item], Item | None]:
    """The labelled issues and PRs, the parent, and the parent's sub-issues."""
    fields = "number,title,state,body,closedAt,url"
    common = ["--label", LABEL, "--state", "all", "--limit", str(LIST_LIMIT), "--json", fields, *_repo_arguments(repo)]
    issues = [item_from_gh(record, is_pr=False) for record in json.loads(run(["issue", "list", *common]))]
    prs = [item_from_gh(record, is_pr=True) for record in json.loads(run(["pr", "list", *common]))]
    parent = find_parent(issues)
    sub_issues: list[Item] = []
    if parent is not None:
        path = f"repos/{repo or '{owner}/{repo}'}/issues/{parent.number}/sub_issues"
        output = run(["api", "--paginate", path, "--jq", ".[]"])
        sub_issues = [item_from_gh(json.loads(line), is_pr=False) for line in output.splitlines() if line.strip()]
    return [*issues, *prs], sub_issues, parent


def _touches_text(touches: Touches | None) -> str:
    if not touches:
        return ""
    return "; ".join(f"{group}={','.join(touches[group])}" for group in GROUPS if group in touches)


def _row(item: Item) -> str:
    reference = f"{'PR ' if item.is_pr else ''}#{item.number}"
    kind = item.kind or "?"
    return f"  {reference:<9} {item.state:<7} {kind:<18} {item.title}"


def render_text(registry: Registry) -> str:
    lines: list[str] = []
    window = f"open, and closed since {registry.cutoff.date().isoformat()}"
    if registry.filters:
        wanted = "; ".join(f"{group}={','.join(sorted(values))}" for group, values in registry.filters.items())
        window += f"; touching {wanted}"
    lines.append(f"Calibration registry ({window})")
    lines.append("")

    lines.append(f"Items ({len(registry.items)})")
    lines.extend(f"{_row(item)}\n{'':12}{_touches_text(item.touches)}" for item in registry.items)
    if not registry.items:
        lines.append("  none")
    lines.append("")

    if registry.parent is None:
        lines.append(f'Open reviews: no open issue titled "{PARENT_TITLE}"')
    else:
        lines.append(f"Open reviews under #{registry.parent.number} ({len(registry.reviews)})")
        for review in registry.reviews:
            lines.append(_row(review))
            lines.append(f"{'':12}{_touches_text(review.touches) or 'no Touches line'}")
        if not registry.reviews:
            lines.append("  none")
    lines.append("")

    lines.append(f"No Touches line or Calibration line ({len(registry.needs_lines)})")
    for item in registry.needs_lines:
        lines.append(_row(item))
        lines.append(f"{'':12}{'; '.join(item.problems)}")
    if not registry.needs_lines:
        lines.append("  none")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--since",
        type=int,
        default=DEFAULT_SINCE_DAYS,
        metavar="DAYS",
        help=f"also list items closed within this many days (default {DEFAULT_SINCE_DAYS})",
    )
    for group, option in FILTER_OPTIONS.items():
        parser.add_argument(
            f"--{option}",
            dest=group,
            action="append",
            default=[],
            metavar=option.upper(),
            help=f"keep items whose Touches {group} include this; repeatable or comma-separated",
        )
    parser.add_argument("--json", action="store_true", help="print JSON for agents in place of text")
    parser.add_argument("--repo", help="OWNER/NAME; defaults to the repository gh infers from the current directory")
    return parser


def main(argv: list[str] | None = None, run: Runner = gh_runner, now: datetime | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    filters = normalize_filters({group: getattr(arguments, group) for group in GROUPS})
    cutoff = (now or datetime.now(UTC)) - timedelta(days=arguments.since)
    try:
        members, sub_issues, parent = fetch(run, arguments.repo)
    except (RuntimeError, json.JSONDecodeError) as error:
        print(f"calibration_registry: {error}", file=sys.stderr)
        return EXIT_GH_FAILED
    registry = build_registry(members, sub_issues, parent, cutoff=cutoff, filters=filters)
    if arguments.json:
        print(json.dumps(registry.to_json(), indent=2))
    else:
        print(render_text(registry), end="")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
