"""The package-shape views of the calibration report: count grids of the narrator package at a calibration state,
each count against the code's state. Periods are ``narrate``'s own (``narrator/chapters.py``); the tier rule is on
``row_tiers``, and what both mean to a reader on the command page (``benchmark calibrate report``, Views)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Final, NamedTuple

from tinarrative.benchmarking.calibration.coverage import Tables
from tinarrative.benchmarking.calibration.distribution import distribution_view, render_distribution
from tinarrative.benchmarking.calibration.readout import reason_text
from tinarrative.benchmarking.calibration.replay import (
    LEVELS,
    SCHEMA_VERSION,
    CampaignResult,
    Replay,
    ReplayError,
    ReplayState,
    default_state,
    replay,
    replayed_reason,
    type_scaling,
)
from tinarrative.config import NarratorSettings
from tinarrative.narrative.scalings import decided_outright
from tinarrative.narrator.chapters import (
    PERIODS,
    filing_position,
    interval_granularity,
    period_bounds,
    period_label,
    span_period,
)

VIEWS: Final = ("period", "tiers", "events", "distribution")
PERIOD_VIEWS: Final = ("period", "tiers", "events")
"""The views that count events per period; ``--periods`` filters these."""
"""The views ``--view`` takes, in the order they print."""
TIERS: Final = ("top-level", "member", "cited only", "explained", "below")
LOW_RESOLUTION_DAYS: Final = 365
"""Saves further apart than this make every period between them low-resolution: no density conclusion is drawn."""
_LEVEL_NAMES: Final = {"campaign_defining": "defining"}
"""Level names shortened to fit the grid's first column."""
_WIDTH: Final = 14
EVENTS_CAP: Final = 15
"""Events the text lists per campaign period before it prints a count of the cut ones; JSON carries all."""
MEMBERS_SHOWN: Final = 3
"""Member labels the text digest names."""

Cell = dict[str, int]
"""A count at the replayed state and at the code's: ``{"replay": n, "code": m}``."""
Grid = dict[str, dict[str, Cell]]
"""Level, most significant first, then tier; a cell that is 0 at both states is left out."""


class ViewError(ReplayError):
    """An unknown view or period key, or a period flag without a view that reads it."""


@dataclass(frozen=True)
class CampaignPeriods:
    """The package's periods of one campaign."""

    period: str
    """The period asked for or derived from the span; coarsened labels are coarser."""
    requested: bool
    span_days: int
    keys: tuple[str, ...]
    """Every period from the first to the last closing save, in order, empty ones included."""
    intervals: tuple[Mapping[str, Any], ...]
    """Every interval in order, as the narrator package writes it (``key``, ``not_before``, ``date``)."""
    labels: tuple[str, ...]
    """The period of each of ``intervals``."""
    coarsened: tuple[str, ...]
    """The periods coarser than ``period`` because the saves are too sparse for it."""
    low_resolution: Mapping[str, int]
    """Each low-resolution period with the longest save gap over ``LOW_RESOLUTION_DAYS`` that touches it, in days."""
    positions: Mapping[str, int]
    """The position of each interval key in ``intervals``."""

    def of_row(self, row: Mapping[str, Any]) -> str:
        """The period ``narrate`` tells ``row`` in: an atomic row in its interval's, a narrative row by
        ``filing_position``; ``ViewError`` for a row whose interval has no dates."""
        positions = self.positions
        if row["interval"] not in positions:
            raise ViewError(f"row {row['id']} names interval {row['interval']}, which has no dates")
        if row["tier"] != "narrative":
            return self.labels[positions[row["interval"]]]
        event = {
            "start": row["start"],
            "start_basis": row["start_basis"],
            "end": row["end"],
            "intervals": [interval["key"] for interval in row["intervals"]] or [row["interval"]],
        }
        return self.labels[filing_position(event, self.intervals, positions)]


def parse_views(values: Sequence[str]) -> tuple[str, ...]:
    """The views of comma-separated, repeatable ``--view`` values, in ``VIEWS`` order; ``ViewError`` for an unknown
    or repeated one."""
    names = _items(values)
    unknown = [name for name in names if name not in VIEWS]
    if unknown:
        raise ViewError(f"unknown view(s): {', '.join(unknown)} (known: {', '.join(VIEWS)})")
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise ViewError(f"view(s) given twice: {', '.join(repeated)}")
    return tuple(name for name in VIEWS if name in names)


