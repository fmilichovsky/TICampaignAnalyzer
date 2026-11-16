"""The calibration readout over the golden table: the goldens the page's formatters match, and the report's shape."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any

import pytest

from tests.benchmarking.calibration_golden import GOLDEN
from tests.golden import AssertGolden
from tinarrative.benchmarking.calibration.readout import (
    override_state,
    render_json,
    render_text,
    shared_paragraph,
    snippet,
)
from tinarrative.benchmarking.calibration.replay import (
    ReplayState,
    ReplayStateError,
    default_state,
    encode_state,
    load,
    replay,
)

READOUT = GOLDEN.parent / "readout"
INDEX, TABLES, DRAFTS = load(GOLDEN)
CODE = default_state(INDEX)
POWER = CODE.references["power"]

STATES: dict[str, ReplayState] = {
    "code": CODE,
    "lower": replace(CODE, references={**CODE.references, "power": POWER * 10**-0.2, "faction": 1e-7}),
    "free": replace(CODE, clamp=False, campaigns=("beta",), types=("atomic.thing",)),
}
"""The golden states: the code's, members falling apart under a lower power reference, and the clamp off."""
SECTIONS = [
    "Calibration state",
    "Summary",
    "Level counts",
    "What moves",
    "Member verdicts",
    "Cut-offs",
    "Snippet",
]


@pytest.mark.parametrize("name", list(STATES))
def test_the_readouts_of_the_golden_states_are_current(name: str, assert_golden: AssertGolden) -> None:
    state = STATES[name]
    result = replay(INDEX, TABLES, state, DRAFTS)
    state_hash = encode_state(state, INDEX)

    assert_golden(shared_paragraph(INDEX, result) + "\n" + snippet(INDEX, result) + "\n", READOUT / f"{name}.txt")
    assert_golden(render_text(INDEX, result, state_hash=state_hash), READOUT / f"{name}.md")
    document = render_json(INDEX, TABLES, result, state_hash=state_hash)
    assert_golden(json.dumps(document, indent=2) + "\n", READOUT / f"{name}.json")


@pytest.mark.parametrize("name", list(STATES))
def test_the_text_readout_has_its_seven_sections_in_order(name: str) -> None:
    result = replay(INDEX, TABLES, STATES[name])
    text = render_text(INDEX, result, state_hash=encode_state(STATES[name], INDEX))

    assert re.findall(r"^## (.+)$", text, re.MULTILINE) == SECTIONS
    assert re.findall(r"^### (.+)$", text, re.MULTILINE) == list(INDEX["measures"])


def test_the_paragraph_and_the_snippet_are_ascii_and_name_only_changed_references() -> None:
    result = replay(INDEX, TABLES, STATES["lower"])

    for text in (shared_paragraph(INDEX, result), snippet(INDEX, result)):
        assert text.isascii()
    lines = snippet(INDEX, result).splitlines()
    assert [line.split(":")[0] for line in lines] == ["StakeMeasure.POWER", "StakeMeasure.FACTION"]
    assert "every other measure at the code's" in shared_paragraph(INDEX, result)
    assert "every measure at the code's" in shared_paragraph(INDEX, replay(INDEX, TABLES, CODE))


def test_the_json_readout_holds_only_the_edges() -> None:
    state = STATES["lower"]
    result = replay(INDEX, TABLES, state, DRAFTS)
    document = render_json(INDEX, TABLES, result, state_hash=encode_state(state, INDEX))
    fallen = {
        (name, member["id"])
        for name, campaign in result["campaigns"].items()
        for member in campaign["members"]
        if member["verdict"] == "falls_apart"
    }
    oracle = {(name, row["id"]): row["level"] for name, rows in TABLES.items() for row in rows}
    changed = {
        (name, event["id"])
        for name, campaign in result["campaigns"].items()
        for event in campaign["events"]
        if event["level"] != oracle[name, event["id"]]
    } - fallen
    neighbours = [
        item
        for cutoffs in document["cutoffs"].values()
        for cutoff in cutoffs
        for item in [*cutoff["below"], *cutoff["above"]]
    ]

    assert changed
    assert {(item["campaign"], item["id"]) for item in document["moved"]} == changed
    assert all(item["level"] != item["code_level"] for item in document["moved"])
    assert set(document) == {
        "schema_version",
        "key",
        "hash",
        "state",
        "totals",
        "moves",
        "level_counts",
        "members",
        "moved",
        "cutoffs",
    }
    edges = changed | {(item["campaign"], item["id"]) for item in neighbours}
    assert set(oracle) - edges, "an event that neither moved nor sits by a cut-off stays out"
    assert all(member["verdict"] != "keeps_members" for member in document["members"])
    assert {"falls_apart", "loses_members"} <= {member["verdict"] for member in document["members"]}


def test_the_level_counts_sum_the_enabled_campaigns() -> None:
    document = render_json(INDEX, TABLES, replay(INDEX, TABLES, CODE), state_hash="")

    for event_type, counts in document["level_counts"].items():
        rows = [row for rows in TABLES.values() for row in rows if row["type"] == event_type]
        assert sum(counts["baseline"].values()) == len(rows)


def test_flags_override_the_state_and_accumulate() -> None:
    state = override_state(
        STATES["free"],
        INDEX,
        references=["power=0.002,hab=0.03", "battle=1e-3"],
        campaigns=["beta", "alpha"],
        types=["atomic.thing,atomic.near"],
        clamp="on",
    )

    assert state.references == {**CODE.references, "power": 0.002, "hab": 0.03, "battle": 0.001}
    assert state.campaigns == ("alpha", "beta")
    assert state.types == ("atomic.near", "atomic.thing")
    assert state.clamp
    assert override_state(state, INDEX) == state


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        ({"references": ["warp=0.1"]}, "unknown measure 'warp'"),
        ({"references": ["power=0.1,power=0.2"]}, "'power' is given twice"),
        ({"references": ["power=0.1", "power=0.2"]}, "'power' is given twice"),
        ({"references": ["power"]}, "MEASURE=VALUE"),
        ({"references": ["power=0"]}, "positive number"),
        ({"references": ["power=nan"]}, "positive number"),
        ({"campaigns": ["gamma"]}, "unknown campaign"),
        ({"campaigns": ["alpha", "alpha"]}, "given twice"),
        ({"types": ["atomic.thing,atomic.thing"]}, "given twice"),
    ],
)
def test_invalid_flags_fail_with_a_clear_error(flags: dict[str, Any], message: str) -> None:
    with pytest.raises(ReplayStateError, match=re.escape(message)):
        override_state(CODE, INDEX, **flags)
