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
    replayed_reason,
    with_scalings,
)
from tinarrative.benchmarking.calibration.table import reason_entry
from tinarrative.model.kinds import UNEXAMINED

READOUT = GOLDEN.parent / "readout"
INDEX, TABLES, DRAFTS = load(GOLDEN)
CODE = default_state(INDEX)
POWER = CODE.rises["power"]

STATES: dict[str, ReplayState] = {
    "code": CODE,
    "lower": replace(CODE, rises={**CODE.rises, "power": POWER * 10**-0.2, "faction": 1e-7}),
    "free": replace(CODE, campaigns=("beta",), types=("atomic.thing",)),
    "switched": replace(CODE, type_bases={"atomic.thing": "major", "atomic.far": "trivial"}),
    "split": replace(
        with_scalings(CODE, INDEX, {"atomic.near": "atomic.near", "atomic.far": "atomic.near"}),
        rises={**CODE.rises, "atomic.near": POWER * 10**0.5},
        drops={"atomic.near": POWER / 10},
    ),
}
"""The golden states: the code's, members falling apart under a lower power rise share, a campaign and type
filter, two switched base levels, and a split-off scaling that a second type joins."""
SECTIONS = [
    "Calibration state",
    "Summary",
    "Level counts",
    "Coverage",
    "What moves",
    "Member verdicts",
    "Cut-offs",
    "Draft shares",
    "Snippet",
]


@pytest.mark.parametrize("name", list(STATES))
def test_the_readouts_of_the_golden_states_are_current(name: str, assert_golden: AssertGolden) -> None:
    state = STATES[name]
    result = replay(INDEX, TABLES, state, DRAFTS)
    state_hash = encode_state(state, INDEX)

    assert_golden(shared_paragraph(INDEX, result) + "\n" + snippet(INDEX, result) + "\n", READOUT / f"{name}.txt")
    assert_golden(render_text(INDEX, TABLES, result, state_hash=state_hash, drafts=DRAFTS), READOUT / f"{name}.md")
    document = render_json(INDEX, TABLES, result, state_hash=state_hash, drafts=DRAFTS)
    assert_golden(json.dumps(document, indent=2) + "\n", READOUT / f"{name}.json")


@pytest.mark.parametrize("name", list(STATES))
def test_the_text_readout_has_its_nine_sections_in_order(name: str) -> None:
    result = replay(INDEX, TABLES, STATES[name], DRAFTS)
    text = render_text(INDEX, TABLES, result, state_hash=encode_state(STATES[name], INDEX), drafts=DRAFTS)
    drafted = [f"{draft['name']} on {name}" for draft in INDEX["drafts"] for name in draft["scalings"].values()]

    assert re.findall(r"^## (.+)$", text, re.MULTILINE) == SECTIONS
    assert re.findall(r"^### (.+)$", text, re.MULTILINE) == [*result["state"]["rises"], *drafted]


def test_the_paragraph_and_the_snippet_are_ascii_and_name_only_changed_scalings() -> None:
    result = replay(INDEX, TABLES, STATES["lower"])

    for text in (shared_paragraph(INDEX, result), snippet(INDEX, result)):
        assert text.isascii()
    lines = snippet(INDEX, result).splitlines()
    assert [line.split(":")[0] for line in lines] == ["Scaling.POWER", "Scaling.FACTION"]
    assert "every other scaling at the code's" in shared_paragraph(INDEX, result)
    assert "every scaling at the code's" in shared_paragraph(INDEX, replay(INDEX, TABLES, CODE))


def test_the_paragraph_and_the_snippet_state_the_switched_base_levels() -> None:
    kinds = INDEX["kinds"]
    none = replay(INDEX, TABLES, CODE)
    one = replay(INDEX, TABLES, replace(CODE, type_bases={"atomic.thing": "major"}))
    several = replay(INDEX, TABLES, STATES["switched"])
    every = replay(
        INDEX,
        TABLES,
        replace(CODE, type_bases={name: "trivial" if kinds[name]["base"] != "trivial" else "minor" for name in kinds}),
    )

    assert "Base levels: every type at the code's. " in shared_paragraph(INDEX, none)
    assert snippet(INDEX, none) == "# Every scaling, kind's scaling and base level is the code's."
    assert "Base levels: atomic.thing major (code minor); every other type at the code's. " in shared_paragraph(
        INDEX, one
    )
    assert snippet(INDEX, one) == "# atomic.thing: base MINOR -> MAJOR"
    assert (
        "Base levels: atomic.far trivial (code minor), atomic.thing major (code minor); every other"
        in shared_paragraph(INDEX, several)
    )
    assert snippet(INDEX, several).splitlines() == [
        "# atomic.far: base MINOR -> TRIVIAL",
        "# atomic.thing: base MINOR -> MAJOR",
    ]
    assert "; every other type" not in shared_paragraph(INDEX, every)


def test_the_snippet_lists_the_changed_scalings_before_the_switched_base_levels() -> None:
    state = replace(STATES["lower"], type_bases={"atomic.thing": "major"})
    lines = snippet(INDEX, replay(INDEX, TABLES, state)).splitlines()

    assert [line.split(":")[0] for line in lines] == ["Scaling.POWER", "Scaling.FACTION", "# atomic.thing"]


