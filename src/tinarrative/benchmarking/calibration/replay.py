"""The replay: the calibration table rescored for a calibration state, and the state's URL-hash codec.

It is the only replay; the calibration page draws what the server answers from it (ADR-0022).
"""

from __future__ import annotations

import heapq
import math
import re
import threading
from collections import Counter
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal, TypedDict

from tinarrative.benchmarking.calibration.drafts import draft_name
from tinarrative.benchmarking.calibration.table import SCHEMA_VERSION as SCHEMA_VERSION
from tinarrative.benchmarking.calibration.table import read_campaign, read_index
from tinarrative.model.events import SIGNIFICANCE_ORDER, Significance
from tinarrative.narrative.scalings import check_shares, cut_off, decided_outright, midpoint, own_score, scale
from tinarrative.narrative.significance import settled_score

STATE_KEYS: Final = ("rise", "drop", "scaling", "campaigns", "types", "base", "focus")
"""The hash keys, in the order ``encode_state`` writes them."""

LEVELS: Final = [level.value for level in SIGNIFICANCE_ORDER]
"""The levels, least significant first: the code's, not the index's."""

Row = Mapping[str, Any]
Verdict = Literal["keeps_members", "loses_members", "falls_apart", "could_become_member"]


class ReplayError(ValueError):
    """A calibration table the replay cannot evaluate: an unknown cited row, or a citation that is not to an earlier
    layer."""


class ReplayStateError(ReplayError):
    """A calibration state or state hash that names an unknown or repeated key, scaling, measure, campaign or type, or
    holds an invalid value."""


@dataclass(frozen=True)
class ReplayState:
    """What the replay is asked: the rise share and any drop share of each scaling, the scaling each event type uses,
    the enabled campaigns, a type filter, a base level per draft share, the base levels tried on event types and the
    focus.

    ``rises`` holds every scaling of the index's ``scalings`` and every split-off one; ``drops`` those with a drop
    share, the others keeping the default width. ``scalings`` holds the reassigned types: a type mapped to its own
    name is split off into a scaling of its own, starting as a copy of its code scaling; one mapped to another
    scaling on the same measure is joined to it. ``types`` empty means every type. ``bases`` empty means each draft's
    own base. ``type_bases`` holds the switched types; a type absent, or at the code's base level (the index's
    ``kinds``), keeps the code's. ``focus`` is the page's focused measure; the output does not depend on it.
    """

    rises: Mapping[str, float]
    campaigns: tuple[str, ...]
    types: tuple[str, ...] = ()
    focus: str | None = None
    bases: Mapping[str, str] = field(default_factory=dict)
    type_bases: Mapping[str, str] = field(default_factory=dict)
    drops: Mapping[str, float] = field(default_factory=dict)
    scalings: Mapping[str, str] = field(default_factory=dict)


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
    """Rows at each oracle level: the pipeline at the code's scalings."""


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
    stale_share: bool
    """The group's own share still counts the members it lost."""


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
    """The draft share of a draft row; ``None`` for a real one."""


class Sides(TypedDict):
    below: list[Neighbour]
    above: list[Neighbour]


class Cutoff(TypedDict):
    step: int
    """The levels an event moves from its starting level past this share: 1 at the rise share, -1 at the drop share."""
    offset: float
    """``log10(cut-off / midpoint)``, the midpoint the scaling's derived √(drop × rise)."""
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
    """Rows whose score a cited row set instead of the draft's own share."""


class StateResult(TypedDict):
    rises: dict[str, float]
    drops: dict[str, float]
    scalings: dict[str, str]
    """The reassigned types only, sorted."""
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
    then type, then the from and to levels in band order. ``cutoffs`` hold every scaling of ``state.rises`` in index
    order then the split-off ones sorted, each ascending by step; neighbours are nearest first, then by campaign
    order and id. Scores, steps and counts are integers, shares, offsets and distances plain floats.
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


@dataclass(slots=True)
class _Scored:
    row: Row
    score: int
    level: str
    decided_by: str
    start: int
    """The base the row's own score started from."""
    member: MemberResult | None = None


def default_state(index: Mapping[str, Any]) -> ReplayState:
    """The code's scalings, every campaign and each draft's own base: the state whose replay is the pipeline."""
    scalings = index["scalings"]
    rises = {name: float(spec["rise"]) for name, spec in scalings.items()}
    drops = {name: float(spec["drop"]) for name, spec in scalings.items() if spec["drop"] is not None}
    bases = {draft["name"]: draft["base"] for draft in index["drafts"]}
    return ReplayState(rises=rises, drops=drops, campaigns=tuple(index["campaigns"]), bases=bases)


