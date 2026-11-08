"""Measure the processing runtime of ``events`` on benchmark samples or a save directory, and report it."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO, TypeGuard, cast

from ..log import ENV_VAR, TIMING_ENV_VAR
from .manifest import MANIFEST, decompress_samples, sample_files, sha256_file
from .metrics import STDERR_TAIL, load_matrix

TOOL_VERSION = 1
MARKER = "<!-- runtime-metrics -->"
STAGES = (
    "survey",
    "decode",
    "normalize",
    "situation",
    "diff",
    "analyzers",
    "reconstruction",
    "significance",
    "aggregation",
)
"""``decode`` is reading and decoding a save for analysis: the load time less normalization."""
INTERVAL_STAGES = ("diff", "analyzers", "reconstruction", "significance")
FLAG_SHARE = 10.0
"""A stage is flagged when it changes by at least this per cent and at least ``FLAG_SECONDS``."""
FLAG_SECONDS = 0.5
NOISE_FACTOR = 2.0
"""A flagged change also exceeds this multiple of the larger spread (slowest less fastest) of a side's runs."""
TOP_RULES = 5

_LINE = re.compile(r"^INFO tinarrative\.timing: (\w+) (.*)$")
_FIELD = re.compile(r"(\w+)=(\S+)")


@dataclass(frozen=True)
class Side:
    """One revision to measure: its key in the results (``base`` or ``head``), interpreter and label."""

    name: str
    python: str
    label: str


def parse_timings(stderr: str) -> dict[str, Any] | None:
    """Stage totals, seconds per interval and per narrative rule from the timing lines; ``None`` without any.

    An interval's seconds include loading and reporting its later save, so the series shows growth per save. With
    worker processes the stages are CPU seconds summed over them; ``peak_memory`` sums every process's ``memory``
    line, an upper bound because the peaks need not coincide.
    """
    stages = dict.fromkeys(STAGES, 0.0)
    saves: dict[int, float] = {}
    intervals: dict[int, float] = {}
    rules: dict[str, float] = {}
    peaks: list[int] = []
    found = False
    for line in stderr.splitlines():
        match = _LINE.match(line)
        if match is None:
            continue
        found = True
        kind, values = match.group(1), dict(_FIELD.findall(match.group(2)))
        if kind in ("survey", "normalize"):
            stages[kind] += float(values["seconds"])
        elif kind == "aggregate":
            stages["aggregation"] += float(values["seconds"])
        elif kind == "save":
            stages["decode"] += float(values["load"])
            stages["situation"] += float(values["situation"])
            saves[int(values["index"])] = float(values["load"]) + float(values["situation"])
        elif kind == "interval":
            seconds = [float(values.get(stage, 0.0)) for stage in INTERVAL_STAGES]
            for stage, value in zip(INTERVAL_STAGES, seconds, strict=True):
                stages[stage] += value
            intervals[int(values["index"])] = sum(seconds)
        elif kind == "rule":
            rules[values["name"]] = rules.get(values["name"], 0.0) + float(values["seconds"])
        elif kind == "memory":
            peaks.append(int(values["peak"]))
    if not found:
        return None
    stages["decode"] = max(stages["decode"] - stages["normalize"], 0.0)
    series = [intervals[index] + saves.get(index + 1, 0.0) for index in sorted(intervals)]
    return {
        "saves": len(saves),
        "stages": {stage: round(value, 3) for stage, value in stages.items()},
        "intervals": [round(value, 3) for value in series],
        "rules": {name: round(value, 3) for name, value in sorted(rules.items())},
        "processes": len(peaks),
        "peak_memory": sum(peaks) if peaks else None,
    }


def _environment() -> dict[str, str]:
    """No settings file or log level from the environment; timing lines on."""
    environment = {key: value for key, value in os.environ.items() if key not in ("TINARRATIVE_CONFIG", ENV_VAR)}
    environment[TIMING_ENV_VAR] = "1"
    return environment


