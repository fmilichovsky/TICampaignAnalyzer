"""Shared invariants of a calibration table, and the hand-built rows the replay tests and the golden table use."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from tinarrative.benchmarking.calibration.drafts import ROW_PREFIX, DraftStake, draft_row_id
from tinarrative.benchmarking.calibration.replay import default_state, replay
from tinarrative.benchmarking.calibration.table import build_index, layers, type_kinds
from tinarrative.kinds.registry import kind_for
from tinarrative.model.events import SCORE_BANDS, Significance
from tinarrative.model.kinds import Stake, StakeMeasure
from tinarrative.narrative.significance import NARRATIVE_STAKE_IMPLEMENTATIONS, NarrativeScaling

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


def check_rows(rows: list[dict[str, Any]], drafts: Sequence[dict[str, Any]] = ()) -> None:
    """Every row has the schema, a score inside its level's band, and cites only rows of an earlier layer; a draft
    row is a narrative row with ``ruled``, cites only real rows and is cited by none."""
    assert rows
    by_id = {row["id"]: row for row in rows}
    assert len(by_id) == len(rows)
    assert not any(row["id"].startswith(ROW_PREFIX) for row in rows)
    assert not any(cited.startswith(ROW_PREFIX) for row in rows for cited in row["cited"])
    layer_of = layers()
    kinds = type_kinds(row["type"] for row in rows)
    for draft in drafts:
        assert set(draft) == ROW_FIELDS | {"ruled"}
        assert draft["id"].startswith(ROW_PREFIX) and draft["tier"] == "narrative"
        assert isinstance(draft["ruled"], bool)
        assert draft["ruled"] is (draft["rule"] is not None)
        low, high = SCORE_BANDS[Significance(draft["level"])]
        assert low <= draft["score"] <= high
        own = layer_of[draft["type"]]
        assert all(cited in by_id and layer_of.get(by_id[cited]["type"], 0) < own for cited in draft["cited"])
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


def check_parity(
    rows: list[dict[str, Any]], drafts: Sequence[dict[str, Any]] = (), declared: Sequence[DraftStake] = ()
) -> None:
    """At the code's references and each draft's own base, the replay is the pipeline: every score
    and level, every group, every draft row of the ``declared`` drafts."""
    kinds = type_kinds(row["type"] for row in rows)
    index = build_index(["campaign"], key="", extracted_at="", kinds=kinds, drafts=declared)
    result = replay(index, {"campaign": rows}, default_state(index), {"campaign": drafts})
    oracle = {row["id"]: (row["score"], row["level"]) for row in rows}
    campaign = result["campaigns"]["campaign"]

    assert {event["id"]: (event["score"], event["level"]) for event in campaign["events"]} == oracle
    assert [(event["id"], event["score"], event["level"]) for event in campaign["drafts"]] == [
        (draft["id"], draft["score"], draft["level"]) for draft in drafts
    ]
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
    rule: str | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "type": type,
        "tier": tier,
        "interval": "i",
        "date": None,
        "label": id,
        "base": base(level),
        "rule": rule,
        "stakes": [{"measure": measure, "share": share} for measure, share in stakes],
        "entities": [{"id": entity, "name": None} for entity in entities],
        "cited": list(cited),
        "score": base(level),
        "level": level,
    }


def synthetic_kinds(tables: Mapping[str, Sequence[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """The ``kinds`` map of hand-built rows: a declared type's code base level and rule, and for a type no kind
    declares, the level of the base score its first rule-free row starts from (else its first row's) and the first
    rule any of its rows names."""
    every = [item for rows in tables.values() for item in rows]
    types = {item["type"] for item in every}
    declared = type_kinds(event_type for event_type in types if kind_for(event_type) is not None)
    level_of = {base(level): level for level in CONSTANTS["level_bands"]}
    synthetic: dict[str, dict[str, Any]] = {}
    for event_type in sorted(types - set(declared)):
        own = [item for item in every if item["type"] == event_type]
        free = next((item for item in own if item["rule"] is None), own[0])
        rule = next((item["rule"] for item in own if item["rule"] is not None), None)
        synthetic[event_type] = {"base": level_of[free["base"]], "rule": rule}
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


FIRST, SECOND, THIRD = (next(name for name, number in INDEX["layers"].items() if number == n) for n in (1, 2, 3))
"""A narrative type of each of the first three layers."""
ACTOR = NARRATIVE_STAKE_IMPLEMENTATIONS[Stake.ACTOR]
DRAFTS = (
    DraftStake(
        name="held",
        label="Held share",
        issue=1,
        event_types=(FIRST, SECOND, THIRD),
        scalings=(ACTOR, NarrativeScaling(StakeMeasure.POPULATION, ACTOR.entities)),
        base=Significance.MINOR,
    ),
    DraftStake(
        name="moved",
        label="Moved share",
        issue=2,
        event_types=(FIRST,),
        scalings=(NarrativeScaling(StakeMeasure.POPULATION, ACTOR.entities),),
        base=Significance.TRIVIAL,
    ),
)
"""Two fixture draft stakes on the chain's types, side by side on its first layer."""
DRAFT_INDEX = build_index(["one"], key="", extracted_at="", kinds={}, drafts=DRAFTS)


def draft_row(
    name: str,
    of: dict[str, Any],
    *,
    level: str | None = None,
    stakes: tuple[tuple[str, float], ...] = (),
    ruled: bool = False,
) -> dict[str, Any]:
    """The shadow row of draft ``name`` for the real row ``of``: its type and citations, at the draft's base (or at
    ``level`` when ``ruled``); the oracle is set by ``with_draft_oracle``."""
    draft = next(draft for draft in DRAFT_INDEX["drafts"] if draft["name"] == name)
    shadow = row(
        draft_row_id(name, of["id"]),
        of["type"],
        tier="narrative",
        level=level if ruled and level is not None else draft["base"],
        stakes=stakes,
        cited=tuple(of["cited"]),
    )
    return {**shadow, "ruled": ruled}


def with_draft_oracle(
    index: dict[str, Any], rows: list[dict[str, Any]], drafts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """The draft rows with the code's replay as their oracle, as extraction would record it."""
    state = replace(default_state(index), campaigns=(index["campaigns"][0],))
    result = replay(index, {index["campaigns"][0]: rows}, state, {index["campaigns"][0]: drafts})
    by_id = {event["id"]: event for event in result["campaigns"][index["campaigns"][0]]["drafts"]}
    return [{**item, "score": by_id[item["id"]]["score"], "level": by_id[item["id"]]["level"]} for item in drafts]


def drafted() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The chain and its draft rows: one floored by its cited row, one ruled, one with two candidates, and a second
    draft beside the first on the chain's first layer."""
    rows = chain()
    land, deal, grow, arc = rows
    shadows = [
        draft_row("held", deal, stakes=power(-10)),
        draft_row("held", grow, level="major", stakes=power(2), ruled=True),
        draft_row("held", arc, stakes=(*power(-4), ("population", POPULATION * 10**0.3))),
        draft_row("moved", deal, stakes=(("population", POPULATION * 10**1.2),)),
    ]
    return rows, with_draft_oracle(DRAFT_INDEX, rows, shadows)


INVALID_HASHES = [
    ("speed=1", "unknown state hash key 'speed'"),
    ("clamp=off", "unknown state hash key 'clamp'"),
    ("ref=power:0.002&clamp=on", "unknown state hash key 'clamp'"),
    ("campaigns", "not key=value"),
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
    ("base=", "lists no base"),
    ("base=held", "draft:level"),
    ("base=nobody:major", "unknown draft stake or event type 'nobody'"),
]
"""State hashes both codecs reject, with the start of the Python error."""
