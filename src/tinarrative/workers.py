"""Worker processes for the save pipeline: a spawn pool whose workers log like the coordinator and report progress,
and the default worker count, bounded by CPUs and memory."""

from __future__ import annotations

import multiprocessing
import os
import sys
import threading
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from multiprocessing.queues import SimpleQueue
from typing import Any, cast

from .log import TIMING_LOGGER, configure_logging, fields, get_logger, logging_state

timing = get_logger(TIMING_LOGGER)

WORKER_BYTES_PER_SAVE_BYTE = 7
"""Resident bytes per byte of save file while a save is decoded and normalized; a pair of Resist-size saves (about
80 MB each) peaks near 1 GB."""
MEMORY_SHARE = 2
"""Workers may use 1/MEMORY_SHARE of physical memory, leaving the rest to the coordinator and everything else."""
MIN_PARALLEL_BYTES = 8 << 20
"""Below this many save bytes in all, starting workers costs more than it saves."""
UNKNOWN_MEMORY_JOBS = 2
"""The default worker count where physical memory cannot be read."""

_ticks: SimpleQueue[Any] | None = None


def _initialize(level: str, timing_on: bool, ticks: SimpleQueue[Any]) -> None:
    global _ticks
    configure_logging(level, timing=timing_on)  # spawned processes start without the coordinator's handlers
    _ticks = ticks


def tick() -> None:
    """Report one unit of work to the coordinator's progress; nothing outside a worker."""
    if _ticks is not None:
        _ticks.put(1)


@contextmanager
def pool(
    jobs: int, progress: Callable[[], None] | None = None, *, tasks_per_child: int | None = None
) -> Iterator[ProcessPoolExecutor]:
    """A pool of ``jobs`` spawned workers; every ``tick`` in a worker calls ``progress`` on a coordinator thread.

    Spawn on every platform, so a test on Linux starts workers as macOS and Windows do. On an exception (or a closed
    generator) the pending tasks are cancelled before the running ones are waited for.
    """
    context = multiprocessing.get_context("spawn")
    ticks: SimpleQueue[Any] = context.SimpleQueue()
    level, timing_on = logging_state()

    def drain() -> None:
        while ticks.get() is not None:
            if progress is not None:
                progress()

    drainer = threading.Thread(target=drain, name="tinarrative-progress", daemon=True)
    drainer.start()
    executor = ProcessPoolExecutor(
        jobs,
        mp_context=context,
        initializer=_initialize,
        initargs=(level, timing_on, ticks),
        max_tasks_per_child=tasks_per_child,
    )
    try:
        yield executor
    except BaseException:
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)
    finally:
        ticks.put(None)
        drainer.join()
        ticks.close()


def default_jobs(save_bytes: Sequence[int]) -> int:
    """Workers for saves of these sizes: one for small inputs, else the CPUs, at most what memory holds."""
    if not save_bytes or sum(save_bytes) < MIN_PARALLEL_BYTES:
        return 1
    memory = _physical_memory()
    if memory is None:
        bound = UNKNOWN_MEMORY_JOBS
    else:
        bound = memory // MEMORY_SHARE // (WORKER_BYTES_PER_SAVE_BYTE * 2 * max(save_bytes))
    return max(1, min(_cpu_count(), bound))


def _cpu_count() -> int:
    counter = cast("Callable[[], int | None]", getattr(os, "process_cpu_count", os.cpu_count))  # 3.13+ honours affinity
    return counter() or 1


def _physical_memory() -> int | None:
    """Total physical memory in bytes, ``None`` where it cannot be read."""
    try:
        if sys.platform == "win32":
            total = _windows_memory()
        else:
            total = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, ValueError, OSError):
        return None
    return total if total > 0 else None


if sys.platform == "win32":
    import ctypes

    class _MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    def _windows_memory() -> int:
        """``os.sysconf`` does not exist on Windows; ``GlobalMemoryStatusEx`` reports the same total."""
        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("GlobalMemoryStatusEx failed")
        return int(status.ullTotalPhys)


def memory_line() -> None:
    """The timing line with this process's peak resident bytes; none on Windows, which lacks ``resource``."""
    try:
        import resource
    except ImportError:
        return
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    timing.info("memory %s", fields(peak=peak * (1 if sys.platform == "darwin" else 1024)))  # Linux reports KiB
