"""`benchmark calibrate open`: the server it starts, the order of page and rebuild, and the browser it may not get."""

from __future__ import annotations

import json
import shutil
import socket
import urllib.request
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
PAGE = files("tinarrative.benchmarking.calibration").joinpath("page")


class Run:
    """One command run on a free port whose stdout can be read while it is still running."""

    def __init__(self) -> None:
        self.stdout = StringIO()
        self.stderr = StringIO()

    def __call__(self, paths: tuple[Path, Path], *flags: str) -> int:
        samples, out = paths
        with redirect_stdout(self.stdout), redirect_stderr(self.stderr):
            return cli.main([*COMMAND, "--samples", str(samples), "--out", str(out), "--port", "0", *flags])

    @property
    def url(self) -> str:
        return self.stdout.getvalue().splitlines()[0]


def fetch(url: str, body: dict[str, Any] | None = None) -> bytes:
    data = None if body is None else json.dumps(body).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as response:
        content: bytes = response.read()
        return content


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
def run() -> Run:
    return Run()


@pytest.fixture
def waits(monkeypatch: pytest.MonkeyPatch, run: Run) -> list[str]:
    """Stands in for the wait on Ctrl-C: records the page the server gives while the command would block."""
    pages: list[str] = []

    def served() -> None:
        pages.append(fetch(run.url).decode("utf-8"))

    monkeypatch.setattr(cli, "_wait_for_interrupt", served)
    return pages


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


def test_with_no_cache_it_builds_the_table_then_serves_the_page(
    paths: tuple[Path, Path], browser: list[str], waits: list[str], run: Run
) -> None:
    _, out = paths
    shutil.rmtree(out)

    code = run(paths, "--no-open")

    assert code == cli.EXIT_SUCCESS
    assert run.url.startswith("http://127.0.0.1:") and run.url.endswith("/")
    assert "Extracting the calibration table" in run.stderr.getvalue()
    assert browser == []
    assert waits == [PAGE.joinpath("index.html").read_text(encoding="utf-8")]
    assert table.read_status(out / "status.js")["state"] == "fresh"
    assert not (out / "index.html").exists()


def test_a_fresh_cache_opens_the_page_without_a_rebuild(
    paths: tuple[Path, Path], browser: list[str], extractions: list[Path], waits: list[str], run: Run
) -> None:
    code = run(paths)

    assert (code, extractions) == (cli.EXIT_SUCCESS, [])
    assert browser == [run.url]
    assert "the calibration table" not in run.stderr.getvalue()
    assert "Serving" in run.stderr.getvalue()


def test_a_stale_cache_serves_the_old_table_during_the_rebuild_then_turns_fresh(
    paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, waits: list[str], run: Run
) -> None:
    _, out = paths
    old = make_stale(out)
    seen: list[tuple[str, str, bytes]] = []
    real = table.extract_all

    def observed(samples: Path, directory: Path, **kwargs: Any) -> list[str]:
        status = table.read_status(out / "status.js")["state"]
        seen.append((run.stdout.getvalue(), status, fetch(run.url + "index.js")))
        return real(samples, directory, **kwargs)

    monkeypatch.setattr(table, "extract_all", observed)

    code = run(paths, "--no-open")

    assert code == cli.EXIT_SUCCESS
    assert seen == [(f"{run.url}\n", "rebuilding", old)]
    assert table.read_status(out / "status.js")["state"] == "fresh"
    assert table.read_index(out / "index.js")["key"] != "old"
    assert len(waits) == 1


def test_a_stale_cache_opens_the_browser_before_the_rebuild(
    paths: tuple[Path, Path], browser: list[str], monkeypatch: pytest.MonkeyPatch, waits: list[str], run: Run
) -> None:
    _, out = paths
    make_stale(out)
    opened_before: list[int] = []
    real = table.extract_all

    def observed(samples: Path, directory: Path, **kwargs: Any) -> list[str]:
        opened_before.append(len(browser))
        return real(samples, directory, **kwargs)

    monkeypatch.setattr(table, "extract_all", observed)

    assert run(paths) == cli.EXIT_SUCCESS
    assert opened_before == [1]
    assert browser == [run.url]


def test_a_failed_rebuild_keeps_serving_the_old_table_and_exits_with_a_usage_error(
    paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, waits: list[str], run: Run
) -> None:
    _, out = paths
    old = make_stale(out)

    def broken(*args: Any, **kwargs: Any) -> list[str]:
        raise RuntimeError("the pipeline broke")

    monkeypatch.setattr(table, "extract_all", broken)

    code = run(paths, "--no-open")

    assert code == cli.EXIT_USAGE_ERROR
    assert len(waits) == 1
    assert "the pipeline broke" in run.stderr.getvalue()
    assert (out / "index.js").read_bytes() == old
    status = table.read_status(out / "status.js")
    assert status["state"] == "failed"
    assert "RuntimeError: the pipeline broke" in status["message"]


def test_a_failed_first_extraction_stops_at_once(
    paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, waits: list[str], run: Run
) -> None:
    _, out = paths
    shutil.rmtree(out)

    def broken(*args: Any, **kwargs: Any) -> list[str]:
        raise RuntimeError("the pipeline broke")

    monkeypatch.setattr(table, "extract_all", broken)

    code = run(paths, "--no-open")

    assert (code, run.stdout.getvalue(), waits) == (cli.EXIT_USAGE_ERROR, "", [])
    assert "the pipeline broke" in run.stderr.getvalue()


def test_ctrl_c_stops_the_server_with_success(
    paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, run: Run
) -> None:
    def interrupted() -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_wait_for_interrupt", interrupted)

    code = run(paths, "--no-open")

    assert code == cli.EXIT_SUCCESS
    with pytest.raises(OSError):
        fetch(run.url)


def test_a_browser_that_cannot_be_opened_only_warns(
    paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, waits: list[str], run: Run
) -> None:
    monkeypatch.setattr(cli.webbrowser, "open", lambda *args, **kwargs: False)

    code = run(paths)

    assert code == cli.EXIT_SUCCESS
    assert f"cannot open a browser; open {run.url} by hand" in run.stderr.getvalue()


def test_a_port_in_use_is_an_output_error(paths: tuple[Path, Path], waits: list[str]) -> None:
    samples, out = paths
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        stderr = StringIO()
        with redirect_stdout(StringIO()), redirect_stderr(stderr):
            code = cli.main([*COMMAND, "--samples", str(samples), "--out", str(out), "--port", str(port), "--no-open"])

    assert code == cli.EXIT_OUTPUT_ERROR
    assert f"cannot serve on 127.0.0.1:{port}" in stderr.getvalue()
    assert waits == []


def test_unreadable_samples_are_an_input_error(paths: tuple[Path, Path], tmp_path: Path, run: Run) -> None:
    _, out = paths

    code = run((tmp_path / "missing", out), "--no-open")

    assert code == cli.EXIT_INPUT_ERROR


def test_an_unwritable_out_is_an_output_error(paths: tuple[Path, Path], tmp_path: Path, run: Run) -> None:
    samples, _ = paths
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")

    code = run((samples, blocker / "out"), "--no-open")

    assert code == cli.EXIT_OUTPUT_ERROR
