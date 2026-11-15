"""Run ``replay.js`` in Node and compare it with ``replay.py`` byte for byte; used by the ``browser_replay`` tests."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from tinarrative.benchmarking.calibration.replay import ReplayState, encode_state, js_number, load, replay

HARNESS = Path(__file__).with_name("replay_harness.js")
REPLAY_JS = Path(str(files("tinarrative.benchmarking.calibration").joinpath("replay.js")))
NODE_HINT = (
    "the browser_replay tests need Node.js on PATH (test-only): install the LTS from https://nodejs.org or run "
    "`brew install node`"
)


def node() -> str:
    """The ``node`` binary, or a test failure that says how to install it."""
    binary = shutil.which("node")
    if binary is None:
        pytest.fail(NODE_HINT)
    return binary


def run_harness(directory: Path, requests: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The harness's answer to each request over the calibration table in ``directory``."""
    assert REPLAY_JS.is_file(), f"replay.js is not package data at {REPLAY_JS}"
    done = subprocess.run(
        [node(), str(HARNESS), str(REPLAY_JS), str(directory)],
        input=json.dumps(list(requests)),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if done.returncode != 0:
        pytest.fail(f"the replay harness failed:\n{done.stderr}")
    answers: list[dict[str, Any]] = json.loads(done.stdout)
    return answers


def js_json(value: Any) -> str:
    """``value`` as ``JSON.stringify`` writes it: compact, keys in insertion order, numbers as ``String`` does."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return js_number(value) if math.isfinite(value) else "null"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, Mapping):
        return (
            "{"
            + ",".join(f"{json.dumps(str(key), ensure_ascii=False)}:{js_json(item)}" for key, item in value.items())
            + "}"
        )
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(js_json(item) for item in value) + "]"
    raise TypeError(f"cannot write {type(value).__name__} as JSON")


def state_object(state: ReplayState) -> dict[str, Any]:
    """``state`` as ``replay.js`` holds it."""
    return {
        "references": dict(state.references),
        "clamp": state.clamp,
        "campaigns": list(state.campaigns),
        "types": list(state.types),
        "focus": state.focus,
    }


def assert_replays_agree(directory: Path, states: Sequence[ReplayState]) -> None:
    """For every state, ``replay.js`` (fed the Python hash) writes exactly the JSON of ``replay.py``."""
    index, tables = load(directory)
    hashes = [encode_state(state, index) for state in states]
    answers = run_harness(directory, [{"op": "replay", "hash": text} for text in hashes])
    for state, text, answer in zip(states, hashes, answers, strict=True):
        assert "ok" in answer, f"replay.js rejected #{text}: {answer}"
        expected = js_json(replay(index, tables, state))
        if answer["ok"] != expected:
            pytest.fail(f"replay.js differs from replay.py for #{text}: {_first_difference(answer['ok'], expected)}")


def _first_difference(actual: str, expected: str) -> str:
    pairs = enumerate(zip(actual, expected, strict=False))
    at = next((i for i, (a, b) in pairs if a != b), min(len(actual), len(expected)))
    start = max(0, at - 120)
    return f"at byte {at}\n  js: …{actual[start : at + 80]}\n  py: …{expected[start : at + 80]}"
