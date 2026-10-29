"""Assemble an LLM narrator request from a narrator package, without calling any API.

The output is a Messages-style body without model or limits, byte-stable for the same inputs so it can be diffed.
``--sample`` trims the package to one period (``2032``, ``2032-H1``, ``2032-Q2``) for iterating on the prompt.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from tinarrative.narrator.chapters import PERIODS, glossary_for, referenced
from tinarrative.narrator.request import AUDIENCES, CITATIONS, STYLES, build_request, render_request

OPTIONS = ("period", "audience", "citations", "style", "length", "focus")

SAMPLE = re.compile(r"^(\d{4})(?:-(H[12]|Q[1-4]))?$")


def sample_bounds(label: str) -> tuple[str, str]:
    """The half-open range ``[start, end)`` of a sample label, as game times comparable with the package's."""
    match = SAMPLE.match(label)
    if match is None:
        raise ValueError(f"sample {label!r} is not YYYY, YYYY-H1/H2 or YYYY-Q1..Q4")
    year, part = int(match.group(1)), match.group(2)
    first, months = 1, 12
    if part is not None:
        months = 6 if part[0] == "H" else 3
        first = (int(part[1]) - 1) * months + 1
    last = first + months
    end = f"{year + 1:04d}-01-01" if last > 12 else f"{year:04d}-{last:02d}-01"
    return f"{year:04d}-{first:02d}-01T00:00:00", f"{end}T00:00:00"


def sample(package: dict[str, Any], label: str) -> dict[str, Any]:
    """The package trimmed to the period ``label``; events without dates are left out."""
    start, end = sample_bounds(label)

    def overlaps(first: Any, last: Any, *, open_start: bool) -> bool:
        if not isinstance(first, str) or not isinstance(last, str):
            return False
        return first < end and (last > start if open_start else last >= start)

    trimmed = dict(package)
    trimmed["narrative"] = [
        event for event in package["narrative"] if overlaps(event["start"], event["end"], open_start=False)
    ]
    trimmed["intervals"] = [
        interval
        for interval in package["intervals"]
        if overlaps(interval["not_before"], interval["date"], open_start=True)
    ]
    dates = {interval[key] for interval in trimmed["intervals"] for key in ("not_before", "date")}
    trimmed["saves"] = [save for save in package["saves"] if save["date"] in dates]
    refs = referenced({key: trimmed[key] for key in ("saves", "intervals", "narrative")})
    trimmed["glossary"] = glossary_for(package["glossary"], refs)
    return trimmed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("package", nargs="?", type=Path, help="Narrator package JSON (default: stdin).")
    parser.add_argument("--period", choices=PERIODS)
    parser.add_argument("--audience", choices=AUDIENCES)
    parser.add_argument("--citations", choices=CITATIONS)
    parser.add_argument("--style", choices=STYLES)
    parser.add_argument("--length", help="A target length, for example '2000 words'.")
    parser.add_argument("--focus", help="A faction or nation to centre the account on.")
    parser.add_argument("--sample", metavar="PERIOD", help="Trim the package to one period: YYYY, YYYY-H1 or YYYY-Q2.")
    args = parser.parse_args(argv)
    text = args.package.read_text(encoding="utf-8") if args.package else sys.stdin.read()
    options = {key: value for key in OPTIONS if (value := getattr(args, key)) is not None}
    try:
        package = json.loads(text)
        notes = ()
        if args.sample is not None:
            package = sample(package, args.sample)
            notes = (f"sample: {args.sample} (the package is trimmed to what overlaps this period)",)
        request = build_request(package, options, notes=notes)
    except ValueError as error:
        print(f"narrator_prompt: {error}", file=sys.stderr)
        return 2
    sys.stdout.write(render_request(request))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
