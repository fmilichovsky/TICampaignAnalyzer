"""Coverage for scripts/package_metrics.py: the breakdown, the samples manifest, a measurement and the report."""

from __future__ import annotations

import json
import lzma
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts.package_metrics import (
    COMMENT_LIMIT,
    MANIFEST,
    MARKER,
    MAX_KEYS,
    REPOSITORY_ROOT,
    breakdown,
    compare,
    main,
    measure,
    member_changes,
    update_samples,
    verify_samples,
)
from tests.fixtures import fixture_path

SAVES = ["politics_reverted.json", "politics_before.json", "politics_after.json"]


def _samples(root: Path) -> Path:
    """A samples directory of one campaign: the synthetic politics saves, compressed, with its manifest."""
    samples = root / "samples"
    campaign = samples / "politics"
    campaign.mkdir(parents=True)
    for name in SAVES:
        (campaign / f"{name}.xz").write_bytes(
            lzma.compress(fixture_path("io", "terra_invicta_json_v1", name).read_bytes())
        )
    manifest = update_samples(samples)
    manifest["campaigns"]["politics"]["description"] = "Synthetic politics sequence."
    (samples / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    return samples


def _metrics(label: str, *, members: dict[str, int], est_tokens: int = 100, narrate: Any = None) -> dict[str, Any]:
    chars = est_tokens * 3
    events = {"bytes": chars, "chars": chars, "est_tokens": est_tokens, "counts": {"narrative": 2}, "members": members}
    plan = narrate or {
        "prompt_version": "p",
        "chapters": 1,
        "estimate_total": est_tokens + 50,
        "estimate_max": est_tokens + 50,
        "reductions": {},
        "chars": {"system": 150, "block": 10, "package": chars, "total": chars + 160},
        "members": members,
    }
    return {
        "label": label,
        "chars_per_token": 3,
        "matrix_sha256": "m",
        "samples_sha256": "s",
        "matrix": {"events": ["major"], "narrate": ["default"]},
        "campaigns": {"camp": {"events": {"major": events}, "narrate": {"default": plan}}},
    }


def test_the_breakdown_counts_every_member_with_its_key_over_list_elements() -> None:
    wide = {f"id{index}": index for index in range(MAX_KEYS + 1)}

    sizes = breakdown({"a": [{"x": 1, "y": "zz"}, {"x": 22}], "b": {"c": True}, "w": {"m": wide}})

    assert sizes["a"] == len('"a":[{"x":1,"y":"zz"},{"x":22}]')
    assert sizes["a[].x"] == len('"x":1') + len('"x":22')
    assert sizes["a[].y"] == len('"y":"zz"')
    assert sizes["b.c"] == len('"c":true')
    assert "w.m" in sizes
    assert not any(path.startswith("w.m.") for path in sizes)


def test_a_change_is_named_by_the_member_that_explains_it() -> None:
    before = {"saves": 1000, "saves[].situation": 900, "saves[].situation.seat": 100, "glossary": 50}
    after = {"saves": 905, "saves[].situation": 805, "saves[].situation.seat": 5, "glossary": 60}

    assert member_changes(before, after) == [("saves[].situation.seat", -95), ("glossary", 10)]


def test_an_unchanged_measurement_reports_no_change() -> None:
    metrics = _metrics("base", members={"saves": 200, "narrative": 100})

    report = compare(metrics, metrics)

    assert report.startswith(MARKER)
    assert "No change in package sizes above 1%." in report
    assert "### Package members" in report


def test_a_change_is_highlighted_with_its_member() -> None:
    base = _metrics("base", members={"saves": 200, "saves[].seat": 60, "narrative": 100})
    head = _metrics("head", members={"saves": 140, "narrative": 100}, est_tokens=80)

    report = compare(base, head, threshold=1.0, run_url="https://example.invalid/run")

    assert "| camp · events `major` | 100 → 80 | ▼ -20 (-20.0%) | `saves[].seat` -60 |" in report
    assert "### Member changes" in report
    assert "| `saves[].seat` | 60 | – | ▼ -60 (-100.0%) | 0.0% |" in report
    assert report.rstrip().endswith("(https://example.invalid/run).")


def test_failures_and_new_failures_are_noted() -> None:
    base = _metrics("base", members={"saves": 200})
    head = _metrics(
        "head",
        members={"saves": 200},
        narrate={"exit": 2, "error": "needs about 1234 input tokens", "needs_tokens": 1234},
    )

    report = compare(base, head)

    assert "camp · narrate `default` now fails: over budget: needs ~1,234 tokens." in report
    assert "| camp | `default` | 1 → over budget: needs ~1,234 tokens |" in report


def test_the_report_fits_in_a_comment() -> None:
    members = {f"member{index}.{'x' * 200}": index + 1 for index in range(2_000)}
    base = _metrics("base", members=members)
    head = _metrics("head", members={name: size * 2 for name, size in members.items()})

    report = compare(base, head)

    assert len(report) <= COMMENT_LIMIT
    assert "did not fit in a comment" in report


def test_the_samples_manifest_catches_changed_and_unlisted_files(tmp_path: Path) -> None:
    samples = _samples(tmp_path)
    assert verify_samples(samples) == []

    first = samples / "politics" / f"{SAVES[0]}.xz"
    first.write_bytes(first.read_bytes() + b"\0")
    (samples / "politics" / "extra.json.xz").write_bytes(lzma.compress(b"{}"))

    assert verify_samples(samples) == [
        "politics/extra.json.xz: not listed in samples.json",
        f"politics/{SAVES[0]}.xz: does not match its size and SHA-256 in samples.json",
    ]


def test_the_committed_samples_match_their_manifest() -> None:
    assert verify_samples(REPOSITORY_ROOT / "benchmarks" / "samples") == []


@pytest.mark.fixture
def test_a_measurement_runs_the_matrix_against_every_campaign(tmp_path: Path) -> None:
    samples = _samples(tmp_path)
    matrix = tmp_path / "matrix.toml"
    matrix.write_text(
        '[[events]]\nid = "major"\nargs = ["--narrative", "--include-constituents", "--format", "json"]\n'
        '[[narrate]]\nid = "default"\npackage = "major"\nargs = []\n'
        '[[narrate]]\nid = "tiny"\npackage = "major"\nargs = ["--max-input-tokens", "1000"]\n',
        encoding="utf-8",
    )
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    out = tmp_path / "out"

    metrics = measure(
        python=sys.executable,
        samples=samples,
        matrix_path=matrix,
        config=config,
        out=out,
        label="test",
        chars_per_token=3,
        log=None,
    )

    events = metrics["campaigns"]["politics"]["events"]["major"]
    package = json.loads((out / "packages" / "politics" / "major.json").read_text(encoding="utf-8"))
    assert events["counts"]["narrative"] == len(package["narrative"]) > 0
    assert events["chars"] == len(json.dumps(package, ensure_ascii=False, separators=(",", ":")))
    assert {"saves", "intervals", "narrative", "glossary"} <= set(events["members"])
    plan = metrics["campaigns"]["politics"]["narrate"]["default"]
    assert plan["chapters"] >= 1
    assert plan["chars"]["package"] > 0
    assert (out / "narrate" / "politics" / "default" / "plan.json").is_file()
    tiny = metrics["campaigns"]["politics"]["narrate"]["tiny"]
    assert tiny["exit"] == 2


def test_a_malformed_matrix_is_a_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    samples = _samples(tmp_path)
    matrix = tmp_path / "matrix.toml"
    matrix.write_text('[[events]]\nid = "a"\n[[narrate]]\nid = "b"\npackage = "missing"\n', encoding="utf-8")

    code = main(["measure", "--samples", str(samples), "--matrix", str(matrix), "--out", str(tmp_path / "out")])

    assert code == 2
    assert "narrate.b: package must name an events run" in capsys.readouterr().err
