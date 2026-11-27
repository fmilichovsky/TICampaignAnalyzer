"""The distribution view of the calibration report: how each kind's shares are spread, per scaling, so a rise or drop
share can be stated as a game quantity and fitted to how the game distributes it. The command page
(``benchmark calibrate report``, Views) says what a reader takes from it."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Final

from tinarrative.benchmarking.calibration.coverage import Tables
from tinarrative.benchmarking.calibration.readout import restated_text
from tinarrative.benchmarking.calibration.replay import (
    ReplayState,
    code_scaling,
    restated_reason,
    scaling_order,
    type_scaling,
)
from tinarrative.benchmarking.calibration.stats import PERCENTILES, percentiles
from tinarrative.model.events import Significance
from tinarrative.narrative.scalings import drop_share, own_score, scale

SPREAD: Final = tuple(f"p{percent}" for percent in PERCENTILES)
"""The keys of the percentiles a spread prints, in order."""
POINTS: Final = ("first", "last", "all")
"""Where a campaign's shares are read: its events at the first save, at the last save, and over all."""
DRAFT_PREFIX: Final = "draft:"
"""A draft's key beside the event types in a scaling's kinds."""


def _base_score(index: Mapping[str, Any], level: str) -> int:
    low, high = index["constants"]["level_bands"][level]
    return int((low + high) // 2)


def _ends(rows: Sequence[Mapping[str, Any]]) -> tuple[str | None, str | None]:
    """The key of the campaign's first interval and of its last, by closing save; ``None`` for rows with none."""
    ends = {interval["key"]: interval["end"] for row in rows for interval in row["intervals"]}
    ordered = sorted(ends, key=lambda key: (ends[key], key))
    return (ordered[0], ordered[-1]) if ordered else (None, None)


def _shares(rows: Sequence[Mapping[str, Any]], measure: str) -> list[float]:
    found: list[float] = []
    for row in rows:
        on_measure = [item["share"] for item in row["shares"] if item["measure"] == measure]
        if on_measure:
            found.append(max(on_measure))
    return found


def _spread(rows: Sequence[Mapping[str, Any]], measure: str, first: str | None, last: str | None) -> dict[str, Any]:
    """The share percentiles of ``rows`` at the first save, at the last and over all (``None`` where none)."""
    return {
        "first": percentiles(_shares([row for row in rows if first is not None and row["interval"] == first], measure)),
        "last": percentiles(_shares([row for row in rows if last is not None and row["interval"] == last], measure)),
        "all": percentiles(_shares(rows, measure)),
    }


def _landing(index: Mapping[str, Any], level: str, median: float, rise: float, drop: float | None) -> str:
    """The level a share lands on from ``level``'s base score on a scaling: a readout, never a validation."""
    moved = own_score(_base_score(index, level), [scale(median, rise, drop)])
    return Significance.of(moved).value


def distribution_view(
    index: Mapping[str, Any],
    tables: Tables,
    drafts: Tables | None,
    state: ReplayState,
    *,
    non_standard: Mapping[str, Sequence[str]],
    include_non_standard: bool = False,
) -> dict[str, Any]:
    """The kinds' share distributions at ``state``, per scaling: each campaign of ``state`` apart from the ones in
    ``non_standard`` (campaign to the reasons its profile marks it), unless ``include_non_standard``.

    A scaling lists the kinds that read it, the real event types and each draft share, with their share percentiles
    per campaign and pooled over the campaigns, the level the pooled median share lands on beside the base, and how
    many of the pooled shares sit at or above the rise share and at or below the drop share. The world quantity of
    its measure comes beside it, per campaign, from the index.
    """
    left_out = {name: list(non_standard[name]) for name in state.campaigns if non_standard.get(name)}
    used = [name for name in state.campaigns if include_non_standard or name not in left_out]
    types = frozenset(state.types)
    ends = {name: _ends(tables[name]) for name in used}
    names = set(index["kinds"]) | {row["type"] for name in used for row in tables[name]}
    draft_index = {draft["name"]: draft for draft in index["drafts"]}
    scalings: dict[str, Any] = {}
    for scaling in scaling_order(index, state):
        spec = code_scaling(index, scaling)
        measure = str(spec["measure"])
        rise = state.rises.get(scaling, float(spec["rise"]))
        drop = state.drops.get(scaling)
        kinds: dict[str, Any] = {}
        for event_type in sorted(names):
            if type_scaling(index, state, event_type) != scaling or (types and event_type not in types):
                continue
            level = state.type_bases.get(event_type) or index["kinds"].get(event_type, {}).get("base")
            if level is None:
                continue
            rows = {name: [row for row in tables[name] if row["type"] == event_type] for name in used}
            kinds[event_type] = _kind(index, rows, ends, measure, level, rise, drop)
        for name, draft in draft_index.items():
            if draft["scalings"].get(measure) != scaling or not drafts:
                continue
            rows = {
                campaign: [
                    row
                    for row in drafts.get(campaign, ())
                    if row["id"].startswith(f"draft:{name}:") and (not types or row["type"] in types)
                ]
                for campaign in used
            }
            kinds[f"{DRAFT_PREFIX}{name}"] = _kind(
                index, rows, ends, measure, state.bases.get(name, draft["base"]), rise, drop
            )
        if not any(kind["pooled"] for kind in kinds.values()):
            continue
        medians = [kind["pooled"]["p50"] for kind in kinds.values() if kind["pooled"] and kind["pooled"]["p50"] > 0]
        scalings[scaling] = {
            "measure": measure,
            "label": index["measures"][measure]["label"],
            "rise": rise,
            "drop": drop_share(rise, drop),
            "reason": _reason(index, spec),
            "median_span": max(medians) / min(medians) if len(medians) > 1 else None,
            "world": {name: found for name in used if (found := index.get("world", {}).get(name, {}).get(measure))},
            "kinds": kinds,
        }
    return {"campaigns": used, "left_out": left_out, "scalings": scalings}


def _kind(
    index: Mapping[str, Any],
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
    ends: Mapping[str, tuple[str | None, str | None]],
    measure: str,
    level: str,
    rise: float,
    drop: float | None,
) -> dict[str, Any]:
    pooled = [share for found in rows.values() for share in _shares(found, measure)]
    summary = percentiles(pooled)
    low = drop_share(rise, drop)
    return {
        "base": level,
        "campaigns": {name: _spread(found, measure, *ends[name]) for name, found in rows.items() if found},
        "pooled": summary,
        "lands_on": None if summary is None else _landing(index, level, float(summary["p50"]), rise, drop),
        "median_over_rise": None if summary is None else float(summary["p50"]) / rise,
        "at_rise": sum(1 for share in pooled if share >= rise),
        "at_drop": sum(1 for share in pooled if share <= low),
    }


def _reason(index: Mapping[str, Any], spec: Mapping[str, Any]) -> dict[str, Any]:
    reason = restated_reason(index, spec["reason"])
    return {
        "principle": reason["principle"],
        "because": reason["because"],
        "status": reason["status"],
        "text": restated_text(index, reason),
    }


# --- Text ------------------------------------------------------------------------------------------------------


def _number(value: float, rise: float, drop: float) -> str:
    """``value`` to 3 figures, marked ``^`` at or above the rise share and ``v`` at or below the drop share."""
    mark = "^" if value >= rise else "v" if value <= drop else ""
    return f"{value:.3g}{mark}"


def _row(label: str, found: Mapping[str, Any] | None, rise: float, drop: float) -> str:
    if found is None:
        return f"    {label:<10} no events"
    values = "  ".join(f"{_number(float(found[key]), rise, drop):>9}" for key in SPREAD)
    return f"    {label:<10} {values}   n={found['n']}"


def render_distribution(view: Mapping[str, Any]) -> list[str]:
    """The view as text lines; every percentile marked ``^`` at or above the scaling's rise share, ``v`` at or below
    its drop share."""
    lines = ["distribution view - the shares of each kind, per scaling"]
    if view["left_out"]:
        lines.append(
            "left out (non-standard sample; --include-non-standard keeps it): "
            + "; ".join(f"{name} ({', '.join(why)})" for name, why in view["left_out"].items())
        )
    if not view["scalings"]:
        return [*lines, "", "no shares"]
    header = "          " + "  ".join(f"{key:>9}" for key in SPREAD)
    for name, scaling in view["scalings"].items():
        rise, drop = float(scaling["rise"]), float(scaling["drop"])
        lines += [
            "",
            f"scaling {name} - {scaling['label']} - rise {rise:.3g} - drop {drop:.3g}",
            f"  reason: {scaling['reason']['text']}",
        ]
        if scaling["median_span"] is not None:
            lines.append(f"  the kinds' median shares span x{scaling['median_span']:.3g}")
        for campaign, world in scaling["world"].items():
            lines.append(f"  world quantity - {campaign} (share of the world total, over the entities of a save)")
            lines.append("  " + header)
            lines.append(_row("first", world.get("first"), rise, drop))
            lines.append(_row("last", world.get("last"), rise, drop))
            # How far an entity moved is a ratio of shares, not a share: no rise or drop share to mark.
            lines.append(_row("moved x", world.get("moved"), math.inf, -math.inf))
        for kind, found in scaling["kinds"].items():
            if found["pooled"] is None:
                lines += ["", f"  {kind} - base {found['base']} - no shares"]
                continue
            lines += [
                "",
                f"  {kind} - base {found['base']} - median {found['pooled']['p50']:.3g} "
                f"(x{found['median_over_rise']:.3g} of rise) lands on {found['lands_on']}"
                f" - {found['at_rise']} at rise, {found['at_drop']} at drop of {found['pooled']['n']}",
            ]
            for campaign, spread in found["campaigns"].items():
                lines.append(f"  {campaign}")
                lines.append("  " + header)
                lines += [_row(point, spread[point], rise, drop) for point in POINTS]
    return lines
