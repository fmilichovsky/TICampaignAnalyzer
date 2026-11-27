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
from tinarrative.benchmarking.calibration.table import build_index, reason_entry
from tinarrative.model.kinds import Reason
from tinarrative.model.principles import Principle

GOLDEN = FIXTURES_ROOT / "benchmarking" / "calibration_table_v1" / "golden"
CAMPAIGNS = ("alpha", "beta")
STALE = Principle.TRIVIAL_IS_A_ROLE


def golden_index() -> dict[str, Any]:
    """The index of the golden tables. Two hand-built types carry a stated reason, one examined and one stale, so
    the readouts show every status: the replay finds the second stale, judged at r1 of a principle this index raises
    to r2 after extraction."""
    kinds = synthetic_kinds({name: document["events"] for name, document in golden_tables().items()})
    kinds["atomic.other"] = {
        **kinds["atomic.other"],
        "reason": reason_entry(Reason(Principle.THE_ORDINARY_INSTANCE, "the rise of a regional power", revision=1)),
    }
    kinds["atomic.scatter"] = {
        **kinds["atomic.scatter"],
        "reason": reason_entry(Reason(STALE, "scattered churn", revision=1)),
    }
    index = build_index(
        list(CAMPAIGNS), key="golden", extracted_at="2026-01-01T00:00:00+00:00", kinds=kinds, drafts=DRAFTS
    )
    index["principles"][STALE.identifier]["revision"] = 2
    return index


def spread() -> list[dict[str, Any]]:
    """Seeded rows across five decades of power and population: many distinct cut-off distances."""
    rng = random.Random(462)
    levels = list(CONSTANTS["level_bands"])
    rows = []
    for n in range(48):
        level = rng.choice(levels)
        measure = rng.choice(("power", "population"))
        share = POWER * 10 ** rng.uniform(-3.5, 1.5)
        # One type per measure: a kind's scaling reads one measure.
        kind = "atomic.spread" if measure == "power" else "atomic.scatter"
        rows.append(row(f"spread-{n}", kind, level=level, shares=((measure, share),)))
    return rows


def golden_tables() -> dict[str, dict[str, Any]]:
    """The document of each golden campaign, its rows and draft rows with the code's replay as their oracle."""
    minimum = GATE["minimum"]
    chain_rows, shadows = drafted()
    top = (CONSTANTS["level_bands"]["campaign_defining"][0] - base("major")) - 1
    # The drop and rise shares of the starting power scaling, in log10 against its midpoint.
    window = (-1.25, 1.25)
    low = window[0]
    alpha = [
        row("atomic", "atomic.thing", shares=power(3)),
        row("no-share", "atomic.plain"),
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
        row("outside", MEMBER, tier="narrative", level="major", shares=power(15)),
    ]
    beta = [
        row("atomic", "atomic.thing", shares=power(3)),
        row("lean", "atomic.thing", level="major", shares=power(-8)),
        row("judged", "atomic.thing", level="major", shares=power(2), rule="judged"),
        row("land", "atomic.land", shares=(("population", POPULATION * 3),)),
        row("quiet", "atomic.plain", level="trivial"),
        *spread(),
    ]
    alpha = with_oracle(alpha)
    index = build_index(["alpha"], key="", extracted_at="", kinds={}, drafts=DRAFTS)
    return {
        "alpha": {"events": alpha, "drafts": with_draft_oracle(index, alpha, shadows)},
        "beta": {"events": with_oracle(beta), "drafts": []},
    }