def _timed_run(command: Sequence[str]) -> tuple[int, float, int | None, str]:
    """Exit code, wall seconds, peak resident bytes (``None`` where unavailable) and stderr of one command."""
    started = time.perf_counter()
    process = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=_environment(), text=True, encoding="utf-8"
    )
    assert process.stderr is not None
    stderr = process.stderr.read()
    process.stderr.close()
    peak: int | None = None
    if hasattr(os, "wait4"):
        _, status, usage = os.wait4(process.pid, 0)
        process.returncode = os.waitstatus_to_exitcode(status)
        peak = usage.ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    else:
        process.wait()
    return process.returncode, time.perf_counter() - started, peak, stderr


def _campaigns(samples: Path, scratch: Path) -> dict[str, Path]:
    """The save directory of every campaign: decompressed benchmark samples, or ``samples`` itself without a
    manifest."""
    if not (samples / MANIFEST).exists():
        return {samples.name: samples}
    directories: dict[str, Path] = {}
    for campaign, files in sample_files(samples).items():
        directory = scratch / campaign
        directory.mkdir()
        decompress_samples(files, directory)
        directories[campaign] = directory
    return directories


def _fastest(runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The fastest successful run with every run's seconds, or the first failure when none succeeded."""
    succeeded = [run for run in runs if run["exit"] == 0]
    if not succeeded:
        return dict(runs[0])
    fastest = min(succeeded, key=lambda run: run["seconds"])
    return {**fastest, "runs": [round(run["seconds"], 3) for run in runs]}


def measure(
    *,
    sides: Sequence[Side],
    samples: Path,
    matrix_path: Path,
    run_id: str,
    config: Path,
    repeats: int,
    campaign: str | None = None,
    log: TextIO | None = sys.stderr,
    on_run_complete: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run the ``events`` entry ``run_id`` of the matrix once per side, campaign and repeat, one command at a time.

    Sides alternate and every other repeat reverses their order, so a drift in machine speed falls on both. Each
    side keeps its fastest run. ``campaign`` is passed to ``events`` as ``--campaign``.
    """
    entry = next((entry for entry in load_matrix(matrix_path)["events"] if entry["id"] == run_id), None)
    if entry is None:
        raise ValueError(f"the matrix has no events run {run_id!r}")
    args: list[str] = list(entry.get("args", []))
    if campaign is not None:
        args += ["--campaign", campaign]
    runs: dict[str, dict[str, list[dict[str, Any]]]] = {side.name: {} for side in sides}
    with tempfile.TemporaryDirectory(prefix="runtime-metrics-") as scratch:
        directories = _campaigns(samples, Path(scratch))
        print(
            f"runtime_metrics: {len(directories)} campaigns ({', '.join(directories)}), {len(sides)} sides, "
            f"{repeats} runs each",
            file=log,
            flush=True,
        )
        for name, directory in directories.items():
            for repeat in range(repeats):
                for side in sides if repeat % 2 == 0 else list(reversed(sides)):
                    command = [side.python, "-m", "tinarrative.cli", "events", str(directory), *args]
                    code, seconds, peak, stderr = _timed_run([*command, "--config", str(config)])
                    run: dict[str, Any] = {"exit": code, "seconds": round(seconds, 3), "max_rss": peak}
                    if code == 0:
                        run["timings"] = parse_timings(stderr)
                    else:
                        run["error"] = stderr.strip()[-STDERR_TAIL:]
                    runs[side.name].setdefault(name, []).append(run)
                    line = f"runtime_metrics: {name} · {side.name} · run {repeat + 1}/{repeats} · {seconds:.1f}s"
                    if code != 0:
                        line += f" · exit {code}"
                    if on_run_complete is None:
                        print(line, file=log, flush=True)
                    else:
                        on_run_complete(line)
    return {
        "tool_version": TOOL_VERSION,
        "run": run_id,
        "args": args,
        "repeats": repeats,
        "samples_sha256": sha256_file(samples / MANIFEST) if (samples / MANIFEST).exists() else None,
        "sides": {
            side.name: {
                "label": side.label,
                "campaigns": {name: _fastest(measured) for name, measured in runs[side.name].items()},
            }
            for side in sides
        },
    }


# Reporting


def _seconds(value: float | None) -> str:
    return "–" if value is None else f"{value:.2f}s"


def _megabytes(value: int | None) -> str:
    return "–" if value is None else f"{value / 1_000_000:,.0f} MB"


def _change(base: float | None, head: float | None, noise: float = 0.0) -> tuple[str, bool]:
    """The relative change and whether it is large enough to flag: above both thresholds and above ``noise``."""
    if base is None or head is None or base <= 0:
        return "", False
    share = (head - base) / base * 100
    flagged = abs(share) >= FLAG_SHARE and abs(head - base) >= max(FLAG_SECONDS, noise)
    text = f"{share:+.1f}%"
    return (f"**{text}**" if flagged else text), flagged


def _spread(run: Mapping[str, Any] | None) -> float:
    """How far one side's repeated wall times lie apart: the noise a change has to exceed to be flagged."""
    runs = (run or {}).get("runs") or []
    return max(runs) - min(runs) if runs else 0.0


def _stage_rows(run: Mapping[str, Any] | None) -> dict[str, float | None]:
    """Wall time, every stage and the rest (start-up, rendering, writing) of one run."""
    if run is None or run.get("exit") != 0:
        return {}
    rows: dict[str, float | None] = {"total": run["seconds"]}
    timings = run.get("timings")
    if timings is None:
        return rows
    rows.update(timings["stages"])
    if not _workers(run):
        rows["other"] = max(run["seconds"] - sum(timings["stages"].values()), 0.0)
    return rows


def _workers(run: Mapping[str, Any] | None) -> int:
    """The worker processes of a run: its ``memory`` lines less the coordinator's."""
    return max(int(((run or {}).get("timings") or {}).get("processes") or 0) - 1, 0)


def _peak(run: Mapping[str, Any] | None) -> int | None:
    """Every process's peak summed from the timing lines, else the command's own maximum resident set."""
    summed = ((run or {}).get("timings") or {}).get("peak_memory")
    return cast("int | None", summed if summed is not None else (run or {}).get("max_rss"))


def _growth(run: Mapping[str, Any] | None) -> float | None:
    """Mean seconds of the last third of the intervals over the first third; ``None`` below three intervals."""
    series = ((run or {}).get("timings") or {}).get("intervals") or []
    third = len(series) // 3
    if third == 0:
        return None
    first, last = sum(series[:third]) / third, sum(series[-third:]) / third
    return None if first <= 0 else last / first


def _ok(run: Mapping[str, Any] | None) -> TypeGuard[Mapping[str, Any]]:
    return run is not None and run.get("exit") == 0


def report(runtime: Mapping[str, Any], *, run_url: str | None = None) -> str:
    """The Markdown report of one measurement: ``head`` against ``base`` when both were measured."""
    sides: Mapping[str, Any] = runtime["sides"]
    head = sides.get("head") or next(iter(sides.values()))
    base = sides.get("base") if "head" in sides else None
    labels = f"`{base['label']}` → `{head['label']}`" if base is not None else f"`{head['label']}`"
    campaigns = list(head["campaigns"])
    if base is not None:
        campaigns += [name for name in base["campaigns"] if name not in campaigns]
    repeats = runtime["repeats"]
    runs = "one run per side" if repeats == 1 else f"the fastest of {repeats} runs per side"
    lines = [
        MARKER,
        "## Processing runtime",
        "",
        f"{labels} · `events` run `{runtime['run']}` on {len(campaigns)} campaigns · {runs}, alternating on one "
        f"machine. Informational: timings vary between runs. A change is in bold when it is at least {FLAG_SHARE:g}% "
        f"and {FLAG_SECONDS:g}s, and more than {NOISE_FACTOR:g}× the spread of either side's runs.",
        "",
    ]
    flagged: list[str] = []
    notes: list[str] = []
    sections: list[str] = []
    for name in campaigns:
        after = head["campaigns"].get(name)
        before = base["campaigns"].get(name) if base is not None else None
        for side, run in (("head", after), ("base", before)):
            if run is not None and not _ok(run):
                notes.append(f"{name} · {side} failed with exit {run.get('exit')}: `{run.get('error', '')[-200:]}`")
            elif _ok(run) and run.get("timings") is None:
                notes.append(f"{name} · {side} writes no timing lines; only its wall time and peak memory are shown.")
            elif _workers(run):
                notes.append(
                    f"{name} · {side} ran {_workers(run)} worker processes: its stages are CPU seconds summed over "
                    "them, so `total` is the time to compare and `other` is not shown; peak memory sums every "
                    "process's peak."
                )
        saves = next((run["timings"]["saves"] for run in (after, before) if _ok(run) and run.get("timings")), None)
        title = f"### {name}" + ("" if saves is None else f" · {saves} saves")
        head_rows, base_rows = _stage_rows(after), _stage_rows(before)
        names = [row for row in ("total", *STAGES, "other") if row in head_rows or row in base_rows]
        if base is not None:
            table = ["| Stage | Base | Head | Δ |", "| --- | ---: | ---: | ---: |"]
            noise = NOISE_FACTOR * max(_spread(before), _spread(after))
            for row in names:
                old, new = base_rows.get(row), head_rows.get(row)
                text, flag = _change(old, new, noise)
                table.append(f"| {row} | {_seconds(old)} | {_seconds(new)} | {text} |")
                if flag:
                    flagged.append(f"{name} · {row}: {_seconds(old)} → {_seconds(new)} ({text.strip('*')})")
            peaks = [_peak(run) for run in (before, after)]
            table.append(f"| peak memory | {_megabytes(peaks[0])} | {_megabytes(peaks[1])} | |")
        else:
            table = ["| Stage | Seconds |", "| --- | ---: |"]
            table += [f"| {row} | {_seconds(head_rows.get(row))} |" for row in names]
            table.append(f"| peak memory | {_megabytes(_peak(after))} |")
        extra: list[str] = []
        growth = {side: _growth(run) for side, run in (("base", before), ("head", after))}
        if growth["head"] is not None:
            shown = [f"{side} ×{value:.2f}" for side, value in growth.items() if value is not None]
            extra.append(f"Seconds per interval, last third over first third: {', '.join(shown)}.")
        rules = ((after or {}).get("timings") or {}).get("rules") or {}
        old_rules = ((before or {}).get("timings") or {}).get("rules") or {}
        slowest = sorted(rules.items(), key=lambda item: -item[1])[:TOP_RULES]
        if slowest:
            named = [
                f"`{rule}` {_seconds(seconds)}" + (f" (base {_seconds(old_rules[rule])})" if rule in old_rules else "")
                for rule, seconds in slowest
            ]
            extra.append(f"Slowest narrative rules: {', '.join(named)}.")
        sections += [title, "", *table, ""]
        if extra:
            sections += [*extra, ""]
    if base is not None:
        lines += ["### Highlights", ""]
        if flagged:
            lines += [f"- {item}" for item in flagged]
        else:
            lines.append("No stage changed by more than the thresholds and the noise between runs.")
        lines.append("")
    lines += ["<details><summary>Detailed runtime tables</summary>", "", *sections]
    if notes:
        lines += ["### Notes", "", *(f"- {note}" for note in notes), ""]
    if run_url:
        lines.append(f"Both sides' measurements are in the [`runtime-metrics` artifact]({run_url}).")
    lines += ["", "</details>"]
    return "\n".join(lines).rstrip("\n") + "\n"
