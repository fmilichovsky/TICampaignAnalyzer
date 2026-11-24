"""How long the calibration server takes to answer a fixed list of requests, replayed through its handler."""

from __future__ import annotations

import json
import math
import os
import statistics
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final

from tinarrative.benchmarking.calibration.replay import LEVELS, ReplayError
from tinarrative.benchmarking.calibration.server import Calibration, Request, Tables
from tinarrative.benchmarking.calibration.table import CalibrationTableError

FULL: Final = "full"
SWEEP: Final = "sweep"
TYPE_FILTER: Final = "type_filter"
BASE_SWITCH: Final = "base_switch"
SWEEP_STEPS: Final = 25
"""Rise shares a sweep asks for, evenly spaced on the slider's log scale; a drag sends many more."""
SWEEP_ANSWERS: Final = "full"
"""What a sweep request asks for: a full answer, until the server has a summary answer."""
_WINDOW: Final = 1.75
"""The slider's domain around the code's midpoint, as the page's ``prepare`` draws it."""

Body = dict[str, Any]


class TimingError(Exception):
    """The server could not answer a request of the list."""


def requests(index: Mapping[str, Any], tables: Tables) -> dict[str, list[Body]]:
    """The requests of each type, in the bodies the page posts to ``/replay``."""
    focus = next(iter(index["measures"]))
    return {
        FULL: [{"state": {}}],
        SWEEP: [{"state": {"rises": {focus: share}}} for share in _sweep_shares(index, tables, focus)],
        TYPE_FILTER: [{"state": {"types": [_commonest_type(tables)]}}],
        BASE_SWITCH: [{"state": {"type_bases": _switch(index, tables)}}],
    }


def measure(
    calibration: Calibration, *, repeats: int, base_python: str | None = None, base_samples: Path | None = None
) -> dict[str, Any]:
    """Each request of ``requests`` sent ``repeats`` times through ``calibration.handle``, timed one by one.

    The table is loaded, and one answer given, first, so the load is not in any timing. With ``base_python`` (and
    the ``base_samples`` it extracts from) the same requests are also timed on that revision (``measure_revision``) and
    its report is under ``base``. Raises ``TimingError`` when the table cannot be read or a request is not answered.
    """
    try:
        key, index, tables, _ = calibration.load()
    except (OSError, ReplayError, CalibrationTableError) as error:
        raise TimingError(str(error)) from error
    asked = requests(index, tables)
    _answer(calibration, asked[FULL][0])
    seconds, sizes = collect(lambda body: _answer(calibration, body), asked, repeats=repeats)
    measured = report(key, tables, asked, seconds, sizes, repeats=repeats)
    if base_python is not None:
        assert base_samples is not None
        measured["base"] = measure_revision(base_python, base_samples, asked, repeats=repeats)
    return measured


def collect(
    answer: Callable[[Body], int], asked: Mapping[str, Sequence[Body]], *, repeats: int
) -> tuple[dict[str, list[float]], dict[str, list[int]]]:
    """The seconds and answer bytes of each request of ``asked`` sent ``repeats`` times through ``answer``."""
    seconds: dict[str, list[float]] = {kind: [] for kind in asked}
    sizes: dict[str, list[int]] = {kind: [] for kind in asked}
    for _ in range(repeats):
        for kind, bodies in asked.items():
            for body in bodies:
                started = time.perf_counter()
                size = answer(body)
                seconds[kind].append(time.perf_counter() - started)
                sizes[kind].append(size)
    return seconds, sizes


def report(
    key: str,
    tables: Tables,
    asked: Mapping[str, Sequence[Body]],
    seconds: Mapping[str, Sequence[float]],
    sizes: Mapping[str, Sequence[int]],
    *,
    repeats: int,
) -> dict[str, Any]:
    """The timing report of one revision; a request type with no measurement (``seconds`` empty) is ``None``."""
    return {
        "key": key,
        "campaigns": {name: len(rows) for name, rows in tables.items()},
        "repeats": repeats,
        "sweep_answers": SWEEP_ANSWERS,
        "requests": {
            kind: None
            if not seconds[kind]
            else {
                "count": len(seconds[kind]),
                "median_seconds": statistics.median(seconds[kind]),
                "p95_seconds": _percentile(seconds[kind], 0.95),
                "answer_bytes": int(statistics.median(sizes[kind])),
            }
            for kind in asked
        },
    }


_REVISION_SCRIPT: Final = """
import json, sys, time
from pathlib import Path
from http import HTTPStatus
from tinarrative.benchmarking.calibration import cache
from tinarrative.benchmarking.calibration.server import Calibration, Request

samples, out, asked, repeats = Path(sys.argv[1]), Path(sys.argv[2]), json.loads(sys.argv[3]), int(sys.argv[4])
cache.refresh(samples, out)
calibration = Calibration(out)
key, _, tables, _ = calibration.load()


def answer(body):
    response = calibration.handle(Request("POST", "/replay", json.dumps(body).encode("utf-8")))
    if response.status != HTTPStatus.OK or "error" in json.loads(response.body):
        return None
    return len(response.body)


seconds = {kind: [] for kind in asked}
sizes = {kind: [] for kind in asked}
for kind, bodies in asked.items():
    if any(answer(body) is None for body in bodies):
        seconds[kind] = sizes[kind] = None
for _ in range(repeats):
    for kind, bodies in asked.items():
        if seconds[kind] is None:
            continue
        for body in bodies:
            started = time.perf_counter()
            size = answer(body)
            seconds[kind].append(time.perf_counter() - started)
            sizes[kind].append(size)
json.dump(
    {"key": key, "campaigns": {name: len(rows) for name, rows in tables.items()}, "seconds": seconds, "sizes": sizes},
    sys.stdout,
)
"""
"""Run by another revision's interpreter: its own table extraction and its own request handler.

A request type that revision does not answer (any body refused, or answered with an ``error``) has ``null`` figures.
"""


