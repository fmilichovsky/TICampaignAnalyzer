"""The readout of a replay: the shared paragraph and the snippet (mirrored by the page), and the report formats.

``shared_paragraph`` and ``snippet`` are pure functions of the index and the replay, ASCII only, with every number
written as JavaScript's ``String(number)``: the page formats them again and must give the same bytes.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any, Final

from tinarrative.benchmarking.calibration.drafts import draft_name
from tinarrative.benchmarking.calibration.replay import (
    SCHEMA_VERSION,
    Neighbour,
    Replay,
    ReplayState,
    ReplayStateError,
    js_number,
)

TOP_MOVES: Final = 5
"""The What moves rows the shared paragraph names."""
_NUMBER = re.compile(r"(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?", re.ASCII)

Tables = Mapping[str, Sequence[Mapping[str, Any]]]


def override_state(
    state: ReplayState,
    index: Mapping[str, Any],
    *,
    references: Sequence[str] = (),
    campaigns: Sequence[str] = (),
    types: Sequence[str] = (),
    clamp: str | None = None,
) -> ReplayState:
    """``state`` with the report's flags applied; each flag value is a comma-separated list, and repeats accumulate.

    ``references`` override the named measures only; given ``campaigns`` or ``types`` replace the state's. Raises
    ``ReplayStateError`` for an unknown or repeated measure or campaign and a reference that is not a positive number;
    ``replay`` checks the types against the rows.
    """
    changed: dict[str, float] = {}
    for item in _items(references):
        measure, separator, number = item.partition("=")
        if not separator:
            raise ReplayStateError(f"--reference {item!r} is not MEASURE=VALUE")
        if measure not in index["measures"]:
            raise ReplayStateError(f"unknown measure {measure!r} (known: {', '.join(index['measures'])})")
        if measure in changed:
            raise ReplayStateError(f"measure {measure!r} is given twice")
        value = float(number) if _NUMBER.fullmatch(number) else math.nan
        if not math.isfinite(value) or value <= 0:
            raise ReplayStateError(f"the reference of {measure} must be a positive number, not {number!r}")
        changed[measure] = value
    if changed:
        state = replace(state, references={**state.references, **changed})
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
    if clamp is not None:
        state = replace(state, clamp=clamp == "on")
    return state


def _items(values: Sequence[str]) -> list[str]:
    return [item.strip() for value in values for item in value.split(",") if item.strip()]


# --- Shared with the page -----------------------------------------------------------------------------------


def shared_paragraph(index: Mapping[str, Any], result: Replay) -> str:
    """One paragraph: the references against the code's, the clamp, campaigns and types, the totals, the top moves
    and every draft stake with its issue, so a draft left behind after its issue closed still shows."""
    state = result["state"]
    code = index["measures"]
    changed = [
        f"{measure} {js_number(state['references'][measure])} (code {js_number(code[measure]['reference'])})"
        for measure in code
        if state["references"][measure] != code[measure]["reference"]
    ]
    if not changed:
        references = "every measure at the code's"
    elif len(changed) == len(code):
        references = ", ".join(changed)
    else:
        references = ", ".join(changed) + "; every other measure at the code's"
    totals = result["totals"]
    package = totals["package"]
    moves = "; ".join(_move(move) for move in result["moves"][:TOP_MOVES]) or "nothing"
    return (
        f"References: {references}. "
        f"Clamp {'on' if state['clamp'] else 'off'}. "
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
    """The changed references as measure registry entries, one line each in index order."""
    references = result["state"]["references"]
    lines = [
        f"StakeMeasure.{measure.upper()}: MeasureSpec(reference={js_number(references[measure])}, ...),"
        f"  # code: {js_number(spec['reference'])}"
        for measure, spec in index["measures"].items()
        if references[measure] != spec["reference"]
    ]
    return "\n".join(lines) if lines else "# Every reference is the code's."


def _move(move: Mapping[str, Any]) -> str:
    via = f" ({move['via_cited']} via a cited event)" if move["via_cited"] else ""
    return f"{move['type']} {move['from_level']} -> {move['to_level']} {move['count']}{via}"


def _events(count: int) -> str:
    return f"{count} {'event' if count == 1 else 'events'}"


def _signed(number: int) -> str:
    return f"+{number}" if number > 0 else str(number)


# --- Report formats ----------------------------------------------------------------------------------------


def render_text(index: Mapping[str, Any], result: Replay, *, state_hash: str, drafts: Tables | None = None) -> str:
    """The Markdown readout, in eight sections: state, summary, level counts, What moves, members, cut-offs, draft
    stakes, snippet. ``drafts`` are the draft rows of each campaign, which say which rows are ruled."""
    state = result["state"]
    levels = list(index["constants"]["level_bands"])
    lines = ["# Stake calibration readout", "", "## Calibration state", ""]
    lines += ["| Measure | Reference | Code's |", "| --- | ---: | ---: |"]
    for measure, spec in index["measures"].items():
        value = state["references"][measure]
        mark = " (changed)" if value != spec["reference"] else ""
        lines.append(f"| {measure} | {js_number(value)}{mark} | {js_number(spec['reference'])} |")
    lines += [
        "",
        f"- Campaigns: {', '.join(state['campaigns']) or 'none'}",
        f"- Clamp: {'on' if state['clamp'] else 'off'}",
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
        ["Campaign", "Event", "Type", "Verdict", "Kept", "Lost", "Distinct / minimum", "Stale stake"],
        [
            f"| {name} | `{member['id']}` | {member['type']} | {member['verdict']} | {len(member['kept'])} "
            f"| {_ids(member['lost'])} | {member['distinct']} / {member['minimum']} "
            f"| {'yes' if member['stale_stake'] else 'no'} |"
            for name, member in members
            if member["verdict"] != "keeps_members"
        ],
        "Every group keeps its members.",
    )
    lines += ["", "## Cut-offs", ""]
    for measure, cutoffs in result["cutoffs"].items():
        lines += [f"### {measure}", ""]
        if not cutoffs:
            lines += ["No cut-off.", ""]
        for cutoff in cutoffs:
            lines += [f"Cut-off at share {cutoff['share']:.3g} (offset {js_number(cutoff['offset'])}):", ""]
            lines += _table(
                ["Side", "Campaign", "Event", "Type", "Share", "Score", "Level", "Code level", "Decided by"],
                [_neighbour_row("below", item) for item in cutoff["below"]]
                + [_neighbour_row("above", item) for item in cutoff["above"]],
                "No event has this stake.",
            )
            lines.append("")
    lines += ["## Draft stakes", ""]
    lines += _draft_text(index, result, drafts or {})
    lines += ["## Snippet", "", "```python", snippet(index, result), "```", ""]
    return "\n".join(lines)


def _draft_text(index: Mapping[str, Any], result: Replay, drafts: Tables) -> list[str]:
    levels = list(index["constants"]["level_bands"])
    summaries = draft_summaries(index, result, drafts)
    if not summaries:
        return ["No draft stakes are declared.", ""]
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
        for measure, cutoffs in item["cutoffs"].items():
            lines += [f"### {item['name']} on {measure}", ""]
            if not cutoffs:
                lines += ["No cut-off.", ""]
            for cutoff in cutoffs:
                lines += [f"Cut-off at share {cutoff['share']:.3g} (offset {js_number(cutoff['offset'])}):", ""]
                lines += _table(
                    ["Side", "Campaign", "Event", "Share", "Score", "Level", "Own base level", "Decided by", "Ruled"],
                    [_draft_neighbour_row("below", entry) for entry in cutoff["below"]]
                    + [_draft_neighbour_row("above", entry) for entry in cutoff["above"]],
                    "No row of this draft has this stake.",
                )
                lines.append("")
    return lines


def draft_summaries(index: Mapping[str, Any], result: Replay, drafts: Tables) -> list[dict[str, Any]]:
    """Each draft stake as the page's draft panel shows it, in index order: its base against its own, its rows'
    levels, how many are ruled (their kind's context rule sets the level, so the base does not apply) or set by a
    cited event, and its own nearest rows at every cut-off of its measures. Rows of the enabled campaigns and
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
                "cutoffs": {
                    measure: [
                        {
                            "offset": cutoff["offset"],
                            "share": cutoff["share"],
                            "below": [_draft_neighbour(entry, ruled) for entry in cutoff["drafts"][name]["below"]],
                            "above": [_draft_neighbour(entry, ruled) for entry in cutoff["drafts"][name]["above"]],
                        }
                        for cutoff in result["cutoffs"][measure]
                    ]
                    for measure in draft["measures"]
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
    draft stakes (``draft_summaries`` of the ``drafts`` rows)."""
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
                    "stakes": row["stakes"],
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
        "members": [
            {"campaign": name, **member}
            for name, campaign in result["campaigns"].items()
            for member in campaign["members"]
            if member["verdict"] != "keeps_members"
        ],
        "moved": moved,
        "cutoffs": {
            measure: [
                {
                    "offset": cutoff["offset"],
                    "share": cutoff["share"],
                    "below": [_neighbour(item) for item in cutoff["below"]],
                    "above": [_neighbour(item) for item in cutoff["above"]],
                }
                for cutoff in cutoffs
            ]
            for measure, cutoffs in result["cutoffs"].items()
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
