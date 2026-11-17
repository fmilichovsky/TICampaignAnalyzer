"""PROTOTYPE, throwaway: mock text output of `benchmark calibrate report --view period` (#561).

Run from the worktree:  PYTHONPATH=src python3 <this file> [--base TYPE=LEVEL] [--periods 2035] [--cap 5]

Reads today's schema-3 table, replays it with the real replay, and derives the five tiers by hand. Faked:
- explained: schema 3 has no explained flag; a nation.band_crossed / nation.unrest_attempts_changed row nothing
  cites, sharing an entity and interval with a top-level event, counts as explained by it.
- interval dates: the interval key (its closing save date) stands in for the schema-4 interval dates.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from tinarrative.benchmarking.calibration.replay import default_state, load, replay
from dataclasses import replace

TABLE = Path("/Users/f.milichovsky/code/TICampaignAnalyzer/build/calibration")
LEVELS = ["campaign_defining", "major", "minor", "trivial"]
SHORT = {"campaign_defining": "defining", "major": "major", "minor": "minor", "trivial": "trivial"}
TIERS = ["top-level", "member", "cited only", "explained", "below"]
PACKAGE = {"campaign_defining", "major"}
EXPLAINABLE = {"nation.band_crossed", "nation.unrest_attempts_changed"}


def period_of(date: str, period: str) -> str:
    year, month = int(date[:4]), int(date[5:7])
    return {"year": f"{year}", "half": f"{year}-H{(month - 1) // 6 + 1}", "quarter": f"{year}-Q{(month - 1) // 3 + 1}"}[period]


def derive(rows: list[dict]) -> str:
    dates = sorted(r["interval"] for r in rows)
    from datetime import datetime

    days = (datetime.fromisoformat(dates[-1]) - datetime.fromisoformat(dates[0])).days
    return "quarter" if days <= 730 else "half" if days <= 1825 else "year"


def tiers(rows: list[dict], result: dict) -> dict[str, tuple[str, str, str | None]]:
    """id -> (level, tier, the top-level/group id that put it there)."""
    level = {e["id"]: e["level"] for e in result["events"]}
    by_id = {r["id"]: r for r in rows}
    package = {r["id"] for r in rows if r["tier"] == "narrative" and level[r["id"]] in PACKAGE}
    member_of: dict[str, str] = {}
    for m in result["members"]:
        if m["id"] in package and m["verdict"] != "could_become_member":
            for kept in m["kept"]:
                member_of[kept] = m["id"]
    top = package - set(member_of)
    cited_by: dict[str, str] = {}
    for tid in sorted(top | set(member_of)):
        for c in by_id[tid]["cited"]:
            if c not in top and c not in member_of:
                cited_by.setdefault(c, tid)
    touch: dict[tuple[str, str], str] = {}
    for tid in sorted(top):
        for ent in by_id[tid]["entities"]:
            touch.setdefault((ent["id"], by_id[tid]["interval"]), tid)
    out = {}
    for r in rows:
        rid = r["id"]
        if rid in top:
            out[rid] = (level[rid], "top-level", None)
        elif rid in member_of:
            out[rid] = (level[rid], "member", member_of[rid])
        elif rid in cited_by:
            out[rid] = (level[rid], "cited only", cited_by[rid])
        elif r["type"] in EXPLAINABLE and (
            hit := next((touch[(e["id"], r["interval"])] for e in r["entities"] if (e["id"], r["interval"]) in touch), None)
        ):
            out[rid] = (level[rid], "explained", hit)
        else:
            out[rid] = (level[rid], "below", None)
    return out


def cell(now: int, then: int | None) -> str:
    if then is None or now == then:
        return f"{now}"
    return f"{now} {now - then:+d}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", action="append", default=[])
    p.add_argument("--campaign", default="resist-long")
    p.add_argument("--periods", default="")
    p.add_argument("--period", default=None)
    p.add_argument("--cap", type=int, default=5)
    a = p.parse_args()
    index, tables, drafts = load(TABLE)
    code = default_state(index)
    tried = replace(code, type_bases=dict(b.split("=") for b in a.base))
    name = a.campaign
    rows = tables[name]
    by_id = {r["id"]: r for r in rows}
    base_t = tiers(rows, replay(index, tables, replace(code, campaigns=(name,)), drafts)["campaigns"][name])
    is_tried = bool(tried.type_bases)
    cur_t = tiers(rows, replay(index, tables, replace(tried, campaigns=(name,)), drafts)["campaigns"][name]) if is_tried else base_t
    period = a.period or derive(rows)
    pick = set(a.periods.split(",")) if a.periods else None

    def per(t: dict) -> dict:
        grid: dict[str, Counter] = defaultdict(Counter)
        for rid, (lvl, tier, _) in t.items():
            grid[period_of(by_id[rid]["interval"], period)][(lvl, tier)] += 1
        return grid

    now, then = per(cur_t), per(base_t)
    state = " ".join(f"--base {b}" for b in a.base) or "the code's state"
    print(f"period view · {name} · by {period} ({'--period' if a.period else 'span 19.6 years, narrate default'})")
    print(f"state  {state}" + ("   (delta against the code's state)" if is_tried else ""))
    pk_now = sum(1 for v in cur_t.values() if v[1] == "top-level")
    pk_then = sum(1 for v in base_t.values() if v[1] == "top-level")
    print(f"campaign  top-level {cell(pk_now, pk_then if is_tried else None)} · rows {len(rows)}")
    print("explained is FAKED (no flag before schema 4)\n")
    shown = 0
    hidden = []
    for key in sorted(now):
        if pick and key not in pick:
            continue
        g, h = now[key], then[key]
        moved = [rid for rid in cur_t if period_of(by_id[rid]["interval"], period) == key and cur_t[rid][:2] != base_t[rid][:2]]
        if not is_tried or moved or pick:
            pass
        else:
            hidden.append(key)
            continue
        shown += 1
        top_now = sum(g[(l, "top-level")] for l in LEVELS)
        top_then = sum(h[(l, "top-level")] for l in LEVELS)
        print(f"{key}   top-level {cell(top_now, top_then if is_tried else None)}")
        print("  " + f"{'':10}" + "".join(f"{t:>14}" for t in TIERS))
        for l in LEVELS:
            vals = [cell(g[(l, t)], h[(l, t)] if is_tried else None) for t in TIERS]
            if all(v == "0" for v in vals):
                continue
            print("  " + f"{SHORT[l]:10}" + "".join(f"{v:>14}" for v in vals))
        if is_tried and moved:
            moved.sort(key=lambda rid: (base_t[rid][1] != "top-level", cur_t[rid][1] != "top-level", rid))
            print(f"  moved ({min(len(moved), a.cap)} of {len(moved)}" + (f"; {len(moved) - a.cap} cut)" if len(moved) > a.cap else ")"))
            for rid in moved[: a.cap]:
                r = by_id[rid]
                (l0, t0, _), (l1, t1, via) = base_t[rid], cur_t[rid]
                label = r["label"] if len(r["label"]) <= 60 else r["label"][:57] + "..."
                print(f"    {r['type']}  {SHORT[l0]}>{SHORT[l1]}  {t0}>{t1}")
                print(f"      {label}")
                if via:
                    v = by_id[via]
                    vp = period_of(v["interval"], period)
                    mark = "" if vp == key else f" @{v['interval'][:10]}"
                    print(f"      via {v['type']}{mark}")
                outside = [c for c in r["cited"] if period_of(by_id[c]["interval"], period) != key]
                if outside:
                    marks = ", ".join(f"{by_id[c]['type']} @{by_id[c]['interval'][:10]}" for c in outside[:2])
                    more = f", {len(outside) - 2} cut" if len(outside) > 2 else ""
                    print(f"      cites from outside {key}: {marks}{more}")
        print()
    if hidden:
        print(f"unchanged periods: {', '.join(hidden)}")


main()
