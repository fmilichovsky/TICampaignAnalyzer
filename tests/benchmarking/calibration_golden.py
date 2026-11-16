"""The golden calibration table: two hand-built campaigns in the cache's wrapper format, the browser replay's input.

``test_the_golden_calibration_table_is_current`` keeps the committed files equal to ``golden_tables()``; rewrite
them with ``pytest --update-goldens``.
"""

from __future__ import annotations

import random
from typing import Any

from tests.benchmarking.calibration_support import (
    CONSTANTS,
    GATE,
    MEMBER,
    POPULATION,
    POWER,
    base,
    chain,
    members,
    power,
    row,
    synthetic_kinds,
    with_oracle,
)
from tests.fixtures import FIXTURES_ROOT
from tinarrative.benchmarking.calibration.replay import cutoff_offsets
from tinarrative.benchmarking.calibration.table import build_index

GOLDEN = FIXTURES_ROOT / "benchmarking" / "calibration_table_v1" / "golden"
CAMPAIGNS = ("alpha", "beta")


def golden_index() -> dict[str, Any]:
    return build_index(
        list(CAMPAIGNS),
        key="golden",
        extracted_at="2026-01-01T00:00:00+00:00",
        kinds=synthetic_kinds(golden_tables()),
    )


def spread() -> list[dict[str, Any]]:
    """Seeded rows across five decades of power and population: many distinct ratios for the log10 parity."""
    rng = random.Random(462)
    levels = list(CONSTANTS["level_bands"])
    return [
        row(
            f"spread-{n}",
            "atomic.spread",
            level=rng.choice(levels),
            stakes=((rng.choice(("power", "population")), POWER * 10 ** rng.uniform(-3.5, 1.5)),),
        )
        for n in range(48)
    ]


def golden_tables() -> dict[str, list[dict[str, Any]]]:
    """The rows of each golden campaign, with the code's replay as their oracle."""
    minimum = GATE["minimum"]
    top = (CONSTANTS["level_bands"]["campaign_defining"][0] - base("major")) - 1
    window = cutoff_offsets(CONSTANTS, clamp=True)
    further = [offset for offset in cutoff_offsets(CONSTANTS, clamp=False) if offset not in window]
    low = window[0]
    alpha = [
        row("atomic", "atomic.thing", stakes=power(3)),
        row("no-stake", "atomic.plain"),
        row("both", "atomic.thing", stakes=(("power", POWER), ("population", POPULATION * 10))),
        row("zero", "atomic.thing", stakes=(("power", 0.0),)),
        row("organized", "atomic.other", level="major", stakes=(("organization", 0.004),)),
        row("at-cut", "atomic.thing", stakes=(("power", POWER * 10**low),)),
        *(row(f"near-{n}", "atomic.near", stakes=power(10 * low - 0.3 * (n + 1))) for n in range(7)),
        row("inside", "atomic.near", stakes=power(10 * low + 0.2)),
        row("far-low", "atomic.far", stakes=power(10 * max(o for o in further if o < 0) - 1)),
        row("far-high", "atomic.far", level="trivial", stakes=power(10 * min(o for o in further if o > 0) + 1)),
        *chain(),
        *members("kept", [0.0] * minimum),
        *members("shrunk", [top, *([0.0] * minimum)]),
        *members("gone", [top, *([0.0] * (minimum - 1))]),
        row("outside", MEMBER, tier="narrative", level="major", stakes=power(CONSTANTS["scale_max"])),
    ]
    beta = [
        row("atomic", "atomic.thing", stakes=power(3)),
        row("lean", "atomic.thing", level="major", stakes=power(-8)),
        row("land", "atomic.other", stakes=(("population", POPULATION * 3),)),
        row("quiet", "atomic.plain", level="trivial"),
        *spread(),
    ]
    return {"alpha": with_oracle(alpha), "beta": with_oracle(beta)}
