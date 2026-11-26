"""The readout of a replay: the shared paragraph and the snippet, which the page shows as the server sends them, and
the report formats.

``shared_paragraph`` and ``snippet`` are pure functions of the index and the replay, ASCII only, with every number
written by ``number_text``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any, Final

from tinarrative.benchmarking.calibration.coverage import Tables, coverage
from tinarrative.benchmarking.calibration.drafts import draft_name
from tinarrative.benchmarking.calibration.replay import (
    SCHEMA_VERSION,
    Neighbour,
    Replay,
    ReplayState,
    ReplayStateError,
    code_scaling,
    number_text,
    switched_types,
    with_scalings,
    with_shares,
)

TOP_MOVES: Final = 5
"""The What moves rows the shared paragraph names."""
_NUMBER = re.compile(r"(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?", re.ASCII)


def override_state(
    state: ReplayState,
    index: Mapping[str, Any],
    *,
    rises: Sequence[str] = (),
    drops: Sequence[str] = (),
    scalings: Sequence[str] = (),
    campaigns: Sequence[str] = (),
    types: Sequence[str] = (),
    bases: Sequence[str] = (),
) -> ReplayState:
    """``state`` with the report's flags applied; each flag value is a comma-separated list, and repeats accumulate.

    ``scalings`` (``TYPE=SCALING``, the type's own name to split it off) reassign the named types first, so a split
    scaling can take ``rises`` and ``drops`` (``SCALING=VALUE``), which change the named scalings only; given
    ``campaigns`` or ``types`` replace the state's. ``bases`` (``TYPE=LEVEL``) switch the named event types only, and
    one at the code's base level clears its switch. Raises ``ReplayStateError`` for an unknown or repeated scaling,
    campaign or switched type, a share that is not a positive number, a drop share not below its rise share, a type
    reassigned across measures and a base level that is not a level; ``replay`` checks the filter's types against
    the rows.
    """
    reassigned: dict[str, str] = {}
    for item in _items(scalings):
        event_type, separator, name = item.partition("=")
        if not separator or not name:
            raise ReplayStateError(f"--scaling {item!r} is not TYPE=SCALING")
        if event_type not in index["kinds"]:
            raise ReplayStateError(f"unknown event type {event_type!r} (known: the table's event types)")
        if event_type in reassigned:
            raise ReplayStateError(f"event type {event_type!r} is given twice")
        reassigned[event_type] = name
    if reassigned:
        state = with_scalings(state, index, reassigned)
    state = with_shares(state, index, rises=_shares(rises, "rise"), drops=_shares(drops, "drop"))
    if campaigns:
        names = _items(campaigns)
        unknown = [name for name in names if name not in index["campaigns"]]
        if unknown:
            known = ", ".join(index["campaigns"])
            raise ReplayStateError(f"unknown campaign(s): {', '.join(unknown)} (known: {known})")
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise ReplayStateError(f"campaign(s) given twice: {', '.join(repeated)}")
        state = replace(state, campaigns=tuple(name for name in index["campaigns"] if name in names))
    if types:
        names = _items(types)
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise ReplayStateError(f"type(s) given twice: {', '.join(repeated)}")
        state = replace(state, types=tuple(sorted(names)))
    levels = list(index["constants"]["level_bands"])
    tried: dict[str, str] = {}
    for item in _items(bases):
        event_type, separator, level = item.partition("=")
        if not separator:
            raise ReplayStateError(f"--base {item!r} is not TYPE=LEVEL")
        if event_type not in index["kinds"]:
            raise ReplayStateError(f"unknown event type {event_type!r} (known: the table's event types)")
        if event_type in tried:
            raise ReplayStateError(f"event type {event_type!r} is given twice")
        if level not in levels:
            raise ReplayStateError(
                f"the base level of {event_type} must be a level ({', '.join(levels)}), not {level!r}"
            )
        tried[event_type] = level
    if tried:
        state = replace(state, type_bases={**state.type_bases, **tried})
        state = replace(state, type_bases=switched_types(state, index))
    return state


def _shares(values: Sequence[str], what: str) -> dict[str, float]:
    changed: dict[str, float] = {}
    for item in _items(values):
        name, separator, number = item.partition("=")
        if not separator:
            raise ReplayStateError(f"--{what} {item!r} is not SCALING=VALUE")
        if name in changed:
            raise ReplayStateError(f"scaling {name!r} is given twice")
        value = float(number) if _NUMBER.fullmatch(number) else math.nan
        if not math.isfinite(value) or value <= 0:
            raise ReplayStateError(f"the {what} share of {name} must be a positive number, not {number!r}")
        changed[name] = value
    return changed


def _items(values: Sequence[str]) -> list[str]:
    return [item.strip() for value in values for item in value.split(",") if item.strip()]


# --- Shared with the page -----------------------------------------------------------------------------------


def shared_paragraph(index: Mapping[str, Any], result: Replay) -> str:
    """One paragraph: the scalings' rise and drop shares and the reassigned kinds against the code's, the base levels,
    campaigns and types, the totals, the top moves and every draft share with its issue, so a draft left behind after
    its issue closed still shows."""
    state = result["state"]
    changed = [_scaling_change(index, result, name) for name in state["rises"] if _scaling_changed(index, result, name)]
    if not changed:
        scalings = "every scaling at the code's"
    else:
        scalings = ", ".join(changed) + "; every other scaling at the code's"
    reassigned = [
        f"{event_type} {_assignment(event_type, name)} (code {index['kinds'][event_type]['scaling']})"
        for event_type, name in state["scalings"].items()
    ]
    kinds = ", ".join(reassigned) if reassigned else "every type on its code scaling"
    switched = [
        f"{event_type} {level} (code {index['kinds'][event_type]['base']})"
        for event_type, level in result["state"]["type_bases"].items()
    ]
    if not switched:
        bases = "every type at the code's"
    elif len(switched) == len(index["kinds"]):
        bases = ", ".join(switched)
    else:
        bases = ", ".join(switched) + "; every other type at the code's"
    totals = result["totals"]
    package = totals["package"]
    moves = "; ".join(_move(move) for move in result["moves"][:TOP_MOVES]) or "nothing"
    return (
        f"Scalings: {scalings}. "
        f"Kinds: {kinds}. "
        f"Base levels: {bases}. "
        f"Campaigns: {', '.join(state['campaigns']) or 'none'}. "
        f"Types: {', '.join(state['types']) or 'all'}. "
        f"{_events(totals['events_moved'])} move level; "
        f"the narrator package goes from {package['baseline']} to {package['replay']} "
        f"{'event' if package['replay'] == 1 else 'events'} at {index['constants']['package_level']} or above "
        f"({_signed(package['change'])}); "
        f"{_events(totals['members_changed'])} with members change. "
        f"What moves: {moves}. "
        f"Drafts: {_drafts(index, result)}."
    )


def _drafts(index: Mapping[str, Any], result: Replay) -> str:
    levels = list(index["constants"]["level_bands"])
    parts = []
    for draft in index["drafts"]:
        own = result["drafts"][draft["name"]]
        counts = own["level_counts"]
        base = own["base"]
        instead = "" if base == draft["base"] else f" instead of {draft['base']}"
        shown = [
            f"{level} {counts['replay'][level]}"
            + (
                f" {_signed(counts['replay'][level] - counts['baseline'][level])}"
                if counts["replay"][level] != counts["baseline"][level]
                else ""
            )
            for level in levels
            if counts["replay"][level] or counts["baseline"][level]
        ]
        total = sum(counts["replay"].values())
        parts.append(
            f"{draft['name']} (#{draft['issue']}) at base {base}{instead}: {_events(total)}"
            + (f" ({', '.join(shown)})" if shown else "")
            + f", {own['floored']} set by a cited event"
        )
    return "; ".join(parts) or "none"


def snippet(index: Mapping[str, Any], result: Replay) -> str:
    """The changed scalings as scaling registry entries, one line each in the state's scaling order (a split one as
    a new entry named after its type), then one comment line per reassigned type and per switched event type, each
    sorted by type."""
    state = result["state"]
    lines = []
    for name in state["rises"]:
        if not _scaling_changed(index, result, name):
            continue
        code = code_scaling(index, name)
        rise, drop = state["rises"][name], state["drops"].get(name)
        shares = f"rise={number_text(rise)}" + ("" if drop is None else f", drop={number_text(drop)}")
        was = f"rise {number_text(code['rise'])}" + (
            "" if code["drop"] is None else f", drop {number_text(code['drop'])}"
        )
        key, note = (
            (name.upper(), f"code: {was}") if name in index["scalings"] else (_constant(name), f"new; copies {was}")
        )
        lines.append(f"Scaling.{key}: ScalingSpec(Measure.{code['measure'].upper()}, {shares}, ...),  # {note}")
    lines += [
        f"# {event_type}: scaling=Scaling.{index['kinds'][event_type]['scaling'].upper()} -> "
        f"Scaling.{_constant(name) if name not in index['scalings'] else name.upper()}"
        for event_type, name in state["scalings"].items()
    ]
    lines += [
        f"# {event_type}: base {index['kinds'][event_type]['base'].upper()} -> {level.upper()}"
        for event_type, level in state["type_bases"].items()
    ]
    return "\n".join(lines) if lines else "# Every scaling, kind's scaling and base level is the code's."


def _constant(name: str) -> str:
    return name.replace(".", "_").replace("-", "_").upper()


def _scaling_changed(index: Mapping[str, Any], result: Replay, name: str) -> bool:
    """A split scaling always counts as changed: it is a new scaling, even at its copy's shares."""
    if name not in index["scalings"]:
        return True
    code = index["scalings"][name]
    state = result["state"]
    return bool(state["rises"][name] != code["rise"] or state["drops"].get(name) != code["drop"])


