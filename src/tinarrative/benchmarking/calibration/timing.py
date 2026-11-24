"""How long the calibration server takes to answer a fixed list of requests, replayed through its handler."""

from __future__ import annotations

import json
import math
import statistics
import time
from collections.abc import Mapping, Sequence
from http import HTTPStatus
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


def measure(calibration: Calibration, *, repeats: int) -> dict[str, Any]:
    """Each request of ``requests`` sent ``repeats`` times through ``calibration.handle``, timed one by one.

    The table is loaded, and one answer given, first, so the load is not in any timing. Raises ``TimingError`` when
    the table cannot be read or a request is not answered.
    """
    try:
        key, index, tables, _ = calibration.load()
    except (OSError, ReplayError, CalibrationTableError) as error:
        raise TimingError(str(error)) from error
    asked = requests(index, tables)
    _answer(calibration, asked[FULL][0])
    seconds: dict[str, list[float]] = {kind: [] for kind in asked}
    sizes: dict[str, list[int]] = {kind: [] for kind in asked}
    for _ in range(repeats):
        for kind, bodies in asked.items():
            for body in bodies:
                started = time.perf_counter()
                size = _answer(calibration, body)
                seconds[kind].append(time.perf_counter() - started)
                sizes[kind].append(size)
    return {
        "key": key,
        "campaigns": {name: len(rows) for name, rows in tables.items()},
        "repeats": repeats,
        "sweep_answers": SWEEP_ANSWERS,
        "requests": {
            kind: {
                "count": len(seconds[kind]),
                "median_seconds": statistics.median(seconds[kind]),
                "p95_seconds": _percentile(seconds[kind], 0.95),
                "answer_bytes": int(statistics.median(sizes[kind])),
            }
            for kind in asked
        },
    }


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
