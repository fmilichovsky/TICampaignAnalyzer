from __future__ import annotations

import json
import lzma
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from tests.fixtures import fixture_path
from tinarrative import cli
from tinarrative.benchmarking.manifest import verify_samples


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_explicit_files_are_compressed_and_manifest_is_updated(tmp_path: Path, monkeypatch) -> None:
    samples = tmp_path / "samples"
    samples.mkdir()
    monkeypatch.setattr(cli, "BENCHMARK_SAMPLES_DIR", samples)
    save = fixture_path("io", "terra_invicta_json_v1", "campaign_assets.json")

    code, out, err = run_cli(["benchmark", "sample", "fixture", str(save), "--description", "Synthetic campaign."])

    imported = samples / "fixture" / f"{save.name}.xz"
    assert code == cli.EXIT_SUCCESS
    assert "Imported 1 saves" in out
    assert "matrix.toml" in out
    assert "Compressing saves" not in err
    assert lzma.decompress(imported.read_bytes()) == save.read_bytes()
    manifest = json.loads((samples / "samples.json").read_text(encoding="utf-8"))
    entry = manifest["campaigns"]["fixture"]
    assert entry["description"] == "Synthetic campaign."
    assert entry["files"][imported.name]["raw_bytes"] == save.stat().st_size
    assert verify_samples(samples) == []


def test_directory_import_selects_campaign_and_skips_unusable_files(tmp_path: Path, monkeypatch) -> None:
    samples = tmp_path / "samples"
    samples.mkdir()
    monkeypatch.setattr(cli, "BENCHMARK_SAMPLES_DIR", samples)
    saves = tmp_path / "saves"
    saves.mkdir()
    source = fixture_path("io", "terra_invicta_json_v1", "campaign_assets.json")
    (saves / source.name).write_bytes(source.read_bytes())
    (saves / "unusable.json").write_text("not a save", encoding="utf-8")

    code, out, err = run_cli(["benchmark", "sample", "fixture", str(saves), "--campaign", "latest"])

    assert code == cli.EXIT_SUCCESS
    assert (samples / "fixture" / f"{source.name}.xz").is_file()
    assert "description" in out
    assert "matrix.toml" in out
    assert f"skipped {saves / 'unusable.json'}" in err


def test_invalid_explicit_save_does_not_replace_existing_campaign(tmp_path: Path, monkeypatch) -> None:
    samples = tmp_path / "samples"
    campaign = samples / "fixture"
    campaign.mkdir(parents=True)
    sentinel = campaign / "old.json.xz"
    sentinel.write_bytes(b"existing")
    (samples / "samples.json").write_text(
        json.dumps({"max_file_bytes": 5_000_000, "campaigns": {"fixture": {"description": "old", "files": {}}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "BENCHMARK_SAMPLES_DIR", samples)
    invalid = fixture_path("io", "terra_invicta_json_v1", "malformed_truncated.json")

    code, _, err = run_cli(["benchmark", "sample", "fixture", str(invalid)])

    assert code == cli.EXIT_UNSUPPORTED_INPUT
    assert "malformed" in err
    assert sentinel.read_bytes() == b"existing"
    assert (
        json.loads((samples / "samples.json").read_text(encoding="utf-8"))["campaigns"]["fixture"]["description"]
        == "old"
    )


def test_refresh_replaces_files_and_preserves_or_updates_description(tmp_path: Path, monkeypatch) -> None:
    samples = tmp_path / "samples"
    samples.mkdir()
    monkeypatch.setattr(cli, "BENCHMARK_SAMPLES_DIR", samples)
    first = fixture_path("io", "terra_invicta_json_v1", "campaign_assets.json")
    second = fixture_path("io", "terra_invicta_json_v1", "politics_before.json")

    assert run_cli(["benchmark", "sample", "fixture", str(first), "--description", "Original description."])[0] == 0
    code, _, _ = run_cli(["benchmark", "sample", "fixture", str(second)])
    assert code == 0
    assert not (samples / "fixture" / f"{first.name}.xz").exists()
    manifest = json.loads((samples / "samples.json").read_text(encoding="utf-8"))
    assert manifest["campaigns"]["fixture"]["description"] == "Original description."
    assert run_cli(["benchmark", "sample", "fixture", str(first), "--description", "Updated."])[0] == 0
    manifest = json.loads((samples / "samples.json").read_text(encoding="utf-8"))
    assert manifest["campaigns"]["fixture"]["description"] == "Updated."


def test_progress_tracker_reports_phase_filename_and_count_only_on_tty(monkeypatch) -> None:
    class TerminalBuffer(StringIO):
        def isatty(self) -> bool:
            return True

    terminal = TerminalBuffer()
    monkeypatch.setattr(cli.sys, "stderr", terminal)
    tracker = cli._ProgressTracker("benchmark sample", 3)
    tracker.update("Compressing saves", 2, 3, "save.json")
    assert "Compressing saves 2/3: save.json" in terminal.getvalue()

    plain = StringIO()
    monkeypatch.setattr(cli.sys, "stderr", plain)
    tracker = cli._ProgressTracker("benchmark sample", 3)
    tracker.update("Compressing saves", 2, 3, "save.json")
    assert plain.getvalue() == ""
    tracker.advance("Measuring runs", 1)
    assert plain.getvalue() == ""


def test_metrics_defaults_resolve_from_the_working_directory() -> None:
    args = cli.build_parser().parse_args(["benchmark", "metrics", "measure", "--out", "out"])

    assert args.samples == Path.cwd() / "benchmarks" / "samples"
    assert args.matrix == Path.cwd() / "benchmarks" / "matrix.toml"
    assert args.config == Path.cwd() / "benchmarks" / "config.toml"