def test_the_reports_carry_the_switched_base_levels_of_the_state() -> None:
    state = STATES["switched"]
    result = replay(INDEX, TABLES, state, DRAFTS)
    state_hash = encode_state(state, INDEX)
    document = render_json(INDEX, TABLES, result, state_hash=state_hash, drafts=DRAFTS)
    text = render_text(INDEX, TABLES, result, state_hash=state_hash, drafts=DRAFTS)

    assert document["state"]["type_bases"] == {"atomic.far": "trivial", "atomic.thing": "major"}
    assert "| atomic.thing | major (changed) | minor |" in text


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
        "coverage",
        "members",
        "moved",
        "cutoffs",
        "drafts",
    }
    edges = changed | {(item["campaign"], item["id"]) for item in neighbours}
    assert set(oracle) - edges, "an event that neither moved nor sits by a cut-off stays out"
    assert all(member["verdict"] != "keeps_members" for member in document["members"])
    assert {"falls_apart", "loses_members"} <= {member["verdict"] for member in document["members"]}


def test_the_draft_section_names_every_draft_and_its_own_rows_only() -> None:
    state = replace(CODE, bases={**CODE.bases, "held": "major"})
    result = replay(INDEX, TABLES, state, DRAFTS)
    document = render_json(INDEX, TABLES, result, state_hash=encode_state(state, INDEX), drafts=DRAFTS)
    paragraph = shared_paragraph(INDEX, result)
    held, moved = document["drafts"]
    rows = {row["id"]: row for row in DRAFTS["alpha"]}

    assert [(item["name"], item["issue"]) for item in document["drafts"]] == [("held", 1), ("moved", 2)]
    assert "Drafts: held (#1) at base major instead of minor: 3 events" in paragraph
    assert "moved (#2) at base trivial: 1 event" in paragraph
    assert (held["base"], held["own_base"], moved["base"]) == ("major", "minor", "trivial")
    assert held["events"] == sum(held["level_counts"]["baseline"].values()) == 3
    assert held["ruled"] == sum(1 for row in rows.values() if row["ruled"] and row["id"].startswith("draft:held:"))
    assert held["level_counts"] != replay(INDEX, TABLES, CODE, DRAFTS)["drafts"]["held"]["level_counts"]
    for item in document["drafts"]:
        assert list(item["cutoffs"]) == item["measures"]
        entries = [
            entry
            for cutoffs in item["cutoffs"].values()
            for cutoff in cutoffs
            for entry in [*cutoff["below"], *cutoff["above"]]
        ]
        assert entries
        assert all(entry["id"].startswith(f"draft:{item['name']}:") for entry in entries)
        assert all(entry["ruled"] is rows[entry["id"]]["ruled"] for entry in entries)
    real = [entry for cutoffs in document["cutoffs"].values() for cutoff in cutoffs for entry in cutoff["below"]]
    assert not any(entry["id"].startswith("draft:") for entry in real)


def test_a_table_without_drafts_says_so() -> None:
    bare = {**INDEX, "drafts": []}
    result = replay(bare, TABLES, replace(CODE, bases={}))

    assert shared_paragraph(bare, result).endswith(" Drafts: none.")
    assert "No draft shares are declared." in render_text(bare, TABLES, result, state_hash="")
    assert render_json(bare, TABLES, result, state_hash="")["drafts"] == []


def test_the_level_counts_sum_the_enabled_campaigns() -> None:
    document = render_json(INDEX, TABLES, replay(INDEX, TABLES, CODE), state_hash="")

    for event_type, counts in document["level_counts"].items():
        rows = [row for rows in TABLES.values() for row in rows if row["type"] == event_type]
        assert sum(counts["baseline"].values()) == len(rows)


def test_flags_override_the_state_and_accumulate() -> None:
    state = override_state(
        STATES["free"],
        INDEX,
        rises=["power=0.002,hab=0.03", "battle=1e-3"],
        drops=["power=0.0001"],
        campaigns=["beta", "alpha"],
        types=["atomic.thing,atomic.near"],
    )

    assert state.rises == {**CODE.rises, "power": 0.002, "hab": 0.03, "battle": 0.001}
    assert state.drops == {"power": 0.0001}
    assert state.campaigns == ("alpha", "beta")
    assert state.types == ("atomic.near", "atomic.thing")
    assert override_state(state, INDEX) == state


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        ({"rises": ["warp=0.1"]}, "unknown scaling 'warp'"),
        ({"rises": ["power=0.1,power=0.2"]}, "'power' is given twice"),
        ({"drops": ["power=0.01", "power=0.02"]}, "'power' is given twice"),
        ({"rises": ["power"]}, "SCALING=VALUE"),
        ({"rises": ["power=0"]}, "positive number"),
        ({"rises": ["power=nan"]}, "positive number"),
        ({"drops": ["power=1"]}, "below its rise share"),
        ({"scalings": ["atomic.thing"]}, "TYPE=SCALING"),
        ({"scalings": ["atomic.thing=population"]}, "reads another measure"),
        ({"scalings": ["atomic.plain=power"]}, "has no scaling to reassign"),
        ({"scalings": ["atomic.thing=power", "atomic.thing=power"]}, "'atomic.thing' is given twice"),
        ({"campaigns": ["gamma"]}, "unknown campaign"),
        ({"campaigns": ["alpha", "alpha"]}, "given twice"),
        ({"types": ["atomic.thing,atomic.thing"]}, "given twice"),
        ({"bases": ["atomic.thing"]}, "TYPE=LEVEL"),
        ({"bases": ["atomic.none=major"]}, "unknown event type 'atomic.none'"),
        ({"bases": ["atomic.thing=huge"]}, "must be a level"),
        ({"bases": ["atomic.thing=major", "atomic.thing=minor"]}, "'atomic.thing' is given twice"),
    ],
)
def test_invalid_flags_fail_with_a_clear_error(flags: dict[str, Any], message: str) -> None:
    with pytest.raises(ReplayStateError, match=re.escape(message)):
        override_state(CODE, INDEX, **flags)


