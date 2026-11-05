"""The default worker count and the physical memory it is bounded by."""

from __future__ import annotations

import os

import pytest

from tinarrative import workers
from tinarrative.workers import MIN_PARALLEL_BYTES, UNKNOWN_MEMORY_JOBS, default_jobs

GIB = 1 << 30
SAVE = 80_000_000


def test_small_inputs_run_in_one_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workers, "_cpu_count", lambda: 16)
    assert default_jobs([]) == 1
    assert default_jobs([MIN_PARALLEL_BYTES // 4] * 3) == 1


def test_large_inputs_take_the_cpus_up_to_what_memory_holds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workers, "_cpu_count", lambda: 16)
    monkeypatch.setattr(workers, "_physical_memory", lambda: 64 * GIB)
    assert default_jobs([SAVE] * 20) == 16
    monkeypatch.setattr(workers, "_physical_memory", lambda: 8 * GIB)
    assert default_jobs([SAVE] * 20) == 3  # 4 GiB for workers over about 1.1 GB each
    monkeypatch.setattr(workers, "_physical_memory", lambda: GIB)
    assert default_jobs([SAVE] * 20) == 1


def test_unknown_memory_caps_the_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workers, "_cpu_count", lambda: 16)
    monkeypatch.setattr(workers, "_physical_memory", lambda: None)
    assert default_jobs([SAVE] * 20) == UNKNOWN_MEMORY_JOBS


def test_physical_memory_is_read_and_unknown_without_sysconf(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.name == "posix":
        memory = workers._physical_memory()
        assert memory is not None and memory > 0
        monkeypatch.delattr(os, "sysconf")  # as on Windows without its own branch
        assert workers._physical_memory() is None
