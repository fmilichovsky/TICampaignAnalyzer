"""Shared invariants of a calibration table, and the hand-built rows the replay tests and the golden table use."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from tinarrative.benchmarking.calibration.replay import default_state, replay
from tinarrative.benchmarking.calibration.table import build_index, layers, type_kinds
from tinarrative.kinds.registry import kind_for
from tinarrative.model.events import SCORE_BANDS, Significance

ROW_FIELDS = {
    "id",
    "type",
    "tier",
    "interval",
    "date",
    "label",
    "base",
    "rule",
    "stakes",
    "entities",
    "cited",
    "score",
    "level",
}


def check_rows(rows: list[dict[str, Any]]) -> None:
    """Every row has the schema, a score inside its level's band, and cites only rows of an earlier layer."""
    assert rows
    by_id = {row["id"]: row for row in rows}
    assert len(by_id) == len(rows)
    layer_of = layers()
    kinds = type_kinds(row["type"] for row in rows)
    for row in rows:
        assert set(row) == ROW_FIELDS
        assert row["rule"] in {None, kinds[row["type"]]["rule"]}
        assert row["tier"] in {"atomic", "reconstructed", "narrative"}
        low, high = SCORE_BANDS[Significance(row["level"])]
        assert low <= row["score"] <= high
        if row["tier"] != "narrative":
            assert row["cited"] == []
        own = layer_of.get(row["type"], 0) if row["tier"] == "narrative" else 0
        for cited in row["cited"]:
            assert cited in by_id
            other = by_id[cited]
            assert (layer_of.get(other["type"], 0) if other["tier"] == "narrative" else 0) < own


def check_parity(rows: list[dict[str, Any]]) -> None:
    """At the code's references with the clamp on, the replay is the pipeline: every score and level, every group."""
    index = build_index(["campaign"], key="", extracted_at="", kinds=type_kinds(row["type"] for row in rows))
    result = replay(index, {"campaign": rows}, default_state(index))
    oracle = {row["id"]: (row["score"], row["level"]) for row in rows}
    campaign = result["campaigns"]["campaign"]

    assert {event["id"]: (event["score"], event["level"]) for event in campaign["events"]} == oracle
    assert all(member["verdict"] == "keeps_members" for member in campaign["members"])
    assert result["totals"]["events_moved"] == 0
    assert result["totals"]["package"]["change"] == 0
    assert result["totals"]["members_changed"] == 0
    assert result["moves"] == []


# --- Hand-built rows ---------------------------------------------------------------------------------------

INDEX = build_index(["one", "two"], key="", extracted_at="", kinds={})
CONSTANTS = INDEX["constants"]
POWER = INDEX["measures"]["power"]["reference"]
POPULATION = INDEX["measures"]["population"]["reference"]
GATE = INDEX["member_gates"][0]
GROUP = GATE["group_types"][0]
MEMBER = GATE["member_type"]
CODE = default_state(INDEX)


def base(level: str) -> int:
    low, high = CONSTANTS["level_bands"][level]
    return (low + high) // 2


def row(
    id: str,
    type: str = "atomic.thing",
    *,
    tier: str = "atomic",
    level: str = "minor",
    stakes: tuple[tuple[str, float], ...] = (),
    cited: tuple[str, ...] = (),
    entities: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "id": id,
        "type": type,
        "tier": tier,
        "interval": "i",
        "date": None,
        "label": id,
        "base": base(level),
        "rule": None,
        "stakes": [{"measure": measure, "share": share} for measure, share in stakes],
        "entities": [{"id": entity, "name": None} for entity in entities],
        "cited": list(cited),
        "score": base(level),
        "level": level,
    }


def synthetic_kinds(tables: Mapping[str, Sequence[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """The ``kinds`` map of hand-built rows: a declared type's code base level and rule, and for a type no kind
    declares, its first row's level and no rule."""
    types = {item["type"] for rows in tables.values() for item in rows}
    declared = type_kinds(event_type for event_type in types if kind_for(event_type) is not None)
    synthetic = {
        item["type"]: {"base": item["level"], "rule": None}
        for rows in reversed(list(tables.values()))
        for item in reversed(rows)
        if item["type"] not in declared
    }
    return dict(sorted({**synthetic, **declared}.items()))


def with_oracle(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The rows with the code's replay as their oracle, as extraction would record it."""
    events = replay(INDEX, {"one": rows}, replace(CODE, campaigns=("one",)))["campaigns"]["one"]["events"]
    by_id = {event["id"]: event for event in events}
    return [{**item, "score": by_id[item["id"]]["score"], "level": by_id[item["id"]]["level"]} for item in rows]


def power(scale: float) -> tuple[tuple[str, float], ...]:
    return (("power", POWER * 10 ** (scale / 10)),)


def chain() -> list[dict[str, Any]]:
    """A population-staked atomic row, cited by a power-staked layer 1 row, up a 3-deep narrative chain."""
    layers = INDEX["layers"]
    first, second, third = (next(name for name, number in layers.items() if number == n) for n in (1, 2, 3))
    return with_oracle(
        [
            row("land", stakes=(("population", POPULATION * 10),)),
            row("deal", first, tier="narrative", level="trivial", stakes=power(-10), cited=("land",)),
            row("grow", second, tier="narrative", level="trivial", cited=("deal",)),
            row("arc", third, tier="narrative", level="trivial", cited=("grow",)),
        ]
    )


def members(faction: str, scales: list[float]) -> list[dict[str, Any]]:
    """A group of the gate over one member per scale, each taking its own nation."""
    group_members = [
        row(
            f"{faction}-{number}",
            MEMBER,
            tier="narrative",
            level="major",
            stakes=power(scale),
            entities=(faction, f"{faction}-nation-{number}"),
        )
        for number, scale in enumerate(scales)
    ]
    nations = tuple(f"{faction}-nation-{number}" for number in range(len(scales)))
    group = row(
        f"{faction}-group",
        GROUP,
        tier="narrative",
        level="major",
        cited=tuple(item["id"] for item in group_members),
        entities=(faction, *nations),
    )
    return [*group_members, group]


INVALID_HASHES = [
    ("speed=1", "unknown state hash key 'speed'"),
    ("clamp=off&clamp=on", "'clamp' is repeated"),
    ("clamp", "not key=value"),
    ("clamp=maybe", "on or off"),
    ("ref=warp:0.1", "unknown measure 'warp'"),
    ("ref=power:0.1,power:0.2", "'power' is repeated"),
    ("ref=power:0", "positive number"),
    ("ref=power:-1", "positive number"),
    ("ref=power:1e999", "positive number"),
    ("ref=power:1_0", "positive number"),
    ("ref=power", "measure:number"),
    ("ref=", "lists no reference"),
    ("campaigns=three", "unknown campaign"),
    ("campaigns=one,one", "repeated"),
    ("types=war.arc,war.arc", "repeated"),
    ("types=", "lists no type"),
    ("focus=warp", "unknown focus measure"),
]
"""State hashes both codecs reject, with the start of the Python error."""
