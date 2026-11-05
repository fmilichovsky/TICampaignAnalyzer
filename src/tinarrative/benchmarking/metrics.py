"""Measure and compare the narrator package sizes produced from benchmark samples."""

from __future__ import annotations

import json
import lzma
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, TextIO

from .manifest import MANIFEST, sample_files, sha256_file

TOOL_VERSION = 1
MAX_DEPTH = 4
"""Members are broken down to this many keys below the package, ``saves[].situation.nations[].allies`` being four."""
MAX_KEYS = 30
"""A mapping with more keys than this is keyed by ID rather than by member name, and is not broken down."""
STDERR_TAIL = 1_000
OVER_BUDGET = re.compile(r"needs about (\d+) input tokens")
MARKER = "<!-- package-metrics -->"
COMMENT_LIMIT = 65_536
"""GitHub's limit on the characters of a comment body."""
HIGHLIGHTS = 25
MEMBER_FLOOR = 1.0
"""Breakdown tables list the members holding at least this share of the package (per cent), and every changed one."""


def compact(value: Any) -> int:
    """The characters of ``value`` as JSON in a request: compact separators, no ASCII escaping."""
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def breakdown(document: Mapping[str, Any]) -> dict[str, int]:
    """The compact characters of every member path of ``document``, key included, summed over list elements.

    A path names list elements with ``[]``: ``saves[].situation`` is the situation of every save together. The
    members of one mapping add up to the mapping but for its braces and commas.
    """
    sizes: dict[str, int] = {}

    def walk(value: Any, path: str, depth: int) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item, f"{path}[]", depth)
        elif isinstance(value, dict) and depth < MAX_DEPTH and (depth == 0 or len(value) <= MAX_KEYS):
            for key, member in value.items():
                child = f"{path}.{key}" if path else str(key)
                sizes[child] = sizes.get(child, 0) + compact(key) + 1 + compact(member)
                walk(member, child, depth + 1)

    walk(document, "", 0)
    return sizes


def package_counts(package: Mapping[str, Any]) -> dict[str, int]:
    """How many entries the package lists, by kind; the narrative also by significance."""
    narrative = package.get("narrative") or []
    intervals = package.get("intervals") or []
    counts = {
        "narrative": len(narrative),
        "intervals": len(intervals),
        "interval_events": sum(len(interval.get("events") or []) for interval in intervals),
        "interval_inferred": sum(len(interval.get("inferred") or []) for interval in intervals),
        "glossary": len(package.get("glossary") or []),
        "saves": len(package.get("saves") or []),
    }
    for event in narrative:
        key = f"narrative.{event.get('significance')}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def request_package(content: str) -> tuple[str, dict[str, Any]]:
    """The JSON body of a request's user message and the package it holds, as ``request.chapter_package`` reads it."""
    _, fence, rest = content.partition("```json\n")
    body, closing, _ = rest.rpartition("\n```")
    if not fence or not closing:
        raise ValueError("the request carries no narrator package")
    package = json.loads(body)
    if not isinstance(package, dict):
        raise ValueError("the request carries no narrator package")
    return body, package


# Measuring