def _items(values: Sequence[str]) -> list[str]:
    return [item.strip() for value in values for item in value.split(",") if item.strip()]


def campaign_periods(
    rows: Sequence[Mapping[str, Any]], period: str | None = None, settings: NarratorSettings | None = None
) -> CampaignPeriods:
    """The periods of a campaign's rows, as ``narrate`` derives them from the same saves: ``period``, else the
    ``span_period`` of the first and last save under ``settings`` (the defaults when ``None``), coarsened where the
    saves are sparse unless ``period`` is given.

    The intervals are the rows' own; a stretch between two saves no row's interval covers counts as one interval. A
    period is low-resolution when an interval over ``LOW_RESOLUTION_DAYS`` touches it, its closing save included.
    """
    dates: dict[str, tuple[str, str]] = {}
    for row in rows:
        for interval in row["intervals"]:
            dates[interval["key"]] = (interval["start"], interval["end"])
    if not dates:
        raise ViewError("the rows carry no interval dates")
    observed = sorted(dates.items(), key=lambda item: (item[1][1], item[0]))
    intervals: list[dict[str, str]] = []
    for key, (start, end) in observed:
        if intervals and start > intervals[-1]["date"]:
            # No row's interval covers this stretch between two saves: an interval with nothing in it.
            intervals.append({"key": start, "not_before": intervals[-1]["date"], "date": start})
        intervals.append({"key": key, "not_before": start, "date": end})
    first, last = intervals[0]["not_before"], intervals[-1]["date"]
    chosen = period or span_period(first, last, settings or NarratorSettings())
    granularity = interval_granularity(intervals, chosen, requested=period is not None)
    labels = [period_label(interval["date"], each) for interval, each in zip(intervals, granularity, strict=True)]
    coarsened = tuple(
        dict.fromkeys(
            period_label(interval["date"], each)
            for interval, each in zip(intervals, granularity, strict=True)
            if each != chosen
        )
    )
    keys = set(labels)
    moment, final = period_bounds(period_label(intervals[0]["date"], chosen))[0], datetime.fromisoformat(last)
    while moment <= final:
        label = period_label(moment.isoformat(), chosen)
        coarser = PERIODS[: PERIODS.index(chosen)]
        if not any(period_label(moment.isoformat(), each) in coarsened for each in coarser):
            keys.add(label)
        moment = period_bounds(label)[1]
    ordered = tuple(sorted(keys, key=period_bounds))
    low: dict[str, int] = {}
    for interval in intervals:
        opening, closing = datetime.fromisoformat(interval["not_before"]), datetime.fromisoformat(interval["date"])
        days = (closing - opening).days
        if days <= LOW_RESOLUTION_DAYS:
            continue
        for key in ordered:
            opens, closes = period_bounds(key)
            if opening < closes and closing >= opens:
                low[key] = max(low.get(key, 0), days)
    span = (datetime.fromisoformat(last) - datetime.fromisoformat(first)).days
    return CampaignPeriods(
        period=chosen,
        requested=period is not None,
        span_days=span,
        keys=ordered,
        intervals=tuple(intervals),
        labels=tuple(labels),
        positions={interval["key"]: position for position, interval in enumerate(intervals)},
        coarsened=coarsened,
        low_resolution=low,
    )


