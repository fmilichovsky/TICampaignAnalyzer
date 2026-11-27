"""The calibration server's request handler, as a function over the golden table, and one request over a socket."""

from __future__ import annotations

import json
import shutil
import threading
import urllib.request
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from tests.benchmarking.calibration_golden import GOLDEN
from tests.benchmarking.calibration_support import check_cached_answers, page_session, random_states
from tinarrative.benchmarking.calibration import readout, server
from tinarrative.benchmarking.calibration.replay import Replay, decode_state, default_state, load, replay
from tinarrative.benchmarking.calibration.table import read_index, write_index, write_status

PAGE = files("tinarrative.benchmarking.calibration").joinpath("page")
INDEX, TABLES, DRAFTS = load(GOLDEN)
LOWER = "rise=power:0.002"


@pytest.fixture
def calibration(tmp_path: Path) -> server.Calibration:
    out = tmp_path / "out"
    shutil.copytree(GOLDEN, out)
    write_status(out, {"key": "golden", "state": "fresh", "message": "", "written_at": "2026-01-01T00:00:00+00:00"})
    return server.Calibration(out)


def ask(calibration: server.Calibration, body: Any) -> tuple[int, dict[str, Any]]:
    response = calibration.handle(server.Request("POST", "/replay", json.dumps(body).encode("utf-8")))
    assert response.content_type == "application/json"
    document: dict[str, Any] = json.loads(response.body)
    return response.status, document


def projected(result: Replay) -> dict[str, Any]:
    """``result`` as the compact answer writes it, through JSON."""
    compact = server.compact(INDEX, TABLES, DRAFTS, result)
    loaded: dict[str, Any] = json.loads(json.dumps(compact))
    return loaded


