"""Shared invariants of a calibration table, and the hand-built rows the replay tests and the golden table use."""

from __future__ import annotations

import json
import random
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from tests.fixtures import fixture_path
from tinarrative.benchmarking.calibration import server
from tinarrative.benchmarking.calibration.drafts import ROW_PREFIX, DraftShare, draft_row_id
from tinarrative.benchmarking.calibration.replay import default_state, replay
from tinarrative.benchmarking.calibration.table import build_index, layers, type_kinds
from tinarrative.kinds.registry import kind_for
from tinarrative.model.events import SCORE_BANDS, Significance
from tinarrative.model.kinds import Measure, ShareOf
from tinarrative.narrative.scalings import midpoint
from tinarrative.narrative.significance import SHARE_IMPLEMENTATIONS, ShareReading

SEQUENCE = ("politics_before.json", "politics_after.json", "politics_reverted.json")
"""The synthetic politics saves, a quarter apart."""


def saves() -> list[Path]:
    """The ``SEQUENCE`` fixture saves, in order."""
    return [fixture_path("io", "terra_invicta_json_v1", name) for name in SEQUENCE]


ROW_FIELDS = {
    "id",
    "type",
    "tier",
    "interval",
    "date",
    "label",
    "base",
    "rule",
    "shares",
    "entities",
    "targets",
    "explained_by",
    "intervals",
    "start",
    "start_basis",
    "end",
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
    rows: list[dict[str, Any]], drafts: Sequence[dict[str, Any]] = (), declared: Sequence[DraftShare] = ()
) -> None:
    """At the code's scalings and each draft's own base, the replay is the pipeline: every score
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

INDEX = build_index(["one", "two"], key="", extracted_at="", kinds=type_kinds(("war.arc", "faction.takeover")))
CONSTANTS = INDEX["constants"]
POWER = midpoint(INDEX["scalings"]["power"]["rise"], None)
"""The power share that leaves a score at its base: the starting power scaling's midpoint."""
POPULATION = midpoint(INDEX["scalings"]["population"]["rise"], None)
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
    shares: tuple[tuple[str, float], ...] = (),
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
        "shares": [{"measure": measure, "share": share} for measure, share in shares],
        "entities": [{"id": entity, "name": None, "role": None} for entity in entities],
        "targets": None,
        "explained_by": None,
        "intervals": [],
        "start": None,
        "start_basis": None,
        "end": None,
        "cited": list(cited),
        "score": base(level),
        "level": level,
    }


