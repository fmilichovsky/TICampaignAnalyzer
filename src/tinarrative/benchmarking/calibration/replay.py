"""The replay: the calibration table rescored for a calibration state, and the state's URL-hash codec.

It is the only replay; the calibration page draws what the server answers from it (ADR-0022).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal, TypedDict

from tinarrative.benchmarking.calibration.drafts import draft_name
from tinarrative.benchmarking.calibration.table import SCHEMA_VERSION as SCHEMA_VERSION
from tinarrative.benchmarking.calibration.table import read_campaign, read_index

STATE_KEYS: Final = ("ref", "campaigns", "types", "base", "focus")
"""The hash keys, in the order ``encode_state`` writes them."""

Row = Mapping[str, Any]
Verdict = Literal["keeps_members", "loses_members", "falls_apart", "could_become_member"]


class ReplayError(ValueError):
    """A calibration table the replay cannot evaluate: an unknown cited row, or a citation that is not to an earlier
    layer."""


class ReplayStateError(ReplayError):
    """A calibration state or state hash that names an unknown or repeated key, measure, campaign or type, or holds an
    invalid value."""


@dataclass(frozen=True)
class ReplayState:
    """What the replay is asked: a reference per measure, the enabled campaigns, a type filter, a base
    level per draft stake, the base levels tried on event types and the focus.

    ``types`` empty means every type. ``bases`` empty means each draft's own base. ``type_bases`` holds the switched
    types; a type absent, or at the code's base level (the index's ``kinds``), keeps the code's. ``focus`` is the
    page's focused measure; the output does not depend on it.
    """

    references: Mapping[str, float]
    campaigns: tuple[str, ...]
    types: tuple[str, ...] = ()
    focus: str | None = None
    bases: Mapping[str, str] = field(default_factory=dict)
    type_bases: Mapping[str, str] = field(default_factory=dict)


class EventResult(TypedDict):
    id: str
    score: int
    level: str
    decided_by: str
    """The row whose own score set ``score``: the row itself, or the one it cites, followed down the chain."""


class LevelCounts(TypedDict):
    replay: dict[str, int]
    """Rows at each level after the replay; a group that falls apart is not counted."""
    baseline: dict[str, int]
    """Rows at each oracle level: the pipeline at the code's references."""


class MemberResult(TypedDict):
    id: str
    type: str
    verdict: Verdict
    kept: list[str]
    """The members still admitted, in ``cited`` order; empty for ``could_become_member``."""
    lost: list[str]
    """The members whose level left the admitted levels."""
    distinct: int
    """The distinct members the kept ones hold; 0 for ``could_become_member``."""
    minimum: int
    stale_stake: bool
    """The group's own stake still counts the members it lost."""


class CampaignResult(TypedDict):
    events: list[EventResult]
    level_counts: dict[str, LevelCounts]
    members: list[MemberResult]
    drafts: list[EventResult]
    """The draft rows, in table order."""


class Package(TypedDict):
    replay: int
    baseline: int
    change: int


class Totals(TypedDict):
    events_moved: int
    """Rows whose level differs from the oracle's; a group that falls apart is not counted."""
    package: Package
    """Narrative rows at the index's ``package_level`` or above."""
    members_changed: int
    """Groups that lose members or fall apart."""


class Move(TypedDict):
    type: str
    from_level: str
    to_level: str
    count: int
    via_cited: int
    """How many of ``count`` a cited row decided."""


class Neighbour(TypedDict):
    campaign: str
    id: str
    type: str
    share: float
    distance: float
    """``|log10(share / cut-off)|``."""
    score: int
    level: str
    oracle_level: str
    decided_by: str
    decisive: bool
    """The row's own score set its score."""
    draft: str | None
    """The draft stake of a draft row; ``None`` for a real one."""


class Sides(TypedDict):
    below: list[Neighbour]
    above: list[Neighbour]


class Cutoff(TypedDict):
    offset: float
    """``log10(cut-off / reference)``."""
    share: float
    below: list[Neighbour]
    above: list[Neighbour]
    drafts: dict[str, Sides]
    """Each draft's own nearest rows, apart from the real ones."""


class DraftResult(TypedDict):
    base: str
    level_counts: LevelCounts
    """The draft's rows at each level, at ``base`` and at its oracle."""
    floored: int
    """Rows whose score a cited row set instead of the draft's own stake."""


