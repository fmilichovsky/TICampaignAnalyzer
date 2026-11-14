"""PROTOTYPE, throwaway (wayfinder ticket #452). Writes data.js for index.html from the benchmark campaigns.

Runs the real pipeline in-process at default settings (`events --narrative --format json`, with the narrator
slimming switched off so `significance_basis` survives) and turns every event into one row. Adds two draft stakes on
nation.space_program_growth (#361: held share and moved share of boost and mission control).

    PYTHONPATH=src .venv/bin/python scripts/prototype_calibrate/extract.py
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from tinarrative.benchmarking.manifest import decompress_samples, sample_files  # noqa: E402
from tinarrative.kinds import kind_for  # noqa: E402

CAMPAIGNS = ("protectorate", "protectorate-short", "resist")


def report(directory: Path) -> dict:
    """The pipeline's own events (not the rendered listing, which digests members) and situation reports."""
    import tinarrative.cli as cli
    from tinarrative.sequence import situations

    captured: dict = {}

    def capture(plan, intervals, *, narrative, **_):  # type: ignore[no-untyped-def]
        captured["intervals"], captured["narrative"] = intervals, narrative
        return {}

    cli.build_document = capture
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        cli.main(["events", str(directory), "--narrative", "--format", "json"])
    intervals = captured["intervals"]
    return {
        "saves": [{"key": str(report.date), "situation": report.to_dict()} for report in situations(intervals)],
        "narrative": [event.to_dict() for event in captured["narrative"]],
        "intervals": [
            {
                "events": [event.to_dict() for event in interval.objective],
                "inferred": [event.to_dict() for event in interval.inferred or ()],
            }
            for interval in intervals
        ],
    }


def name_of(event: dict) -> str:
    names = [ref.get("name") or ref["ref"] for ref in event.get("entities", [])[:3]]
    return ", ".join(names)


def main() -> None:
    manifest = json.loads((ROOT / "benchmarks" / "samples" / "samples.json").read_text())["campaigns"]
    files = {
        campaign: [path for path in paths if path.name in manifest.get(campaign, {}).get("files", {})]
        for campaign, paths in sample_files(ROOT / "benchmarks" / "samples").items()
    }
    rows: list[dict] = []
    index: dict[tuple[int, str], int] = {}
    waves: list[tuple[int, dict]] = []
    growth: list[tuple[int, dict, dict]] = []
    for c, campaign in enumerate(CAMPAIGNS):
        with tempfile.TemporaryDirectory() as tmp:
            decompress_samples(files[campaign], Path(tmp))
            document = report(Path(tmp))
        saves = {save["key"]: save["situation"] for save in document["saves"]}
        events = [(e, "n") for e in document["narrative"]]
        for interval in document["intervals"]:
            events += [(e, "o") for e in interval["events"]]
            events += [(e, "i") for e in interval["inferred"] or ()]
        for event, status in events:
            index[(c, event["id"])] = len(rows)
            kind = kind_for(event["event_type"])
            basis = event.get("significance_basis")
            row = {
                "c": c,
                "t": event["event_type"],
                "s": status,
                "n": name_of(event),
                "d": (event.get("date") or event.get("end") or event.get("not_before") or "")[:10],
                "p": event["score"],
                "kb": kind.base.base,
            }
            if basis:
                row.update(b=basis["base"], m=basis["measure"], sh=basis["share"])
                if basis["base"] != kind.base.base:
                    row["ruled"] = 1
            rows.append(row)
            row["_cites"] = event.get("constituents", []) if status == "n" else []
            if event["event_type"] == "faction.takeover":
                row["tg"] = [r["entity"]["ref"] for r in event.get("roles", []) if r["role"] == "target"]
            if event["event_type"] == "faction.takeover_wave":
                waves.append((len(rows) - 1, event))
            if event["event_type"] == "nation.space_program_growth":
                growth.append((len(rows) - 1, event, saves))
    for row in rows:
        c = row["c"]
        cites = [index[(c, ref)] for ref in row.pop("_cites") if (c, ref) in index]
        if cites:
            row["ci"] = cites
    for position, _ in waves:
        rows[position]["wave"] = 1
        for member in rows[position].get("ci", []):
            if rows[member]["t"] == "faction.takeover":
                rows[member]["mo"] = position
    drafts = []
    for draft_id, label, moved in (("held", "held share", False), ("moved", "moved share", True)):
        for position, event, saves in growth:
            real = rows[position]
            situation = saves.get(event["intervals"][-1]) or next(iter(saves.values()))
            candidates = {}
            for measure, field in (("boost", "boost"), ("mission_control", "mission_control")):
                total = sum(nation.get(field) or 0 for nation in situation["nations"])
                before = event["attributes"].get(f"{field}_before") or 0
                after = event["attributes"].get(f"{field}_after") or 0
                value = abs(after - before) if moved else after
                if total > 0 and value > 0 and after != before:
                    candidates[measure] = value / total
            if not candidates:
                continue
            draft = {
                "draft": draft_id,
                "c": real["c"],
                "t": real["t"],
                "s": "n",
                "n": real["n"],
                "d": real["d"],
                "kb": real["kb"],
                "cand": candidates,
            }
            if real.get("ci"):
                draft["ci"] = real["ci"]
            drafts.append(draft)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    payload = {
        "commit": commit.stdout.strip(),
        "campaigns": list(CAMPAIGNS),
        "rows": rows,
        "drafts": drafts,
        "draftInfo": {
            "held": {"issue": 361, "label": "space program growth: held share"},
            "moved": {"issue": 361, "label": "space program growth: moved share"},
        },
    }
    here = Path(__file__).parent
    (here / "data.js").write_text("window.CALIB = " + json.dumps(payload, separators=(",", ":")) + ";\n")
    (here / "status.js").write_text(
        "window.CALIB_STATUS = " + json.dumps({"stale": False, "built_from": payload["commit"]}) + ";\n"
    )
    print(f"{len(rows)} rows, {sum('m' in r for r in rows)} scaled, {len(drafts)} draft rows")


if __name__ == "__main__":
    main()