def synthetic_kinds(tables: Mapping[str, Sequence[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """The ``kinds`` map of hand-built rows: a declared type's code base level, rule and scaling, and for a type no
    kind declares, the level of the base score its first rule-free row starts from (else its first row's), the first
    rule any of its rows names and the starting scaling of the measure its first share reads. A declared type whose
    rows carry a share its kind's scaling does not read takes that measure's starting scaling."""
    every = [item for rows in tables.values() for item in rows]
    types = {item["type"] for item in every}
    declared = type_kinds(event_type for event_type in types if kind_for(event_type) is not None)
    level_of = {base(level): level for level in CONSTANTS["level_bands"]}
    synthetic: dict[str, dict[str, Any]] = {}
    for event_type in sorted(types - set(declared)):
        own = [item for item in every if item["type"] == event_type]
        free = next((item for item in own if item["rule"] is None), own[0])
        rule = next((item["rule"] for item in own if item["rule"] is not None), None)
        scaling = next((item["shares"][0]["measure"] for item in own if item["shares"]), None)
        synthetic[event_type] = {"base": level_of[free["base"]], "rule": rule, "scaling": scaling}
    for event_type, kind in declared.items():
        # A hand-built row may carry a share on a type its kind does not scale: it reads the measure's starting one.
        measures = {share["measure"] for item in every if item["type"] == event_type for share in item["shares"]}
        if measures and kind["scaling"] not in measures:
            declared[event_type] = {**kind, "scaling": sorted(measures)[0]}
    return dict(sorted({**synthetic, **declared}.items()))


def with_oracle(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The rows with the code's replay as their oracle, as extraction would record it."""
    events = replay(INDEX, {"one": rows}, replace(CODE, campaigns=("one",)))["campaigns"]["one"]["events"]
    by_id = {event["id"]: event for event in events}
    return [{**item, "score": by_id[item["id"]]["score"], "level": by_id[item["id"]]["level"]} for item in rows]


def power(scale: float) -> tuple[tuple[str, float], ...]:
    return (("power", POWER * 10 ** (scale / 10)),)


def chain() -> list[dict[str, Any]]:
    """A population-measured atomic row, cited by a power-measured layer 1 row, up a 3-deep narrative chain."""
    layers = INDEX["layers"]
    first, second, third = (next(name for name, number in layers.items() if number == n) for n in (1, 2, 3))
    return with_oracle(
        [
            row("land", "atomic.land", shares=(("population", POPULATION * 10),)),
            row("deal", first, tier="narrative", level="trivial", shares=power(-10), cited=("land",)),
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
            shares=power(scale),
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
ACTOR = SHARE_IMPLEMENTATIONS[ShareOf.ACTOR]
DRAFTS = (
    DraftShare(
        name="held",
        label="Held share",
        issue=1,
        event_types=(FIRST, SECOND, THIRD),
        readings=(ACTOR, ShareReading(Measure.POPULATION, ACTOR.entities)),
        base=Significance.MINOR,
    ),
    DraftShare(
        name="moved",
        label="Moved share",
        issue=2,
        event_types=(FIRST,),
        readings=(ShareReading(Measure.POPULATION, ACTOR.entities),),
        base=Significance.TRIVIAL,
    ),
)
"""Two fixture draft shares on the chain's types, side by side on its first layer."""
DRAFT_INDEX = build_index(["one"], key="", extracted_at="", kinds={}, drafts=DRAFTS)


def draft_row(
    name: str,
    of: dict[str, Any],
    *,
    level: str | None = None,
    shares: tuple[tuple[str, float], ...] = (),
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
        shares=shares,
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
        draft_row("held", deal, shares=power(-10)),
        draft_row("held", grow, level="major", shares=power(2), ruled=True),
        draft_row("held", arc, shares=(*power(-4), ("population", POPULATION * 10**0.3))),
        draft_row("moved", deal, shares=(("population", POPULATION * 10**1.2),)),
    ]
    return rows, with_draft_oracle(DRAFT_INDEX, rows, shadows)


INVALID_HASHES = [
    ("speed=1", "unknown state hash key 'speed'"),
    ("clamp=off", "unknown state hash key 'clamp'"),
    ("rise=power:0.2&clamp=on", "unknown state hash key 'clamp'"),
    ("ref=power:0.002", "the reference was replaced by scalings"),
    ("campaigns", "not key=value"),
    ("rise=warp:0.1", "unknown scaling 'warp'"),
    ("rise=power:0.1,power:0.2", "'power' is repeated"),
    ("rise=power:0", "positive number"),
    ("rise=power:-1", "positive number"),
    ("rise=power:1e999", "positive number"),
    ("rise=power:1_0", "positive number"),
    ("rise=power", "scaling:number"),
    ("rise=", "lists no rise share"),
    ("drop=power:1", "below its rise share"),
    ("drop=", "lists no drop share"),
    ("scaling=", "lists no scaling"),
    ("scaling=war.arc", "type:scaling"),
    ("scaling=war.arc:population", "reads another measure"),
    ("scaling=war.arc:nobody", "unknown scaling 'nobody'"),
    ("scaling=atomic.plain:atomic.plain", "has no scaling to reassign"),
    ("rise=war.arc:0.2", "unknown scaling 'war.arc'"),
    ("campaigns=three", "unknown campaign"),
    ("campaigns=one,one", "repeated"),
    ("types=war.arc,war.arc", "repeated"),
    ("types=", "lists no type"),
    ("focus=warp", "unknown focus scaling"),
    ("base=", "lists no base"),
    ("base=held", "draft:level"),
    ("base=nobody:major", "unknown draft share or event type 'nobody'"),
]
"""State hashes both codecs reject, with the start of the Python error."""


# --- Cached-versus-fresh answers -----------------------------------------------------------------------------


def page_session(index: Mapping[str, Any], tables: Mapping[str, Sequence[dict[str, Any]]]) -> list[dict[str, Any]]:
    """The states a page session sends, as ``POST /replay`` bodies: a drag of one rise share with, partway through, a
    base-level switch, a split-off scaling, and the base levels of an unscaled type and of a draft share switched back
    and forth; then the type filter on and off, a campaign turned off, and a drop share set and cleared. The drag is
    the first 13 bodies."""
    scaling = next(
        name for name in index["scalings"] if any(kind["scaling"] == name for kind in index["kinds"].values())
    )
    rise = float(index["scalings"][scaling]["rise"])
    switched = next(event_type for event_type, kind in index["kinds"].items() if kind["base"] != "major")
    split = next(event_type for event_type, kind in index["kinds"].items() if kind["scaling"] == scaling)
    counts = Counter(row["type"] for rows in tables.values() for row in rows)
    commonest = counts.most_common(1)[0][0]
    unscaled = next(
        event_type
        for event_type, _ in counts.most_common()
        if event_type in index["kinds"] and index["kinds"][event_type]["scaling"] is None
    )
    unscaled_level = "major" if index["kinds"][unscaled]["base"] != "major" else "minor"
    draft = next(iter(index["drafts"]), None)
    draft_level = None if draft is None else ("major" if draft["base"] != "major" else "minor")
    state: dict[str, Any] = {}
    bodies: list[dict[str, Any]] = [{"state": {}}]
    for step in range(12):
        state = {**state, "rises": {scaling: rise * 10 ** (-1 + step / 6)}}
        if step == 4:
            state = {**state, "scalings": {split: split}}
        if step == 9:
            state = {key: value for key, value in state.items() if key != "scalings"}
        type_bases = {switched: "major"} if step >= 6 else {}
        if step == 2 or step >= 8:
            type_bases = {**type_bases, unscaled: unscaled_level}
        state = {**state, "type_bases": type_bases}
        if draft is not None:
            state = {**state, "bases": {draft["name"]: draft_level} if step in (4, 7, 8, 9, 10, 11) else {}}
        bodies.append({"state": state})
    state = {**state, "types": [commonest]}
    bodies.append({"state": state})
    state = {key: value for key, value in state.items() if key != "types"}
    bodies.append({"state": state})
    state = {**state, "campaigns": list(index["campaigns"])[1:]}
    bodies.append({"state": state})
    state = {**state, "drops": {scaling: state["rises"][scaling] / 30}}
    bodies.append({"state": state})
    state = {key: value for key, value in state.items() if key != "drops"}
    bodies.append({"state": state})
    return bodies


def random_states(
    index: Mapping[str, Any], tables: Mapping[str, Sequence[dict[str, Any]]], seed: int, count: int
) -> list[dict[str, Any]]:
    """``count`` seeded states over every control, as ``POST /replay`` bodies."""
    rng = random.Random(seed)
    scaled = sorted(event_type for event_type, kind in index["kinds"].items() if kind["scaling"] is not None)
    types = sorted({row["type"] for rows in tables.values() for row in rows})
    levels = list(index["constants"]["level_bands"])
    bodies: list[dict[str, Any]] = []
    for _ in range(count):
        split = rng.sample(scaled, k=min(len(scaled), rng.randint(0, 2)))
        names = [*index["scalings"], *split]
        rises = {
            name: float(index["scalings"][index["kinds"][name]["scaling"] if name in split else name]["rise"])
            * 10 ** rng.uniform(-1.5, 1.5)
            for name in names
            if rng.random() < 0.4
        }
        drops = {
            name: rises.get(name, float(index["scalings"].get(name, {"rise": 1})["rise"])) / 10 ** rng.uniform(0.5, 3)
            for name in index["scalings"]
            if rng.random() < 0.2
        }
        state: dict[str, Any] = {
            "rises": rises,
            "drops": drops,
            "scalings": {event_type: event_type for event_type in split},
            "campaigns": [name for name in index["campaigns"] if rng.random() < 0.8],
            "types": rng.sample(types, k=rng.choice((0, 0, 1, 2))),
            "bases": {draft["name"]: rng.choice(levels) for draft in index["drafts"] if rng.random() < 0.5},
            "type_bases": {event_type: rng.choice(levels) for event_type in rng.sample(scaled, k=rng.randint(0, 2))},
        }
        bodies.append({"state": state})
    return bodies


def check_cached_answers(out: Path, bodies: Sequence[dict[str, Any]]) -> None:
    """One long-lived server answers each of ``bodies`` in turn as a fresh server answers it alone."""
    lasting = server.Calibration(out)
    for body in bodies:
        request = server.Request("POST", "/replay", json.dumps(body).encode("utf-8"))
        cached = lasting.handle(request)
        fresh = server.Calibration(out).handle(request)
        assert (cached.status, json.loads(cached.body)) == (fresh.status, json.loads(fresh.body)), body
        assert "error" not in json.loads(cached.body), body