class StateResult(TypedDict):
    references: dict[str, float]
    campaigns: list[str]
    types: list[str]
    bases: dict[str, str]
    type_bases: dict[str, str]
    """The switched types only, sorted."""
    focus: str | None


class Replay(TypedDict):
    """The replay of a calibration table for one state.

    ``campaigns`` follow the index order, and ``events``, ``members`` and ``drafts`` the table order; ``level_counts``
    keys are sorted types, each with every level in band order. The top-level ``drafts`` follow the index order;
    draft rows never enter the real counts, totals, moves or neighbours. ``moves`` are sorted by count descending,
    then type, then the from and to levels in band order. ``cutoffs`` hold every measure in index order, each
    ascending by offset; neighbours are nearest first, then by campaign order and id. Scores and counts are integers,
    shares, offsets and distances plain floats.
    """

    schema_version: int
    state: StateResult
    campaigns: dict[str, CampaignResult]
    totals: Totals
    moves: list[Move]
    cutoffs: dict[str, list[Cutoff]]
    drafts: dict[str, DraftResult]


@dataclass(frozen=True)
class _Gate:
    group_types: frozenset[str]
    member_type: str
    admitted: frozenset[str]
    minimum: int


@dataclass
class _Scored:
    row: Row
    score: int
    level: str
    decided_by: str
    member: MemberResult | None = None


def default_state(index: Mapping[str, Any]) -> ReplayState:
    """The code's references, every campaign and each draft's own base: the state whose replay is the
    pipeline."""
    references = {name: float(measure["reference"]) for name, measure in index["measures"].items()}
    bases = {draft["name"]: draft["base"] for draft in index["drafts"]}
    return ReplayState(references=references, campaigns=tuple(index["campaigns"]), bases=bases)


Tables = dict[str, list[dict[str, Any]]]


def load(directory: Path) -> tuple[dict[str, Any], Tables, Tables]:
    """The index, the rows and the draft rows of every campaign of a calibration table directory; ``ReplayError`` for
    a table at another schema version, with the rebuild hint."""
    index = read_index(directory / "index.js")
    if index.get("schema_version") != SCHEMA_VERSION:
        raise ReplayError(
            f"index.js has schema {index.get('schema_version')}; this replay reads schema {SCHEMA_VERSION}. "
            "Run tinarrative benchmark calibrate report --rebuild."
        )
    documents = {name: read_campaign(directory / "tables" / f"{name}.js") for name in index["campaigns"]}
    tables = {name: document["events"] for name, document in documents.items()}
    drafts = {name: document["drafts"] for name, document in documents.items()}
    return index, tables, drafts


def replay(
    index: Mapping[str, Any],
    tables: Mapping[str, Sequence[Row]],
    state: ReplayState,
    drafts: Mapping[str, Sequence[Row]] | None = None,
) -> Replay:
    """Rescore the rows of the enabled campaigns, and their ``drafts`` rows, for ``state`` (``Replay`` describes the
    output). A state without ``bases`` takes each draft's own.

    Raises ``ReplayStateError`` for a state that names a measure, campaign, type, draft or level the table does not
    have, and ``ReplayError`` for a table whose citations do not run to earlier layers or a draft row of no declared
    draft.
    """
    drafts = drafts or {}
    state = _with_bases(index, state)
    _validate(index, tables, state)
    constants = index["constants"]
    levels = list(constants["level_bands"])
    gates = [
        _Gate(frozenset(gate["group_types"]), gate["member_type"], frozenset(gate["admitted_levels"]), gate["minimum"])
        for gate in index["member_gates"]
    ]
    types = frozenset(state.types)
    scored: dict[str, list[_Scored]] = {}
    shadows: dict[str, list[_Scored]] = {}
    for name in state.campaigns:
        scored[name], shadows[name] = _replay_campaign(index, tables[name], drafts.get(name, ()), state, gates)
    selected = {
        name: [item for item in items if not types or item.row["type"] in types] for name, items in scored.items()
    }
    shadowed = {
        name: [item for item in items if not types or item.row["type"] in types] for name, items in shadows.items()
    }
    every = [item for items in selected.values() for item in items]
    return {
        "schema_version": SCHEMA_VERSION,
        "state": {
            "references": dict(state.references),
            "campaigns": list(state.campaigns),
            "types": list(state.types),
            "bases": {draft["name"]: state.bases[draft["name"]] for draft in index["drafts"]},
            "type_bases": switched_types(state, index),
            "focus": state.focus,
        },
        "campaigns": {
            name: {
                "events": [_event(item) for item in scored[name]],
                "level_counts": _level_counts(selected[name], levels),
                "members": [item.member for item in selected[name] if item.member is not None],
                "drafts": [_event(item) for item in shadows[name]],
            }
            for name in state.campaigns
        },
        "totals": _totals(every, levels, constants["package_level"]),
        "moves": _moves(every, levels),
        "cutoffs": {measure: _cutoffs(measure, state, index, selected, shadowed) for measure in index["measures"]},
        "drafts": _drafts(index, state, shadowed, levels),
    }


