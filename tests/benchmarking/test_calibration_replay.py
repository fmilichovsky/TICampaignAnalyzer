"""The calibration replay over hand-built rows and the politics fixture, and its state codec."""

from __future__ import annotations

import math
import random
from dataclasses import replace
from typing import Any

import pytest

from tests.benchmarking.calibration_support import (
    CODE,
    CONSTANTS,
    GATE,
    GROUP,
    INDEX,
    INVALID_HASHES,
    MEMBER,
    POPULATION,
    POWER,
    base,
    chain,
    check_parity,
    members,
    power,
    row,
    with_oracle,
)
from tests.fixtures import fixture_path
from tinarrative.benchmarking.calibration.replay import (
    Replay,
    ReplayError,
    ReplayState,
    ReplayStateError,
    _js_number,
    cutoff_offsets,
    decode_state,
    encode_state,
    portable_log10,
    replay,
)
from tinarrative.benchmarking.calibration.table import extract_campaign


def run(rows: list[dict[str, Any]], **changes: Any) -> Replay:
    state = replace(CODE, campaigns=("one",), **changes)
    return replay(INDEX, {"one": rows}, state)


def events(result: Replay) -> dict[str, dict[str, Any]]:
    return {event["id"]: dict(event) for event in result["campaigns"]["one"]["events"]}


def test_the_replay_at_the_code_references_is_the_pipeline_on_the_fixture_sequence() -> None:
    saves = [
        fixture_path("io", "terra_invicta_json_v1", name)
        for name in ("politics_before.json", "politics_after.json", "politics_reverted.json")
    ]

    check_parity(extract_campaign(saves))


def test_the_clamp_bounds_the_scale_and_a_zero_share_takes_the_lowest_scale() -> None:
    rows = [row("big", stakes=power(40)), row("zero", stakes=(("power", 0.0),))]

    scored = events(run(rows))

    assert scored["big"]["score"] == base("minor") + CONSTANTS["scale_max"]
    assert scored["zero"]["score"] == base("minor") + CONSTANTS["scale_min"]


def test_without_the_clamp_the_scale_is_free_and_a_zero_share_drives_the_score_to_the_bottom() -> None:
    rows = [
        row("big", stakes=power(30)),
        row("huge", level="campaign_defining", stakes=power(40)),
        row("zero", stakes=(("power", 0.0),)),
    ]

    scored = events(run(rows, clamp=False))

    assert scored["big"]["score"] == base("minor") + 30
    assert scored["huge"]["score"] == CONSTANTS["score_max"]
    assert scored["zero"]["score"] == CONSTANTS["score_min"]


def test_a_stake_with_several_candidates_takes_the_highest_scale() -> None:
    rows = [row("both", stakes=(("power", POWER), ("population", POPULATION * 10)))]

    assert events(run(rows))["both"]["score"] == base("minor") + 10


def test_a_cited_row_of_another_measure_decides_the_level_down_the_chain() -> None:
    rows = chain()
    lowered = {**CODE.references, "population": POPULATION / 10**0.5}

    scored = events(run(rows, references=lowered))

    assert scored["arc"]["decided_by"] == "land"
    assert scored["arc"]["score"] == scored["land"]["score"] == base("minor") + 15
    assert scored["land"]["decided_by"] == "land"
    assert scored["arc"]["level"] != rows[-1]["level"]


def test_a_row_decides_its_own_score_when_it_reaches_the_cited_maximum() -> None:
    rows = chain()
    rows[1]["base"] = base("major")

    assert events(run(rows))["deal"]["decided_by"] == "deal"


def test_a_citation_that_is_not_to_an_earlier_layer_is_rejected() -> None:
    rows = chain()
    rows[1]["cited"] = ["grow"]

    with pytest.raises(ReplayError, match="not in an earlier layer"):
        run(rows)


def test_a_citation_of_an_unknown_row_is_rejected() -> None:
    rows = chain()
    rows[1]["cited"] = ["gone"]

    with pytest.raises(ReplayError, match="gone"):
        run(rows)