def load_matrix(path: Path) -> dict[str, list[dict[str, Any]]]:
    """The ``events`` and ``narrate`` runs of a matrix file; raises ``ValueError`` on a malformed one."""
    matrix = tomllib.loads(path.read_text(encoding="utf-8"))
    runs: dict[str, list[dict[str, Any]]] = {"events": matrix.get("events", []), "narrate": matrix.get("narrate", [])}
    for kind, entries in runs.items():
        ids = [entry.get("id") for entry in entries]
        if len(set(ids)) != len(ids) or not all(isinstance(run_id, str) and run_id for run_id in ids):
            raise ValueError(f"{kind}: every run needs a unique id")
        for entry in entries:
            args = entry.get("args", [])
            if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
                raise ValueError(f"{kind}.{entry['id']}: args must be a list of strings")
    known = {entry["id"] for entry in runs["events"]}
    for entry in runs["narrate"]:
        if entry.get("package") not in known:
            raise ValueError(f"narrate.{entry['id']}: package must name an events run")
    if not runs["events"]:
        raise ValueError("the matrix lists no events runs")
    return runs


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run a tinarrative command with no settings file from the environment."""
    environment = {key: value for key, value in os.environ.items() if key != "TINARRATIVE_CONFIG"}
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=environment, check=False)


Timed = tuple[subprocess.CompletedProcess[str], float]


def _timed_run(command: Sequence[str]) -> Timed:
    """``_run``, and the seconds the command took."""
    started = time.perf_counter()
    completed = _run(command)
    return completed, time.perf_counter() - started


def _serial(cli: Sequence[str]) -> list[str]:
    """``--jobs 1`` when the revision's ``events`` takes it: the runs already fill the CPUs, and workers per run would
    multiply processes and memory. An older revision is run as it is."""
    return ["--jobs", "1"] if "--jobs" in _run([*cli, "events", "--help"]).stdout else []


def _failure(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    error = completed.stderr.strip()[-STDERR_TAIL:]
    failure: dict[str, Any] = {"exit": completed.returncode, "error": error}
    if (match := OVER_BUDGET.search(error)) is not None:
        failure["needs_tokens"] = int(match.group(1))
    return failure


def _tree(groups: Sequence[tuple[str, Sequence[tuple[str, str]]]]) -> list[str]:
    """The lines of a two-level tree: each group's label above its ``(name, note)`` rows, names padded to one width."""
    width = max((len(name) for _, rows in groups for name, _ in rows), default=0)
    lines = []
    for index, (label, rows) in enumerate(groups):
        last = index == len(groups) - 1
        lines.append(f"{'└─' if last else '├─'} {label}")
        for row, (name, note) in enumerate(rows):
            branch = "└─" if row == len(rows) - 1 else "├─"
            lines.append(f"{'   ' if last else '│  '}{branch} {name.ljust(width)}  {note}")
    return lines


def measure_package(text: str, chars_per_token: float) -> dict[str, Any]:
    """The metrics of one narrator package, given as the text ``events`` wrote."""
    package = json.loads(text)
    chars = compact(package)
    return {
        "bytes": len(text.encode("utf-8")),
        "chars": chars,
        "est_tokens": math.ceil(chars / chars_per_token),
        "counts": package_counts(package),
        "members": breakdown(package),
    }


def measure_narration(directory: Path) -> dict[str, Any]:
    """The metrics of a ``narrate --output`` directory: the plan and the characters of its requests."""
    plan = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
    chapters = plan["chapters"]
    totals = {"system": 0, "block": 0, "package": 0}
    members: dict[str, int] = {}
    per_chapter = []
    for chapter, path in zip(chapters, sorted((directory / "requests").glob("*.json")), strict=True):
        request = json.loads(path.read_text(encoding="utf-8"))
        content = request["messages"][0]["content"]
        body, package = request_package(content)
        totals["system"] += len(request["system"])
        totals["block"] += len(content) - len(body)
        totals["package"] += len(body)
        for member, size in breakdown(package).items():
            members[member] = members.get(member, 0) + size
        per_chapter.append(
            {
                key: chapter[key]
                for key in ("index", "part", "developments", "continuing", "recalled", "estimate", "reduction")
            }
        )
    estimates = [chapter["estimate"] for chapter in chapters]
    reductions: dict[str, int] = {}
    for chapter in chapters:
        if chapter["reduction"] is not None:
            reductions[chapter["reduction"]] = reductions.get(chapter["reduction"], 0) + 1
    return {
        "prompt_version": plan["prompt_version"],
        "settings": plan["settings"],
        "chapters": len(chapters),
        "estimate_total": sum(estimates),
        "estimate_max": max(estimates, default=0),
        "reductions": reductions,
        "chars": {**totals, "total": sum(totals.values())},
        "members": members,
        "per_chapter": per_chapter,
    }


