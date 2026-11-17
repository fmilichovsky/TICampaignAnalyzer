"""`benchmark calibrate report`: argument wiring, the cache it refreshes, its exit codes and output formats."""

from __future__ import annotations

import json
import shutil
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from tests.benchmark_support import synthetic_samples
from tinarrative import cli
from tinarrative.benchmarking.calibration import drafts, table
from tinarrative.benchmarking.calibration.drafts import DraftStake
from tinarrative.benchmarking.calibration.replay import load
from tinarrative.benchmarking.manifest import MANIFEST

COMMAND = ["benchmark", "calibrate", "report"]


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Synthetic samples and the cache the command builds from them, once per module."""
    root = tmp_path_factory.mktemp("calibrate")
    samples = synthetic_samples(root)
    out = root / "out"
    code, _, err = run_cli([*COMMAND, "--samples", str(samples), "--out", str(out)])
    assert code == cli.EXIT_SUCCESS, err
    return samples, out


@pytest.fixture
def paths(built: tuple[Path, Path], tmp_path: Path) -> tuple[Path, Path]:
    samples, out = built
    shutil.copytree(samples, tmp_path / "samples")
    shutil.copytree(out, tmp_path / "out")
    return tmp_path / "samples", tmp_path / "out"


def report(paths: tuple[Path, Path], *flags: str) -> tuple[int, str, str]:
    samples, out = paths
    return run_cli([*COMMAND, "--samples", str(samples), "--out", str(out), *flags])


def report_json(paths: tuple[Path, Path], *flags: str) -> dict[str, Any]:
    code, stdout, stderr = report(paths, *flags, "--format", "json")
    assert code == cli.EXIT_SUCCESS, stderr
    document: dict[str, Any] = json.loads(stdout)
    return document


def test_the_first_run_builds_the_cache_and_prints_the_text_readout(paths: tuple[Path, Path]) -> None:
    _, out = paths
    shutil.rmtree(out)

    code, stdout, stderr = report(paths)

    assert code == cli.EXIT_SUCCESS
    assert "Extracting the calibration table" in stderr
    assert stdout.startswith("# Stake calibration readout")
    assert "## Snippet" in stdout
    assert table.read_status(out / "status.js")["state"] == "fresh"


def test_a_fresh_cache_is_reused_and_rebuild_forces_an_extraction(
    paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []
    real = table.extract_all

    def counting(samples: Path, directory: Path, **kwargs: Any) -> list[str]:
        calls.append(directory)
        return real(samples, directory, **kwargs)

    monkeypatch.setattr(table, "extract_all", counting)

    code, _, stderr = report(paths)
    assert (code, calls, stderr) == (cli.EXIT_SUCCESS, [], "")

    code, _, stderr = report(paths, "--rebuild")
    assert code == cli.EXIT_SUCCESS
    assert len(calls) == 1
    assert "Rebuilding the calibration table" in stderr


def test_a_table_at_an_older_schema_is_refused_with_the_rebuild_hint(paths: tuple[Path, Path]) -> None:
    _, out = paths
    index = table.read_index(out / "index.js")
    table.write_index(out, {**index, "schema_version": table.SCHEMA_VERSION - 1})

    code, stdout, stderr = report(paths)

    assert (code, stdout) == (cli.EXIT_USAGE_ERROR, "")
    assert f"schema {table.SCHEMA_VERSION - 1}" in stderr
    assert "--rebuild" in stderr


def test_references_accumulate_over_commas_and_repeats(paths: tuple[Path, Path]) -> None:
    document = report_json(paths, "--reference", "power=0.002,hab=0.03", "--reference", "battle=0.001")

    assert {key: document["state"]["references"][key] for key in ("power", "hab", "battle")} == {
        "power": 0.002,
        "hab": 0.03,
        "battle": 0.001,
    }
    assert document["hash"] == "ref=power:0.002,hab:0.03,battle:0.001"


def test_campaign_type_and_clamp_flags_reach_the_state(paths: tuple[Path, Path]) -> None:
    samples, out = paths
    index, tables, _ = load(out)
    types = sorted({row["type"] for rows in tables.values() for row in rows})[:2]

    document = report_json(paths, "--campaign", index["campaigns"][0], "--type", ",".join(types), "--clamp", "off")

    assert document["state"]["campaigns"] == index["campaigns"][:1]
    assert document["state"]["types"] == types
    assert document["state"]["clamp"] is False
    assert set(document["level_counts"]) <= set(types)


def test_explicit_flags_override_the_state_hash(paths: tuple[Path, Path]) -> None:
    document = report_json(paths, "--state", "#ref=power:0.002,hab:0.03&clamp=off", "--reference", "power=0.005")

    assert document["state"]["references"]["power"] == 0.005
    assert document["state"]["references"]["hab"] == 0.03
    assert document["state"]["clamp"] is False
    assert report_json(paths, "--state", document["hash"])["state"] == document["state"]
    assert report_json(paths, "--state", "clamp=off", "--clamp", "on")["state"]["clamp"] is True


def test_base_flags_switch_event_types_and_override_the_state_hash(paths: tuple[Path, Path]) -> None:
    _, out = paths
    index, _, _ = load(out)
    first, second = list(index["kinds"])[:2]
    other = {level for level in index["constants"]["level_bands"] if level != index["kinds"][first]["base"]}
    level = sorted(other)[0]
    code = index["kinds"][second]["base"]

    document = report_json(
        paths,
        "--state",
        f"base={second}:{sorted(other)[-1]}",
        "--base",
        f"{first}={level}",
        "--base",
        f"{second}={code}",
    )

    assert document["state"]["type_bases"] == {first: level}
    assert document["hash"] == f"base={first}:{level}"


def test_the_json_readout_carries_the_state_aggregates_and_edges(paths: tuple[Path, Path]) -> None:
    _, out = paths
    document = report_json(paths)

    assert document["key"] == table.read_index(out / "index.js")["key"]
    assert document["hash"] == ""
    assert document["moved"] == []
    assert {"totals", "moves", "level_counts", "members", "cutoffs"} <= set(document)


@pytest.mark.parametrize(
    "flags",
    [
        ["--reference", "warp=0.1"],
        ["--reference", "power=0.1", "--reference", "power=0.2"],
        ["--reference", "power=-1"],
        ["--campaign", "nowhere"],
        ["--type", "no.such_type"],
        ["--state", "speed=1"],
        ["--state", "ref=power:0.1,power:0.2"],
        ["--base", "no.such_type=major"],
        ["--base", "region.nation_changed=huge"],
        ["--state", "base=no.such_type:major"],
    ],
)
def test_an_invalid_state_is_a_usage_error(paths: tuple[Path, Path], flags: list[str]) -> None:
    code, stdout, stderr = report(paths, *flags)

    assert code == cli.EXIT_USAGE_ERROR
    assert stdout == ""
    assert stderr


@pytest.mark.parametrize("flags", [["--clamp", "maybe"], ["--format", "yaml"]])
def test_an_invalid_choice_is_a_usage_error(paths: tuple[Path, Path], flags: list[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        report(paths, *flags)

    assert raised.value.code == cli.EXIT_USAGE_ERROR


def test_a_sample_that_does_not_match_its_manifest_is_a_usage_error(paths: tuple[Path, Path]) -> None:
    samples, _ = paths
    sample = next(samples.rglob("*.xz"))
    sample.write_bytes(sample.read_bytes() + b"\0")

    code, _, stderr = report(paths)

    assert code == cli.EXIT_USAGE_ERROR
    assert sample.name in stderr


def test_a_failed_extraction_is_a_usage_error_and_keeps_the_old_table(
    paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, out = paths
    before = (out / "index.js").read_bytes()

    def broken(*args: Any, **kwargs: Any) -> list[str]:
        raise RuntimeError("the pipeline broke")

    monkeypatch.setattr(table, "extract_all", broken)

    code, stdout, stderr = report(paths, "--rebuild")

    assert code == cli.EXIT_USAGE_ERROR
    assert stdout == ""
    assert "the pipeline broke" in stderr
    assert (out / "index.js").read_bytes() == before
    assert table.read_status(out / "status.js")["state"] == "failed"


def test_an_invalid_draft_stake_is_a_usage_error(paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    invalid = DraftStake(name="ghost", label="Ghost", issue=1, event_types=("nation.ghost",), scalings=())
    monkeypatch.setattr(drafts, "DRAFT_STAKES", (invalid,))

    code, stdout, stderr = report(paths, "--rebuild")

    assert code == cli.EXIT_USAGE_ERROR
    assert stdout == ""
    assert "ghost" in stderr


def test_a_state_naming_an_unknown_draft_is_a_usage_error(paths: tuple[Path, Path]) -> None:
    code, stdout, stderr = report(paths, "--state", "base=ghost:major")

    assert code == cli.EXIT_USAGE_ERROR
    assert stdout == ""
    assert "unknown draft stake or event type 'ghost'" in stderr


@pytest.mark.parametrize("broken", ["missing", "no-manifest"])
def test_unreadable_samples_are_an_input_error(paths: tuple[Path, Path], broken: str) -> None:
    samples, _ = paths
    if broken == "missing":
        shutil.rmtree(samples)
    else:
        (samples / MANIFEST).unlink()

    code, _, stderr = report(paths)

    assert code == cli.EXIT_INPUT_ERROR
    assert stderr


def test_an_unwritable_out_is_an_output_error(paths: tuple[Path, Path], tmp_path: Path) -> None:
    samples, _ = paths
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")

    code, _, stderr = run_cli([*COMMAND, "--samples", str(samples), "--out", str(blocker / "out")])

    assert code == cli.EXIT_OUTPUT_ERROR
    assert stderr