def switched_types(state: ReplayState, index: Mapping[str, Any]) -> dict[str, str]:
    """The types of ``state.type_bases`` away from the code's base level, sorted by type."""
    kinds = index["kinds"]
    return {
        event_type: level
        for event_type, level in sorted(state.type_bases.items())
        if event_type not in kinds or level != kinds[event_type]["base"]
    }


def _event(item: _Scored) -> EventResult:
    return {"id": item.row["id"], "score": item.score, "level": item.level, "decided_by": item.decided_by}


def _with_bases(index: Mapping[str, Any], state: ReplayState) -> ReplayState:
    if state.bases:
        return state
    return replace(state, bases=default_state(index).bases)


def _validate(index: Mapping[str, Any], tables: Mapping[str, Sequence[Row]], state: ReplayState) -> None:
    measures = list(index["measures"])
    if sorted(state.references) != sorted(measures):
        raise ReplayStateError(f"the state needs a reference for exactly the measures {', '.join(measures)}")
    for measure, value in state.references.items():
        if not math.isfinite(value) or value <= 0:
            raise ReplayStateError(f"the reference of {measure} must be a positive number, not {value!r}")
    for name in state.campaigns:
        if name not in tables:
            raise ReplayStateError(f"unknown campaign {name!r} (known: {', '.join(tables)})")
    known = {row["type"] for rows in tables.values() for row in rows}
    unknown = sorted(set(state.types) - known)
    if unknown:
        raise ReplayStateError(f"unknown event type(s) in the filter: {', '.join(unknown)}")
    if state.focus is not None and state.focus not in measures:
        raise ReplayStateError(f"unknown focus measure {state.focus!r}")
    names = [draft["name"] for draft in index["drafts"]]
    if sorted(state.bases) != sorted(names):
        raise ReplayStateError(f"the state needs a base for exactly the draft stakes {', '.join(names) or '(none)'}")
    for name, level in state.bases.items():
        if level not in index["constants"]["level_bands"]:
            raise ReplayStateError(f"the base of draft stake {name} must be a level, not {level!r}")
    unswitchable = sorted(set(state.type_bases) - set(index["kinds"]))
    if unswitchable:
        raise ReplayStateError(f"unknown event type(s) in the base levels: {', '.join(unswitchable)}")
    for event_type, level in state.type_bases.items():
        if level not in index["constants"]["level_bands"]:
            raise ReplayStateError(f"the base level of {event_type} must be a level, not {level!r}")