def _measure_campaign(
    campaign: str,
    files: Sequence[Path],
    matrix: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    cli: Sequence[str],
    serial: Sequence[str] = (),
    config: Path,
    scratch: Path,
    out: Path,
    chars_per_token: float,
    runs: ThreadPoolExecutor,
    on_progress: Callable[[int], None] | None,
) -> tuple[dict[str, Any], list[str]]:
    """Run the matrix against one campaign on ``runs``; its results, in matrix order, and the lines of its log.

    Every ``events`` run starts at once, and each ``narrate`` run as soon as the package it plans is written.
    """
    started = time.perf_counter()
    saves = scratch / campaign
    saves.mkdir()
    for file in files:
        with lzma.open(file) as source, (saves / file.name.removesuffix(".xz")).open("wb") as target:
            shutil.copyfileobj(source, target, 1 << 20)
    decompressed = time.perf_counter() - started
    packages = out / "packages" / campaign
    packages.mkdir(parents=True)
    results: dict[str, dict[str, Any]] = {"events": {}, "narrate": {}}
    seconds: dict[tuple[str, str], float] = {}
    events: dict[Future[Timed], str] = {
        runs.submit(
            _timed_run, [*cli, "events", str(saves), *entry.get("args", []), *serial, "--config", str(config)]
        ): entry["id"]
        for entry in matrix["events"]
    }
    narrations: dict[Future[Timed], Mapping[str, Any]] = {}
    for future in as_completed(events):
        run_id = events[future]
        completed, seconds["events", run_id] = future.result()
        planned = [entry for entry in matrix["narrate"] if entry["package"] == run_id]
        if completed.returncode != 0:
            results["events"][run_id] = _failure(completed)
            for entry in planned:
                results["narrate"][entry["id"]] = {"exit": None, "error": f"events {run_id} failed"}
            if on_progress is not None:
                on_progress(1 + len(planned))
            continue
        package = packages / f"{run_id}.json"
        package.write_text(completed.stdout, encoding="utf-8", newline="\n")
        for entry in planned:
            target = out / "narrate" / campaign / entry["id"]
            command = [*cli, "narrate", "--package", str(package), "--output", str(target)]
            narrations[runs.submit(_timed_run, [*command, *entry.get("args", []), "--config", str(config)])] = entry
        results["events"][run_id] = measure_package(completed.stdout, chars_per_token)
        if on_progress is not None:
            on_progress(1)
    for future in as_completed(narrations):
        entry = narrations[future]
        completed, seconds["narrate", entry["id"]] = future.result()
        if completed.returncode != 0:
            results["narrate"][entry["id"]] = _failure(completed)
            if on_progress is not None:
                on_progress(1)
            continue
        target = out / "narrate" / campaign / entry["id"]
        results["narrate"][entry["id"]] = {"package": entry["package"], **measure_narration(target)}
        if on_progress is not None:
            on_progress(1)
    shutil.rmtree(saves)

    ordered = {kind: {entry["id"]: results[kind][entry["id"]] for entry in matrix[kind]} for kind in results}

    def row(kind: str, run_id: str) -> tuple[str, str]:
        result = ordered[kind][run_id]
        if (kind, run_id) not in seconds:
            return run_id, f"skipped: {result['error']}"
        took = f"{seconds[kind, run_id]:6.1f}s"
        return run_id, took if _ok(result) else f"{took}  {_failed(result)}"

    header = (
        f"package_metrics: {campaign} · {len(files)} saves · {time.perf_counter() - started:.1f}s "
        f"(decompressing {decompressed:.1f}s)"
    )
    tree = _tree([(kind, [row(kind, run_id) for run_id in ordered[kind]]) for kind in ordered if ordered[kind]])
    return ordered, [header, *tree]