def measure_revision(
    python: str, samples: Path, asked: Mapping[str, Sequence[Body]], *, repeats: int
) -> dict[str, Any]:
    """The timing report of the revision whose interpreter is ``python``, for the requests ``asked``.

    That interpreter extracts its own table from ``samples`` and times its own server handler; an answer type it
    cannot give is ``None``. Raises ``TimingError`` when it cannot be run or does not extract.
    """
    if os.sep in python:
        python = os.path.abspath(python)  # not resolved: a virtual environment's interpreter is a symlink
    with tempfile.TemporaryDirectory(prefix="calibration-base-") as scratch:
        try:
            completed = subprocess.run(
                [python, "-c", _REVISION_SCRIPT, str(samples.resolve()), scratch, json.dumps(asked), str(repeats)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=scratch,
                check=False,
            )
        except OSError as error:
            raise TimingError(f"cannot run {python}: {error}") from error
    if completed.returncode != 0:
        tail = completed.stderr.strip().splitlines()[-1:] or [f"exit code {completed.returncode}"]
        raise TimingError(f"{python} could not extract and time its table: {tail[0]}")
    try:
        measured = json.loads(completed.stdout)
        seconds = {kind: measured["seconds"][kind] or [] for kind in asked}
        sizes = {kind: measured["sizes"][kind] or [] for kind in asked}
        tables: Tables = {name: [{}] * count for name, count in measured["campaigns"].items()}
        return report(str(measured["key"]), tables, asked, seconds, sizes, repeats=repeats)
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise TimingError(f"{python} gave no readable timing: {error}") from error


MARKER: Final = "<!-- calibration-metrics -->"
NOT_AVAILABLE: Final = "n/a"
_KINDS: Final = {
    FULL: "full answer",
    SWEEP: "sweep request",
    TYPE_FILTER: "type filter",
    BASE_SWITCH: "base switch",
}


def markdown(
    head: Mapping[str, Any],
    base: Mapping[str, Any],
    *,
    head_label: str,
    base_label: str,
    run_url: str | None = None,
) -> str:
    """The PR comment: ``MARKER``, then per request type base and head median and p95 seconds and answer bytes, and
    the tables' row counts."""

    def cells(figures: Mapping[str, Any] | None) -> list[str]:
        if figures is None:
            return [NOT_AVAILABLE] * 3
        return [f"{figures['median_seconds']:.3f}", f"{figures['p95_seconds']:.3f}", f"{figures['answer_bytes']:,}"]

    lines = [
        MARKER,
        "## Calibration requests timing",
        "",
        *([f"[View workflow run]({run_url})"] if run_url else []),
        "",
        "| Request | Median s (base) | Median s (head) | p95 s (base) | p95 s (head) | Bytes (base) | Bytes (head) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for kind, name in _KINDS.items():
        old, new = cells(base["requests"].get(kind)), cells(head["requests"].get(kind))
        lines.append(f"| {name} | {old[0]} | {new[0]} | {old[1]} | {new[1]} | {old[2]} | {new[2]} |")
    base_rows, head_rows = sum(base["campaigns"].values()), sum(head["campaigns"].values())
    lines += [
        "",
        f"Base `{base_label}`: {base_rows:,} table rows.",
        "",
        f"Head `{head_label}`: {head_rows:,} table rows.",
    ]
    return "\n".join(lines) + "\n"


def _answer(calibration: Calibration, body: Body) -> int:
    response = calibration.handle(Request("POST", "/replay", json.dumps(body).encode("utf-8")))
    if response.status != HTTPStatus.OK:
        raise TimingError(f"{response.status}: {response.body.decode('utf-8', 'replace')}")
    document = json.loads(response.body)
    if "error" in document:
        raise TimingError(f"the server did not read {body}: {document['error']}")
    return len(response.body)


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(math.ceil(fraction * len(ordered)) - 1, 0)]


def _sweep_shares(index: Mapping[str, Any], tables: Tables, measure: str) -> list[float]:
    """Rise shares from one end of the focus ``measure``'s slider domain to the other."""
    scaling = index["scalings"][measure]
    midpoint = math.log10(scaling["rise"]) - math.log10(index["constants"]["default_width"]) / 2
    low, high = midpoint - _WINDOW, midpoint + _WINDOW
    for rows in tables.values():
        for row in rows:
            for share in row["shares"]:
                if share["measure"] == measure and share["share"] > 0:
                    low, high = min(low, math.log10(share["share"])), max(high, math.log10(share["share"]))
    low, high = math.floor(low), math.ceil(high)
    drop = scaling["drop"] or 0.0
    shares = {float(f"{10 ** (low + (high - low) * step / (SWEEP_STEPS - 1)):.3g}") for step in range(SWEEP_STEPS)}
    return sorted(share for share in shares if share > drop)


def _commonest_type(tables: Tables) -> str:
    counts: dict[str, int] = {}
    for rows in tables.values():
        for row in rows:
            counts[row["type"]] = counts.get(row["type"], 0) + 1
    return min(counts, key=lambda name: (-counts[name], name))


def _switch(index: Mapping[str, Any], tables: Tables) -> dict[str, str]:
    """The commonest type the index can switch, moved to the top level, or to the bottom one if it already is there."""
    counts = {name: 0 for name in index["kinds"]}
    for rows in tables.values():
        for row in rows:
            if row["type"] in counts:
                counts[row["type"]] += 1
    event_type = min(counts, key=lambda name: (-counts[name], name))
    level = LEVELS[-1] if index["kinds"][event_type]["base"] != LEVELS[-1] else LEVELS[0]
    return {event_type: level}