def _scaling_change(index: Mapping[str, Any], result: Replay, name: str) -> str:
    state = result["state"]
    code = code_scaling(index, name)
    rise = f"rise {number_text(state['rises'][name])} (code {number_text(code['rise'])})"
    drop = state["drops"].get(name)
    if drop is not None or code["drop"] is not None:
        shown = "default" if drop is None else number_text(drop)
        coded = "default" if code["drop"] is None else number_text(code["drop"])
        rise += f", drop {shown} (code {coded})"
    own = " (split off)" if name not in index["scalings"] else ""
    return f"{name}{own} {rise}"


def _assignment(event_type: str, name: str) -> str:
    return "split off" if name == event_type else f"joined to {name}"


def _move(move: Mapping[str, Any]) -> str:
    via = f" ({move['via_cited']} via a cited event)" if move["via_cited"] else ""
    return f"{move['type']} {move['from_level']} -> {move['to_level']} {move['count']}{via}"


def _events(count: int) -> str:
    return f"{count} {'event' if count == 1 else 'events'}"


def _signed(number: int) -> str:
    return f"+{number}" if number > 0 else str(number)


# --- Report formats ----------------------------------------------------------------------------------------


def render_text(
    index: Mapping[str, Any], tables: Tables, result: Replay, *, state_hash: str, drafts: Tables | None = None
) -> str:
    """The Markdown readout, in nine sections: state, summary, level counts, coverage, What moves, members, cut-offs,
    draft shares, snippet. ``drafts`` are the draft rows of each campaign, which say which rows are ruled."""
    state = result["state"]
    levels = list(index["constants"]["level_bands"])
    lines = ["# Share calibration readout", "", "## Calibration state", ""]
    lines += ["| Scaling | Measure | Rise share | Drop share | Code's |", "| --- | --- | ---: | ---: | ---: |"]
    for name, rise in state["rises"].items():
        code = code_scaling(index, name)
        drop = state["drops"].get(name)
        mark = " (changed)" if _scaling_changed(index, result, name) else ""
        coded = f"{number_text(code['rise'])} / {'default' if code['drop'] is None else number_text(code['drop'])}"
        lines.append(
            f"| {name}{mark} | {code['measure']} | {number_text(rise)} "
            f"| {'default' if drop is None else number_text(drop)} | {coded} |"
        )
    if state["scalings"]:
        lines += ["", "| Event type | Scaling | Code's |", "| --- | --- | ---: |"]
        lines += [
            f"| {event_type} | {_assignment(event_type, name)} | {index['kinds'][event_type]['scaling']} |"
            for event_type, name in state["scalings"].items()
        ]
    else:
        lines += ["", "Every event type is on its code scaling."]
    switched = state["type_bases"]
    if switched:
        lines += ["", "| Event type | Base level | Code's |", "| --- | --- | ---: |"]
        lines += [
            f"| {event_type} | {level} (changed) | {index['kinds'][event_type]['base']} |"
            for event_type, level in switched.items()
        ]
    else:
        lines += ["", "Every event type is at the code's base level."]
    lines += [
        "",
        f"- Campaigns: {', '.join(state['campaigns']) or 'none'}",
        f"- Types: {', '.join(state['types']) or 'all'}",
        f"- Cache key: `{index['key']}`",
        f"- State: `#{state_hash}`" if state_hash else "- State: the default (no hash)",
        "",
        "## Summary",
        "",
        shared_paragraph(index, result),
        "",
        "## Level counts",
        "",
    ]
    counts = level_counts(result, levels)
    rows = [
        f"| {event_type} | {level} | {replayed} | {baseline} | {_signed(replayed - baseline)} |"
        for event_type, by_type in counts.items()
        for level in levels
        for replayed, baseline in [(by_type["replay"][level], by_type["baseline"][level])]
        if replayed or baseline
    ]
    lines += _table(["Type", "Level", "Replay", "Baseline", "Change"], rows, "No events.")
    lines += ["", "## Coverage", ""]
    lines += _coverage_text(index, tables)
    lines += ["", "## What moves", ""]
    lines += _table(
        ["Type", "From", "To", "Count", "Via a cited event"],
        [
            f"| {move['type']} | {move['from_level']} | {move['to_level']} | {move['count']} | {move['via_cited']} |"
            for move in result["moves"]
        ],
        "No event moves.",
    )
    lines += ["", "## Member verdicts", ""]
    members = [(name, member) for name, campaign in result["campaigns"].items() for member in campaign["members"]]
    verdicts: dict[str, int] = {}
    for _, member in members:
        verdicts[member["verdict"]] = verdicts.get(member["verdict"], 0) + 1
    lines.append(
        "Groups and candidates: "
        + (", ".join(f"{verdict} {count}" for verdict, count in sorted(verdicts.items())) or "none")
        + "."
    )
    lines.append("")
    lines += _table(
        ["Campaign", "Event", "Type", "Verdict", "Kept", "Lost", "Distinct / minimum", "Stale share"],
        [
            f"| {name} | `{member['id']}` | {member['type']} | {member['verdict']} | {len(member['kept'])} "
            f"| {_ids(member['lost'])} | {member['distinct']} / {member['minimum']} "
            f"| {'yes' if member['stale_share'] else 'no'} |"
            for name, member in members
            if member["verdict"] != "keeps_members"
        ],
        "Every group keeps its members.",
    )
    lines += ["", "## Cut-offs", ""]
    for name, cutoffs in result["cutoffs"].items():
        lines += [f"### {name}", ""]
        if not cutoffs:
            lines += ["No cut-off.", ""]
        for cutoff in cutoffs:
            lines += [f"{_step(cutoff['step'])} at share {cutoff['share']:.3g}:", ""]
            lines += _table(
                ["Side", "Campaign", "Event", "Type", "Share", "Score", "Level", "Code level", "Decided by"],
                [_neighbour_row("below", item) for item in cutoff["below"]]
                + [_neighbour_row("above", item) for item in cutoff["above"]],
                "No event has this share.",
            )
            lines.append("")
    lines += ["## Draft shares", ""]
    lines += _draft_text(index, result, drafts or {})
    lines += ["## Snippet", "", "```python", snippet(index, result), "```", ""]
    return "\n".join(lines)


