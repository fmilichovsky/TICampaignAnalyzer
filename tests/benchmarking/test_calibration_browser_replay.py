"""``replay.js`` equals ``replay.py`` exactly on the golden table: replay output, state codec and number primitives."""

from __future__ import annotations

import random
from dataclasses import replace
from pathlib import Path

import pytest

from tests.benchmarking.browser_replay import (
    assert_readouts_agree,
    assert_replays_agree,
    js_json,
    run_harness,
    state_object,
)
from tests.benchmarking.calibration_golden import GOLDEN
from tests.benchmarking.calibration_support import FIRST, GROUP, INVALID_HASHES, MEMBER
from tinarrative.benchmarking.calibration.replay import (
    SCHEMA_VERSION,
    STATE_KEYS,
    ReplayError,
    ReplayStateError,
    decode_state,
    default_state,
    encode_state,
    load,
    portable_log10,
    replay,
)
from tinarrative.benchmarking.calibration.table import write_campaign, write_index

pytestmark = pytest.mark.browser_replay

INDEX, TABLES, DRAFTS = load(GOLDEN)
CODE = default_state(INDEX)


def moved(**factors: float) -> dict[str, float]:
    return {**CODE.references, **{measure: CODE.references[measure] * factor for measure, factor in factors.items()}}


STATES = [
    CODE,
    replace(CODE, references=moved(power=10**-0.2)),
    replace(CODE, references=moved(power=10**0.5)),
    replace(CODE, references=moved(power=10**-1.4, population=10**-0.5)),
    replace(CODE, references=moved(population=10**0.7, organization=3.0)),
    replace(CODE, references=moved(power=1 / 7)),
    replace(CODE, references=moved(power=10**-3)),
    replace(CODE, references=moved(power=10**3)),
    replace(CODE, campaigns=("beta",)),
    replace(CODE, campaigns=()),
    replace(CODE, types=("atomic.near", "faction.takeover")),
    replace(CODE, focus="population"),
    replace(CODE, bases={**CODE.bases, "held": "major"}),
    replace(CODE, bases={"held": "trivial", "moved": "campaign_defining"}, references=moved(population=10**0.5)),
    replace(CODE, bases={**CODE.bases, "moved": "major"}, campaigns=("alpha",), types=(FIRST,)),
    replace(CODE, type_bases={"atomic.thing": "campaign_defining"}),
    replace(CODE, type_bases={"atomic.thing": "trivial", FIRST: "campaign_defining"}, references=moved(power=10**0.5)),
    replace(CODE, type_bases={MEMBER: "campaign_defining"}, types=(GROUP,)),
    replace(CODE, type_bases={FIRST: "trivial"}, bases={**CODE.bases, "held": "major"}),
    replace(
        CODE,
        references={**CODE.references, "power": 0.002},
        campaigns=("alpha",),
        types=("atomic.thing",),
        focus="power",
    ),
]


def test_replay_js_writes_the_json_of_replay_py_for_every_state() -> None:
    assert_replays_agree(GOLDEN, STATES)


def test_readout_js_writes_the_paragraph_and_snippet_of_readout_py_for_every_state() -> None:
    every_measure = replace(CODE, references={measure: value * 2 for measure, value in CODE.references.items()})
    assert_readouts_agree(GOLDEN, [*STATES, every_measure])


def test_a_state_hash_round_trips_between_the_codecs() -> None:
    hashes = [encode_state(state, INDEX) for state in STATES]
    requests = [{"op": "encode", "state": state_object(state)} for state in STATES]
    requests += [{"op": "decode", "hash": f"#{text}"} for text in hashes]

    answers = run_harness(GOLDEN, requests)
    encoded, decoded = answers[: len(STATES)], answers[len(STATES) :]

    assert [answer["ok"] for answer in encoded] == [js_json(text) for text in hashes]
    for state, text, answer in zip(STATES, hashes, decoded, strict=True):
        assert decode_state(text, INDEX) == state
        assert answer["ok"] == js_json(state_object(state))