def _replay_campaign(
    index: Mapping[str, Any], rows: Sequence[Row], shadows: Sequence[Row], state: ReplayState, gates: Sequence[_Gate]
) -> tuple[list[_Scored], list[_Scored]]:
    """The rows and the draft rows rescored; a draft row may cite only real rows of an earlier layer."""
    constants = index["constants"]
    layer_of = index["layers"]
    bands = [(level, low, high) for level, (low, high) in constants["level_bands"].items()]

    def layer(row: Row) -> int:
        return int(layer_of.get(row["type"], 0)) if row["tier"] == "narrative" else 0

    by_id = {row["id"]: row for row in rows}
    done: dict[str, _Scored] = {}
    switched = switched_types(state, index)
    own_bases = {draft["name"]: draft["base"] for draft in index["drafts"]}

    def start(row: Row) -> int:
        """The row's base, or the tried base level of its type where no context rule decided."""
        if row["rule"] is None and row["type"] in switched:
            return _level_base(constants, switched[row["type"]])
        return int(row["base"])

    def draft_start(row: Row, name: str) -> int:
        """A ruled draft row's own base; else the draft's switched base, its type's tried level or its own base."""
        if row["ruled"]:
            return int(row["base"])
        level = state.bases[name]
        if level == own_bases.get(name) and row["type"] in switched:
            level = switched[row["type"]]
        return _level_base(constants, level)

    def settle(row: Row, base: int) -> _Scored:
        own_layer = layer(row)
        for cited in row["cited"]:
            if cited not in by_id:
                raise ReplayError(f"{row['id']} cites {cited}, which is not a row of its campaign")
            if layer(by_id[cited]) >= own_layer:
                raise ReplayError(f"{row['id']} (layer {own_layer}) cites {cited}, which is not in an earlier layer")
        gate = next((gate for gate in gates if row["type"] in gate.group_types), None)
        cited_rows = [done[cited] for cited in row["cited"]]
        lost: list[str] = []
        if gate is not None:
            lost = [
                item.row["id"]
                for item in cited_rows
                if item.row["type"] == gate.member_type and item.level not in gate.admitted
            ]
            cited_rows = [item for item in cited_rows if item.row["id"] not in lost]
        own = _own_score(row, base, state, constants)
        best = max(cited_rows, key=lambda item: item.score, default=None)
        if best is None or own >= best.score:
            score, decided_by = own, row["id"]
        else:
            score, decided_by = best.score, best.decided_by
        level = next(level for level, low, high in bands if low <= score <= high)
        item = _Scored(row, score, level, decided_by)
        if gate is not None:
            item.member = _group_verdict(row, gate, cited_rows, lost)
        return item

    for row in sorted(rows, key=layer):
        done[row["id"]] = settle(row, start(row))
    for item in done.values():
        member_gate = next((gate for gate in gates if item.row["type"] == gate.member_type), None)
        if (
            member_gate is not None
            and item.row["level"] not in member_gate.admitted
            and item.level in member_gate.admitted
        ):
            item.member = {
                "id": item.row["id"],
                "type": item.row["type"],
                "verdict": "could_become_member",
                "kept": [],
                "lost": [],
                "distinct": 0,
                "minimum": member_gate.minimum,
                "stale_stake": False,
            }
    drafted: list[_Scored] = []
    for row in shadows:
        name = draft_name(row["id"])
        if name not in state.bases:
            raise ReplayError(f"{row['id']} is a row of no declared draft stake")
        item = settle(row, draft_start(row, name))
        item.member = None
        drafted.append(item)
    return [done[row["id"]] for row in rows], drafted


def _level_base(constants: Mapping[str, Any], level: str) -> int:
    """The midpoint of the level's band: the score of an event whose base alone decides its level."""
    low, high = constants["level_bands"][level]
    return (int(low) + int(high)) // 2


def _own_score(row: Row, base: int, state: ReplayState, constants: Mapping[str, Any]) -> int:
    """``base`` moved by the highest candidate scale, inside the score bound."""
    if not row["stakes"]:
        return base
    scales = [_scale(stake["share"], state.references[stake["measure"]], constants) for stake in row["stakes"]]
    return max(int(constants["score_min"]), min(int(constants["score_max"]), base + max(scales)))


def _scale(share: float, reference: float, constants: Mapping[str, Any]) -> int:
    """``round(10 * log10(share / reference))``, bounded by ``scale_min`` and ``scale_max``; no share takes
    ``scale_min``."""
    low, high = int(constants["scale_min"]), int(constants["scale_max"])
    if share <= 0:
        return low
    return max(low, min(high, round(10 * math.log10(share / reference))))


def _group_verdict(row: Row, gate: _Gate, kept_rows: Sequence[_Scored], lost: Sequence[str]) -> MemberResult:
    kept = [item for item in kept_rows if item.row["type"] == gate.member_type]
    # The group's first entity is its actor (ADR-0009); the rest are the members' distinct entities.
    held = {entity["id"] for item in kept for entity in item.row["entities"]}
    distinct = sum(1 for entity in row["entities"][1:] if entity["id"] in held)
    verdict: Verdict = "keeps_members"
    if lost:
        verdict = "loses_members" if distinct >= gate.minimum else "falls_apart"
    return {
        "id": row["id"],
        "type": row["type"],
        "verdict": verdict,
        "kept": [item.row["id"] for item in kept],
        "lost": list(lost),
        "distinct": distinct,
        "minimum": gate.minimum,
        "stale_stake": bool(lost),
    }


def _fallen(item: _Scored) -> bool:
    return item.member is not None and item.member["verdict"] == "falls_apart"