def _coverage_text(index: Mapping[str, Any], tables: Tables) -> list[str]:
    """Occurrences per sample campaign of each event type and measure, each with its coverage label."""
    found = coverage(index, tables)
    campaigns = list(tables)
    lines: list[str] = []
    for heading, key in (("Type", "types"), ("Measure", "measures")):
        lines += _table(
            [heading, "Coverage", "Total", *campaigns],
            [
                f"| {name} | {entry['label']} | {entry['total']} | "
                + " | ".join(str(entry["campaigns"][campaign]) for campaign in campaigns)
                + " |"
                for name, entry in found[key].items()
            ],
            f"No {key}.",
        )
        lines.append("")
    return lines[:-1]


def _draft_text(index: Mapping[str, Any], result: Replay, drafts: Tables) -> list[str]:
    levels = list(index["constants"]["level_bands"])
    summaries = draft_summaries(index, result, drafts)
    if not summaries:
        return ["No draft shares are declared.", ""]
    lines = _table(
        ["Draft", "Label", "Issue", "Measures", "Base", "Own base", "Events", "Ruled", "Set by a cited event"],
        [
            f"| {item['name']} | {item['label']} | #{item['issue']} | {', '.join(item['measures'])} | {item['base']} "
            f"| {item['own_base']} | {item['events']} | {item['ruled']} | {item['floored']} |"
            for item in summaries
        ],
        "",
    )
    lines += ["", "Level counts at each draft's base, against its own:", ""]
    lines += _table(
        ["Draft", "Level", "Replay", "Own base", "Change"],
        [
            f"| {item['name']} | {level} | {replayed} | {baseline} | {_signed(replayed - baseline)} |"
            for item in summaries
            for level in levels
            for replayed, baseline in [(item["level_counts"]["replay"][level], item["level_counts"]["baseline"][level])]
            if replayed or baseline
        ],
        "No draft rows.",
    )
    lines.append("")
    for item in summaries:
        for name, cutoffs in item["cutoffs"].items():
            lines += [f"### {item['name']} on {name}", ""]
            if not cutoffs:
                lines += ["No cut-off.", ""]
            for cutoff in cutoffs:
                lines += [f"{_step(cutoff['step'])} at share {cutoff['share']:.3g}:", ""]
                lines += _table(
                    ["Side", "Campaign", "Event", "Share", "Score", "Level", "Own base level", "Decided by", "Ruled"],
                    [_draft_neighbour_row("below", entry) for entry in cutoff["below"]]
                    + [_draft_neighbour_row("above", entry) for entry in cutoff["above"]],
                    "No row of this draft has this share.",
                )
                lines.append("")
    return lines