def expanded(name: str, columns: dict[str, list[Any]], own: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The page's reading of a column block back into the replay's per-row results."""
    levels = list(INDEX["constants"]["level_bands"])
    rows = TABLES[name]
    return [
        {
            "id": own[position]["id"],
            "score": score,
            "level": levels[columns["level"][position]],
            "decided_by": own[position]["id"] if decided is None else rows[decided]["id"],
        }
        for position, (score, decided) in enumerate(zip(columns["score"], columns["decided"], strict=True))
    ]


def test_the_page_files_and_the_cached_tables_are_served(calibration: server.Calibration) -> None:
    root = calibration.handle(server.Request("GET", "/"))
    assert (root.status, root.body) == (200, PAGE.joinpath("index.html").read_bytes())
    assert root.content_type.startswith("text/html")
    script = calibration.handle(server.Request("GET", "/app.js"))
    assert (script.status, script.body) == (200, PAGE.joinpath("app.js").read_bytes())
    table = calibration.handle(server.Request("GET", "/tables/alpha.js"))
    assert (table.status, table.body) == (200, (GOLDEN / "tables" / "alpha.js").read_bytes())
    assert calibration.handle(server.Request("GET", "/status.js?poll=17")).status == 200


@pytest.mark.parametrize(
    "path", ["/tables/gamma.js", "/../index.js", "/tables/../index.js", "/tables/.hidden.js", "/replay.js", "/x"]
)
def test_anything_else_is_not_found(calibration: server.Calibration, path: str) -> None:
    assert calibration.handle(server.Request("GET", path)).status == 404


def test_the_empty_hash_answers_the_code_state_with_its_readout(calibration: server.Calibration) -> None:
    status, answer = ask(calibration, {"hash": ""})

    result = replay(INDEX, TABLES, default_state(INDEX), DRAFTS)
    assert status == 200
    assert (answer["hash"], answer["is_code"], answer["key"]) == ("", True, "golden")
    assert answer["paragraph"] == readout.shared_paragraph(INDEX, result)
    assert answer["snippet"] == readout.snippet(INDEX, result)
    assert answer["replay"] == projected(result)
    assert answer["unfiltered"] is None
    assert "error" not in answer


def test_a_hash_and_the_same_values_give_the_same_answer(calibration: server.Calibration) -> None:
    _, by_hash = ask(calibration, {"hash": f"#{LOWER}"})
    _, by_values = ask(calibration, {"state": by_hash["state"]})

    assert by_hash["hash"] == LOWER
    assert by_hash["is_code"] is False
    assert by_values == by_hash
    assert by_hash["replay"] == projected(replay(INDEX, TABLES, decode_state(LOWER, INDEX), DRAFTS))


def test_values_left_out_keep_the_code_and_a_switch_to_the_code_level_is_dropped(
    calibration: server.Calibration,
) -> None:
    event_type, kind = next(iter(INDEX["kinds"].items()))

    _, answer = ask(calibration, {"state": {"focus": "population", "type_bases": {event_type: kind["base"]}}})

    assert (answer["hash"], answer["is_code"]) == ("focus=population", True)
    assert answer["state"]["type_bases"] == {}


def test_the_compact_columns_read_back_to_the_replay(calibration: server.Calibration) -> None:
    _, answer = ask(calibration, {"hash": LOWER})

    result = replay(INDEX, TABLES, decode_state(LOWER, INDEX), DRAFTS)
    for name, campaign in result["campaigns"].items():
        compact = answer["replay"]["campaigns"][name]
        assert expanded(name, compact["events"], TABLES[name]) == campaign["events"]
        assert expanded(name, compact["drafts"], DRAFTS[name]) == campaign["drafts"]
    assert answer["replay"]["cutoffs"] == json.loads(json.dumps(result["cutoffs"]))


def test_a_type_filter_also_answers_the_replay_without_it(calibration: server.Calibration) -> None:
    event_type = TABLES["alpha"][0]["type"]

    _, answer = ask(calibration, {"hash": f"{LOWER}&types={event_type}"})

    state = decode_state(LOWER, INDEX)
    filtered = replay(INDEX, TABLES, replace(state, types=(event_type,)), DRAFTS)
    full = replay(INDEX, TABLES, state, DRAFTS)
    assert answer["replay"] == projected(filtered)
    assert answer["unfiltered"] == json.loads(
        json.dumps(
            {
                "moves": full["moves"],
                "level_counts": {name: item["level_counts"] for name, item in full["campaigns"].items()},
                "members": {name: item["members"] for name, item in full["campaigns"].items()},
            }
        )
    )


@pytest.mark.parametrize(
    "body",
    [
        {"hash": "rise=nope:1"},
        {"hash": "ref=power:1"},
        {"hash": "types=no.such.type"},
        {"hash": 3},
        {"state": {"rises": {"power": -1}}},
        {"state": {"rises": {"power": True}}},
        {"state": {"drops": {"power": 1}}},
        {"state": {"scalings": {"war.arc": "population"}}},
        {"state": {"references": {"power": 0.1}}},
        {"state": {"clamp": False}},
        {"state": {"campaigns": ["gamma"]}},
        {"state": {"bases": {"nope": "major"}}},
        {"state": {"type_bases": {"no.such.type": "major"}}},
        {"state": {"focus": "nope"}},
        {"state": {"colour": "red"}},
        {"state": []},
    ],
)
def test_an_invalid_state_answers_the_error_and_the_code_state(calibration: server.Calibration, body: Any) -> None:
    status, answer = ask(calibration, body)

    assert status == 200
    assert answer["error"]
    assert (answer["hash"], answer["is_code"]) == ("", True)


def split_on_the_page(values: dict[str, Any], event_type: str) -> dict[str, Any]:
    """``values`` with ``event_type`` split off as the page splits it: its own scaling, a copy of the one it reads."""
    own = INDEX["kinds"][event_type]["scaling"]
    rises = {**values["rises"], event_type: values["rises"][own]}
    drops = {**values["drops"], **({event_type: values["drops"][own]} if own in values["drops"] else {})}
    return {**values, "rises": rises, "drops": drops, "scalings": {**values["scalings"], event_type: event_type}}


def test_a_page_state_with_a_drop_share_and_a_split_kind_reads_back_through_its_hash_and_the_report(
    calibration: server.Calibration,
) -> None:
    _, code = ask(calibration, {"hash": ""})
    split = split_on_the_page(code["state"], "faction.takeover")
    asked = {
        **split,
        "drops": {**split["drops"], "faction.takeover": 0.0002},
        "scalings": {**split["scalings"], "faction.takeover_wave": "faction.takeover"},
        "focus": "faction.takeover",
    }

    _, answer = ask(calibration, {"state": asked})
    _, again = ask(calibration, {"hash": answer["hash"]})

    assert "error" not in answer
    assert answer["hash"] == (
        "drop=faction.takeover:0.0002"
        "&scaling=faction.takeover:faction.takeover,faction.takeover_wave:faction.takeover&focus=faction.takeover"
    )
    assert again == answer
    # The report given the copied hash reads the same paragraph and snippet as the page shows.
    result = replay(INDEX, TABLES, decode_state(answer["hash"], INDEX), DRAFTS)
    assert answer["paragraph"] == readout.shared_paragraph(INDEX, result)
    assert answer["snippet"] == readout.snippet(INDEX, result)
    assert "faction.takeover" in answer["snippet"]


def test_a_split_kind_joined_back_leaves_the_code_state_and_its_joined_kinds_follow(
    calibration: server.Calibration,
) -> None:
    _, code = ask(calibration, {"hash": ""})
    split = split_on_the_page(code["state"], "faction.takeover")
    _, joined = ask(
        calibration, {"state": {**split, "scalings": {**split["scalings"], "nation.cession": "faction.takeover"}}}
    )
    # The page joins the split kind back and moves the kinds joined to its scaling with it; the split shares go.
    back = {
        **joined["state"],
        "rises": {name: share for name, share in joined["state"]["rises"].items() if name != "faction.takeover"},
        "drops": {name: share for name, share in joined["state"]["drops"].items() if name != "faction.takeover"},
        "scalings": {},
    }

    _, answer = ask(calibration, {"state": back})

    assert joined["hash"] == "scaling=faction.takeover:faction.takeover,nation.cession:faction.takeover"
    assert (answer["hash"], answer["is_code"]) == ("", True)
    assert answer["state"]["scalings"] == {}


def test_a_focus_names_a_scaling_and_one_no_longer_split_is_refused(calibration: server.Calibration) -> None:
    _, code = ask(calibration, {"hash": ""})
    split = split_on_the_page(code["state"], "faction.takeover")

    _, focused = ask(calibration, {"state": {**split, "focus": "faction.takeover"}})
    _, stale = ask(calibration, {"state": {**code["state"], "focus": "faction.takeover"}})

    assert focused["hash"] == "scaling=faction.takeover:faction.takeover&focus=faction.takeover"
    assert "unknown focus scaling 'faction.takeover'" in stale["error"]


def without_row_columns(answer: dict[str, Any]) -> dict[str, Any]:
    """A full answer as a summary answer is meant to read: no per-campaign event and draft-row columns, no readout."""
    campaigns = {
        name: {key: value for key, value in campaign.items() if key not in {"events", "drafts"}}
        for name, campaign in answer["replay"]["campaigns"].items()
    }
    summary = {key: value for key, value in answer.items() if key not in {"paragraph", "snippet"}}
    summary["replay"] = {**answer["replay"], "campaigns": campaigns}
    return summary


def a_state_of_each_kind() -> list[dict[str, Any]]:
    event_type = TABLES["alpha"][0]["type"]
    return [
        {"hash": ""},
        {"hash": LOWER},
        {"hash": f"{LOWER}&types={event_type}"},
        {"hash": "rise=nope:1"},
        {"state": {"focus": "population", "campaigns": ["alpha"]}},
    ]


@pytest.mark.parametrize("body", a_state_of_each_kind())
def test_a_summary_answer_is_the_full_answer_without_the_row_columns_and_readout(
    calibration: server.Calibration, body: dict[str, Any]
) -> None:
    _, full = ask(calibration, body)
    status, summary = ask(calibration, {**body, "summary": True})

    assert status == 200
    assert summary == without_row_columns(full)


@pytest.mark.parametrize("body", a_state_of_each_kind())
def test_a_request_not_asking_for_a_summary_gets_the_full_answer(
    calibration: server.Calibration, body: dict[str, Any]
) -> None:
    _, plain = ask(calibration, body)
    _, declined = ask(calibration, {**body, "summary": False})

    assert declined == plain
    assert {"paragraph", "snippet"} <= plain.keys()
    assert all({"events", "drafts"} <= item.keys() for item in plain["replay"]["campaigns"].values())


@pytest.mark.parametrize(
    "body",
    [b"not json", b"[]", b'{"hash": "", "state": {}}', b"{}", b'{"summary": true}', b'{"hash": "", "summary": 1}'],
)
def test_a_request_of_another_shape_is_a_bad_request(calibration: server.Calibration, body: bytes) -> None:
    assert calibration.handle(server.Request("POST", "/replay", body)).status == 400


def test_a_table_at_another_schema_answers_unavailable(calibration: server.Calibration) -> None:
    write_index(calibration.out, {**read_index(calibration.out / "index.js"), "schema_version": 0})

    status, answer = ask(calibration, {"hash": ""})

    assert status == 503
    assert "--rebuild" in answer["fatal"]


def test_a_rebuilt_table_is_read_again(calibration: server.Calibration) -> None:
    ask(calibration, {"hash": ""})
    write_index(calibration.out, {**read_index(calibration.out / "index.js"), "key": "rebuilt"})

    _, answer = ask(calibration, {"hash": ""})

    assert answer["key"] == "rebuilt"


def test_the_meta_names_the_level_bases_and_each_draft_row(calibration: server.Calibration) -> None:
    _, answer = ask(calibration, {"hash": ""})

    meta = answer["meta"]
    assert set(meta["level_bases"]) == set(INDEX["constants"]["level_bands"])
    assert {name: len(names) for name, names in meta["draft_names"].items()} == {
        name: len(rows) for name, rows in DRAFTS.items()
    }
    assert {name for names in meta["draft_names"].values() for name in names} <= {
        draft["name"] for draft in INDEX["drafts"]
    }


def test_the_server_answers_over_a_socket(calibration: server.Calibration) -> None:
    http = server.bind(calibration, 0)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        url = server.url(http)
        with urllib.request.urlopen(url, timeout=30) as response:
            assert response.read() == PAGE.joinpath("index.html").read_bytes()
        request = urllib.request.Request(f"{url}replay", data=json.dumps({"hash": LOWER}).encode("utf-8"))
        with urllib.request.urlopen(request, timeout=30) as response:
            assert response.headers["Cache-Control"] == "no-store"
            assert json.loads(response.read())["hash"] == LOWER
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=30)


def test_a_long_lived_server_answers_a_page_session_as_a_fresh_server_does(calibration: server.Calibration) -> None:
    bodies = page_session(INDEX, TABLES)

    check_cached_answers(calibration.out, bodies)


def test_a_long_lived_server_answers_more_base_level_choices_than_it_keeps_as_a_fresh_server_does(
    calibration: server.Calibration,
) -> None:
    present = {row["type"] for rows in TABLES.values() for row in rows}
    unscaled = next(
        event_type for event_type, kind in INDEX["kinds"].items() if kind["scaling"] is None and event_type in present
    )
    levels = list(INDEX["constants"]["level_bands"])
    # Every level, the first again after the others have pushed it out, then the code's.
    tried = [*levels, levels[0], *levels[:2]]
    bodies = [{"state": {"type_bases": {unscaled: level}}} for level in tried] + [{"state": {}}]

    check_cached_answers(calibration.out, bodies)


def test_a_long_lived_server_answers_random_states_as_a_fresh_server_does(calibration: server.Calibration) -> None:
    bodies = random_states(INDEX, TABLES, seed=683, count=40)

    assert any(body["state"]["types"] for body in bodies)
    assert any(body["state"]["scalings"] for body in bodies)
    check_cached_answers(calibration.out, bodies)
