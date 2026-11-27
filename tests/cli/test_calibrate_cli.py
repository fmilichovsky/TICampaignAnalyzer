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
from tinarrative.benchmarking.calibration.drafts import DraftShare
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
    lines = stderr.splitlines()
    assert any("politics" in line for line in lines[1:-1]), "a line per finished campaign"
    assert "took" in lines[-1], "the time the extraction took"
    assert "\r" not in stderr, "no live line off a terminal"
    assert stdout.startswith("# Share calibration readout")
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


def test_rise_and_drop_shares_accumulate_over_commas_and_repeats(paths: tuple[Path, Path]) -> None:
    document = report_json(paths, "--rise", "power=0.002,hab=0.03", "--rise", "battle=0.001", "--drop", "power=0.0001")

    assert {key: document["state"]["rises"][key] for key in ("power", "hab", "battle")} == {
        "power": 0.002,
        "hab": 0.03,
        "battle": 0.001,
    }
    assert document["state"]["drops"] == {"power": 0.0001}
    assert document["hash"] == "rise=power:0.002,hab:0.03,battle:0.001&drop=power:0.0001"


def test_a_scaling_flag_splits_a_type_off_and_its_rise_share_follows(paths: tuple[Path, Path]) -> None:
    _, out = paths
    index, _, _ = load(out)
    scaled = next(name for name, kind in index["kinds"].items() if kind["scaling"] is not None)

    document = report_json(paths, "--scaling", f"{scaled}={scaled}", "--rise", f"{scaled}=0.5")

    assert document["state"]["scalings"] == {scaled: scaled}
    assert document["state"]["rises"][scaled] == 0.5
    assert document["hash"] == f"rise={scaled}:0.5&scaling={scaled}:{scaled}"


def test_campaign_and_type_flags_reach_the_state(paths: tuple[Path, Path]) -> None:
    samples, out = paths
    index, tables, _ = load(out)
    types = sorted({row["type"] for rows in tables.values() for row in rows})[:2]

    document = report_json(paths, "--campaign", index["campaigns"][0], "--type", ",".join(types))

    assert document["state"]["campaigns"] == index["campaigns"][:1]
    assert document["state"]["types"] == types
    assert set(document["level_counts"]) <= set(types)


def test_explicit_flags_override_the_state_hash(paths: tuple[Path, Path]) -> None:
    document = report_json(paths, "--state", "#rise=power:0.002,hab:0.03", "--rise", "power=0.005")

    assert document["state"]["rises"]["power"] == 0.005
    assert document["state"]["rises"]["hab"] == 0.03
    assert report_json(paths, "--state", document["hash"])["state"] == document["state"]


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
        ["--rise", "warp=0.1"],
        ["--rise", "power=0.1", "--rise", "power=0.2"],
        ["--rise", "power=-1"],
        ["--drop", "power=1"],
        ["--scaling", "no.such_type=power"],
        ["--state", "ref=power:0.1"],
        ["--campaign", "nowhere"],
        ["--type", "no.such_type"],
        ["--state", "speed=1"],
        ["--state", "rise=power:0.1,power:0.2"],
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


@pytest.mark.parametrize("flags", [["--clamp", "off"], ["--format", "yaml"]])
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


def test_an_invalid_draft_share_is_a_usage_error(paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    invalid = DraftShare(name="ghost", label="Ghost", issue=1, event_types=("nation.ghost",), readings=())
    monkeypatch.setattr(drafts, "DRAFT_SHARES", (invalid,))

    code, stdout, stderr = report(paths, "--rebuild")

    assert code == cli.EXIT_USAGE_ERROR
    assert stdout == ""
    assert "ghost" in stderr


def test_a_state_naming_an_unknown_draft_is_a_usage_error(paths: tuple[Path, Path]) -> None:
    code, stdout, stderr = report(paths, "--state", "base=ghost:major")

    assert code == cli.EXIT_USAGE_ERROR
    assert stdout == ""
    assert "unknown draft share or event type 'ghost'" in stderr


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


def test_views_replace_the_readout_in_text_and_json(paths: tuple[Path, Path]) -> None:
    code, stdout, stderr = report(paths, "--view", "period,tiers", "--period", "quarter")

    assert code == cli.EXIT_SUCCESS, stderr
    assert stdout.strip() and "# Share calibration readout" not in stdout
    document = report_json(paths, "--view", "tiers", "--view", "period", "--period", "quarter")
    assert set(document["views"]) == {"period", "tiers"}
    assert {campaign["period"] for campaign in document["views"]["period"]["campaigns"].values()} == {"quarter"}


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        (["--view", "shape"], "shape"),
        (["--period", "year"], "choose the periods of a --view"),
        (["--periods", "2031"], "choose the periods of a --view"),
        (["--view", "period", "--periods", "1999"], "unknown period"),
        (["--view", "period", "--include-non-standard"], "belongs to the distribution view"),
        (["--view", "distribution", "--periods", "2031"], "no periods"),
    ],
)
def test_invalid_view_flags_are_usage_errors(paths: tuple[Path, Path], flags: list[str], message: str) -> None:
    code, _, stderr = report(paths, *flags)

    assert code == cli.EXIT_USAGE_ERROR
    assert message in stderr


def test_the_distribution_view_leaves_a_non_standard_sample_out_unless_asked_for(paths: tuple[Path, Path]) -> None:
    samples, _ = paths
    manifest = json.loads((samples / "samples.json").read_text(encoding="utf-8"))
    name = next(iter(manifest["campaigns"]))
    entry = manifest["campaigns"][name]
    entry["profile"] = {**(entry.get("profile") or {}), "non_standard": ["research_speed"]}
    (samples / "samples.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    left = report_json(paths, "--view", "distribution", "--campaign", name)["views"]["distribution"]
    kept = report_json(paths, "--view", "distribution", "--campaign", name, "--include-non-standard")["views"][
        "distribution"
    ]

    assert left["campaigns"] == [] and left["left_out"] == {name: ["research_speed"]}
    assert kept["campaigns"] == [name] and kept["left_out"] == {name: ["research_speed"]}
