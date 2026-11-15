"""`benchmark calibrate open`: the page it writes, the order of page and rebuild, and the browser it may not get."""

from __future__ import annotations

import shutil
from contextlib import redirect_stderr, redirect_stdout
from importlib.resources import files
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from tests.benchmark_support import synthetic_samples
from tinarrative import cli
from tinarrative.benchmarking.calibration import cache, table

COMMAND = ["benchmark", "calibrate", "open"]
PACKAGE = files("tinarrative.benchmarking.calibration")


class Run:
    """One command run whose stdout can be read while it is still running."""

    def __init__(self) -> None:
        self.stdout = StringIO()
        self.stderr = StringIO()

    def __call__(self, paths: tuple[Path, Path], *flags: str) -> int:
        samples, out = paths
        with redirect_stdout(self.stdout), redirect_stderr(self.stderr):
            return cli.main([*COMMAND, "--samples", str(samples), "--out", str(out), *flags])


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Synthetic samples and a fresh cache built from them, once per module."""
    root = tmp_path_factory.mktemp("calibrate-open")
    samples = synthetic_samples(root)
    out = root / "out"
    cache.refresh(samples, out)
    return samples, out


@pytest.fixture
def paths(built: tuple[Path, Path], tmp_path: Path) -> tuple[Path, Path]:
    samples, out = built
    shutil.copytree(out, tmp_path / "out")
    return samples, tmp_path / "out"


@pytest.fixture
def browser(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The URLs the command asks the browser to open; the test never starts a real browser."""
    opened: list[str] = []

    def fake_open(url: str, *args: Any, **kwargs: Any) -> bool:
        opened.append(url)
        return True

    monkeypatch.setattr(cli.webbrowser, "open", fake_open)
    return opened


@pytest.fixture
def extractions(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    calls: list[Path] = []
    real = table.extract_all

    def counting(samples: Path, directory: Path, **kwargs: Any) -> list[str]:
        calls.append(directory)
        return real(samples, directory, **kwargs)

    monkeypatch.setattr(table, "extract_all", counting)
    return calls


def make_stale(out: Path) -> bytes:
    index = table.read_index(out / "index.js")
    table.write_index(out, {**index, "key": "old"})
    return (out / "index.js").read_bytes()


def test_with_no_cache_it_builds_the_table_then_prints_the_page(paths: tuple[Path, Path], browser: list[str]) -> None:
    _, out = paths
    shutil.rmtree(out)
    run = Run()

    code = run(paths, "--no-open")

    assert code == cli.EXIT_SUCCESS
    page = (out / "index.html").resolve()
    assert run.stdout.getvalue() == f"{page}\n"
    assert "Extracting the calibration table" in run.stderr.getvalue()
    assert browser == []
    assert table.read_status(out / "status.js")["state"] == "fresh"
    for name in cache.PAGE_FILES:
        assert (out / name).read_bytes() == PACKAGE.joinpath("page", name).read_bytes()
    for name in cache.PAGE_SCRIPTS:
        assert (out / name).read_bytes() == PACKAGE.joinpath(name).read_bytes()


def test_a_fresh_cache_opens_the_page_without_a_rebuild(
    paths: tuple[Path, Path], browser: list[str], extractions: list[Path]
) -> None:
    _, out = paths
    run = Run()

    code = run(paths)

    assert (code, extractions, run.stderr.getvalue()) == (cli.EXIT_SUCCESS, [], "")
    assert browser == [(out / "index.html").resolve().as_uri()]
    assert run.stdout.getvalue() == f"{(out / 'index.html').resolve()}\n"


def test_a_stale_cache_shows_the_old_page_first_then_turns_fresh(
    paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, out = paths
    old = make_stale(out)
    run = Run()
    seen: list[tuple[str, str, bytes]] = []
    real = table.extract_all

    def observed(samples: Path, directory: Path, **kwargs: Any) -> list[str]:
        status = table.read_status(out / "status.js")["state"]
        seen.append((run.stdout.getvalue(), status, (out / "index.js").read_bytes()))
        return real(samples, directory, **kwargs)

    monkeypatch.setattr(table, "extract_all", observed)

    code = run(paths, "--no-open")

    page = (out / "index.html").resolve()
    assert code == cli.EXIT_SUCCESS
    assert seen == [(f"{page}\n", "rebuilding", old)]
    assert run.stdout.getvalue() == f"{page}\n"
    assert table.read_status(out / "status.js")["state"] == "fresh"
    assert table.read_index(out / "index.js")["key"] != "old"


def test_a_stale_cache_opens_the_browser_before_the_rebuild(
    paths: tuple[Path, Path], browser: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, out = paths
    make_stale(out)
    opened_before: list[int] = []
    real = table.extract_all

    def observed(samples: Path, directory: Path, **kwargs: Any) -> list[str]:
        opened_before.append(len(browser))
        return real(samples, directory, **kwargs)

    monkeypatch.setattr(table, "extract_all", observed)

    assert Run()(paths) == cli.EXIT_SUCCESS
    assert opened_before == [1]
    assert len(browser) == 1


def test_a_failed_rebuild_keeps_the_old_table_and_says_failed(
    paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, out = paths
    old = make_stale(out)

    def broken(*args: Any, **kwargs: Any) -> list[str]:
        raise RuntimeError("the pipeline broke")

    monkeypatch.setattr(table, "extract_all", broken)
    run = Run()

    code = run(paths, "--no-open")

    assert code == cli.EXIT_USAGE_ERROR
    assert run.stdout.getvalue() == f"{(out / 'index.html').resolve()}\n"
    assert "the pipeline broke" in run.stderr.getvalue()
    assert (out / "index.js").read_bytes() == old
    status = table.read_status(out / "status.js")
    assert status["state"] == "failed"
    assert "RuntimeError: the pipeline broke" in status["message"]


def test_a_browser_that_cannot_be_opened_only_warns(paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.webbrowser, "open", lambda *args, **kwargs: False)
    run = Run()

    code = run(paths)

    assert code == cli.EXIT_SUCCESS
    assert "cannot open a browser" in run.stderr.getvalue()
    assert run.stdout.getvalue().strip().endswith("index.html")


def test_unreadable_samples_are_an_input_error(paths: tuple[Path, Path], tmp_path: Path) -> None:
    _, out = paths

    code = Run()((tmp_path / "missing", out), "--no-open")

    assert code == cli.EXIT_INPUT_ERROR


def test_an_unwritable_out_is_an_output_error(paths: tuple[Path, Path], tmp_path: Path) -> None:
    samples, _ = paths
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")

    code = Run()((samples, blocker / "out"), "--no-open")

    assert code == cli.EXIT_OUTPUT_ERROR
