"""Coverage for package breakdown, the samples manifest, measurement and comparison reports."""

from __future__ import annotations

import io
import json
import lzma
import math
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.benchmark_support import SAVES, synthetic_samples
from tinarrative import cli
from tinarrative.benchmarking import metrics as benchmark_metrics
from tinarrative.benchmarking.manifest import decompress_samples, update_samples, verify_samples
from tinarrative.benchmarking.metrics import (
    COMMENT_LIMIT,
    MANIFEST,
    MARKER,
    MAX_KEYS,
    breakdown,
    compare,
    measure,
    measure_package,
    member_changes,
)
from tinarrative.benchmarking.profile import PROFILE_FIELDS

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_package_estimate_accepts_fractional_chars_per_token() -> None:
    text = '{"saves":[],"narrative":[]}'
    result = measure_package(text, 2.4)

    assert result["est_tokens"] == math.ceil(result["chars"] / 2.4)


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
    assert report.rstrip().endswith("</details>")
    assert "(https://example.invalid/run)." in report


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
    samples = synthetic_samples(tmp_path)
    assert verify_samples(samples) == []

    first = samples / "politics" / f"{SAVES[0]}.xz"
    first.write_bytes(first.read_bytes() + b"\0")
    (samples / "politics" / "extra.json.xz").write_bytes(lzma.compress(b"{}"))

    assert verify_samples(samples) == [
        "politics/extra.json.xz: not listed in samples.json",
        f"politics/{SAVES[0]}.xz: does not match its size and SHA-256 in samples.json",
    ]