def measure(
    *,
    python: str,
    samples: Path,
    matrix_path: Path,
    config: Path,
    out: Path,
    label: str,
    chars_per_token: float,
    jobs: int = os.cpu_count() or 1,
    log: TextIO | None = sys.stderr,
    on_progress: Callable[[int], None] | None = None,
    on_campaign_complete: Callable[[Sequence[str]], None] | None = None,
) -> dict[str, Any]:
    """Run the matrix against every sample campaign and return the metrics; packages and plans go under ``out``.

    The campaigns are measured at once, with at most ``jobs`` commands running. Each campaign's log is written in one
    piece when it is done, so the logs of campaigns never interleave.
    """
    matrix = load_matrix(matrix_path)
    for kept in ("packages", "narrate"):
        shutil.rmtree(out / kept, ignore_errors=True)
    found = sample_files(samples)
    per_campaign = len(matrix["events"]) + len(matrix["narrate"])
    print(
        f"package_metrics: measuring {len(found)} campaigns ({', '.join(found)}), {per_campaign} runs each, "
        f"{jobs} jobs",
        file=log,
        flush=True,
    )
    started = time.perf_counter()
    measured: dict[str, Any] = {}
    cli = [python, "-m", "tinarrative.cli"]
    serial = _serial(cli)
    with (
        tempfile.TemporaryDirectory(prefix="package-metrics-") as scratch,
        ThreadPoolExecutor(max_workers=jobs) as runs,
        ThreadPoolExecutor(max_workers=max(len(found), 1)) as coordinators,
    ):
        # A campaign waits for its runs on a thread of its own, so it never holds one of the ``jobs`` slots.
        futures = {
            coordinators.submit(
                _measure_campaign,
                campaign,
                files,
                matrix,
                cli=cli,
                serial=serial,
                config=config,
                scratch=Path(scratch),
                out=out,
                chars_per_token=chars_per_token,
                runs=runs,
                on_progress=on_progress,
            ): campaign
            for campaign, files in found.items()
        }
        for future in as_completed(futures):
            measured[futures[future]], lines = future.result()
            if on_campaign_complete is None:
                print("\n".join(lines), file=log, flush=True)
            else:
                on_campaign_complete(lines)
    print(f"package_metrics: done in {time.perf_counter() - started:.1f}s", file=log, flush=True)
    campaigns = {campaign: measured[campaign] for campaign in found}
    return {
        "tool_version": TOOL_VERSION,
        "label": label,
        "chars_per_token": chars_per_token,
        "matrix_sha256": sha256_file(matrix_path),
        "samples_sha256": sha256_file(samples / MANIFEST),
        "matrix": {kind: [entry["id"] for entry in entries] for kind, entries in matrix.items()},
        "campaigns": campaigns,
    }


# Comparing


def _number(value: int | None) -> str:
    return "–" if value is None else f"{value:,}"


def _delta(base: int | None, head: int | None) -> str:
    if base is None or head is None:
        return "–"
    change = head - base
    if change == 0:
        return "0"
    mark = "▲" if change > 0 else "▼"
    percent = f" ({change / base:+.1%})" if base else ""
    return f"{mark} {change:+,}{percent}"


def _failed(result: Mapping[str, Any] | None) -> str:
    if result is None:
        return "not run"
    if "needs_tokens" in result:
        return f"over budget: needs ~{result['needs_tokens']:,} tokens"
    if result.get("exit") is None:
        return str(result.get("error", "not run"))
    return f"failed (exit {result['exit']})"


def _ok(result: Mapping[str, Any] | None) -> bool:
    return result is not None and "exit" not in result


def _runs(metrics: Mapping[str, Any]) -> Iterable[tuple[str, str, str, Mapping[str, Any]]]:
    for campaign, results in metrics["campaigns"].items():
        for kind in ("events", "narrate"):
            for run_id, result in results[kind].items():
                yield campaign, kind, run_id, result


def _parent(member: str) -> str:
    return member.rpartition(".")[0].removesuffix("[]")


def member_changes(before: Mapping[str, int], after: Mapping[str, int]) -> list[tuple[str, int]]:
    """The changed members, largest change first, each left out when one of its own members explains its change.

    A member explains its parent's change when it moved the same way by at least nine tenths as much, so dropping a
    field reads as that field and not as every mapping above it.
    """
    deltas = {member: after.get(member, 0) - before.get(member, 0) for member in set(before) | set(after)}
    deltas = {member: delta for member, delta in deltas.items() if delta}
    explained = {
        _parent(member)
        for member, delta in deltas.items()
        if _parent(member) in deltas
        and delta * deltas[_parent(member)] > 0
        and abs(delta) >= 0.9 * abs(deltas[_parent(member)])
    }
    return sorted(
        ((member, delta) for member, delta in deltas.items() if member not in explained),
        key=lambda change: (-abs(change[1]), change[0]),
    )