def row_tiers(
    index: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], campaign: CampaignResult
) -> list[tuple[str, str] | None]:
    """Each row's replayed level and tier, in table order, ``None`` for a row not counted. ``campaign`` is the rows'
    campaign in a replay without a type filter.

    A row takes the first tier that holds: top-level (a narrative row at the package level or above, no member);
    member (kept by a group in the package); cited only (reached through the citations of a top-level row, never
    through a member's, as the narrator listing digests members); explained (``explained_by`` a top-level row or
    member); below (any other narrative row). A group that falls apart is not counted.
    """
    package_levels = frozenset(LEVELS[LEVELS.index(index["constants"]["package_level"]) :])
    level = {event["id"]: event["level"] for event in campaign["events"]}
    fallen = {member["id"] for member in campaign["members"] if member["verdict"] == "falls_apart"}
    in_package = {
        row["id"]
        for row in rows
        if row["tier"] == "narrative" and row["id"] not in fallen and level[row["id"]] in package_levels
    }
    members = {
        kept
        for member in campaign["members"]
        if member["id"] in in_package and member["verdict"] in {"keeps_members", "loses_members"}
        for kept in member["kept"]
    }
    top = in_package - members
    told = top | members
    cited = {row["id"]: row["cited"] for row in rows}
    reached: set[str] = set()
    pending = [item for identifier in top for item in cited[identifier]]
    while pending:
        identifier = pending.pop()
        if identifier in reached or identifier in told:
            continue
        reached.add(identifier)
        pending.extend(cited.get(identifier, ()))
    tiers: list[tuple[str, str] | None] = []
    for row in rows:
        identifier = row["id"]
        if identifier in top:
            tier = "top-level"
        elif identifier in members:
            tier = "member"
        elif identifier in reached:
            tier = "cited only"
        elif row["explained_by"] in told:
            tier = "explained"
        elif row["tier"] == "narrative" and identifier not in fallen:
            tier = "below"
        else:
            tiers.append(None)
            continue
        tiers.append((level[identifier], tier))
    return tiers


def views_document(
    index: Mapping[str, Any],
    tables: Tables,
    drafts: Tables | None,
    state: ReplayState,
    *,
    views: Sequence[str],
    period: str | None = None,
    periods: Sequence[str] = (),
    settings: NarratorSettings | None = None,
    state_hash: str = "",
    non_standard: Mapping[str, Sequence[str]] | None = None,
    include_non_standard: bool = False,
) -> dict[str, Any]:
    """The JSON document of ``views`` at ``state`` against the code's state on the same campaigns and types.

    ``periods`` (comma-separated, repeatable keys) filters the periods printed; a campaign's headline still counts
    its full window. ``ViewError`` for a period key no enabled campaign has. ``non_standard`` is each campaign's
    non-standard marks from its profile; the distribution view leaves a marked campaign out unless
    ``include_non_standard``.
    """
    tried = replace(state, types=(), focus=None)
    code = replace(default_state(index), campaigns=state.campaigns)
    result = replay(index, tables, tried, drafts)
    baseline = result if tried == code else replay(index, tables, code, drafts)
    types = frozenset(state.types)
    keys = _items(periods)
    counted = {
        name: _counted(index, tables[name], result, baseline, name, campaign_periods(tables[name], period, settings))
        for name in state.campaigns
        if any(view in views for view in PERIOD_VIEWS)
    }
    if keys and not counted:
        raise ViewError("--periods filters the period, tiers and events views; the distribution view has no periods")
    known = {key for _, found in counted.values() for key in found.keys}
    unknown = [key for key in keys if key not in known]
    if unknown:
        raise ViewError(
            f"unknown period(s): {', '.join(unknown)} (known: {', '.join(sorted(known, key=period_bounds))})"
        )
    chosen = frozenset(keys)
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "key": index["key"],
        "hash": state_hash,
        "code_state": tried == code,
        "state": result["state"],
        "periods": keys,
        "views": {},
    }
    if "period" in views:
        document["views"]["period"] = {
            "campaigns": {
                name: _period_view(tables[name], rows, found, types, chosen) for name, (rows, found) in counted.items()
            }
        }
    if "tiers" in views:
        document["views"]["tiers"] = {"types": _tiers_view(counted, types, chosen)}
    if "events" in views:
        document["views"]["events"] = _events_view(index, tables, state, result, baseline, counted, types, chosen)
    if "distribution" in views:
        document["views"]["distribution"] = distribution_view(
            index,
            tables,
            drafts,
            state,
            non_standard=non_standard or {},
            include_non_standard=include_non_standard,
        )
    return document


class _Placed(NamedTuple):
    """A row's type, its period, and its level and tier at the replayed state and at the code's."""

    id: str
    type: str
    period: str
    replayed: tuple[str, str] | None
    coded: tuple[str, str] | None


_Counted = list[_Placed]


def _counted(
    index: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    result: Replay,
    baseline: Replay,
    name: str,
    found: CampaignPeriods,
) -> tuple[_Counted, CampaignPeriods]:
    now = row_tiers(index, rows, result["campaigns"][name])
    then = now if baseline is result else row_tiers(index, rows, baseline["campaigns"][name])
    placed: _Counted = [
        _Placed(row["id"], row["type"], found.of_row(row), replayed, coded)
        for row, replayed, coded in zip(rows, now, then, strict=True)
    ]
    return placed, found