def code_scaling(index: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    """The index's scaling of ``name``; for a split-off type, the code scaling it starts as a copy of.
    ``ReplayStateError`` for a name that is neither."""
    if name in index["scalings"]:
        return index["scalings"][name]  # type: ignore[no-any-return]
    own = index["kinds"].get(name, {}).get("scaling")
    if own is None:
        raise ReplayStateError(f"unknown scaling {name!r} (known: {', '.join(index['scalings'])}, or a scaled type)")
    return index["scalings"][own]  # type: ignore[no-any-return]


def type_scaling(index: Mapping[str, Any], state: ReplayState, event_type: str) -> str | None:
    """The scaling ``event_type`` uses in ``state``: its reassigned one, else its kind's (``None`` for none)."""
    if event_type in state.scalings:
        return state.scalings[event_type]
    kind = index["kinds"].get(event_type)
    return None if kind is None else kind.get("scaling")


def with_scalings(state: ReplayState, index: Mapping[str, Any], scalings: Mapping[str, str]) -> ReplayState:
    """``state`` with ``scalings`` reassigned on top of its own: a type at its kind's scaling is dropped, a split one
    gains its own rise and drop shares as a copy of its code scaling, and a scaling no type is split into any more
    loses them. ``ReplayStateError`` for an unscaled type, or a scaling unknown or on another measure."""
    kinds = index["kinds"]
    merged = {**state.scalings, **scalings}
    switched: dict[str, str] = {}
    for event_type, name in sorted(merged.items()):
        own = kinds.get(event_type, {}).get("scaling")
        if own is None:
            raise ReplayStateError(f"event type {event_type!r} has no scaling to reassign")
        if name == own:
            continue
        measure = index["scalings"][own]["measure"]
        if name != event_type and (name not in index["scalings"] and merged.get(name) != name):
            raise ReplayStateError(
                f"unknown scaling {name!r} for {event_type} (known: {', '.join(index['scalings'])}, or a split type)"
            )
        if code_scaling(index, name)["measure"] != measure:
            raise ReplayStateError(f"{event_type} reads {measure}; scaling {name!r} reads another measure")
        switched[event_type] = name
    split = {name for event_type, name in switched.items() if name == event_type}
    rises = {name: value for name, value in state.rises.items() if name in index["scalings"] or name in split}
    drops = {name: value for name, value in state.drops.items() if name in index["scalings"] or name in split}
    for name in sorted(split - set(state.rises)):
        spec = code_scaling(index, name)
        rises[name] = state.rises.get(kinds[name]["scaling"], float(spec["rise"]))
        copied = state.drops.get(kinds[name]["scaling"])
        if copied is not None:
            drops[name] = copied
    return replace(state, rises=rises, drops=drops, scalings=switched)


def scaling_order(index: Mapping[str, Any], state: ReplayState) -> list[str]:
    """Every scaling of ``state``: the index's in its order, then the split-off ones sorted."""
    return [*index["scalings"], *sorted(name for name in state.rises if name not in index["scalings"])]


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
    return prepare(index, tables, drafts).replay(state)


class Unfiltered(TypedDict):
    """The aggregates of a filtered state's replay without its type filter."""

    moves: list[Move]
    level_counts: dict[str, dict[str, LevelCounts]]
    """Each enabled campaign's."""
    members: dict[str, list[MemberResult]]
    """Each enabled campaign's."""


@dataclass(frozen=True)
class _Plan:
    """One campaign's rows and draft rows as the replay walks them, their citations checked once."""

    rows: Sequence[Row]
    order: tuple[int, ...]
    """The row positions in layer order."""
    cited: tuple[tuple[int, ...], ...]
    """The positions of the rows each row cites."""
    gates: tuple[_Gate | None, ...]
    """The member gate each row is a group of."""
    member_gates: tuple[_Gate | None, ...]
    """The member gate each row is a member type of."""
    code_scalings: tuple[tuple[str, ...], ...]
    """The scaling of each share of each row at its kind's scaling."""
    by_type: Mapping[str, tuple[int, ...]]
    shadows: Sequence[Row]
    shadow_cited: tuple[tuple[int, ...], ...]
    shadow_gates: tuple[_Gate | None, ...]
    shadow_drafts: tuple[str, ...]
    """The draft each draft row belongs to."""
    shadow_scalings: tuple[tuple[str, ...], ...]
    """The scaling of each share of each draft row: its draft's per measure."""
    positions: Mapping[str, int]
    """The row positions by id."""
    reachable: tuple[int, ...]
    """The positions, in layer order, of the rows a share can reach: a row with a share, or one citing such a row."""
    unreachable: tuple[int, ...]
    """The other positions, in layer order: no rise, drop or scaling changes their scores."""
    member_positions: tuple[int, ...]
    """The positions, in table order, of the rows a member result can be given: groups and member types."""


@dataclass(frozen=True)
class _Tally:
    """What the aggregates count of a set of scored rows, by event type; two tallies of disjoint rows add up to the
    tally of both."""

    replayed: Counter[tuple[str, str]]
    """Rows by type and level after the replay; a group that falls apart is not counted."""
    baseline: Counter[tuple[str, str]]
    """Rows by type and oracle level."""
    moved: Counter[tuple[str, str, str]]
    """Rows by type, oracle level and level after the replay, where the two differ; a fallen group is not counted."""
    via_cited: Counter[tuple[str, str, str]]
    """The rows of ``moved`` a cited row decided."""
    package: Counter[str]
    """Narrative rows by type at the package level or above after the replay, a fallen group not counted."""
    package_baseline: Counter[str]
    """Narrative rows by type at the package level or above at the oracle."""
    members_changed: Counter[str]
    """Groups by type that lose members or fall apart."""

    def __add__(self, other: _Tally) -> _Tally:
        return _Tally(
            *(
                getattr(self, name) + getattr(other, name)
                for name in (
                    "replayed",
                    "baseline",
                    "moved",
                    "via_cited",
                    "package",
                    "package_baseline",
                    "members_changed",
                )
            )
        )

    def of_types(self, types: frozenset[str]) -> _Tally:
        """The tally of the rows of ``types``; all of them for no filter."""
        if not types:
            return self

        def kept(counter: Counter[Any], typed: bool) -> Counter[Any]:
            return Counter({key: count for key, count in counter.items() if (key[0] if typed else key) in types})

        return _Tally(
            kept(self.replayed, True),
            kept(self.baseline, True),
            kept(self.moved, True),
            kept(self.via_cited, True),
            kept(self.package, False),
            kept(self.package_baseline, False),
            kept(self.members_changed, False),
        )


@dataclass(frozen=True)
class _Fixed:
    """One campaign's rows no share reaches, scored for one choice of switched base levels. Shared between replays
    and never changed: a replay copies ``done`` and ``events`` before it fills in the reachable rows."""

    done: list[_Scored]
    """The scored rows at the unreachable positions; ``None`` at the reachable ones."""
    events: list[EventResult]
    """``done`` as the replay's events; ``None`` at the reachable positions."""
    tally: _Tally


@dataclass(frozen=True)
class _Group:
    """The reachable rows of one campaign that the same scalings reach: through their own shares or the rows they
    cite, transitively. Only those scalings' shares change their scores."""

    scalings: tuple[str, ...]
    """Sorted."""
    positions: tuple[int, ...]
    """In layer order."""


@dataclass(frozen=True)
class _Part:
    """One group's rows scored for one choice of its scalings' shares and the switched base levels. Shared between
    replays and never changed."""

    done: tuple[_Scored, ...]
    """Aligned with the group's positions."""
    events: tuple[EventResult, ...]
    tally: _Tally


@dataclass(frozen=True)
class _Scaled:
    """What one choice of reassigned scalings fixes: each row's scaling per share, each scaling's cut-off
    candidates as ``(position, share)`` pairs per campaign, the real rows' and the draft rows', and each campaign's
    reachable rows grouped by the scalings that reach them."""

    scalings: Mapping[str, Sequence[tuple[str, ...]]]
    candidates: Mapping[str, Mapping[str, tuple[list[tuple[int, float]], list[tuple[int, float]]]]]
    groups: Mapping[str, tuple[_Group, ...]]
    group_of: Mapping[str, Mapping[int, int]]
    """Each reachable position's group, by its index in ``groups``."""


_SCALED_KEPT: Final = 16
"""The scalings choices a prepared table keeps derived: a page session tries a few at a time."""

_FIXED_KEPT: Final = 4
"""The base-level choices a prepared table keeps its unreachable rows scored for; each holds every such row, about
30 MB on the two full sample campaigns."""

_PARTS_KEPT: Final = 4
"""The share choices a prepared table keeps each group of reachable rows scored for, on average: a drag over one
scaling's rise share rescores only the groups it reaches, and stepping back finds the last few kept."""

_CUTS_KEPT: Final = 64
"""The cut-off picks a prepared table keeps: every scaling's for the last few states, so a drag over one scaling
picks the nearest rows of only that one."""


@dataclass(frozen=True, eq=False)
class Prepared:
    """A calibration table with the work no calibration state changes done once (``prepare``); its replays equal
    ``replay``'s. What depends only on the state's reassigned scalings is derived on first use and kept for the last
    ``_SCALED_KEPT`` choices; the rows no share reaches are scored on first use of a choice of switched base levels
    and kept for the ``_FIXED_KEPT`` used last. The reachable rows are scored per group of the scalings that reach
    them, and kept for the last few choices of those scalings' shares; the nearest rows of each cut-off are picked
    per scaling and kept likewise, so a replay that changes one scaling's shares redoes only what that scaling
    reaches. Neither cache changes ``derived``: both turn over while a slider moves. Safe to share between threads.
    Its replays share their scored rows' events and members with each other: read them, never change them."""

    index: Mapping[str, Any]
    plans: Mapping[str, _Plan]
    types: frozenset[str]
    """The event types of every row."""
    fixed_types: frozenset[str]
    """The event types of the rows no share reaches: only their switched base levels change those rows."""
    _scaled: dict[tuple[tuple[str, str], ...], _Scaled] = field(default_factory=dict, repr=False)
    _fixed: dict[tuple[str, tuple[tuple[str, str], ...]], _Fixed] = field(default_factory=dict, repr=False)
    _parts: dict[tuple[Any, ...], _Part] = field(default_factory=dict, repr=False)
    _cuts: dict[tuple[Any, ...], list[_Pick]] = field(default_factory=dict, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _derived: list[int] = field(default_factory=lambda: [0], repr=False)

    @property
    def derived(self) -> int:
        """How many scalings or base-level choices have been derived and kept so far; it grows whenever the table
        keeps more objects for later replays."""
        return self._derived[0]

    @property
    def positions(self) -> dict[str, Mapping[str, int]]:
        """Each campaign's row positions by id."""
        return {name: plan.positions for name, plan in self.plans.items()}

    def replay(self, state: ReplayState) -> Replay:
        """``replay`` of this table for ``state``."""
        return self._replay(state, unfiltered=False)[0]

    def replay_with_unfiltered(self, state: ReplayState) -> tuple[Replay, Unfiltered | None]:
        """``replay`` for ``state`` and, when it filters types, the aggregates without the filter, counted from the
        same scored rows; ``None`` without a filter."""
        return self._replay(state, unfiltered=True)

    def _replay(self, state: ReplayState, *, unfiltered: bool) -> tuple[Replay, Unfiltered | None]:
        index = self.index
        state = _with_bases(index, state)
        _validate(index, self.plans, self.types, state)
        scaled = self._scaled_for(state)
        types = frozenset(state.types)
        campaigns: dict[str, _Campaign] = {}
        for name in state.campaigns:
            plan = self.plans[name]
            fixed = self._fixed_for(name, state)
            done = list(fixed.done)
            events = list(fixed.events)
            tally = fixed.tally
            for group, part in zip(scaled.groups[name], self._parts_for(name, state, scaled, done), strict=True):
                for position, event in zip(group.positions, part.events, strict=True):
                    events[position] = event
                tally = tally + part.tally
            campaigns[name] = _Campaign(
                done=done,
                events=events,
                tally=tally,
                members=[
                    item.member
                    for item in (done[position] for position in plan.member_positions)
                    if item.member is not None
                ],
                shadows=_score_drafts(index, plan, done, state),
            )
        result = _result(index, state, campaigns, types, scaled, self._picks)
        if not unfiltered or not types:
            return result, None
        return result, {
            "moves": _moves(sum((campaign.tally for campaign in campaigns.values()), _empty_tally()), LEVELS),
            "level_counts": {name: _level_counts(campaign.tally, LEVELS) for name, campaign in campaigns.items()},
            "members": {name: list(campaign.members) for name, campaign in campaigns.items()},
        }

    def _fixed_for(self, campaign: str, state: ReplayState) -> _Fixed:
        """The campaign's unreachable rows scored for ``state``'s switched base levels of their types."""
        switched = switched_types(state, self.index)
        key = (
            campaign,
            tuple((event_type, level) for event_type, level in switched.items() if event_type in self.fixed_types),
        )
        with self._lock:
            found = self._fixed.pop(key, None)
            if found is not None:
                # Kept last, so the choices evicted are the least recently used.
                self._fixed[key] = found
        if found is not None:
            return found
        plan = self.plans[campaign]
        done: list[_Scored] = [None] * len(plan.rows)  # type: ignore[list-item]  # the reachable rows stay None
        _score(self.index, plan, plan.unreachable, done, plan.code_scalings, state)
        events: list[EventResult] = [None] * len(plan.rows)  # type: ignore[list-item]  # likewise
        for position in plan.unreachable:
            events[position] = _event(done[position])
        derived = _Fixed(
            done, events, _tally([done[position] for position in plan.unreachable], _package_levels(self.index))
        )
        with self._lock:
            if len(self._fixed) >= _FIXED_KEPT * len(self.plans):
                del self._fixed[next(iter(self._fixed))]
            self._fixed[key] = derived
            self._derived[0] += 1
        return derived

    def _parts_for(self, campaign: str, state: ReplayState, scaled: _Scaled, done: list[_Scored]) -> list[_Part]:
        """The campaign's groups of reachable rows scored for ``state``, in group order, their rows filled into
        ``done``; the groups no kept part has are scored together, in layer order, after the kept ones are filled
        in, since a group cites only rows of groups whose scalings it shares."""
        plan = self.plans[campaign]
        switched = tuple(switched_types(state, self.index).items())
        common = (campaign, tuple(sorted(state.scalings.items())), switched)
        keys = [
            (*common, group.scalings, tuple((state.rises[name], state.drops.get(name)) for name in group.scalings))
            for group in scaled.groups[campaign]
        ]
        parts: list[_Part | None] = []
        with self._lock:
            for key in keys:
                found = self._parts.pop(key, None)
                if found is not None:
                    # Kept last, so the parts evicted are the least recently used.
                    self._parts[key] = found
                parts.append(found)
        for group, part in zip(scaled.groups[campaign], parts, strict=True):
            if part is not None:
                for position, item in zip(group.positions, part.done, strict=True):
                    done[position] = item
        missing = {index for index, part in enumerate(parts) if part is None}
        if not missing:
            return parts  # type: ignore[return-value]  # every group was kept
        group_of = scaled.group_of[campaign]
        positions = [position for position in plan.reachable if group_of[position] in missing]
        _score(self.index, plan, positions, done, scaled.scalings[campaign], state)
        package = _package_levels(self.index)
        fresh: list[tuple[tuple[Any, ...], _Part]] = []
        for index in sorted(missing):
            items = tuple(done[position] for position in scaled.groups[campaign][index].positions)
            part = _Part(items, tuple(_event(item) for item in items), _tally(items, package))
            parts[index] = part
            fresh.append((keys[index], part))
        with self._lock:
            for key, part in fresh:
                if len(self._parts) >= _PARTS_KEPT * sum(len(groups) for groups in scaled.groups.values()):
                    del self._parts[next(iter(self._parts))]
                self._parts[key] = part
        return parts  # type: ignore[return-value]  # every group is scored now

    def _picks(self, key: tuple[Any, ...], pick: Callable[[], list[_Pick]]) -> list[_Pick]:
        """The cut-off picks kept under ``key``, picked now when none are."""
        with self._lock:
            found = self._cuts.pop(key, None)
            if found is not None:
                self._cuts[key] = found
        if found is not None:
            return found
        picked = pick()
        with self._lock:
            if len(self._cuts) >= _CUTS_KEPT:
                del self._cuts[next(iter(self._cuts))]
            self._cuts[key] = picked
        return picked

    def _scaled_for(self, state: ReplayState) -> _Scaled:
        key = tuple(sorted(state.scalings.items()))
        with self._lock:
            found = self._scaled.get(key)
        if found is not None:
            return found
        derived = _derive_scaled(self.plans, state)
        with self._lock:
            if len(self._scaled) >= _SCALED_KEPT:
                del self._scaled[next(iter(self._scaled))]
            self._scaled[key] = derived
            self._derived[0] += 1
        return derived


@dataclass(frozen=True)
class _Campaign:
    """One enabled campaign of a replay: the cached unreachable rows with the reachable ones rescored."""

    done: list[_Scored]
    """Every row scored, in table order."""
    events: list[EventResult]
    tally: _Tally
    """Every row's, unfiltered."""
    members: list[MemberResult]
    """Every row's, unfiltered, in table order."""
    shadows: list[_Scored]
    """The draft rows scored, in table order."""


def prepare(
    index: Mapping[str, Any], tables: Mapping[str, Sequence[Row]], drafts: Mapping[str, Sequence[Row]] | None = None
) -> Prepared:
    """The table ready to replay any state. Raises ``ReplayError`` for a table whose citations do not run to earlier
    layers, a share no scaling of its row's type reads, or a draft row of no declared draft."""
    drafts = drafts or {}
    gates = [
        _Gate(frozenset(gate["group_types"]), gate["member_type"], frozenset(gate["admitted_levels"]), gate["minimum"])
        for gate in index["member_gates"]
    ]
    plans = {name: _plan(index, rows, drafts.get(name, ()), gates) for name, rows in tables.items()}
    return Prepared(
        index=index,
        plans=plans,
        types=frozenset(row["type"] for rows in tables.values() for row in rows),
        fixed_types=frozenset(plan.rows[position]["type"] for plan in plans.values() for position in plan.unreachable),
    )


def _result(
    index: Mapping[str, Any],
    state: ReplayState,
    campaigns: Mapping[str, _Campaign],
    types: frozenset[str],
    scaled: _Scaled,
    picks: Callable[[tuple[Any, ...], Callable[[], list[_Pick]]], list[_Pick]],
) -> Replay:
    levels = LEVELS
    tallies = {name: campaign.tally.of_types(types) for name, campaign in campaigns.items()}
    every = sum(tallies.values(), _empty_tally())
    shadowed = {
        name: [item for item in campaign.shadows if not types or item.row["type"] in types]
        for name, campaign in campaigns.items()
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "state": {
            "rises": {name: state.rises[name] for name in scaling_order(index, state)},
            "drops": {name: state.drops[name] for name in scaling_order(index, state) if name in state.drops},
            "scalings": dict(sorted(state.scalings.items())),
            "campaigns": list(state.campaigns),
            "types": list(state.types),
            "bases": {draft["name"]: state.bases[draft["name"]] for draft in index["drafts"]},
            "type_bases": switched_types(state, index),
            "focus": state.focus,
        },
        "campaigns": {
            name: {
                "events": campaign.events,
                "level_counts": _level_counts(tallies[name], levels),
                "members": [member for member in campaign.members if not types or member["type"] in types],
                "drafts": [_event(item) for item in campaign.shadows],
            }
            for name, campaign in campaigns.items()
        },
        "totals": _totals(every),
        "moves": _moves(every, levels),
        "cutoffs": {
            name: _cutoffs(name, state, index, scaled, campaigns, picks) for name in scaling_order(index, state)
        },
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


def switched_scalings(state: ReplayState, index: Mapping[str, Any]) -> dict[str, str]:
    """The types of ``state.scalings`` away from their kind's scaling, sorted by type."""
    kinds = index["kinds"]
    return {
        event_type: name
        for event_type, name in sorted(state.scalings.items())
        if kinds.get(event_type, {}).get("scaling") != name
    }


def _event(item: _Scored) -> EventResult:
    return {"id": item.row["id"], "score": item.score, "level": item.level, "decided_by": item.decided_by}


def _with_bases(index: Mapping[str, Any], state: ReplayState) -> ReplayState:
    if state.bases:
        return state
    return replace(state, bases=default_state(index).bases)


def _validate(index: Mapping[str, Any], campaigns: Collection[str], known: frozenset[str], state: ReplayState) -> None:
    measures = list(index["measures"])
    split = sorted(name for event_type, name in state.scalings.items() if name == event_type)
    names = [*index["scalings"], *split]
    if sorted(state.rises) != sorted(names):
        raise ReplayStateError(f"the state needs a rise share for exactly the scalings {', '.join(names)}")
    unknown = sorted(set(state.drops) - set(names))
    if unknown:
        raise ReplayStateError(f"drop share(s) for unknown scaling(s): {', '.join(unknown)}")
    for name, value in state.rises.items():
        try:
            check_shares(value, state.drops.get(name))
        except ValueError as error:
            raise ReplayStateError(f"scaling {name}: {error}") from None
    if with_scalings(replace(state, scalings={}), index, state.scalings).scalings != dict(state.scalings):
        raise ReplayStateError("the state's scalings are not reassigned types (use with_scalings)")
    for name in state.campaigns:
        if name not in campaigns:
            raise ReplayStateError(f"unknown campaign {name!r} (known: {', '.join(campaigns)})")
    unknown = sorted(set(state.types) - known)
    if unknown:
        raise ReplayStateError(f"unknown event type(s) in the filter: {', '.join(unknown)}")
    if state.focus is not None and state.focus not in measures:
        raise ReplayStateError(f"unknown focus measure {state.focus!r}")
    names = [draft["name"] for draft in index["drafts"]]
    if sorted(state.bases) != sorted(names):
        raise ReplayStateError(f"the state needs a base for exactly the draft shares {', '.join(names) or '(none)'}")
    for name, level in state.bases.items():
        if level not in LEVELS:
            raise ReplayStateError(f"the base of draft share {name} must be a level, not {level!r}")
    unswitchable = sorted(set(state.type_bases) - set(index["kinds"]))
    if unswitchable:
        raise ReplayStateError(f"unknown event type(s) in the base levels: {', '.join(unswitchable)}")
    for event_type, level in state.type_bases.items():
        if level not in LEVELS:
            raise ReplayStateError(f"the base level of {event_type} must be a level, not {level!r}")


def _plan(index: Mapping[str, Any], rows: Sequence[Row], shadows: Sequence[Row], gates: Sequence[_Gate]) -> _Plan:
    """The walk of one campaign's rows: their layer order, citations, gates and code scalings, checked once; a draft
    row may cite only real rows of an earlier layer."""
    layer_of = index["layers"]
    declared = {draft["name"]: draft for draft in index["drafts"]}

    def layer(row: Row) -> int:
        return int(layer_of.get(row["type"], 0)) if row["tier"] == "narrative" else 0

    positions = {row["id"]: position for position, row in enumerate(rows)}

    def cited(row: Row) -> tuple[int, ...]:
        own_layer = layer(row)
        for name in row["cited"]:
            if name not in positions:
                raise ReplayError(f"{row['id']} cites {name}, which is not a row of its campaign")
            if layer(rows[positions[name]]) >= own_layer:
                raise ReplayError(f"{row['id']} (layer {own_layer}) cites {name}, which is not in an earlier layer")
        return tuple(positions[name] for name in row["cited"])

    def group_gate(row: Row) -> _Gate | None:
        return next((gate for gate in gates if row["type"] in gate.group_types), None)

    def scalings_of(row: Row, draft: str) -> tuple[str, ...]:
        """The scaling of each share of the row: its draft's per measure, else its kind's."""
        named: list[str] = []
        for share in row["shares"]:
            if draft:
                scaling = declared[draft]["scalings"].get(share["measure"])
            elif row["type"] not in index["kinds"]:
                # Only a hand-built table holds a type its index does not: it reads the measure's starting scaling.
                scaling = share["measure"] if share["measure"] in index["scalings"] else None
            else:
                scaling = index["kinds"][row["type"]].get("scaling")
            if scaling is None or code_scaling(index, scaling)["measure"] != share["measure"]:
                raise ReplayError(f"{row['id']} has a share on {share['measure']}, which no scaling of its type reads")
            named.append(scaling)
        return tuple(named)

    order = tuple(sorted(range(len(rows)), key=lambda position: layer(rows[position])))
    cites: list[tuple[int, ...]] = [()] * len(rows)
    code: list[tuple[str, ...]] = [()] * len(rows)
    for position in order:
        cites[position] = cited(rows[position])
        code[position] = scalings_of(rows[position], "")
    by_type: dict[str, list[int]] = {}
    for position, row in enumerate(rows):
        by_type.setdefault(row["type"], []).append(position)
    names: list[str] = []
    for row in shadows:
        name = draft_name(row["id"])
        if name not in declared:
            raise ReplayError(f"{row['id']} is a row of no declared draft share")
        names.append(name)
    shadow_cited = tuple(cited(row) for row in shadows)
    # A row's citations are scored before it, so layer order settles reach in one pass.
    reached = [False] * len(rows)
    for position in order:
        reached[position] = bool(rows[position]["shares"]) or any(reached[found] for found in cites[position])
    group_gates = tuple(group_gate(row) for row in rows)
    member_gates = tuple(next((gate for gate in gates if row["type"] == gate.member_type), None) for row in rows)
    return _Plan(
        rows=rows,
        order=order,
        cited=tuple(cites),
        gates=group_gates,
        member_gates=member_gates,
        code_scalings=tuple(code),
        by_type={event_type: tuple(found) for event_type, found in by_type.items()},
        shadows=shadows,
        shadow_cited=shadow_cited,
        shadow_gates=tuple(group_gate(row) for row in shadows),
        shadow_drafts=tuple(names),
        shadow_scalings=tuple(scalings_of(row, name) for row, name in zip(shadows, names, strict=True)),
        positions=positions,
        reachable=tuple(position for position in order if reached[position]),
        unreachable=tuple(position for position in order if not reached[position]),
        member_positions=tuple(
            position
            for position in range(len(rows))
            if group_gates[position] is not None or member_gates[position] is not None
        ),
    )


def _derive_scaled(plans: Mapping[str, _Plan], state: ReplayState) -> _Scaled:
    """Each row's scalings under ``state.scalings``, each scaling's cut-off candidates and the groups of reachable
    rows; nothing else of ``state`` is read."""
    scalings: dict[str, list[tuple[str, ...]]] = {}
    candidates: dict[str, dict[str, tuple[list[tuple[int, float]], list[tuple[int, float]]]]] = {}
    groups: dict[str, tuple[_Group, ...]] = {}
    group_of: dict[str, dict[int, int]] = {}
    for campaign, plan in plans.items():
        own = list(plan.code_scalings)
        for event_type, name in state.scalings.items():
            for position in plan.by_type.get(event_type, ()):
                own[position] = (name,) * len(own[position])
        scalings[campaign] = own
        for side, (named, rows) in enumerate(((own, plan.rows), (plan.shadow_scalings, plan.shadows))):
            for position, (row, row_scalings) in enumerate(zip(rows, named, strict=True)):
                for share, scaling in zip(row["shares"], row_scalings, strict=True):
                    if share["share"] > 0:
                        sides = candidates.setdefault(scaling, {}).setdefault(campaign, ([], []))
                        sides[side].append((position, float(share["share"])))
        # Layer order scores a row's citations first, so the scalings reaching them are known by then; a cited row
        # outside the reachable ones is reached by none.
        reach: dict[int, frozenset[str]] = {}
        by_scalings: dict[tuple[str, ...], list[int]] = {}
        for position in plan.reachable:
            names = frozenset(own[position]).union(*(reach.get(found, frozenset()) for found in plan.cited[position]))
            reach[position] = names
            by_scalings.setdefault(tuple(sorted(names)), []).append(position)
        groups[campaign] = tuple(_Group(names, tuple(found)) for names, found in sorted(by_scalings.items()))
        group_of[campaign] = {
            position: index for index, group in enumerate(groups[campaign]) for position in group.positions
        }
    return _Scaled(scalings=scalings, candidates=candidates, groups=groups, group_of=group_of)


_Settle = Callable[[Row, int, list[_Scored], _Gate | None, tuple[str, ...]], _Scored]


def _settler(state: ReplayState) -> _Settle:
    """Score one row from its base, the rows it cites (already scored), its member gate and its shares' scalings."""
    rises, drops = state.rises, state.drops
    level_of: dict[int, str] = {}

    def settle(
        row: Row, base: int, cited_rows: list[_Scored], gate: _Gate | None, row_scalings: tuple[str, ...]
    ) -> _Scored:
        lost: list[str] = []
        if gate is not None:
            lost = [
                item.row["id"]
                for item in cited_rows
                if item.row["type"] == gate.member_type and item.level not in gate.admitted
            ]
            cited_rows = [item for item in cited_rows if item.row["id"] not in lost]
        outright = decided_outright(row["rule"] is not None, base)
        scales = (
            ()
            if outright
            else (
                scale(share["share"], rises[scaling], drops.get(scaling))
                for share, scaling in zip(row["shares"], row_scalings, strict=True)
            )
        )
        own = own_score(base, scales)
        best = max(cited_rows, key=lambda item: item.score, default=None)
        score = settled_score(own, (item.score for item in cited_rows))
        decided_by = row["id"] if best is None or score == own else best.decided_by
        level = level_of.get(score)
        if level is None:
            level = level_of[score] = Significance.of(score).value
        item = _Scored(row, score, level, decided_by, base)
        if gate is not None:
            item.member = _group_verdict(row, gate, cited_rows, lost)
        return item

    return settle


def _score(
    index: Mapping[str, Any],
    plan: _Plan,
    positions: Sequence[int],
    done: list[_Scored],
    scalings: Sequence[tuple[str, ...]],
    state: ReplayState,
) -> None:
    """Score the rows at ``positions`` into ``done``: in layer order, each row's citations scored already, here or
    before."""
    switched = switched_types(state, index)
    switched_bases = {event_type: Significance(level).base for event_type, level in switched.items()}
    settle = _settler(state)
    rows = plan.rows
    for position in positions:
        row = rows[position]
        # A context rule's decision keeps the row's own base; a tried base level replaces only the type's default.
        base = switched_bases[row["type"]] if row["rule"] is None and row["type"] in switched else int(row["base"])
        cited_rows = [done[found] for found in plan.cited[position]]
        done[position] = settle(row, base, cited_rows, plan.gates[position], scalings[position])
    for position in positions:
        member_gate = plan.member_gates[position]
        item = done[position]
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
                "stale_share": False,
            }


def _score_drafts(index: Mapping[str, Any], plan: _Plan, done: Sequence[_Scored], state: ReplayState) -> list[_Scored]:
    """The draft rows scored, in table order, against the scored real rows ``done``."""
    switched = switched_types(state, index)
    own_bases = {draft["name"]: draft["base"] for draft in index["drafts"]}
    settle = _settler(state)
    drafted: list[_Scored] = []
    for position, row in enumerate(plan.shadows):
        name = plan.shadow_drafts[position]
        # A switched draft base wins over a tried type level; a ruled row keeps the base its rule set.
        if row["ruled"]:
            base = int(row["base"])
        else:
            level = state.bases[name]
            if level == own_bases.get(name) and row["type"] in switched:
                level = switched[row["type"]]
            base = Significance(level).base
        cited_rows = [done[found] for found in plan.shadow_cited[position]]
        item = settle(row, base, cited_rows, plan.shadow_gates[position], plan.shadow_scalings[position])
        item.member = None
        drafted.append(item)
    return drafted


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
        "stale_share": bool(lost),
    }


def _fallen(item: _Scored) -> bool:
    return item.member is not None and item.member["verdict"] == "falls_apart"


def _package_levels(index: Mapping[str, Any]) -> frozenset[str]:
    """The levels the narrator package holds: the index's ``package_level`` and above."""
    return frozenset(LEVELS[LEVELS.index(index["constants"]["package_level"]) :])


def _empty_tally() -> _Tally:
    return _Tally(Counter(), Counter(), Counter(), Counter(), Counter(), Counter(), Counter())


def _tally(items: Iterable[_Scored], package: frozenset[str]) -> _Tally:
    """What the aggregates count of ``items``."""
    tally = _empty_tally()
    for item in items:
        row = item.row
        event_type, oracle, level = row["type"], row["level"], item.level
        fallen = _fallen(item)
        tally.baseline[event_type, oracle] += 1
        if not fallen:
            tally.replayed[event_type, level] += 1
            if level != oracle:
                tally.moved[event_type, oracle, level] += 1
                if item.decided_by != row["id"]:
                    tally.via_cited[event_type, oracle, level] += 1
        if row["tier"] == "narrative":
            if oracle in package:
                tally.package_baseline[event_type] += 1
            if level in package and not fallen:
                tally.package[event_type] += 1
        if item.member is not None and item.member["verdict"] in {"loses_members", "falls_apart"}:
            tally.members_changed[event_type] += 1
    return tally


def _level_counts(tally: _Tally, levels: Sequence[str]) -> dict[str, LevelCounts]:
    return {
        event_type: {
            "replay": {level: tally.replayed[event_type, level] for level in levels},
            "baseline": {level: tally.baseline[event_type, level] for level in levels},
        }
        for event_type in sorted({event_type for event_type, _ in tally.baseline})
    }


def _totals(tally: _Tally) -> Totals:
    replayed, baseline = tally.package.total(), tally.package_baseline.total()
    return {
        "events_moved": tally.moved.total(),
        "package": {"replay": replayed, "baseline": baseline, "change": replayed - baseline},
        "members_changed": tally.members_changed.total(),
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


def _moves(tally: _Tally, levels: Sequence[str]) -> list[Move]:
    counts, via = tally.moved, tally.via_cited
    ordered = sorted(counts, key=lambda key: (-counts[key], key[0], levels.index(key[1]), levels.index(key[2])))
    return [
        {"type": key[0], "from_level": key[1], "to_level": key[2], "count": counts[key], "via_cited": via[key]}
        for key in ordered
    ]


def cutoff_steps(starts: Iterable[int]) -> list[int]:
    """Every step a share can move an event of one of the ``starts`` bases, ascending: up to campaign-defining, and
    down to minor (to nothing below a trivial start)."""
    top = len(SIGNIFICANCE_ORDER) - 1
    floor = SIGNIFICANCE_ORDER.index(Significance.MINOR)
    steps: set[int] = set()
    for base in starts:
        rank = Significance.of(base).rank
        steps.update(range(1, top - rank + 1))
        if rank > floor:
            steps.update(range(-(rank - floor), 0))
    return sorted(steps)


def _cutoffs(
    name: str,
    state: ReplayState,
    index: Mapping[str, Any],
    scaled: _Scaled,
    campaigns: Mapping[str, _Campaign],
    picks: Callable[[tuple[Any, ...], Callable[[], list[_Pick]]], list[_Pick]],
) -> list[Cutoff]:
    """The cut-offs of scaling ``name`` at every step its rows' starting levels reach, each with the nearest rows
    of the scaling on each side, of the enabled campaigns and the filtered types; a row decided outright never
    counts. Which rows are nearest reads only their shares, ids, types and starting levels, so ``picks`` may keep
    the picks of a scaling whose shares a replay leaves alone; each pick is scored for this replay."""
    key = (
        name,
        tuple(sorted(state.scalings.items())),
        state.rises[name],
        state.drops.get(name),
        tuple(state.campaigns),
        tuple(sorted(state.types)),
        tuple(switched_types(state, index).items()),
        tuple(sorted(state.bases.items())),
    )

    def neighbours(chosen: Sequence[_Chosen]) -> list[Neighbour]:
        return [
            _neighbour(
                campaign, (campaigns[campaign].shadows if drafted else campaigns[campaign].done)[position], *rest
            )
            for campaign, drafted, position, *rest in chosen
        ]

    return [
        {
            "step": pick.step,
            "offset": pick.offset,
            "share": pick.share,
            "below": neighbours(pick.below),
            "above": neighbours(pick.above),
            "drafts": {
                draft: {"below": neighbours(below), "above": neighbours(above)}
                for draft, (below, above) in pick.drafts.items()
            },
        }
        for pick in picks(key, lambda: _pick(name, state, index, scaled, campaigns))
    ]


_Chosen = tuple[str, bool, int, float, float]
"""A row nearest a cut-off: its campaign, whether it is a draft row, its position, share and distance."""


@dataclass(frozen=True)
class _Pick:
    """One cut-off of a scaling and the rows nearest it on each side, not yet scored."""

    step: int
    offset: float
    share: float
    below: tuple[_Chosen, ...]
    above: tuple[_Chosen, ...]
    drafts: Mapping[str, tuple[tuple[_Chosen, ...], tuple[_Chosen, ...]]]


_Candidate = tuple[str, bool, int, _Scored, float]


def _pick(
    name: str, state: ReplayState, index: Mapping[str, Any], scaled: _Scaled, campaigns: Mapping[str, _Campaign]
) -> list[_Pick]:
    constants = index["constants"]
    rise, drop = state.rises[name], state.drops.get(name)
    centre = midpoint(rise, drop)
    types = frozenset(state.types)
    of_scaling = scaled.candidates.get(name, {})
    real: list[_Candidate] = []
    drafted: list[_Candidate] = []
    for campaign in state.campaigns:
        own_real, own_drafted = of_scaling.get(campaign, ([], []))
        scored = campaigns[campaign]
        for found, is_draft, pairs, items in (
            (real, False, own_real, scored.done),
            (drafted, True, own_drafted, scored.shadows),
        ):
            found.extend(
                (campaign, is_draft, position, items[position], share)
                for position, share in pairs
                if not types or items[position].row["type"] in types
            )
    names = [draft["name"] for draft in index["drafts"] if name in draft["scalings"].values()]
    by_draft = {draft: [entry for entry in drafted if draft_name(entry[3].row["id"]) == draft] for draft in names}
    result: list[_Pick] = []
    for step in cutoff_steps({entry[3].start for entry in real} | {entry[3].start for entry in drafted}):
        cut = cut_off(step, rise, drop)
        below, above = _sides(real, cut, step, state.campaigns, constants["neighbours"])
        drafts = {
            draft: _sides(by_draft[draft], cut, step, state.campaigns, constants["neighbours"]) for draft in names
        }
        result.append(_Pick(step, math.log10(cut / centre), cut, below, above, drafts))
    return result


def _sides(
    candidates: Sequence[_Candidate], cut: float, step: int, campaigns: Sequence[str], count: int
) -> tuple[tuple[_Chosen, ...], tuple[_Chosen, ...]]:
    rank = {name: order for order, name in enumerate(campaigns)}
    below: list[_Ranked] = []
    above: list[_Ranked] = []
    for order, (name, _, _, item, share) in enumerate(candidates):
        # A share on the cut-off moves past it: above a rise cut-off, below a drop one.
        side = below if share < cut or (share == cut and step < 0) else above
        side.append((abs(math.log10(share / cut)), rank[name], item.row["id"], order))
    return _nearest(below, candidates, count), _nearest(above, candidates, count)


_Ranked = tuple[float, int, str, int]
"""A cut-off candidate's distance, campaign rank, row id and position among the candidates; the last keeps ties in
candidate order."""


def _nearest(side: list[_Ranked], candidates: Sequence[_Candidate], count: int) -> tuple[_Chosen, ...]:
    """The ``count`` nearest of ``side``, out of thousands of candidates."""
    nearest: list[_Chosen] = []
    for distance, _, _, order in heapq.nsmallest(count, side):
        campaign, is_draft, position, _, share = candidates[order]
        nearest.append((campaign, is_draft, position, share, distance))
    return tuple(nearest)


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
    ``STATE_KEYS``: ``rise=<scaling>:<number>,...`` and ``drop=<scaling>:<number>,...`` (``scaling_order``; a split
    scaling's against the code scaling it copies), ``scaling=<type>:<scaling>,...`` (sorted; a type named as its own
    scaling is split off), ``campaigns=<name>,...`` (index order; empty for none), ``types=<type>,...`` (sorted),
    ``base=<name>:<level>,...`` (the switched drafts in index order, then the switched event types sorted) and
    ``focus=<measure>``. A draft name is a slug and an event type holds a dot, so the two never meet. A number is
    written by ``number_text``.
    """
    default = default_state(index)
    fields: list[str] = []
    order = scaling_order(index, state)
    rises = [
        f"{name}:{number_text(state.rises[name])}"
        for name in order
        if state.rises[name] != float(code_scaling(index, name)["rise"])
    ]
    if rises:
        fields.append("rise=" + ",".join(rises))
    drops = [
        f"{name}:{number_text(state.drops[name])}"
        for name in order
        if name in state.drops and state.drops[name] != code_scaling(index, name)["drop"]
    ]
    if drops:
        fields.append("drop=" + ",".join(drops))
    switched = switched_scalings(state, index)
    if switched:
        fields.append("scaling=" + ",".join(f"{event_type}:{name}" for event_type, name in switched.items()))
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


REFERENCE_RETIRED: Final = (
    "the reference was replaced by scalings: a rise share (and any drop share) per scaling; "
    "restate the link with rise=<scaling>:<share>"
)
"""The error of a state from before scalings, which held a reference per measure (``ref=``)."""


def decode_state(text: str, index: Mapping[str, Any]) -> ReplayState:
    """The state of a URL hash written by ``encode_state``; a leading ``#`` and any key order are accepted.

    Raises ``ReplayStateError`` for an unknown or repeated key, an unknown or repeated scaling, measure, campaign,
    type or draft, a base naming no draft or event type of the index's ``kinds``, a share that is not a positive
    number, a drop share not below its rise share, a type reassigned to a scaling on another measure, a base that is
    not a level, and a state from before scalings (``ref=``). The filter's type names are checked against the rows
    by ``replay``. A type switched to its code's base level or scaling is dropped.
    """
    default = default_state(index)
    campaigns = default.campaigns
    types: tuple[str, ...] = ()
    bases = dict(default.bases)
    type_bases: dict[str, str] = {}
    scalings: dict[str, str] = {}
    rises: dict[str, float] = {}
    drops: dict[str, float] = {}
    focus: str | None = None
    body = text[1:] if text.startswith("#") else text
    seen: set[str] = set()
    for part in body.split("&") if body else ():
        key, separator, value = part.partition("=")
        if not separator:
            raise ReplayStateError(f"state hash field {part!r} is not key=value")
        if key == "ref":
            raise ReplayStateError(REFERENCE_RETIRED)
        if key not in STATE_KEYS:
            raise ReplayStateError(f"unknown state hash key {key!r} (known: {', '.join(STATE_KEYS)})")
        if key in seen:
            raise ReplayStateError(f"state hash key {key!r} is repeated")
        seen.add(key)
        if key == "rise":
            rises = _decode_shares(value, "rise")
        elif key == "drop":
            drops = _decode_shares(value, "drop")
        elif key == "scaling":
            scalings = _decode_scalings(value)
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
    state = ReplayState(
        rises=default.rises, drops=default.drops, campaigns=campaigns, types=types, focus=focus, bases=bases
    )
    state = with_shares(with_scalings(state, index, scalings), index, rises=rises, drops=drops)
    return replace(state, type_bases=switched_types(replace(state, type_bases=type_bases), index))


def with_shares(
    state: ReplayState,
    index: Mapping[str, Any],
    *,
    rises: Mapping[str, float] | None = None,
    drops: Mapping[str, float] | None = None,
) -> ReplayState:
    """``state`` with the named scalings' rise and drop shares tried; ``ReplayStateError`` for a scaling the state
    does not hold (a split one must be split first), a share that is not a positive number, or a drop share not below
    its rise share."""
    rises, drops = dict(rises or {}), dict(drops or {})
    for name in [*rises, *drops]:
        if name not in state.rises:
            known = ", ".join(state.rises)
            raise ReplayStateError(f"unknown scaling {name!r} (known: {known}; a type's own scaling is split first)")
    for what, values in (("rise", rises), ("drop", drops)):
        for name, value in values.items():
            if not math.isfinite(value) or value <= 0:
                raise ReplayStateError(f"the {what} share of {name} must be a positive number, not {value!r}")
    merged_rises = {**state.rises, **rises}
    merged_drops = {**state.drops, **drops}
    for name, value in merged_drops.items():
        if value >= merged_rises[name]:
            raise ReplayStateError(
                f"the drop share of {name} must be below its rise share {number_text(merged_rises[name])}, "
                f"not {number_text(value)}"
            )
    return replace(state, rises=merged_rises, drops=merged_drops)


def _decode_shares(value: str, what: str) -> dict[str, float]:
    shares: dict[str, float] = {}
    if not value:
        raise ReplayStateError(f"state hash key {what!r} lists no {what} share")
    for item in value.split(","):
        name, separator, number = item.partition(":")
        if not separator:
            raise ReplayStateError(f"state hash {what} share {item!r} is not scaling:number")
        if name in shares:
            raise ReplayStateError(f"scaling {name!r} is repeated in the state hash's {what} shares")
        parsed = float(number) if _NUMBER.fullmatch(number) else math.nan
        if not math.isfinite(parsed) or parsed <= 0:
            raise ReplayStateError(f"the {what} share of {name} must be a positive number, not {number!r}")
        shares[name] = parsed
    return shares


def _decode_scalings(value: str) -> dict[str, str]:
    scalings: dict[str, str] = {}
    if not value:
        raise ReplayStateError("state hash key 'scaling' lists no scaling")
    for item in value.split(","):
        event_type, separator, name = item.partition(":")
        if not separator or not name:
            raise ReplayStateError(f"state hash scaling {item!r} is not type:scaling")
        if event_type in scalings:
            raise ReplayStateError(f"{event_type!r} is repeated in the state hash's scalings")
        scalings[event_type] = name
    return scalings


def _decode_bases(value: str, index: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    """The draft bases and the event types' base levels of a ``base`` value."""
    names = [draft["name"] for draft in index["drafts"]]
    levels = LEVELS
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
                    f"the base of draft share {name} must be a level ({', '.join(levels)}), not {level!r}"
                )
            bases[name] = level
        elif name in index["kinds"]:
            if level not in levels:
                raise ReplayStateError(f"the base level of {name} must be a level ({', '.join(levels)}), not {level!r}")
            type_bases[name] = level
        else:
            raise ReplayStateError(
                f"unknown draft share or event type {name!r} in the state hash "
                f"(drafts: {', '.join(names) or '(none)'}; types: the index's kinds)"
            )
    return bases, type_bases


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