def _level_counts(items: Sequence[_Scored], levels: Sequence[str]) -> dict[str, LevelCounts]:
    replayed = Counter((item.row["type"], item.level) for item in items if not _fallen(item))
    baseline = Counter((item.row["type"], item.row["level"]) for item in items)
    return {
        event_type: {
            "replay": {level: replayed[event_type, level] for level in levels},
            "baseline": {level: baseline[event_type, level] for level in levels},
        }
        for event_type in sorted({item.row["type"] for item in items})
    }


def _totals(items: Sequence[_Scored], levels: Sequence[str], package_level: str) -> Totals:
    package = levels[levels.index(package_level) :]
    narrative = [item for item in items if item.row["tier"] == "narrative"]
    replayed = sum(1 for item in narrative if item.level in package and not _fallen(item))
    baseline = sum(1 for item in narrative if item.row["level"] in package)
    return {
        "events_moved": sum(1 for item in items if item.level != item.row["level"] and not _fallen(item)),
        "package": {"replay": replayed, "baseline": baseline, "change": replayed - baseline},
        "members_changed": sum(
            1
            for item in items
            if item.member is not None and item.member["verdict"] in {"loses_members", "falls_apart"}
        ),
    }


def _drafts(
    index: Mapping[str, Any], state: ReplayState, shadowed: Mapping[str, Sequence[_Scored]], levels: Sequence[str]
) -> dict[str, DraftResult]:
    every = [item for items in shadowed.values() for item in items]
    result: dict[str, DraftResult] = {}
    for draft in index["drafts"]:
        name = draft["name"]
        own = [item for item in every if draft_name(item.row["id"]) == name]
        replayed = Counter(item.level for item in own)
        baseline = Counter(item.row["level"] for item in own)
        result[name] = {
            "base": state.bases[name],
            "level_counts": {
                "replay": {level: replayed[level] for level in levels},
                "baseline": {level: baseline[level] for level in levels},
            },
            "floored": sum(1 for item in own if item.decided_by != item.row["id"]),
        }
    return result


def _moves(items: Sequence[_Scored], levels: Sequence[str]) -> list[Move]:
    counts: Counter[tuple[str, str, str]] = Counter()
    via: Counter[tuple[str, str, str]] = Counter()
    for item in items:
        if item.level == item.row["level"] or _fallen(item):
            continue
        key = (item.row["type"], item.row["level"], item.level)
        counts[key] += 1
        via[key] += item.decided_by != item.row["id"]
    ordered = sorted(counts, key=lambda key: (-counts[key], key[0], levels.index(key[1]), levels.index(key[2])))
    return [
        {"type": key[0], "from_level": key[1], "to_level": key[2], "count": counts[key], "via_cited": via[key]}
        for key in ordered
    ]


def cutoff_offsets(constants: Mapping[str, Any]) -> list[float]:
    """Every ``log10(share / reference)`` at which a stake moves an event of some base level one more level, ascending.

    A base sits mid-band, so the score crosses a band edge where ``10 * offset`` is half a point past it. Only the
    offsets the scale window reaches are kept.
    """
    bands = list(constants["level_bands"].values())
    offsets: set[float] = set()
    for low, high in bands:
        base = (low + high) // 2
        for other_low, other_high in bands:
            if other_low > base:
                offsets.add((other_low - base - 0.5) / 10)
            if other_high < base:
                offsets.add((other_high - base + 0.5) / 10)
    return sorted(offset for offset in offsets if constants["scale_min"] <= 10 * offset <= constants["scale_max"])


def _cutoffs(
    measure: str,
    state: ReplayState,
    index: Mapping[str, Any],
    selected: Mapping[str, Sequence[_Scored]],
    shadowed: Mapping[str, Sequence[_Scored]],
) -> list[Cutoff]:
    constants = index["constants"]
    reference = state.references[measure]

    def candidates(groups: Mapping[str, Sequence[_Scored]]) -> list[tuple[str, _Scored, float]]:
        return [
            (name, item, share)
            for name, items in groups.items()
            for item in items
            if (share := _candidate(item.row, measure)) is not None and share > 0
        ]

    real = candidates(selected)
    drafted = candidates(shadowed)
    names = [draft["name"] for draft in index["drafts"]]
    result: list[Cutoff] = []
    for offset in cutoff_offsets(constants):
        cut = reference * 10**offset
        below, above = _sides(real, cut, offset, state.campaigns, constants["neighbours"])
        drafts: dict[str, Sides] = {}
        for name in names:
            own = [entry for entry in drafted if draft_name(entry[1].row["id"]) == name]
            draft_below, draft_above = _sides(own, cut, offset, state.campaigns, constants["neighbours"])
            drafts[name] = {"below": draft_below, "above": draft_above}
        result.append({"offset": offset, "share": cut, "below": below, "above": above, "drafts": drafts})
    return result