def _grid(rows: _Counted) -> tuple[Grid, Cell]:
    now: Counter[tuple[str, str]] = Counter()
    then: Counter[tuple[str, str]] = Counter()
    for item in rows:
        if item.replayed is not None:
            now[item.replayed] += 1
        if item.coded is not None:
            then[item.coded] += 1
    grid: Grid = {}
    for level in reversed(LEVELS):
        cells = {
            tier: {"replay": now[level, tier], "code": then[level, tier]}
            for tier in TIERS
            if now[level, tier] or then[level, tier]
        }
        if cells:
            grid[level] = cells
    top = {
        "replay": sum(now[level, "top-level"] for level in LEVELS),
        "code": sum(then[level, "top-level"] for level in LEVELS),
    }
    return grid, top


def _period_view(
    table: Sequence[Mapping[str, Any]],
    rows: _Counted,
    found: CampaignPeriods,
    types: frozenset[str],
    chosen: frozenset[str],
) -> dict[str, Any]:
    kept = [item for item in rows if not types or item.type in types]
    _, top = _grid(kept)
    printed = []
    for key in found.keys:
        if chosen and key not in chosen:
            continue
        grid, own = _grid([item for item in kept if item.period == key])
        printed.append({"key": key, "low_resolution": found.low_resolution.get(key), "top_level": own, "grid": grid})
    return {
        "period": found.period,
        "basis": "requested" if found.requested else "campaign_span",
        "span_days": found.span_days,
        "coarsened": list(found.coarsened),
        "rows": sum(1 for row in table if not types or row["type"] in types),
        "top_level": top,
        "periods": printed,
    }


def _tiers_view(
    counted: Mapping[str, tuple[_Counted, CampaignPeriods]], types: frozenset[str], chosen: frozenset[str]
) -> dict[str, Any]:
    by_type: dict[str, dict[str, dict[str, _Counted]]] = {}
    for name, (rows, _) in counted.items():
        for item in rows:
            if (types and item.type not in types) or (chosen and item.period not in chosen):
                continue
            if item.replayed is None and item.coded is None:
                continue
            by_type.setdefault(item.type, {}).setdefault(name, {}).setdefault(item.period, []).append(item)
    found: dict[str, Any] = {}
    for event_type in sorted(by_type):
        campaigns = by_type[event_type]
        grid, top = _grid([item for keys in campaigns.values() for items in keys.values() for item in items])
        found[event_type] = {
            "top_level": top,
            "grid": grid,
            "campaigns": {
                name: {key: _grid(items)[0] for key, items in keys.items()} for name, keys in campaigns.items()
            },
        }
    return found


def _when(row: Mapping[str, Any]) -> str | None:
    """The date an event is at, for the ``@date`` marker: its own, else its start, else its last interval's end."""
    found = row["date"] or row["start"] or (row["intervals"][-1]["end"] if row["intervals"] else None)
    return None if found is None else str(found)[:10]


class _Named(NamedTuple):
    """Resolves a row id to a name and, outside the printed period, a date."""

    labels: Mapping[str, str]
    periods: Mapping[str, str]
    dates: Mapping[str, str | None]

    def ref(self, identifier: str, period: str) -> dict[str, Any]:
        entry: dict[str, Any] = {"id": identifier, "label": self.labels.get(identifier, identifier)}
        if self.periods.get(identifier, period) != period:
            entry["at"] = self.dates.get(identifier)
        return entry


def _decided(
    index: Mapping[str, Any], state: ReplayState, row: Mapping[str, Any], by: str, named: _Named, period: str
) -> dict[str, Any]:
    """What set the row's level: a cited event, a context rule that names trivial, its own share (with its scaling
    and shares) or, with nothing to scale, its base level."""
    if by != row["id"]:
        return {"kind": "cited", **named.ref(by, period)}
    if row["rule"] is not None and (decided_outright(True, int(row["base"])) or not row["shares"]):
        return {"kind": "rule", "rule": row["rule"]}
    if not row["shares"]:
        return {"kind": "base"}
    scaling = type_scaling(index, state, row["type"])
    found: dict[str, Any] = {"kind": "share", "scaling": scaling, "shares": row["shares"]}
    if scaling is not None and scaling in state.rises:
        found["rise"] = state.rises[scaling]
        found["drop"] = state.drops.get(scaling)
    return found