def test_each_member_verdict_follows_the_admitted_levels_and_the_minimum() -> None:
    minimum = GATE["minimum"]
    top = (CONSTANTS["level_bands"]["campaign_defining"][0] - base("major")) - 1
    rows = with_oracle(
        [
            *members("kept", [0.0] * minimum),
            *members("shrunk", [top, *([0.0] * minimum)]),
            *members("gone", [top, *([0.0] * (minimum - 1))]),
            row("outside", MEMBER, tier="narrative", level="major", stakes=power(CONSTANTS["scale_max"])),
        ]
    )
    assert rows[-1]["level"] not in GATE["admitted_levels"]

    lowered = run(rows, references={**CODE.references, "power": POWER / 10**0.2})
    verdicts = {member["id"]: member for member in lowered["campaigns"]["one"]["members"]}

    assert verdicts["kept-group"]["verdict"] == "keeps_members"
    assert verdicts["shrunk-group"]["verdict"] == "loses_members"
    assert verdicts["shrunk-group"]["lost"] == ["shrunk-0"]
    assert verdicts["shrunk-group"]["stale_stake"]
    assert verdicts["shrunk-group"]["distinct"] == minimum
    assert verdicts["gone-group"]["verdict"] == "falls_apart"
    assert verdicts["gone-group"]["distinct"] == minimum - 1
    assert lowered["totals"]["members_changed"] == 2
    scored = events(lowered)
    assert scored["shrunk-group"]["decided_by"] != "shrunk-0"
    counts = lowered["campaigns"]["one"]["level_counts"][GROUP]
    assert sum(counts["replay"].values()) == sum(counts["baseline"].values()) - 1

    raised = run(rows, references={**CODE.references, "power": POWER * 10**0.5})
    could = {member["id"]: member["verdict"] for member in raised["campaigns"]["one"]["members"]}
    assert could["outside"] == "could_become_member"


def test_totals_and_moves_count_the_moved_rows_most_first_and_follow_the_type_filter() -> None:
    rows = with_oracle(
        [
            row("a1", "atomic.a", stakes=power(0)),
            row("a2", "atomic.a", stakes=power(0)),
            row("b1", "atomic.b", stakes=power(0)),
            row("still", "atomic.c"),
            *chain(),
        ]
    )
    raised = {**CODE.references, "power": POWER / 10**1.4, "population": POPULATION / 10**0.5}

    result = run(rows, references=raised)
    moves = result["moves"]

    assert [move["count"] for move in moves] == sorted((move["count"] for move in moves), reverse=True)
    assert moves[0] == {"type": "atomic.a", "from_level": "minor", "to_level": "major", "count": 2, "via_cited": 0}
    assert result["totals"]["events_moved"] == sum(move["count"] for move in moves)
    arc = next(move for move in moves if move["type"] == rows[-1]["type"])
    assert arc["via_cited"] == 1
    assert (
        result["totals"]["package"]["change"]
        == result["totals"]["package"]["replay"] - (result["totals"]["package"]["baseline"])
    )

    filtered = run(rows, references=raised, types=("atomic.b",))
    assert [move["type"] for move in filtered["moves"]] == ["atomic.b"]
    assert list(filtered["campaigns"]["one"]["level_counts"]) == ["atomic.b"]
    assert len(filtered["campaigns"]["one"]["events"]) == len(rows)

    with pytest.raises(ReplayStateError, match="unknown event type"):
        run(rows, types=("atomic.none",))


def test_with_the_clamp_on_a_measure_has_the_two_window_ends_as_cut_offs() -> None:
    window = cutoff_offsets(CONSTANTS, clamp=True)

    assert len(window) == 2
    assert window[0] == -window[1]
    assert all(CONSTANTS["scale_min"] <= 10 * offset <= CONSTANTS["scale_max"] for offset in window)
    result = run([row("x", stakes=power(-60))])
    assert [cutoff["offset"] for cutoff in result["cutoffs"]["power"]] == window
    assert list(result["cutoffs"]) == list(INDEX["measures"])


def test_without_the_clamp_further_cut_offs_appear_only_where_data_lies_beyond_them() -> None:
    window = cutoff_offsets(CONSTANTS, clamp=True)
    further = [offset for offset in cutoff_offsets(CONSTANTS, clamp=False) if offset not in window]
    lower = max(offset for offset in further if offset < 0)
    rows = [row("far", stakes=power(10 * lower - 1))]

    offsets = [cutoff["offset"] for cutoff in run(rows, clamp=False)["cutoffs"]["power"]]

    assert offsets == sorted([*window, lower])