def test_both_codecs_reject_every_invalid_hash() -> None:
    answers = run_harness(GOLDEN, [{"op": "decode", "hash": text} for text, _ in INVALID_HASHES])

    for (text, message), answer in zip(INVALID_HASHES, answers, strict=True):
        with pytest.raises(ReplayStateError, match=message):
            decode_state(text, INDEX)
        assert answer.get("error", {}).get("name") == "ReplayStateError", text


def test_both_replays_reject_an_unknown_type_and_a_citation_out_of_layer_order(tmp_path: Path) -> None:
    with pytest.raises(ReplayStateError, match="unknown event type"):
        replay(INDEX, TABLES, replace(CODE, types=("atomic.none",)))
    [unknown] = run_harness(GOLDEN, [{"op": "replay", "hash": "types=atomic.none"}])
    assert unknown["error"]["name"] == "ReplayStateError"

    broken = {name: [dict(row) for row in rows] for name, rows in TABLES.items()}
    deal = next(row for row in broken["alpha"] if row["id"] == "deal")
    deal["cited"] = ["grow"]
    write_index(tmp_path, INDEX)
    for name, rows in broken.items():
        write_campaign(tmp_path, name, {"events": rows, "drafts": DRAFTS[name]})
    with pytest.raises(ReplayError, match="not in an earlier layer"):
        replay(INDEX, broken, CODE, DRAFTS)
    [citation] = run_harness(tmp_path, [{"op": "replay", "hash": ""}])
    assert citation["error"]["name"] == "ReplayError"


def test_the_number_primitives_agree_to_the_bit() -> None:
    rng = random.Random(462)
    logs = [10 ** rng.uniform(-300, 300) for _ in range(20000)]
    logs += [5e-324, 1e-310, 2.2250738585072014e-308, 1.7976931348623157e308, 1.0, 1 + 2**-30, 1 - 2**-40]
    logs += [10.0**power for power in range(-20, 23)]
    rounds = [0.5, 1.5, 2.5, -0.5, -1.5, -2.5, 12.5, -12.5, 0.49999999999999994, -0.4]
    rounds += [rng.uniform(-60, 60) for _ in range(2000)] + [rng.randint(-60, 60) + 0.5 for _ in range(200)]

    answers = run_harness(
        GOLDEN,
        [{"op": "log10", "values": logs}, {"op": "round", "values": rounds}, {"op": "constants"}],
    )

    assert answers[0]["ok"] == js_json([portable_log10(value) for value in logs])
    assert answers[1]["ok"] == js_json([round(value) for value in rounds])
    assert answers[2]["ok"] == js_json({"SCHEMA_VERSION": SCHEMA_VERSION, "STATE_KEYS": list(STATE_KEYS)})


def test_the_states_cover_every_field_of_the_hash() -> None:
    text = "&".join(encode_state(state, INDEX) for state in STATES)

    assert all(f"{key}=" in text for key in STATE_KEYS)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("base=held:huge", "must be a level"),
        ("base=held:major,held:minor", "'held' is repeated"),
        ("base=atomic.none:major", "unknown draft stake or event type 'atomic.none'"),
        ("base=atomic.thing:huge", "the base level of atomic.thing must be a level"),
        ("base=atomic.thing:major,atomic.thing:minor", "'atomic.thing' is repeated"),
    ],
)
def test_both_codecs_reject_a_base_that_is_not_one_level(text: str, message: str) -> None:
    [answer] = run_harness(GOLDEN, [{"op": "decode", "hash": text}])

    with pytest.raises(ReplayStateError, match=message):
        decode_state(text, INDEX)
    assert answer.get("error", {}).get("name") == "ReplayStateError"


def test_a_type_switched_back_to_the_codes_level_decodes_to_the_default_state_in_both_codecs() -> None:
    text = f"base={FIRST}:{INDEX['kinds'][FIRST]['base']}"

    [answer] = run_harness(GOLDEN, [{"op": "decode", "hash": text}])

    assert decode_state(text, INDEX) == CODE
    assert answer["ok"] == js_json(state_object(CODE))