def test_base_flags_switch_types_and_a_switch_to_the_codes_level_clears_it() -> None:
    code_level = INDEX["kinds"]["atomic.thing"]["base"]
    switched = replace(CODE, type_bases={"atomic.thing": "campaign_defining", "atomic.near": "major"})

    state = override_state(switched, INDEX, bases=[f"atomic.thing={code_level},atomic.far=trivial"])

    assert state.type_bases == {"atomic.far": "trivial", "atomic.near": "major"}
    cleared = override_state(
        switched, INDEX, bases=[f"atomic.thing={code_level}", f"atomic.near={INDEX['kinds']['atomic.near']['base']}"]
    )
    assert cleared == CODE
    assert encode_state(cleared, INDEX) == ""


def test_scaling_flags_split_and_join_types_and_a_split_copies_its_code_scalings_shares() -> None:
    state = override_state(
        CODE, INDEX, scalings=["atomic.near=atomic.near,atomic.far=atomic.near"], rises=["atomic.near=0.3"]
    )

    assert state.scalings == {"atomic.far": "atomic.near", "atomic.near": "atomic.near"}
    assert state.rises["atomic.near"] == 0.3
    assert override_state(CODE, INDEX, scalings=["atomic.near=atomic.near"]).rises["atomic.near"] == POWER
    assert override_state(state, INDEX, scalings=["atomic.near=power", "atomic.far=power"]) == CODE


def test_the_readout_prints_each_types_reason_beside_its_level_counts() -> None:
    result = replay(INDEX, TABLES, CODE)
    document = render_json(INDEX, TABLES, result, state_hash="")
    text = render_text(INDEX, TABLES, result, state_hash="")

    statuses = {event_type: counts["reason"]["status"] for event_type, counts in document["level_counts"].items()}
    assert "| Type | Reason | Level | Replay | Baseline | Change |" in text
    assert {statuses["atomic.other"], statuses["atomic.scatter"], statuses["atomic.plain"]} == {
        "examined",
        "stale",
        "unexamined",
    }


def test_a_reasons_status_is_computed_at_replay_against_the_indexs_principle_revisions() -> None:
    stored = INDEX["kinds"]["atomic.scatter"]["reason"]
    principle = stored["principle"]
    assert stored["status"] == "examined" and stored["revision"] < INDEX["principles"][principle]["revision"]
    assert replayed_reason(INDEX, "atomic.scatter")["status"] == "stale"
    current = {**INDEX, "principles": {**INDEX["principles"], principle: {"title": "", "revision": stored["revision"]}}}
    assert replayed_reason(current, "atomic.scatter")["status"] == "examined"
    assert replayed_reason(INDEX, "no.such") == reason_entry(UNEXAMINED)


def test_moved_events_and_draft_rows_carry_labels_and_the_draft_text_prints_them_instead_of_ids() -> None:
    def named(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**row, "label": f"Label of {row['id']}"} for row in rows]

    tables = {name: named(rows) for name, rows in TABLES.items()}
    drafts = {name: named(rows) for name, rows in DRAFTS.items()}
    state = STATES["lower"]
    result = replay(INDEX, tables, state, drafts)
    document = render_json(INDEX, tables, result, state_hash="", drafts=drafts)
    text = render_text(INDEX, tables, result, state_hash="", drafts=drafts)

    assert document["moved"]
    assert all(item["label"] == f"Label of {item['id']}" for item in document["moved"])
    assert all(item["decided_by_label"] == f"Label of {item['decided_by']}" for item in document["moved"])
    entries = [
        entry
        for item in document["drafts"]
        for cutoffs in item["cutoffs"].values()
        for cutoff in cutoffs
        for entry in [*cutoff["below"], *cutoff["above"]]
    ]
    assert entries and all(entry["label"] == f"Label of {entry['id']}" for entry in entries)
    assert f"| Label of {entries[0]['id']} |" in text
    assert f"`{entries[0]['id']}`" not in text.split("## Draft shares")[1]
