"""The calibration replay over hand-built rows and the politics fixture, and its state codec."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from tests.benchmarking.calibration_support import (
    CODE,
    CONSTANTS,
    DRAFT_INDEX,
    DRAFTS,
    FIRST,
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
    drafted,
    members,
    power,
    row,
    synthetic_kinds,
    with_oracle,
)
from tests.fixtures import fixture_path
from tinarrative.benchmarking.calibration.replay import (
    Replay,
    ReplayError,
    ReplayState,
    ReplayStateError,
    cutoff_steps,
    decode_state,
    default_state,
    encode_state,
    number_text,
    replay,
    with_scalings,
)
from tinarrative.benchmarking.calibration.table import build_index, extract_campaign


def run(rows: list[dict[str, Any]], **changes: Any) -> Replay:
    state = replace(CODE, campaigns=("one",), **changes)
    return replay(INDEX, {"one": rows}, state)


def events(result: Replay) -> dict[str, dict[str, Any]]:
    return {event["id"]: dict(event) for event in result["campaigns"]["one"]["events"]}


def test_the_replay_at_the_code_scalings_is_the_pipeline_on_the_fixture_sequence() -> None:
    saves = [
        fixture_path("io", "terra_invicta_json_v1", name)
        for name in ("politics_before.json", "politics_after.json", "politics_reverted.json")
    ]

    check_parity(extract_campaign(saves)["events"])


def test_the_score_is_clipped_at_100_and_a_zero_share_falls_to_the_bottom_of_minor() -> None:
    rows = [row("big", shares=power(100)), row("far", shares=power(30)), row("zero", shares=(("power", 0.0),))]

    scored = events(run(rows))

    assert scored["big"]["score"] == CONSTANTS["score_max"]
    assert scored["far"]["score"] == base("minor") + 30
    assert scored["zero"]["score"] == CONSTANTS["level_bands"]["minor"][0]


def test_a_share_with_several_candidates_takes_the_highest_scale() -> None:
    rows = [row("both", shares=(("power", POWER), ("population", POPULATION * 10)))]

    assert events(run(rows))["both"]["score"] == base("minor") + 10


def test_a_cited_row_of_another_measure_decides_the_level_down_the_chain() -> None:
    rows = chain()
    lowered = {**CODE.rises, "population": CODE.rises["population"] / 10**0.5}

    scored = events(run(rows, rises=lowered))

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
            row("outside", MEMBER, tier="narrative", level="major", shares=power(15)),
        ]
    )
    assert rows[-1]["level"] not in GATE["admitted_levels"]

    lowered = run(rows, rises={**CODE.rises, "power": CODE.rises["power"] / 10**0.2})
    verdicts = {member["id"]: member for member in lowered["campaigns"]["one"]["members"]}

    assert verdicts["kept-group"]["verdict"] == "keeps_members"
    assert verdicts["shrunk-group"]["verdict"] == "loses_members"
    assert verdicts["shrunk-group"]["lost"] == ["shrunk-0"]
    assert verdicts["shrunk-group"]["stale_share"]
    assert verdicts["shrunk-group"]["distinct"] == minimum
    assert verdicts["gone-group"]["verdict"] == "falls_apart"
    assert verdicts["gone-group"]["distinct"] == minimum - 1
    assert lowered["totals"]["members_changed"] == 2
    scored = events(lowered)
    assert scored["shrunk-group"]["decided_by"] != "shrunk-0"
    counts = lowered["campaigns"]["one"]["level_counts"][GROUP]
    assert sum(counts["replay"].values()) == sum(counts["baseline"].values()) - 1

    raised = run(rows, rises={**CODE.rises, "power": CODE.rises["power"] * 10**0.5})
    could = {member["id"]: member["verdict"] for member in raised["campaigns"]["one"]["members"]}
    assert could["outside"] == "could_become_member"


def test_totals_and_moves_count_the_moved_rows_most_first_and_follow_the_type_filter() -> None:
    rows = with_oracle(
        [
            row("a1", "atomic.a", shares=power(0)),
            row("a2", "atomic.a", shares=power(0)),
            row("b1", "atomic.b", shares=power(0)),
            row("still", "atomic.c"),
            *chain(),
        ]
    )
    raised = {**CODE.rises, "power": CODE.rises["power"] / 10**1.4, "population": CODE.rises["population"] / 10**0.5}

    result = run(rows, rises=raised)
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

    filtered = run(rows, rises=raised, types=("atomic.b",))
    assert [move["type"] for move in filtered["moves"]] == ["atomic.b"]
    assert list(filtered["campaigns"]["one"]["level_counts"]) == ["atomic.b"]
    assert len(filtered["campaigns"]["one"]["events"]) == len(rows)

    with pytest.raises(ReplayStateError, match="unknown event type"):
        run(rows, types=("atomic.none",))


def test_a_scaling_has_a_cut_off_at_every_level_its_rows_can_move_to() -> None:
    assert cutoff_steps([base("minor")]) == [1, 2]
    assert cutoff_steps([base("trivial")]) == [1, 2, 3]
    assert cutoff_steps([base("campaign_defining")]) == [-2, -1]
    assert cutoff_steps([base("minor"), base("major")]) == [-1, 1, 2]

    result = run([row("x", shares=power(-60))])
    power_cutoffs = result["cutoffs"]["power"]
    assert [cutoff["step"] for cutoff in power_cutoffs] == [1, 2]
    assert power_cutoffs[0]["share"] == pytest.approx(CODE.rises["power"])
    assert [cutoff["offset"] for cutoff in power_cutoffs] == pytest.approx([1.25, 3.75])
    assert list(result["cutoffs"]) == list(INDEX["scalings"])


def test_a_cut_off_lists_the_nearest_events_on_each_side_and_flags_those_a_cited_row_decided() -> None:
    rise = 12.5
    rows = [row(f"near-{n}", shares=power(rise - 0.1 * (n + 1))) for n in range(CONSTANTS["neighbours"] + 2)]
    rows.append(row("inside", shares=power(rise + 0.1)))
    rows.extend(chain())

    cutoff = run(rows)["cutoffs"]["power"][0]

    assert [item["id"] for item in cutoff["below"]] == [f"near-{n}" for n in range(CONSTANTS["neighbours"])]
    assert cutoff["above"][0]["id"] == "inside"
    assert all(item["distance"] >= 0 for item in cutoff["below"] + cutoff["above"])
    deal = next(item for item in run(chain())["cutoffs"]["power"][0]["below"] if item["id"] == "deal")
    assert deal["decisive"] is False
    assert deal["decided_by"] == "land"


# --- State codec ----------------------------------------------------------------------------------------


def test_the_default_state_encodes_to_an_empty_hash() -> None:
    assert encode_state(CODE, INDEX) == ""
    assert decode_state("", INDEX) == CODE
    assert decode_state("#", INDEX) == CODE


def test_a_state_round_trips_through_its_hash_in_a_stable_key_order() -> None:
    state = ReplayState(
        rises={**CODE.rises, "hab": 0.00002, "power": 0.002},
        campaigns=("two",),
        types=("war.arc", "faction.takeover"),
        focus="hab",
    )

    text = encode_state(state, INDEX)

    assert text == "rise=power:0.002,hab:0.00002&campaigns=two&types=faction.takeover,war.arc&focus=hab"
    assert decode_state(f"#{text}", INDEX) == replace(state, types=("faction.takeover", "war.arc"))
    reordered = "focus=hab&types=war.arc,faction.takeover&campaigns=two&rise=hab:0.00002,power:0.002"
    assert encode_state(decode_state(reordered, INDEX), INDEX) == text


def test_a_drop_share_round_trips_after_the_rise_shares() -> None:
    state = replace(CODE, rises={**CODE.rises, "power": 0.3}, drops={"power": 0.003})

    text = encode_state(state, INDEX)

    assert text == "rise=power:0.3&drop=power:0.003"
    assert decode_state(text, INDEX) == state


def test_a_split_off_scaling_round_trips_and_scores_its_type_apart() -> None:
    split = with_scalings(CODE, INDEX, {"war.arc": "war.arc"})
    assert split.rises["war.arc"] == CODE.rises["power"]
    state = replace(split, rises={**split.rises, "war.arc": 0.3})

    text = encode_state(state, INDEX)

    assert text == "rise=war.arc:0.3&scaling=war.arc:war.arc"
    assert decode_state(text, INDEX) == state
    rows = [
        row("arc", "war.arc", level="major", shares=power(0)),
        row("takeover", "faction.takeover", level="major", shares=power(0)),
    ]
    scored = events(replay(INDEX, {"one": rows, "two": []}, state))
    assert scored["takeover"]["score"] == base("major")
    assert scored["arc"]["score"] < base("major")
    assert list(replay(INDEX, {"one": rows, "two": []}, state)["cutoffs"])[-1] == "war.arc"


def test_a_joined_type_follows_the_scaling_it_joins_and_joining_back_is_no_change() -> None:
    split = with_scalings(CODE, INDEX, {"war.arc": "war.arc"})
    joined = with_scalings(
        replace(split, rises={**split.rises, "war.arc": 0.3}), INDEX, {"faction.takeover": "war.arc"}
    )

    assert encode_state(joined, INDEX) == "rise=war.arc:0.3&scaling=faction.takeover:war.arc,war.arc:war.arc"
    assert decode_state(encode_state(joined, INDEX), INDEX) == joined
    back = with_scalings(joined, INDEX, {"faction.takeover": "power", "war.arc": "power"})
    assert back == CODE
    assert encode_state(back, INDEX) == ""


def test_no_enabled_campaign_round_trips() -> None:
    state = replace(CODE, campaigns=())

    assert decode_state(encode_state(state, INDEX), INDEX) == state


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (0.1, "0.1"),
        (0.002, "0.002"),
        (0.00002, "0.00002"),
        (1e-7, "0.0000001"),
        (100.0, "100"),
        (5, "5"),
        (1e22, "10000000000000000000000"),
        (1 / 7, "0.14285714285714285"),
    ],
)
def test_a_number_is_written_in_its_shortest_positional_digits_that_decode_back(value: float, text: str) -> None:
    assert number_text(value) == text
    assert decode_state(f"rise=power:{text}", INDEX).rises["power"] == value


@pytest.mark.parametrize(("text", "message"), INVALID_HASHES)
def test_an_invalid_hash_fails_with_a_clear_error(text: str, message: str) -> None:
    with pytest.raises(ReplayStateError, match=message):
        decode_state(text, INDEX)


def test_a_state_that_misses_a_measure_or_names_an_unknown_campaign_is_rejected() -> None:
    missing = {name: value for name, value in CODE.rises.items() if name != "power"}

    with pytest.raises(ReplayStateError, match="exactly the scalings"):
        replay(INDEX, {"one": [], "two": []}, replace(CODE, rises=missing))
    with pytest.raises(ReplayStateError, match="below"):
        replay(INDEX, {"one": [], "two": []}, replace(CODE, drops={"power": 1.0}))
    with pytest.raises(ReplayStateError, match="unknown campaign"):
        replay(INDEX, {"one": []}, CODE)


def run_drafts(**changes: Any) -> Replay:
    rows, shadows = drafted()
    state = replace(default_state(DRAFT_INDEX), **changes)
    return replay(DRAFT_INDEX, {"one": rows}, state, {"one": shadows})


def draft_events(result: Replay) -> dict[str, dict[str, Any]]:
    return {event["id"]: dict(event) for event in result["campaigns"]["one"]["drafts"]}


def test_the_draft_rows_replay_to_their_oracle_at_each_drafts_own_base() -> None:
    _, shadows = drafted()

    replayed = draft_events(run_drafts())

    assert {id: (event["score"], event["level"]) for id, event in replayed.items()} == {
        row["id"]: (row["score"], row["level"]) for row in shadows
    }
    assert [draft["name"] for draft in DRAFT_INDEX["drafts"]] == [draft.name for draft in DRAFTS]


def test_the_base_selector_moves_the_drafts_own_rows_and_skips_the_ruled_ones() -> None:
    rows, shadows = drafted()
    ruled = {row["id"] for row in shadows if row["ruled"]}
    held = {row["id"] for row in shadows if row["id"].startswith("draft:held:")}
    code = draft_events(run_drafts())

    raised = draft_events(run_drafts(bases={"held": "major", "moved": "trivial"}))

    assert ruled and ruled < held
    assert all(raised[id]["score"] == code[id]["score"] for id in ruled)
    assert all(raised[id]["score"] > code[id]["score"] for id in held - ruled)
    assert all(raised[id] == code[id] for id in raised if id not in held)


def test_draft_rows_never_change_the_real_rows_counts_or_totals() -> None:
    rows, _ = drafted()
    alone = replay(DRAFT_INDEX, {"one": rows}, default_state(DRAFT_INDEX))
    beside = run_drafts(bases={"held": "campaign_defining", "moved": "campaign_defining"})

    for key in ("events", "level_counts", "members"):
        assert beside["campaigns"]["one"][key] == alone["campaigns"]["one"][key]  # type: ignore[literal-required]
    assert (beside["totals"], beside["moves"]) == (alone["totals"], alone["moves"])
    assert alone["campaigns"]["one"]["drafts"] == []


def test_each_draft_counts_its_levels_at_its_base_and_the_levels_its_cited_floor_sets() -> None:
    result = run_drafts()
    shadows = draft_events(result)

    for name, summary in result["drafts"].items():
        own = [event for id, event in shadows.items() if id.startswith(f"draft:{name}:")]
        assert sum(summary["level_counts"]["replay"].values()) == len(own)
        assert summary["level_counts"]["replay"] == summary["level_counts"]["baseline"]
        assert summary["floored"] == sum(event["decided_by"] != event["id"] for event in own)
    assert result["drafts"]["held"]["floored"] > 0
    assert run_drafts(bases={"held": "major", "moved": "trivial"})["drafts"]["held"]["floored"] == 0


def test_a_drafts_rows_are_its_own_neighbours_at_each_cut_off_and_tagged_with_it() -> None:
    result = run_drafts()
    alone = replay(DRAFT_INDEX, {"one": drafted()[0]}, default_state(DRAFT_INDEX))

    for measure, cutoffs in result["cutoffs"].items():
        plain = {cutoff["step"]: cutoff for cutoff in alone["cutoffs"][measure]}
        for cutoff in cutoffs:
            if cutoff["step"] in plain:
                same = plain[cutoff["step"]]
                assert (cutoff["below"], cutoff["above"]) == (same["below"], same["above"])
            assert all(item["draft"] is None for item in (*cutoff["below"], *cutoff["above"]))
            for name, sides in cutoff["drafts"].items():
                tagged = [*sides["below"], *sides["above"]]
                assert all(item["draft"] == name and item["id"].startswith(f"draft:{name}:") for item in tagged)
    assert any(
        item
        for cutoff in result["cutoffs"]["population"]
        for side in cutoff["drafts"]["moved"].values()
        for item in side
    )


def test_a_draft_row_of_no_declared_draft_is_rejected() -> None:
    rows, shadows = drafted()

    with pytest.raises(ReplayError, match="no declared draft share"):
        replay(INDEX, {"one": rows}, replace(CODE, campaigns=("one",)), {"one": shadows})


def test_a_state_needs_one_level_base_per_draft() -> None:
    with pytest.raises(ReplayStateError, match="a base for exactly the draft shares"):
        run_drafts(bases={"held": "major"})
    with pytest.raises(ReplayStateError, match="must be a level"):
        run_drafts(bases={"held": "huge", "moved": "minor"})


def test_the_draft_bases_round_trip_through_the_hash() -> None:
    code = default_state(DRAFT_INDEX)
    state = replace(code, bases={**code.bases, "moved": "major"})

    text = encode_state(state, DRAFT_INDEX)

    assert text == "base=moved:major"
    assert decode_state(text, DRAFT_INDEX) == state
    assert encode_state(code, DRAFT_INDEX) == ""
    for bad, message in [("base=held:huge", "must be a level"), ("base=held:major,held:minor", "repeated")]:
        with pytest.raises(ReplayStateError, match=message):
            decode_state(bad, DRAFT_INDEX)


# --- Base levels -------------------------------------------------------------------------------------------


def based_rows() -> list[dict[str, Any]]:
    """The chain on an atomic type whose rule decides one row, beside a takeover group and a second atomic row."""
    return [
        *chain(),
        *with_oracle([row("ruled", level="major", rule="judged"), row("quiet", "atomic.plain", level="trivial")]),
        *members("kept", [0.0] * GATE["minimum"]),
    ]


def based_index(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return build_index(["one"], key="", extracted_at="", kinds=synthetic_kinds({"one": rows}), drafts=DRAFTS)


def run_based(rows: list[dict[str, Any]], **changes: Any) -> Replay:
    index = based_index(rows)
    return replay(index, {"one": rows}, replace(default_state(index), **changes))


def based_events(result: Replay) -> dict[str, dict[str, Any]]:
    return {event["id"]: dict(event) for event in result["campaigns"]["one"]["events"]}


def test_switching_an_atomic_type_moves_its_rule_free_rows_and_the_narrative_events_citing_them() -> None:
    rows = based_rows()
    code = based_events(run_based(rows))

    raised = based_events(run_based(rows, type_bases={"atomic.land": "campaign_defining"}))
    lowered = based_events(run_based(rows, type_bases={"atomic.land": "trivial"}))

    assert raised["land"]["score"] == min(
        CONSTANTS["score_max"], code["land"]["score"] + base("campaign_defining") - base("minor")
    )
    assert raised["land"]["level"] == "campaign_defining"
    assert all(raised[id]["score"] >= raised["land"]["score"] for id in ("deal", "grow", "arc"))
    assert all(raised[id]["decided_by"] == "land" for id in ("deal", "grow", "arc"))
    assert lowered["land"]["score"] < code["land"]["score"]
    assert raised["ruled"] == lowered["ruled"] == code["ruled"]
    assert raised["quiet"] == code["quiet"]


def test_switching_a_narrative_type_moves_its_own_start_and_a_higher_cited_row_still_decides() -> None:
    rows = based_rows()
    code = based_events(run_based(rows))
    assert code["deal"]["decided_by"] == "land"

    raised = based_events(run_based(rows, type_bases={FIRST: "campaign_defining"}))
    lowered = based_events(run_based(rows, type_bases={FIRST: "trivial"}))

    assert raised["deal"]["decided_by"] == "deal"
    assert raised["deal"]["score"] > code["deal"]["score"]
    assert raised["grow"]["score"] >= raised["deal"]["score"]
    assert lowered["deal"] == code["deal"]
    assert raised["land"] == code["land"]


def test_switching_the_member_type_re_runs_the_member_gate() -> None:
    rows = based_rows()

    result = run_based(rows, type_bases={MEMBER: "campaign_defining"})

    [group] = result["campaigns"]["one"]["members"]
    assert group["verdict"] == "falls_apart"
    assert result["totals"]["members_changed"] == 1


def test_a_switch_applies_whatever_the_type_filter_selects() -> None:
    rows = based_rows()
    switched = {"atomic.land": "campaign_defining"}

    filtered = run_based(rows, types=(FIRST,), type_bases=switched)
    every = run_based(rows, type_bases=switched)

    assert based_events(filtered) == based_events(every)
    assert set(filtered["campaigns"]["one"]["level_counts"]) == {FIRST}
    assert based_events(filtered)["deal"]["level"] == "campaign_defining"


def test_a_switch_to_the_codes_level_is_no_switch() -> None:
    rows = based_rows()
    index = based_index(rows)
    code = default_state(index)
    back = replace(code, type_bases={"atomic.land": index["kinds"]["atomic.land"]["base"]})

    assert encode_state(back, index) == ""
    assert decode_state(f"base=atomic.land:{back.type_bases['atomic.land']}", index) == code
    assert run_based(rows, type_bases=back.type_bases) == run_based(rows)
    assert run_based(rows)["state"]["type_bases"] == {}


def test_a_draft_row_on_a_switched_type_starts_from_the_tried_level_unless_its_own_base_is_switched() -> None:
    rows, shadows = drafted()
    index = based_index(rows)
    code = default_state(index)

    def drafts(**changes: Any) -> dict[str, dict[str, Any]]:
        result = replay(index, {"one": rows}, replace(code, **changes), {"one": shadows})
        return {event["id"]: dict(event) for event in result["campaigns"]["one"]["drafts"]}

    own = drafts()
    switched = drafts(type_bases={FIRST: "campaign_defining"})
    both = drafts(type_bases={FIRST: "campaign_defining"}, bases={**code.bases, "moved": "minor"})
    moved_only = drafts(bases={**code.bases, "moved": "minor"})

    deal = f"draft:moved:{rows[1]['id']}"
    assert switched[deal]["score"] > own[deal]["score"]
    assert switched[deal]["level"] == "campaign_defining"
    assert both[deal] == moved_only[deal]


def test_the_type_bases_round_trip_through_the_hash_sorted_after_the_drafts() -> None:
    rows = based_rows()
    index = based_index(rows)
    code = default_state(index)
    state = replace(
        code, bases={**code.bases, "moved": "major"}, type_bases={FIRST: "campaign_defining", "atomic.thing": "trivial"}
    )

    text = encode_state(state, index)

    assert text == f"base=moved:major,atomic.thing:trivial,{FIRST}:campaign_defining"
    assert decode_state(text, index) == replace(state, type_bases=dict(sorted(state.type_bases.items())))


def test_a_state_switching_an_unknown_type_or_to_no_level_is_rejected() -> None:
    rows = based_rows()

    with pytest.raises(ReplayStateError, match="unknown event type"):
        run_based(rows, type_bases={"atomic.none": "major"})
    with pytest.raises(ReplayStateError, match="must be a level"):
        run_based(rows, type_bases={"atomic.thing": "huge"})