def _events_view(
    index: Mapping[str, Any],
    tables: Tables,
    state: ReplayState,
    result: Replay,
    baseline: Replay,
    counted: Mapping[str, tuple[_Counted, CampaignPeriods]],
    types: frozenset[str],
    chosen: frozenset[str],
) -> dict[str, Any]:
    """The top-level events of the replayed or the code's state, per campaign and period, each with what set its
    level; the reason of every type listed."""
    tried = replace(state, types=(), focus=None)
    campaigns: dict[str, Any] = {}
    listed: set[str] = set()
    for name, (placed, found) in counted.items():
        rows = {row["id"]: row for row in tables[name]}
        named = _Named(
            {identifier: row["label"] for identifier, row in rows.items()},
            {item.id: item.period for item in placed},
            {identifier: _when(row) for identifier, row in rows.items()},
        )
        now = {event["id"]: event for event in result["campaigns"][name]["events"]}
        then = {event["id"]: event for event in baseline["campaigns"][name]["events"]}
        members = {member["id"]: member for member in result["campaigns"][name]["members"]}
        printed: dict[str, list[dict[str, Any]]] = {}
        for item in placed:
            tops = (item.replayed and item.replayed[1] == "top-level", item.coded and item.coded[1] == "top-level")
            if not any(tops) or (types and item.type not in types) or (chosen and item.period not in chosen):
                continue
            row, event = rows[item.id], now[item.id]
            group = members.get(item.id)
            kept = [named.ref(each, item.period) for each in (group["kept"] if group else ())]
            lost = [named.ref(each, item.period) for each in (group["lost"] if group else ())]
            listed.add(item.type)
            printed.setdefault(item.period, []).append(
                {
                    **named.ref(item.id, item.period),
                    "type": item.type,
                    "level": event["level"],
                    "code_level": then[item.id]["level"],
                    "top_level": {"replay": bool(tops[0]), "code": bool(tops[1])},
                    "score": event["score"],
                    "decided_by": _decided(index, tried, row, event["decided_by"], named, item.period),
                    "members": {"kept": kept, "lost": lost},
                    "cited": len(row["cited"]),
                }
            )
        for entries in printed.values():
            entries.sort(key=lambda entry: (-entry["score"], entry["id"]))
        campaigns[name] = {
            "period": found.period,
            "periods": [{"key": key, "events": printed[key]} for key in found.keys if key in printed],
        }
    return {
        "reasons": {event_type: _reason(index, event_type) for event_type in sorted(listed)},
        "campaigns": campaigns,
    }


def _reason(index: Mapping[str, Any], event_type: str) -> dict[str, Any]:
    """The type's principle, what applies it and its status, as ``replayed_reason`` reads them from the index."""
    reason = replayed_reason(index, event_type)
    return {
        "principle": reason["principle"],
        "because": reason["because"],
        "status": reason["status"],
        "text": reason_text(index, event_type),
    }


# --- Text ------------------------------------------------------------------------------------------------------


def render_views(document: Mapping[str, Any]) -> str:
    """The views as plain text: a state line, then each view's headlines and grids. Every count prints as ``N``,
    or ``N +d`` / ``N -d`` where it differs from the code's state."""
    state = "the code's state" if document["code_state"] else f"#{document['hash']} (delta against the code's state)"
    lines = [f"state  {state}"]
    views = document["views"]
    if "period" in views:
        for name, campaign in views["period"]["campaigns"].items():
            lines += ["", *_period_text(name, campaign)]
    if "tiers" in views:
        lines += ["", *_tiers_text(views["tiers"]["types"], document["periods"])]
    if "events" in views:
        lines += ["", *_events_text(views["events"])]
    if "distribution" in views:
        lines += ["", *render_distribution(views["distribution"])]
    return "\n".join(lines) + "\n"


def _period_text(name: str, campaign: Mapping[str, Any]) -> list[str]:
    years = campaign["span_days"] / 365.25
    basis = "--period" if campaign["basis"] == "requested" else f"span {years:.1f} years, narrate default"
    if campaign["coarsened"]:
        basis += f"; coarsened, saves too sparse: {', '.join(campaign['coarsened'])}"
    lines = [
        f"period view - {name} - by {campaign['period']} ({basis})",
        f"campaign  top-level {_cell(campaign['top_level'])} - rows {campaign['rows']}",
    ]
    for entry in campaign["periods"]:
        headline = f"{entry['key']}   top-level {_cell(entry['top_level'])}"
        if entry["low_resolution"] is not None:
            headline += f"   low resolution: saves {entry['low_resolution']} days apart, no density conclusion"
        lines += ["", headline, *_grid_text(entry["grid"])]
    return lines