def _sides(
    candidates: Sequence[tuple[str, _Scored, float]], cut: float, offset: float, campaigns: Sequence[str], count: int
) -> tuple[list[Neighbour], list[Neighbour]]:
    below: list[Neighbour] = []
    above: list[Neighbour] = []
    for name, item, share in candidates:
        side = below if share < cut or (share == cut and offset > 0) else above
        side.append(_neighbour(name, item, share, abs(math.log10(share / cut))))
    return _nearest(below, campaigns, count), _nearest(above, campaigns, count)


def _nearest(side: list[Neighbour], campaigns: Sequence[str], neighbours: int) -> list[Neighbour]:
    ranked = sorted(side, key=lambda item: (item["distance"], campaigns.index(item["campaign"]), item["id"]))
    return ranked[:neighbours]


def _candidate(row: Row, measure: str) -> float | None:
    return next((float(stake["share"]) for stake in row["stakes"] if stake["measure"] == measure), None)


def _neighbour(campaign: str, item: _Scored, share: float, distance: float) -> Neighbour:
    return {
        "campaign": campaign,
        "id": item.row["id"],
        "type": item.row["type"],
        "share": share,
        "distance": distance,
        "score": item.score,
        "level": item.level,
        "oracle_level": item.row["level"],
        "decided_by": item.decided_by,
        "decisive": item.decided_by == item.row["id"],
        "draft": draft_name(item.row["id"]) or None,
    }


# --- State codec ------------------------------------------------------------------------------------------

_NUMBER = re.compile(r"(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?", re.ASCII)
_NAME = re.compile(r"[A-Za-z0-9._-]+")


def encode_state(state: ReplayState, index: Mapping[str, Any]) -> str:
    """The URL hash of ``state``, without the ``#``; ``""`` for the default state.

    ``&``-separated ``key=value`` fields, only those that differ from ``default_state``, in the order of
    ``STATE_KEYS``: ``ref=<measure>:<number>,...`` (index order), ``campaigns=<name>,...`` (index
    order; empty for none), ``types=<type>,...`` (sorted), ``base=<name>:<level>,...`` (the switched drafts in index
    order, then the switched event types sorted) and ``focus=<measure>``. A draft name is a slug and an event type
    holds a dot, so the two never meet. A number is written by ``number_text``.
    """
    default = default_state(index)
    fields: list[str] = []
    changed = [
        f"{measure}:{number_text(state.references[measure])}"
        for measure in index["measures"]
        if state.references[measure] != default.references[measure]
    ]
    if changed:
        fields.append("ref=" + ",".join(changed))
    campaigns = [name for name in index["campaigns"] if name in state.campaigns]
    if campaigns != list(default.campaigns):
        fields.append("campaigns=" + ",".join(campaigns))
    if state.types:
        fields.append("types=" + ",".join(sorted(state.types)))
    bases = [
        f"{name}:{state.bases[name]}"
        for name in default.bases
        if name in state.bases and state.bases[name] != default.bases[name]
    ]
    bases += [f"{event_type}:{level}" for event_type, level in switched_types(state, index).items()]
    if bases:
        fields.append("base=" + ",".join(bases))
    if state.focus is not None:
        fields.append(f"focus={state.focus}")
    return "&".join(fields)


