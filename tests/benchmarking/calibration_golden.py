"""The golden calibration table: two hand-built campaigns in the cache's wrapper format, read by the replay and
server tests.

``test_the_golden_calibration_table_is_current`` keeps the committed files equal to ``golden_tables()``; rewrite
them with ``pytest --update-goldens``.
"""

from __future__ import annotations

import random
from typing import Any

from tests.benchmarking.calibration_support import (
    CONSTANTS,
    DRAFTS,
    GATE,
    MEMBER,
    POPULATION,
    POWER,
    base,
    drafted,
    members,
    power,
    row,
    synthetic_kinds,
    with_draft_oracle,
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
        kinds=synthetic_kinds({name: document["events"] for name, document in golden_tables().items()}),
        drafts=DRAFTS,
    )


def spread() -> list[dict[str, Any]]:
    """Seeded rows across five decades of power and population: many distinct cut-off distances."""
    rng = random.Random(462)
    levels = list(CONSTANTS["level_bands"])
    return [
        row(
            f"spread-{n}",
            "atomic.spread",
            level=rng.choice(levels),
            shares=((rng.choice(("power", "population")), POWER * 10 ** rng.uniform(-3.5, 1.5)),),
        )
        for n in range(48)
    ]


def golden_tables() -> dict[str, dict[str, Any]]:
    """The document of each golden campaign, its rows and draft rows with the code's replay as their oracle."""
    minimum = GATE["minimum"]
    chain_rows, shadows = drafted()
    top = (CONSTANTS["level_bands"]["campaign_defining"][0] - base("major")) - 1
    window = cutoff_offsets(CONSTANTS)
    low = window[0]
    alpha = [
        row("atomic", "atomic.thing", shares=power(3)),
        row("no-share", "atomic.plain"),
        row("both", "atomic.thing", shares=(("power", POWER), ("population", POPULATION * 10))),
        row("zero", "atomic.thing", shares=(("power", 0.0),)),
        row("organized", "atomic.other", level="major", shares=(("organization", 0.004),)),
        row("at-cut", "atomic.thing", shares=(("power", POWER * 10**low),)),
        *(row(f"near-{n}", "atomic.near", shares=power(10 * low - 0.3 * (n + 1))) for n in range(7)),
        row("inside", "atomic.near", shares=power(10 * low + 0.2)),
        row("far-low", "atomic.far", shares=power(10 * window[0] - 1)),
        row("far-high", "atomic.far", level="trivial", shares=power(10 * window[1] + 1)),
        *chain_rows,
        *members("kept", [0.0] * minimum),
        *members("shrunk", [top, *([0.0] * minimum)]),
        *members("gone", [top, *([0.0] * (minimum - 1))]),
        row("outside", MEMBER, tier="narrative", level="major", shares=power(CONSTANTS["scale_max"])),
    ]
    beta = [
        row("atomic", "atomic.thing", shares=power(3)),
        row("lean", "atomic.thing", level="major", shares=power(-8)),
        row("judged", "atomic.thing", level="major", shares=power(2), rule="judged"),
        row("land", "atomic.other", shares=(("population", POPULATION * 3),)),
        row("quiet", "atomic.plain", level="trivial"),
        *spread(),
    ]
    alpha = with_oracle(alpha)
    index = build_index(["alpha"], key="", extracted_at="", kinds={}, drafts=DRAFTS)
    return {
        "alpha": {"events": alpha, "drafts": with_draft_oracle(index, alpha, shadows)},
        "beta": {"events": with_oracle(beta), "drafts": []},
    }
