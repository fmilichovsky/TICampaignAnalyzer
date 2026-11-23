"""The calibration cache: its key, its freshness, ``status.js`` and the atomic rebuild."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from tests.benchmark_support import synthetic_samples
from tinarrative.benchmarking.calibration import cache, table
from tinarrative.benchmarking.calibration.progress import ProgressSnapshot
from tinarrative.benchmarking.manifest import MANIFEST


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Synthetic samples and a cache built from them, once per module."""
    root = tmp_path_factory.mktemp("calibration-cache")
    samples = synthetic_samples(root)
    out = root / "out"
    cache.refresh(samples, out)
    return samples, out


@pytest.fixture
def copy(built: tuple[Path, Path], tmp_path: Path) -> tuple[Path, Path]:
    samples, out = built
    shutil.copytree(out, tmp_path / "out")
    return samples, tmp_path / "out"


def _package(root: Path) -> Path:
    package = root / "package"
    (package / "sub" / "__pycache__").mkdir(parents=True)
    (package / "module.py").write_text("one = 1\n", encoding="utf-8")
    (package / "sub" / "page.js").write_text("// page\n", encoding="utf-8")
    (package / "sub" / "__pycache__" / "module.cpython.pyc").write_bytes(b"\0")
    return package


def test_the_key_follows_every_package_file_and_the_manifest_and_returns_when_reverted(tmp_path: Path) -> None:
    package = _package(tmp_path)
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / MANIFEST).write_text("{}", encoding="utf-8")
    original = cache.cache_key(samples, package=package)

    for path, edited in [(package / "sub" / "page.js", "// edited\n"), (samples / MANIFEST, '{"x": 1}')]:
        before = path.read_text(encoding="utf-8")
        path.write_text(edited, encoding="utf-8")
        assert cache.cache_key(samples, package=package) != original
        path.write_text(before, encoding="utf-8")
        assert cache.cache_key(samples, package=package) == original

    (package / "new.py").write_text("", encoding="utf-8")
    assert cache.cache_key(samples, package=package) != original


def test_the_key_ignores_bytecode(tmp_path: Path) -> None:
    package = _package(tmp_path)
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / MANIFEST).write_text("{}", encoding="utf-8")
    original = cache.cache_key(samples, package=package)

    (package / "sub" / "__pycache__" / "module.cpython.pyc").write_bytes(b"changed")
    (package / "__pycache__").mkdir()
    (package / "__pycache__" / "other.pyc").write_bytes(b"")

    assert cache.cache_key(samples, package=package) == original


def test_a_fresh_cache_is_not_rebuilt_unless_asked(copy: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    samples, out = copy
    calls: list[Path] = []
    real = table.extract_all

    def counting(samples: Path, directory: Path, **kwargs: Any) -> list[str]:
        calls.append(directory)
        return real(samples, directory, **kwargs)

    monkeypatch.setattr(table, "extract_all", counting)

    assert cache.refresh(samples, out).fresh
    assert calls == []
    assert table.read_status(out / "status.js")["state"] == "fresh"

    cache.refresh(samples, out, rebuild=True)
    assert len(calls) == 1
    assert table.read_index(out / "index.js")["key"] == cache.cache_key(samples)


def test_a_stale_cache_calls_back_before_the_rebuild_starts(
    copy: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    samples, out = copy
    index = table.read_index(out / "index.js")
    table.write_index(out, {**index, "key": "old"})
    seen: list[tuple[str | None, str]] = []
    real = table.extract_all

    def observed(samples: Path, directory: Path, **kwargs: Any) -> list[str]:
        seen.append(("extract", table.read_status(out / "status.js")["state"]))
        return real(samples, directory, **kwargs)

    monkeypatch.setattr(table, "extract_all", observed)

    def stale(found: cache.CacheCheck) -> None:
        assert not found.fresh
        seen.append((found.existing, table.read_status(out / "status.js")["state"]))

    found = cache.refresh(samples, out, on_stale=stale)

    assert seen == [("old", "fresh"), ("extract", "rebuilding")]
    assert found.existing == "old"
    assert table.read_index(out / "index.js")["key"] == found.key
    assert table.read_status(out / "status.js") | {"written_at": ""} == {
        "key": found.key,
        "state": "fresh",
        "message": "",
        "written_at": "",
    }
    assert sorted(path.name for path in out.iterdir()) == ["index.js", "status.js", "tables"]


def test_an_extraction_reports_its_progress_in_the_status_and_to_the_caller(copy: tuple[Path, Path]) -> None:
    samples, out = copy
    statuses: list[dict[str, Any]] = []
    snapshots: list[ProgressSnapshot] = []

    def observed(snapshot: ProgressSnapshot) -> None:
        snapshots.append(snapshot)
        statuses.append(table.read_status(out / "status.js"))

    cache.refresh(samples, out, rebuild=True, on_progress=observed)

    assert statuses and all(status["state"] == "rebuilding" for status in statuses)
    assert statuses[-1]["progress"] == snapshots[-1].to_status()
    assert [snapshot.done_work for snapshot in snapshots] == sorted(snapshot.done_work for snapshot in snapshots)
    assert snapshots[-1].fraction == 1.0
    assert {step.phase for step in snapshots[-1].campaigns} == {"done"}
    assert "progress" not in table.read_status(out / "status.js")


def test_a_failed_rebuild_keeps_the_old_table_and_says_failed(
    copy: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    samples, out = copy
    before = {path.relative_to(out): path.read_bytes() for path in out.rglob("*.js") if path.name != "status.js"}

    def broken(samples: Path, directory: Path, **kwargs: Any) -> list[str]:
        (directory / "tables").mkdir()
        (directory / "tables" / "half.js").write_text("", encoding="utf-8")
        raise RuntimeError("the pipeline broke")

    monkeypatch.setattr(table, "extract_all", broken)

    with pytest.raises(cache.CalibrationCacheError, match="the pipeline broke"):
        cache.refresh(samples, out, rebuild=True)

    after = {path.relative_to(out): path.read_bytes() for path in out.rglob("*.js") if path.name != "status.js"}
    assert after == before
    status = table.read_status(out / "status.js")
    assert status["state"] == "failed"
    assert "RuntimeError: the pipeline broke" in status["message"]
    assert sorted(path.name for path in out.iterdir()) == ["index.js", "status.js", "tables"]


def test_a_broken_index_is_stale(copy: tuple[Path, Path]) -> None:
    samples, out = copy
    (out / "index.js").write_text("not a wrapper", encoding="utf-8")

    assert cache.check(samples, out).existing is None
    assert cache.refresh(samples, out).existing is None
    assert cache.check(samples, out).fresh


def test_a_removed_campaign_leaves_no_table_behind(copy: tuple[Path, Path]) -> None:
    samples, out = copy
    (out / "tables" / "gone.js").write_text("", encoding="utf-8")

    cache.refresh(samples, out, rebuild=True)

    assert sorted(path.stem for path in (out / "tables").iterdir()) == table.read_index(out / "index.js")["campaigns"]