def _highlights(base: Mapping[str, Any], head: Mapping[str, Any], threshold: float) -> list[tuple[float, str]]:
    """One row per run whose estimate, or one of whose members, changed by at least ``threshold`` per cent.

    The estimate is weighed against its base value and a member against the base package, so a small member that
    doubles does not count as much as a large one that shrinks by a fifth. Largest change first.
    """
    rows: list[tuple[float, str]] = []
    for campaign, kind, run_id, after in _runs(head):
        before = base["campaigns"].get(campaign, {}).get(kind, {}).get(run_id)
        if not (_ok(before) and _ok(after)):
            continue
        key = "est_tokens" if kind == "events" else "estimate_total"
        old, new = before[key], after[key]
        weight = before["chars"] if kind == "events" else before["chars"]["package"]
        changes = member_changes(before["members"], after["members"])
        shares = [abs(new - old) / old * 100 if old else 0.0]
        shares += [abs(delta) / weight * 100 for _, delta in changes if weight]
        if max(shares) < threshold:
            continue
        listed = ", ".join(f"`{member}` {delta:+,}" for member, delta in changes[:3])
        if kind == "narrate" and before["chapters"] != after["chapters"]:
            listed = f"{before['chapters']} → {after['chapters']} chapters; {listed}"
        cells = f"{_number(old)} → {_number(new)} | {_delta(old, new)} | {listed or '–'}"
        rows.append((max(shares), f"| {campaign} · {kind} `{run_id}` | {cells} |"))
    rows.sort(key=lambda row: -row[0])
    return rows


def _members_table(before: Mapping[str, int], after: Mapping[str, int], total: int) -> list[str]:
    lines = ["| Member | Base | Head | Δ | Share of head |", "| --- | ---: | ---: | ---: | ---: |"]
    for member in sorted(set(before) | set(after), key=lambda name: (-(after.get(name) or before.get(name, 0)), name)):
        old, new = before.get(member), after.get(member)
        share = (new or 0) / total * 100 if total else 0.0
        if old == new and share < MEMBER_FLOOR:
            continue
        delta = _delta(old or 0, new or 0)
        lines.append(f"| `{member}` | {_number(old)} | {_number(new)} | {delta} | {share:.1f}% |")
    return lines