def decode_state(text: str, index: Mapping[str, Any]) -> ReplayState:
    """The state of a URL hash written by ``encode_state``; a leading ``#`` and any key order are accepted.

    Raises ``ReplayStateError`` for an unknown or repeated key, an unknown or repeated measure, campaign, type or
    draft, a base naming no draft or event type of the index's ``kinds``, a reference that is not a positive number,
    or a base that is not a level. The filter's type names are checked against
    the rows by ``replay``. A type switched to its code's base level is dropped.
    """
    default = default_state(index)
    references = dict(default.references)
    campaigns = default.campaigns
    types: tuple[str, ...] = ()
    bases = dict(default.bases)
    type_bases: dict[str, str] = {}
    focus: str | None = None
    body = text[1:] if text.startswith("#") else text
    seen: set[str] = set()
    for part in body.split("&") if body else ():
        key, separator, value = part.partition("=")
        if not separator:
            raise ReplayStateError(f"state hash field {part!r} is not key=value")
        if key not in STATE_KEYS:
            raise ReplayStateError(f"unknown state hash key {key!r} (known: {', '.join(STATE_KEYS)})")
        if key in seen:
            raise ReplayStateError(f"state hash key {key!r} is repeated")
        seen.add(key)
        if key == "ref":
            references.update(_decode_references(value, index))
        elif key == "campaigns":
            names = _names(value, "campaign", allow_empty=True)
            unknown = [name for name in names if name not in index["campaigns"]]
            if unknown:
                known = ", ".join(index["campaigns"])
                raise ReplayStateError(f"unknown campaign(s) in the state hash: {', '.join(unknown)} (known: {known})")
            campaigns = tuple(name for name in index["campaigns"] if name in names)
        elif key == "types":
            types = tuple(sorted(_names(value, "type", allow_empty=False)))
        elif key == "base":
            drafts, type_bases = _decode_bases(value, index)
            bases.update(drafts)
        else:
            if value not in index["measures"]:
                raise ReplayStateError(f"unknown focus measure {value!r} in the state hash")
            focus = value
    state = ReplayState(references=references, campaigns=campaigns, types=types, focus=focus, bases=bases)
    return replace(state, type_bases=switched_types(replace(state, type_bases=type_bases), index))


def _decode_bases(value: str, index: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    """The draft bases and the event types' base levels of a ``base`` value."""
    names = [draft["name"] for draft in index["drafts"]]
    levels = list(index["constants"]["level_bands"])
    bases: dict[str, str] = {}
    type_bases: dict[str, str] = {}
    if not value:
        raise ReplayStateError("state hash key 'base' lists no base")
    for item in value.split(","):
        name, separator, level = item.partition(":")
        if not separator:
            raise ReplayStateError(f"state hash base {item!r} is not draft:level or type:level")
        if name in bases or name in type_bases:
            raise ReplayStateError(f"{name!r} is repeated in the state hash's base levels")
        if name in names:
            if level not in levels:
                raise ReplayStateError(
                    f"the base of draft stake {name} must be a level ({', '.join(levels)}), not {level!r}"
                )
            bases[name] = level
        elif name in index["kinds"]:
            if level not in levels:
                raise ReplayStateError(f"the base level of {name} must be a level ({', '.join(levels)}), not {level!r}")
            type_bases[name] = level
        else:
            raise ReplayStateError(
                f"unknown draft stake or event type {name!r} in the state hash "
                f"(drafts: {', '.join(names) or '(none)'}; types: the index's kinds)"
            )
    return bases, type_bases


def _decode_references(value: str, index: Mapping[str, Any]) -> dict[str, float]:
    references: dict[str, float] = {}
    if not value:
        raise ReplayStateError("state hash key 'ref' lists no reference")
    for item in value.split(","):
        measure, separator, number = item.partition(":")
        if not separator:
            raise ReplayStateError(f"state hash reference {item!r} is not measure:number")
        if measure not in index["measures"]:
            raise ReplayStateError(
                f"unknown measure {measure!r} in the state hash (known: {', '.join(index['measures'])})"
            )
        if measure in references:
            raise ReplayStateError(f"measure {measure!r} is repeated in the state hash")
        parsed = float(number) if _NUMBER.fullmatch(number) else math.nan
        if not math.isfinite(parsed) or parsed <= 0:
            raise ReplayStateError(f"the reference of {measure} must be a positive number, not {number!r}")
        references[measure] = parsed
    return references


def _names(value: str, what: str, *, allow_empty: bool) -> list[str]:
    if not value:
        if allow_empty:
            return []
        raise ReplayStateError(f"state hash lists no {what}")
    names = value.split(",")
    for name in names:
        if not _NAME.fullmatch(name):
            raise ReplayStateError(f"state hash {what} {name!r} is not a name")
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise ReplayStateError(f"{what}(s) repeated in the state hash: {', '.join(repeated)}")
    return names


def number_text(value: float) -> str:
    """``value`` as the state hash and the readout write it: the shortest digits that read back to it, always
    positional and without a trailing ``.0`` (``0.002``, ``0.00002``, ``5``)."""
    return format(Decimal(repr(float(value))).normalize(), "f")