def test_the_samples_manifest_requires_a_profile_of_every_listed_save(tmp_path: Path) -> None:
    samples = synthetic_samples(tmp_path)
    manifest = json.loads((samples / MANIFEST).read_text(encoding="utf-8"))
    entry = manifest["campaigns"]["politics"]
    assert tuple(entry["profile"]) == PROFILE_FIELDS

    entry["profile"]["saves"] += 1
    (samples / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    assert verify_samples(samples) == [
        f"politics: profile counts {len(SAVES) + 1} saves, {len(SAVES)} listed; run benchmark metrics samples --update"
    ]

    del entry["profile"]
    (samples / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    assert verify_samples(samples) == ["politics: no profile; run benchmark metrics samples --update"]


def test_decompressing_many_files_concurrently_yields_the_original_bytes(tmp_path: Path) -> None:
    contents = {f"save-{index}.json": f'{{"n": {index}}}'.encode() * (index + 1) * 1000 for index in range(6)}
    files = []
    for name, data in contents.items():
        file = tmp_path / f"{name}.xz"
        file.write_bytes(lzma.compress(data))
        files.append(file)
    target = tmp_path / "out"
    target.mkdir()

    decompress_samples(files, target)

    assert {path.name: path.read_bytes() for path in target.iterdir()} == contents


def test_a_corrupt_file_fails_the_whole_decompression(tmp_path: Path) -> None:
    good = tmp_path / "good.json.xz"
    good.write_bytes(lzma.compress(b"{}"))
    bad = tmp_path / "bad.json.xz"
    bad.write_bytes(b"not xz")
    target = tmp_path / "out"
    target.mkdir()

    with pytest.raises(lzma.LZMAError):
        decompress_samples([good, bad], target)


def test_the_committed_samples_match_their_manifest() -> None:
    assert verify_samples(REPOSITORY_ROOT / "benchmarks" / "samples") == []


def test_metrics_cli_samples_update_and_compare_write_their_outputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    samples = synthetic_samples(tmp_path)
    extra = samples / "politics" / "extra.json.xz"
    extra.write_bytes(lzma.compress(b"{}"))

    code = cli.main(["benchmark", "metrics", "samples", "--samples", str(samples)])
    assert code == cli.EXIT_USAGE_ERROR
    assert "not listed" in capsys.readouterr().err

    assert cli.main(["benchmark", "metrics", "samples", "--samples", str(samples), "--update"]) == cli.EXIT_SUCCESS
    assert verify_samples(samples) == []

    base, head, report = tmp_path / "base.json", tmp_path / "head.json", tmp_path / "report.md"
    base.write_text(json.dumps(_metrics("base", members={"saves": 100})), encoding="utf-8")
    head.write_text(json.dumps(_metrics("head", members={"saves": 100})), encoding="utf-8")
    assert cli.main(["benchmark", "metrics", "compare", str(base), str(head), "--out", str(report)]) == cli.EXIT_SUCCESS
    assert report.read_text(encoding="utf-8").startswith(MARKER)


def test_metrics_cli_measure_writes_the_metrics_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    samples = synthetic_samples(tmp_path)
    matrix = tmp_path / "matrix.toml"
    matrix.write_text('[[events]]\nid = "bare"\nargs = []\n', encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr(
        benchmark_metrics,
        "measure",
        lambda **kwargs: {"label": kwargs["label"], "chars_per_token": kwargs["chars_per_token"]},
    )

    code = cli.main(
        [
            "benchmark",
            "metrics",
            "measure",
            "--samples",
            str(samples),
            "--matrix",
            str(matrix),
            "--config",
            str(config),
            "--out",
            str(out),
            "--label",
            "test label",
            "--chars-per-token",
            "4.5",
            "--jobs",
            "2",
        ]
    )

    assert code == cli.EXIT_SUCCESS
    assert json.loads((out / "metrics.json").read_text(encoding="utf-8")) == {
        "label": "test label",
        "chars_per_token": 4.5,
    }


def test_a_measurement_runs_the_matrix_against_every_campaign(tmp_path: Path) -> None:
    samples = synthetic_samples(tmp_path)
    matrix = tmp_path / "matrix.toml"
    matrix.write_text(
        '[[events]]\nid = "major"\nargs = ["--narrative", "--constituents", "evidence", "--format", "json"]\n'
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


def _stub_python(tmp_path: Path, usage: str) -> tuple[Path, Path]:
    """A fake interpreter whose ``--help`` prints ``usage`` and whose every other run is logged and fails."""
    calls = tmp_path / "calls.txt"
    python = tmp_path / "python"
    python.write_text(
        f'#!/bin/sh\ncase "$*" in *--help*) echo "usage: ... {usage} ..."; exit 0;; esac\n'
        f'echo "$*" >> "{calls}"\necho "stub failure" >&2\nexit 1\n',
        encoding="utf-8",
    )
    python.chmod(python.stat().st_mode | stat.S_IEXEC)
    return python, calls


@pytest.mark.skipif(sys.platform == "win32", reason="the fake interpreter is a POSIX shell script")
@pytest.mark.parametrize(("usage", "serial"), [("[--jobs N]", True), ("[--campaign SELECTOR]", False)])
def test_events_runs_get_one_job_only_where_the_revision_takes_it(tmp_path: Path, usage: str, serial: bool) -> None:
    samples = synthetic_samples(tmp_path)
    matrix = tmp_path / "matrix.toml"
    matrix.write_text('[[events]]\nid = "bare"\nargs = []\n', encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    python, calls = _stub_python(tmp_path, usage)

    measure(
        python=str(python),
        samples=samples,
        matrix_path=matrix,
        config=config,
        out=tmp_path / "out",
        label="test",
        chars_per_token=3,
        log=None,
    )

    (run,) = calls.read_text(encoding="utf-8").splitlines()
    assert " events " in f" {run} "
    assert ("--jobs 1" in run) is serial


GROUPABLE = (
    '[[events]]\nid = "major"\nargs = ["--narrative", "--constituents", "evidence", "--format", "json", '
    '"--min-significance", "major"]\n'
    '[[events]]\nid = "bare"\nargs = ["--narrative", "--format", "json"]\n'
    '[[events]]\nid = "minor-all"\nargs = ["--narrative", "--format", "json", "--min-significance=minor", '
    '"--constituents=all"]\n'
    '[[narrate]]\nid = "default"\npackage = "major"\nargs = []\n'
)


@pytest.mark.skipif(sys.platform == "win32", reason="the fake interpreter is a POSIX shell script")
def test_a_revision_without_events_output_is_measured_per_entry_with_one_job(tmp_path: Path) -> None:
    samples = synthetic_samples(tmp_path)
    matrix = tmp_path / "matrix.toml"
    matrix.write_text(GROUPABLE, encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    python, calls = _stub_python(tmp_path, "[--jobs N] [--campaign SELECTOR]")

    measure(
        python=str(python),
        samples=samples,
        matrix_path=matrix,
        config=config,
        out=tmp_path / "out",
        label="test",
        chars_per_token=3,
        jobs=8,
        log=None,
    )

    runs = calls.read_text(encoding="utf-8").splitlines()
    assert len(runs) == 3
    assert all("--jobs 1" in run and "--output" not in run for run in runs)


@pytest.mark.skipif(sys.platform == "win32", reason="the fake interpreter is a POSIX shell script")
def test_entries_sharing_their_analysis_run_as_one_process_and_fail_together(tmp_path: Path) -> None:
    samples = _two_campaign_samples(tmp_path)
    matrix = tmp_path / "matrix.toml"
    matrix.write_text(GROUPABLE, encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    python, calls = _stub_python(tmp_path, "[--jobs N] [--output MIN_SIGNIFICANCE:CONSTITUENTS:PATH]")
    log = io.StringIO()

    metrics = measure(
        python=str(python),
        samples=samples,
        matrix_path=matrix,
        config=config,
        out=tmp_path / "out",
        label="test",
        chars_per_token=3,
        jobs=8,
        log=log,
    )

    runs = calls.read_text(encoding="utf-8").splitlines()
    assert len(runs) == 2
    for run in runs:
        assert f"--jobs {benchmark_metrics.events_jobs(8, 2)}" in run
        assert "--min-significance" not in run and "--constituents" not in run
        outputs = [part for part in run.split() if part.count(":") >= 2]
        assert [output.split(":", 2)[:2] for output in outputs] == [
            ["major", "evidence"],
            ["trivial", "none"],
            ["minor", "all"],
        ]
    for results in metrics["campaigns"].values():
        assert {run_id: result["exit"] for run_id, result in results["events"].items()} == {
            "major": 1,
            "bare": 1,
            "minor-all": 1,
        }
        assert results["narrate"]["default"] == {"exit": None, "error": "events major failed"}
    assert log.getvalue().count("major, bare, minor-all") == 2


@pytest.mark.parametrize(("jobs", "processes", "workers"), [(4, 1, 4), (8, 3, 2), (4, 4, 1), (2, 6, 1), (1, 1, 1)])
def test_a_grouped_events_process_gets_its_share_of_the_jobs(jobs: int, processes: int, workers: int) -> None:
    assert benchmark_metrics.events_jobs(jobs, processes) == workers


def test_entries_are_grouped_by_their_args_without_the_cut_and_the_constituents() -> None:
    entries = [
        {"id": "a", "args": ["--narrative", "--min-significance", "major", "--constituents", "evidence"]},
        {"id": "b", "args": ["--narrative"]},
        {"id": "c", "args": ["--format", "json"]},
        {"id": "d", "args": ["--constituents=all", "--narrative"]},
    ]

    groups = benchmark_metrics.group_events(entries)

    assert [(group.args, group.outputs) for group in groups] == [
        (("--narrative",), (("a", "major", "evidence"), ("b", "trivial", "none"), ("d", "trivial", "all"))),
        (("--format", "json"), (("c", "trivial", "none"),)),
    ]


def test_grouped_packages_are_byte_identical_to_per_entry_ones(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    samples = synthetic_samples(tmp_path)
    matrix = tmp_path / "matrix.toml"
    matrix.write_text(GROUPABLE, encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")

    def run(out: Path) -> dict[str, Any]:
        return measure(
            python=sys.executable,
            samples=samples,
            matrix_path=matrix,
            config=config,
            out=out,
            label="test",
            chars_per_token=3,
            log=None,
        )

    grouped = run(tmp_path / "grouped")
    # A stub interpreter cannot write real packages, so the fallback is forced through the help it reads.
    monkeypatch.setattr(benchmark_metrics, "_events_help", lambda cli: "usage: ... [--jobs N] ...")
    per_entry = run(tmp_path / "per-entry")

    assert grouped == per_entry
    for run_id in ("major", "bare", "minor-all"):
        written = (tmp_path / "grouped" / "packages" / "politics" / f"{run_id}.json").read_bytes()
        assert written == (tmp_path / "per-entry" / "packages" / "politics" / f"{run_id}.json").read_bytes()
    assert grouped["campaigns"]["politics"]["narrate"]["default"]["chapters"] >= 1


def test_concurrent_campaigns_keep_the_matrix_order_and_log_in_one_piece_each(tmp_path: Path) -> None:
    samples = synthetic_samples(tmp_path)
    shutil.copytree(samples / "politics", samples / "politics-copy")
    (samples / MANIFEST).write_text(json.dumps(update_samples(samples)), encoding="utf-8")
    matrix = tmp_path / "matrix.toml"
    matrix.write_text(
        '[[events]]\nid = "bare"\nargs = ["--narrative", "--format", "json"]\n'
        '[[events]]\nid = "major"\nargs = ["--narrative", "--constituents", "evidence", "--format", "json"]\n'
        '[[events]]\nid = "broken"\nargs = ["--no-such-option"]\n'
        '[[narrate]]\nid = "default"\npackage = "major"\nargs = []\n'
        '[[narrate]]\nid = "orphan"\npackage = "broken"\nargs = []\n',
        encoding="utf-8",
    )
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    log = io.StringIO()
    progress: list[int] = []

    metrics = measure(
        python=sys.executable,
        samples=samples,
        matrix_path=matrix,
        config=config,
        out=tmp_path / "out",
        label="test",
        chars_per_token=3,
        jobs=4,
        log=log,
        on_progress=progress.append,
    )

    assert list(metrics["campaigns"]) == ["politics", "politics-copy"]
    original, copy = metrics["campaigns"]["politics"], metrics["campaigns"]["politics-copy"]
    assert original == copy
    assert list(original["events"]) == ["bare", "major", "broken"]
    assert list(original["narrate"]) == ["default", "orphan"]
    assert original["narrate"]["orphan"] == {"exit": None, "error": "events broken failed"}
    lines = log.getvalue().splitlines()
    headers = [index for index, line in enumerate(lines) if line.startswith("package_metrics: politics")]
    assert len(headers) == 2
    assert sum(progress) == 10
    for start in headers:
        block = lines[start + 1 : start + 7]
        names = [line.split("─ ", 1)[1].split("  ")[0] for line in block]
        assert names == ["events", "bare, major", "broken", "narrate", "default", "orphan"]
        assert "failed (exit 2)" in block[2]
        assert block[5].endswith("skipped: events broken failed")


def test_a_malformed_matrix_is_a_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    samples = synthetic_samples(tmp_path)
    matrix = tmp_path / "matrix.toml"
    matrix.write_text('[[events]]\nid = "a"\n[[narrate]]\nid = "b"\npackage = "missing"\n', encoding="utf-8")

    from tinarrative.cli import main

    code = main(
        [
            "benchmark",
            "metrics",
            "measure",
            "--samples",
            str(samples),
            "--matrix",
            str(matrix),
            "--out",
            str(tmp_path / "out"),
        ]
    )

    assert code == 2
    assert "narrate.b: package must name an events run" in capsys.readouterr().err


def _write_matrix(tmp_path: Path) -> tuple[Path, Path]:
    matrix = tmp_path / "matrix.toml"
    matrix.write_text('[[events]]\nid = "bare"\nargs = ["--narrative", "--format", "json"]\n', encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    return matrix, config


def _two_campaign_samples(tmp_path: Path) -> Path:
    samples = synthetic_samples(tmp_path)
    shutil.copytree(samples / "politics", samples / "second")
    manifest = update_samples(samples)
    for name in manifest["campaigns"]:
        manifest["campaigns"][name]["description"] = name
    (samples / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    return samples


def test_a_measurement_can_be_limited_to_named_campaigns(tmp_path: Path) -> None:
    samples = _two_campaign_samples(tmp_path)
    matrix, config = _write_matrix(tmp_path)

    metrics = measure(
        python=sys.executable,
        samples=samples,
        matrix_path=matrix,
        config=config,
        out=tmp_path / "out",
        label="test",
        chars_per_token=3,
        log=None,
        campaigns=["second"],
    )

    assert list(metrics["campaigns"]) == ["second"]
    assert not (tmp_path / "out" / "packages" / "politics").exists()


def test_an_unknown_campaign_is_refused_before_measuring(tmp_path: Path) -> None:
    samples = _two_campaign_samples(tmp_path)
    matrix, config = _write_matrix(tmp_path)

    with pytest.raises(ValueError, match="unknown campaign 'nope'"):
        measure(
            python=sys.executable,
            samples=samples,
            matrix_path=matrix,
            config=config,
            out=tmp_path / "out",
            label="test",
            chars_per_token=3,
            log=None,
            campaigns=["nope"],
        )


def test_metrics_cli_measure_rejects_an_unknown_campaign(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    samples = _two_campaign_samples(tmp_path)
    matrix, config = _write_matrix(tmp_path)

    code = cli.main(
        ["benchmark", "metrics", "measure", "--samples", str(samples), "--matrix", str(matrix), "--config", str(config)]
        + ["--out", str(tmp_path / "out"), "--campaign", "nope"]
    )

    assert code == cli.EXIT_USAGE_ERROR
    assert "unknown campaign 'nope'" in capsys.readouterr().err


def _per_campaign(name: str, *, est_tokens: int = 100) -> dict[str, Any]:
    metrics = _metrics("L", members={"saves": est_tokens}, est_tokens=est_tokens)
    metrics["campaigns"] = {name: metrics["campaigns"]["camp"]}
    return metrics


def test_merged_per_campaign_metrics_equal_one_measurement_of_all_campaigns() -> None:
    first, second = _per_campaign("alpha"), _per_campaign("beta", est_tokens=200)
    everything = _metrics("L", members={"saves": 1})
    everything["campaigns"] = {**first["campaigns"], **second["campaigns"]}

    assert benchmark_metrics.merge([second, first]) == everything
    assert list(benchmark_metrics.merge([second, first])["campaigns"]) == ["alpha", "beta"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("label", "other"),
        ("tool_version", 2),
        ("chars_per_token", 4),
        ("matrix_sha256", "x"),
        ("samples_sha256", "x"),
        ("matrix", {"events": ["other"], "narrate": []}),
    ],
)
def test_merge_refuses_inputs_whose_metadata_differs(field: str, value: Any) -> None:
    first, second = _per_campaign("alpha"), _per_campaign("beta")
    second[field] = value

    with pytest.raises(ValueError, match=f"differ in {field}"):
        benchmark_metrics.merge([first, second])


def test_merge_refuses_a_campaign_in_more_than_one_input() -> None:
    with pytest.raises(ValueError, match="campaign 'alpha' appears in more than one input"):
        benchmark_metrics.merge([_per_campaign("alpha"), _per_campaign("alpha")])


def test_metrics_cli_merge_writes_one_file_and_names_its_failures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = []
    for name in ("alpha", "beta"):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(_per_campaign(name)), encoding="utf-8")
        paths.append(str(path))
    out = tmp_path / "merged" / "metrics.json"

    assert cli.main(["benchmark", "metrics", "merge", *paths, "--out", str(out)]) == cli.EXIT_SUCCESS
    assert list(json.loads(out.read_text(encoding="utf-8"))["campaigns"]) == ["alpha", "beta"]

    assert cli.main(["benchmark", "metrics", "merge", paths[0], paths[0], "--out", str(out)]) == cli.EXIT_USAGE_ERROR
    assert "appears in more than one input" in capsys.readouterr().err

    missing = str(tmp_path / "missing.json")
    assert cli.main(["benchmark", "metrics", "merge", paths[0], missing, "--out", str(out)]) == cli.EXIT_INPUT_ERROR


def test_merging_separate_campaign_measurements_equals_measuring_all_at_once(tmp_path: Path) -> None:
    samples = _two_campaign_samples(tmp_path)
    matrix, config = _write_matrix(tmp_path)

    def run(name: str, campaigns: list[str] | None) -> dict[str, Any]:
        return measure(
            python=sys.executable,
            samples=samples,
            matrix_path=matrix,
            config=config,
            out=tmp_path / name,
            label="test",
            chars_per_token=3,
            log=None,
            campaigns=campaigns,
        )

    merged = benchmark_metrics.merge([run("second", ["second"]), run("politics", ["politics"])])

    assert json.dumps(merged) == json.dumps(run("all", None))