def compare(
    base: Mapping[str, Any], head: Mapping[str, Any], *, threshold: float = 1.0, run_url: str | None = None
) -> str:
    """The Markdown report of ``head`` against ``base``, at most ``COMMENT_LIMIT`` characters."""
    campaigns = sorted(set(base["campaigns"]) | set(head["campaigns"]))
    per_campaign = len(head["matrix"]["events"]), len(head["matrix"]["narrate"])
    header = [
        MARKER,
        "## Narrator package size",
        "",
        f"`{base['label']}` → `{head['label']}` · {len(campaigns)} sample campaigns · {per_campaign[0]} `events` and "
        f"{per_campaign[1]} `narrate` runs each. Sizes are characters of the compact JSON a request carries; tokens "
        f"are estimated at {head['chars_per_token']} characters per token.",
        "",
    ]
    notes = []
    if base["matrix_sha256"] != head["matrix_sha256"] or base["samples_sha256"] != head["samples_sha256"]:
        notes.append("The two sides were measured with different matrices or samples; the numbers are not comparable.")
    versions = {
        side: {result["prompt_version"] for _, kind, _, result in _runs(metrics) if kind == "narrate" and _ok(result)}
        for side, metrics in (("base", base), ("head", head))
    }
    if versions["base"] and versions["head"] and versions["base"] != versions["head"]:
        notes.append("The narrator prompt changed, so every request's system text changed with it.")
    for campaign, kind, run_id, result in _runs(head):
        before = base["campaigns"].get(campaign, {}).get(kind, {}).get(run_id)
        if not _ok(result) and _ok(before):
            notes.append(f"{campaign} · {kind} `{run_id}` now fails: {_failed(result)}.")
        elif _ok(result) and before is not None and not _ok(before):
            notes.append(f"{campaign} · {kind} `{run_id}` failed on the base: {_failed(before)}.")

    highlights = _highlights(base, head, threshold)
    summary = ["### Highlights", ""]
    if highlights:
        summary += [
            f"Runs whose estimate, or one of whose members, changed by at least {threshold:g}% of the run, largest "
            "first, with the members that changed most (characters).",
            "",
            "| Run | Est. tokens | Δ | Largest member changes |",
            "| --- | ---: | ---: | --- |",
            *(row for _, row in highlights[:HIGHLIGHTS]),
        ]
        if len(highlights) > HIGHLIGHTS:
            summary += ["", f"{len(highlights) - HIGHLIGHTS} more in the tables below."]
    else:
        summary.append(f"No change in package sizes above {threshold:g}%.")
    summary.append("")

    events = [
        "### `events` packages",
        "",
        "| Campaign | Run | Est. tokens | Δ | Narrative events | Atomic events | Glossary |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    narrate = [
        "### `narrate` plans",
        "",
        "| Campaign | Run | Chapters | Est. tokens, all chapters | Δ | Largest chapter | Reductions |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    details: list[tuple[bool, bool, list[str]]] = []
    for campaign in campaigns:
        for kind, table in (("events", events), ("narrate", narrate)):
            ids = list(head["campaigns"].get(campaign, {}).get(kind, {}))
            ids += [run_id for run_id in base["campaigns"].get(campaign, {}).get(kind, {}) if run_id not in ids]
            for run_id in ids:
                before = base["campaigns"].get(campaign, {}).get(kind, {}).get(run_id)
                after = head["campaigns"].get(campaign, {}).get(kind, {}).get(run_id)
                if not (_ok(before) or _ok(after)):
                    table.append(f"| {campaign} | `{run_id}` | {_failed(after)} | | | | |")
                    continue
                table.append(_row(kind, campaign, run_id, before, after))
                if _ok(before) and _ok(after):
                    total = after["chars"] if kind == "events" else after["chars"]["package"]
                    section = [
                        f"<details><summary>{campaign} · {kind} <code>{run_id}</code> members</summary>",
                        "",
                        *_members_table(before["members"], after["members"], total),
                        "",
                        "</details>",
                        "",
                    ]
                    changed = bool(member_changes(before["members"], after["members"]))
                    details.append((changed, kind == "events" and run_id == ids[0], section))
    body = [*summary, *events, "", *narrate, ""]
    if notes:
        body += ["### Notes", "", *(f"- {note}" for note in notes), ""]
    footer = []
    if run_url:
        footer.append(f"Packages, plans and requests of both sides are in the [`package-metrics` artifact]({run_url}).")
    report = "\n".join([*header, *body])
    # The runs whose members changed; when none did, the first events package of each campaign as it stands.
    shown = [section for changed, _, section in details if changed]
    title = "### Member changes"
    if not shown:
        shown = [section for _, first, section in details if first]
        title = "### Package members"
    breakdowns = [title, ""]
    for section in shown:
        text = "\n".join(section)
        if len(report) + len("\n".join(breakdowns)) + len(text) + 400 > COMMENT_LIMIT:
            breakdowns.append("The remaining breakdowns did not fit in a comment; they are in `metrics.json`.")
            break
        breakdowns.append(text)
    return "\n".join([report, *(breakdowns if shown else []), *footer]) + "\n"


def _row(
    kind: str, campaign: str, run_id: str, before: Mapping[str, Any] | None, after: Mapping[str, Any] | None
) -> str:
    def get(result: Mapping[str, Any] | None, *keys: str) -> Any:
        value: Any = result if _ok(result) else None
        for key in keys:
            value = None if value is None else value.get(key)
        return value

    def pair(*keys: str) -> str:
        old, new = get(before, *keys), get(after, *keys)
        if old == new:
            return _number(new)
        return f"{_failed(before) if old is None else _number(old)} → {_failed(after) if new is None else _number(new)}"

    if kind == "events":
        delta = _delta(get(before, "est_tokens"), get(after, "est_tokens"))
        counts = [pair("counts", name) for name in ("narrative", "interval_events", "glossary")]
        return f"| {campaign} | `{run_id}` | {pair('est_tokens')} | {delta} | {' | '.join(counts)} |"
    reductions = {
        side: ", ".join(f"{name} ×{count}" for name, count in (get(result, "reductions") or {}).items()) or "–"
        for side, result in (("base", before), ("head", after))
    }
    reduced = reductions["head"] if reductions["base"] == reductions["head"] else " → ".join(reductions.values())
    delta = _delta(get(before, "estimate_total"), get(after, "estimate_total"))
    return (
        f"| {campaign} | `{run_id}` | {pair('chapters')} | {pair('estimate_total')} | {delta} | "
        f"{pair('estimate_max')} | {reduced} |"
    )