def _step(step: int) -> str:
    """A cut-off by the levels it moves an event from its starting level."""
    what = "Rise" if step > 0 else "Drop"
    count = abs(step)
    return f"{what} share" if count == 1 else f"{what} {count} levels"


def draft_summaries(index: Mapping[str, Any], result: Replay, drafts: Tables) -> list[dict[str, Any]]:
    """Each draft share as the page's draft panel shows it, in index order: its base against its own, its rows'
    levels, how many are ruled (their kind's context rule sets the level, so the base does not apply) or set by a
    cited event, and its own nearest rows at every cut-off of its scalings. Rows of the enabled campaigns and
    types only."""
    types = set(result["state"]["types"])
    ruled = {
        (name, row["id"]): bool(row["ruled"])
        for name in result["state"]["campaigns"]
        for row in drafts.get(name, ())
        if not types or row["type"] in types
    }
    summaries = []
    for draft in index["drafts"]:
        name = draft["name"]
        own = result["drafts"][name]
        summaries.append(
            {
                "name": name,
                "label": draft["label"],
                "issue": draft["issue"],
                "measures": list(draft["measures"]),
                "base": own["base"],
                "own_base": draft["base"],
                "events": sum(own["level_counts"]["replay"].values()),
                "ruled": sum(1 for (_, row_id), flag in ruled.items() if flag and draft_name(row_id) == name),
                "floored": own["floored"],
                "level_counts": own["level_counts"],
                "scalings": dict(draft["scalings"]),
                "cutoffs": {
                    scaling: [
                        {
                            "step": cutoff["step"],
                            "offset": cutoff["offset"],
                            "share": cutoff["share"],
                            "below": [_draft_neighbour(entry, ruled) for entry in cutoff["drafts"][name]["below"]],
                            "above": [_draft_neighbour(entry, ruled) for entry in cutoff["drafts"][name]["above"]],
                        }
                        for cutoff in result["cutoffs"][scaling]
                    ]
                    for scaling in dict.fromkeys(draft["scalings"].values())
                },
            }
        )
    return summaries