def test_a_cut_off_lists_the_nearest_events_on_each_side_and_flags_those_a_cited_row_decided() -> None:
    low = cutoff_offsets(CONSTANTS, clamp=True)[0]
    rows = [row(f"near-{n}", stakes=power(10 * low - 0.1 * (n + 1))) for n in range(CONSTANTS["neighbours"] + 2)]
    rows.append(row("inside", stakes=power(10 * low + 0.1)))
    rows.extend(chain())

    cutoff = run(rows)["cutoffs"]["power"][0]

    assert [item["id"] for item in cutoff["below"]] == [f"near-{n}" for n in range(CONSTANTS["neighbours"])]
    assert cutoff["above"][0]["id"] == "inside"
    deal = next(item for item in cutoff["above"] if item["id"] == "deal")
    assert deal["decisive"] is False
    assert deal["decided_by"] == "land"
    assert all(item["distance"] >= 0 for item in cutoff["below"] + cutoff["above"])


def test_the_portable_log10_is_within_an_ulp_of_the_platform_and_exact_on_powers_of_ten() -> None:
    rng = random.Random(461)
    values = [10 ** rng.uniform(-300, 300) for _ in range(20000)] + [5e-324, 1e-310, 1.0, 1 + 2**-30]

    assert all(abs(portable_log10(value) - math.log10(value)) <= math.ulp(math.log10(value)) for value in values)
    assert [portable_log10(10.0**power) for power in range(-20, 23)] == list(range(-20, 23))
    assert portable_log10(0.0) == -math.inf
    assert math.isnan(portable_log10(-1.0))


# --- State codec ----------------------------------------------------------------------------------------


def test_the_default_state_encodes_to_an_empty_hash() -> None:
    assert encode_state(CODE, INDEX) == ""
    assert decode_state("", INDEX) == CODE
    assert decode_state("#", INDEX) == CODE


def test_a_state_round_trips_through_its_hash_in_a_stable_key_order() -> None:
    state = ReplayState(
        references={**CODE.references, "hab": 0.00002, "power": 0.002},
        clamp=False,
        campaigns=("two",),
        types=("war.arc", "faction.takeover"),
        focus="hab",
    )

    text = encode_state(state, INDEX)

    assert text == "ref=power:0.002,hab:0.00002&clamp=off&campaigns=two&types=faction.takeover,war.arc&focus=hab"
    assert decode_state(f"#{text}", INDEX) == replace(state, types=("faction.takeover", "war.arc"))
    reordered = "focus=hab&types=war.arc,faction.takeover&campaigns=two&clamp=off&ref=hab:0.00002,power:0.002"
    assert encode_state(decode_state(reordered, INDEX), INDEX) == text


def test_no_enabled_campaign_round_trips() -> None:
    state = replace(CODE, campaigns=())

    assert decode_state(encode_state(state, INDEX), INDEX) == state


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (0.1, "0.1"),
        (0.00001, "0.00001"),
        (1e-7, "1e-7"),
        (100.0, "100"),
        (1e21, "1e+21"),
        (1 / 7, "0.14285714285714285"),
    ],
)
def test_a_number_is_written_as_javascript_writes_it(value: float, text: str) -> None:
    assert _js_number(value) == text


@pytest.mark.parametrize(("text", "message"), INVALID_HASHES)
def test_an_invalid_hash_fails_with_a_clear_error(text: str, message: str) -> None:
    with pytest.raises(ReplayStateError, match=message):
        decode_state(text, INDEX)


def test_a_state_that_misses_a_measure_or_names_an_unknown_campaign_is_rejected() -> None:
    missing = {measure: value for measure, value in CODE.references.items() if measure != "power"}

    with pytest.raises(ReplayStateError, match="exactly the measures"):
        replay(INDEX, {"one": [], "two": []}, replace(CODE, references=missing))
    with pytest.raises(ReplayStateError, match="unknown campaign"):
        replay(INDEX, {"one": []}, CODE)
