"""Experiment helper (#331, temporary): run a command and report its wall time and the peak of the summed RSS of its
process tree, sampled every 0.25 s. Usage: python scripts/peak_rss_tree.py -- COMMAND [ARG...]"""

from __future__ import annotations

import subprocess
import sys
import threading
import time


def tree_rss(root: int) -> int:
    rows = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,rss="], capture_output=True, text=True, check=False)
    children: dict[int, list[int]] = {}
    rss: dict[int, int] = {}
    for line in rows.stdout.splitlines():
        pid, ppid, kib = (int(part) for part in line.split())
        children.setdefault(ppid, []).append(pid)
        rss[pid] = kib
    total, stack = 0, [root]
    while stack:
        pid = stack.pop()
        total += rss.get(pid, 0)
        stack.extend(children.get(pid, []))
    return total * 1024


def main() -> int:
    command = sys.argv[sys.argv.index("--") + 1 :]
    started = time.perf_counter()
    process = subprocess.Popen(command)
    peak = 0
    stop = threading.Event()

    def sample() -> None:
        nonlocal peak
        while not stop.is_set():
            peak = max(peak, tree_rss(process.pid))
            stop.wait(0.25)

    thread = threading.Thread(target=sample)
    thread.start()
    code = process.wait()
    stop.set()
    thread.join()
    print(
        f"peak_rss_tree: wall={time.perf_counter() - started:.1f}s peak_rss={peak / 2**20:.0f}MiB exit={code}",
        file=sys.stderr,
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