def _draft_neighbour(item: Neighbour, ruled: Mapping[tuple[str, str], bool]) -> dict[str, Any]:
    return {**_neighbour(item), "ruled": ruled.get((item["campaign"], item["id"]), False)}


def _draft_neighbour_row(side: str, item: Mapping[str, Any]) -> str:
    decided = "own" if item["decisive"] else f"`{item['decided_by']}`"
    return (
        f"| {side} | {item['campaign']} | `{item['id']}` | {item['share']:.3g} | {item['score']} | {item['level']} "
        f"| {item['code_level']} | {decided} | {'yes' if item['ruled'] else 'no'} |"
    )


def render_json(
    index: Mapping[str, Any], tables: Tables, result: Replay, *, state_hash: str, drafts: Tables | None = None
) -> dict[str, Any]:
    """The JSON readout: the state, the aggregates, only the edges (moved events and cut-off neighbours) and the
    draft shares (``draft_summaries`` of the ``drafts`` rows), and the coverage labels of every type and measure."""
    levels = list(index["constants"]["level_bands"])
    types = set(result["state"]["types"])
    moved: list[dict[str, Any]] = []
    for name, campaign in result["campaigns"].items():
        fallen = {member["id"] for member in campaign["members"] if member["verdict"] == "falls_apart"}
        for row, event in zip(tables[name], campaign["events"], strict=True):
            if event["level"] == row["level"] or event["id"] in fallen or (types and row["type"] not in types):
                continue
            moved.append(
                {
                    "campaign": name,
                    "id": event["id"],
                    "type": row["type"],
                    "shares": row["shares"],
                    "score": event["score"],
                    "level": event["level"],
                    "code_level": row["level"],
                    "decided_by": event["decided_by"],
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "key": index["key"],
        "hash": state_hash,
        "state": result["state"],
        "totals": result["totals"],
        "moves": result["moves"],
        "level_counts": level_counts(result, levels),
        "coverage": coverage(index, tables),
        "members": [
            {"campaign": name, **member}
            for name, campaign in result["campaigns"].items()
            for member in campaign["members"]
            if member["verdict"] != "keeps_members"
        ],
        "moved": moved,
        "cutoffs": {
            name: [
                {
                    "step": cutoff["step"],
                    "offset": cutoff["offset"],
                    "share": cutoff["share"],
                    "below": [_neighbour(item) for item in cutoff["below"]],
                    "above": [_neighbour(item) for item in cutoff["above"]],
                }
                for cutoff in cutoffs
            ]
            for name, cutoffs in result["cutoffs"].items()
        },
        "drafts": draft_summaries(index, result, drafts or {}),
    }


def level_counts(result: Replay, levels: Sequence[str]) -> dict[str, dict[str, dict[str, int]]]:
    """Each type's replayed and baseline count per level, summed over the enabled campaigns; types sorted."""
    summed: dict[str, dict[str, dict[str, int]]] = {}
    for campaign in result["campaigns"].values():
        for event_type, counts in campaign["level_counts"].items():
            entry = summed.setdefault(
                event_type, {"replay": dict.fromkeys(levels, 0), "baseline": dict.fromkeys(levels, 0)}
            )
            for level in levels:
                entry["replay"][level] += counts["replay"][level]
                entry["baseline"][level] += counts["baseline"][level]
    return dict(sorted(summed.items()))


def _neighbour(item: Neighbour) -> dict[str, Any]:
    return {
        "campaign": item["campaign"],
        "id": item["id"],
        "type": item["type"],
        "share": item["share"],
        "score": item["score"],
        "level": item["level"],
        "code_level": item["oracle_level"],
        "decided_by": item["decided_by"],
        "decisive": item["decisive"],
    }


def _neighbour_row(side: str, item: Neighbour) -> str:
    decided = "own" if item["decisive"] else f"`{item['decided_by']}`"
    return (
        f"| {side} | {item['campaign']} | `{item['id']}` | {item['type']} | {item['share']:.3g} | {item['score']} "
        f"| {item['level']} | {item['oracle_level']} | {decided} |"
    )


def _ids(ids: Sequence[str]) -> str:
    return ", ".join(f"`{item}`" for item in ids) or "-"


def _table(header: Sequence[str], rows: Sequence[str], empty: str) -> list[str]:
    if not rows:
        return [empty]
    return ["| " + " | ".join(header) + " |", "|" + " --- |" * len(header), *rows]