def _tiers_text(types: Mapping[str, Any], periods: Sequence[str]) -> list[str]:
    scope = f"periods {', '.join(periods)}" if periods else "every period"
    lines = [f"tiers view - every enabled campaign - {scope}"]
    if not types:
        return [*lines, "", "no events"]
    for event_type, entry in types.items():
        lines += ["", f"{event_type}   top-level {_cell(entry['top_level'])}", *_grid_text(entry["grid"])]
    return lines


def _events_text(view: Mapping[str, Any]) -> list[str]:
    lines = ["events view - the top-level events"]
    if not view["reasons"]:
        return [*lines, "", "no events"]
    lines += ["", "reasons"]
    lines += [f"  {event_type}   {reason['text']}" for event_type, reason in view["reasons"].items()]
    for name, campaign in view["campaigns"].items():
        for entry in campaign["periods"]:
            events = entry["events"]
            lines += ["", f"{name} - {entry['key']} - {len(events)} top-level events"]
            for event in events[:EVENTS_CAP]:
                lines += _event_text(event)
            if len(events) > EVENTS_CAP:
                lines.append(f"  ... {len(events) - EVENTS_CAP} more cut; --format json lists all")
    return lines


def _event_text(event: Mapping[str, Any]) -> list[str]:
    level = _LEVEL_NAMES.get(event["level"], event["level"])
    if event["code_level"] != event["level"]:
        level += f" (code: {_LEVEL_NAMES.get(event['code_level'], event['code_level'])})"
    flag = "" if event["top_level"]["replay"] else "   no longer top-level"
    if not event["top_level"]["code"]:
        flag = "   newly top-level"
    lines = [
        f"  {event['label']}{_at(event)}",
        f"    {event['type']} - {level} - score {event['score']} - cited {event['cited']}{flag}",
        f"    decided by {_decided_text(event['decided_by'])}",
    ]
    members = event["members"]
    if members["kept"] or members["lost"]:
        names = [f"{item['label']}{_at(item)}" for item in members["kept"][:MEMBERS_SHOWN]]
        rest = len(members["kept"]) - MEMBERS_SHOWN
        digest = f"{len(members['kept'])} members: {', '.join(names)}" + (f", +{rest} more" if rest > 0 else "")
        if members["lost"]:
            digest += f"; lost {len(members['lost'])}"
        lines.append(f"    {digest}")
    return lines


def _at(entry: Mapping[str, Any]) -> str:
    return f" @{entry['at']}" if entry.get("at") else ""


def _decided_text(decided: Mapping[str, Any]) -> str:
    if decided["kind"] == "cited":
        return f"cited event {decided['label']}{_at(decided)}"
    if decided["kind"] == "rule":
        return f"context rule {decided['rule']}"
    if decided["kind"] == "base":
        return "its base level"
    shares = ", ".join(f"{item['measure']} {item['share']:.3g}" for item in decided["shares"])
    scaling = decided["scaling"]
    text = f"own share {shares}" + ("" if scaling is None else f" on scaling {scaling}")
    if "rise" in decided:
        drop = "" if decided["drop"] is None else f", drop {decided['drop']:.3g}"
        text += f" (rise {decided['rise']:.3g}{drop})"
    return text


def _grid_text(grid: Grid) -> list[str]:
    if not grid:
        return ["  no events"]
    lines = ["  " + " " * 10 + "".join(f"{tier:>{_WIDTH}}" for tier in TIERS)]
    for level, cells in grid.items():
        values = [_cell(cells.get(tier, {"replay": 0, "code": 0})) for tier in TIERS]
        lines.append("  " + f"{_LEVEL_NAMES.get(level, level):10}" + "".join(f"{value:>{_WIDTH}}" for value in values))
    return lines


def _cell(cell: Cell) -> str:
    change = cell["replay"] - cell["code"]
    return str(cell["replay"]) if not change else f"{cell['replay']} {change:+d}"
