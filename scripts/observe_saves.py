"""Observe how Terra Invicta writes its save directory, for the continuous-capture evidence pass.

The script polls a save directory and appends one JSON line per change to a log: the base file name, its size,
modification and change times, inode and birth time where the platform has them, the SHA-256 of the content, and for
a ``.json`` file the game time from the save header (``gameTimeString``). It reads no other save value. Every distinct
save version that was read while it did not change is kept in an archive as ``<sha256>.json.xz``, so that the records
carried forward along a line of play can be compared afterwards, across autosaves the game has since overwritten.
Lines typed on standard input while it runs are logged as notes: the player's account of loads, battles and exits.

It opens save files for reading only and never writes into the save directory; the log and the archive must lie
outside it. Both hold file names and whole saves, so they stay private. See ``scripts/observe_saves.md``.

The script uses the standard library only and never imports ``tinarrative``, so it runs on the gaming machine as is.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import os
import platform
import queue
import re
import signal
import sys
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from stat import S_ISREG
from typing import Any, TextIO

TOOL_VERSION = 1
DEFAULT_INTERVAL = 0.2
HEADER_BYTES = 65_536
"""The game time is looked for in this many leading bytes of a save."""
GAME_TIME = re.compile(rb'"gameTimeString"\s*:\s*"([^"\\]{1,64})"')
SAVE_SUFFIX = ".json"
ARCHIVE_SUFFIX = ".json.xz"
XZ_PRESET = 3
"""Close to the default preset's size on a full save at a tenth of its time."""
ARCHIVE_BACKLOG = 4
"""Save versions read but not yet compressed; a poll waits while the backlog is full."""
RETRIES = 25
"""Polls on which a file whose read failed or overlapped a write is read again although its listing did not change."""


@dataclass(frozen=True)
class Entry:
    """What one directory listing says about a file."""

    size: int
    mtime_ns: int
    ctime_ns: int
    inode: int
    birthtime_ns: int | None
    is_file: bool

    def fields(self) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "size": self.size,
            "mtime_ns": self.mtime_ns,
            "ctime_ns": self.ctime_ns,
            "inode": self.inode,
        }
        if self.birthtime_ns is not None:
            fields["birthtime_ns"] = self.birthtime_ns
        if not self.is_file:
            fields["is_file"] = False
        return fields


def birthtime_ns(stat: os.stat_result) -> int | None:
    """The creation time where the platform reports one."""
    nanoseconds = getattr(stat, "st_birthtime_ns", None)
    if nanoseconds is not None:
        return int(nanoseconds)
    seconds = getattr(stat, "st_birthtime", None)
    return None if seconds is None else int(seconds * 1_000_000_000)


def entry_of(stat: os.stat_result, inode: int) -> Entry:
    return Entry(
        size=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        ctime_ns=stat.st_ctime_ns,
        inode=inode,
        birthtime_ns=birthtime_ns(stat),
        is_file=S_ISREG(stat.st_mode),
    )


def scan(directory: Path) -> dict[str, Entry]:
    """One listing of ``directory`` by base name; a file removed while it is listed is left out."""
    listing: dict[str, Entry] = {}
    with os.scandir(directory) as entries:
        for item in entries:
            try:
                stat = item.stat(follow_symlinks=False)
                inode = item.inode()
            except FileNotFoundError:
                continue
            listing[item.name] = entry_of(stat, inode)
    return listing


def changes(previous: Mapping[str, Entry], current: Mapping[str, Entry]) -> list[tuple[str, str]]:
    """``(kind, name)`` per file that was ``added``, ``changed`` or ``removed`` between two listings, by name."""
    found: list[tuple[str, str]] = []
    for name in sorted(previous.keys() | current.keys()):
        before, after = previous.get(name), current.get(name)
        if before is None:
            found.append(("added", name))
        elif after is None:
            found.append(("removed", name))
        elif (before.size, before.mtime_ns, before.inode) != (after.size, after.mtime_ns, after.inode):
            found.append(("changed", name))
    return found


def game_time(data: bytes) -> str | None:
    """``gameTimeString`` from the header of a save, the only save value the script reads."""
    match = GAME_TIME.search(data, 0, HEADER_BYTES)
    return None if match is None else match.group(1).decode("utf-8", "replace")


def is_save(name: str) -> bool:
    return name.lower().endswith(SAVE_SUFFIX)


def real_case(path: Path) -> str:
    """``path`` with every component spelled as the file system lists it, which a case-insensitive one may not."""
    resolved = path.resolve()
    spelled = Path(resolved.anchor)
    for part in resolved.parts[1:]:
        try:
            names = [item.name for item in os.scandir(spelled)]
        except OSError:
            names = []
        exact = part in names
        matches = [name for name in names if name.casefold() == part.casefold()]
        spelled = spelled / (part if exact or not matches else matches[0])
    return str(spelled)


def now() -> tuple[str, int]:
    nanoseconds = time.time_ns()
    stamp = datetime.fromtimestamp(nanoseconds / 1_000_000_000, UTC).isoformat(timespec="microseconds")
    return stamp, nanoseconds


class Log:
    """The JSON-lines log, shared by the poll loop and the archive worker."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._lock = threading.Lock()

    def write(self, event: str, observed: tuple[str, int] | None = None, **fields: Any) -> None:
        stamp, nanoseconds = observed or now()
        record = {"event": event, "observed": stamp, "observed_ns": nanoseconds, **fields}
        with self._lock:
            self._stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._stream.flush()


class Archive:
    """Content-addressed ``<sha256>.json.xz`` copies, compressed on a worker thread."""

    def __init__(self, directory: Path, log: Log) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        self._log = log
        self._pending: set[str] = set()
        self._queue: queue.Queue[tuple[str, bytes] | None] = queue.Queue(maxsize=ARCHIVE_BACKLOG)
        self._worker = threading.Thread(target=self._run, name="archive", daemon=True)
        self._worker.start()

    def path(self, digest: str) -> Path:
        return self.directory / f"{digest}{ARCHIVE_SUFFIX}"

    def submit(self, digest: str, data: bytes) -> str:
        """``queued``, or ``duplicate`` when the version is archived or queued already."""
        if digest in self._pending or self.path(digest).exists():
            return "duplicate"
        self._pending.add(digest)
        self._queue.put((digest, data))
        return "queued"

    def close(self) -> None:
        """Wait until every queued version is written."""
        self._queue.put(None)
        self._worker.join()

    def _run(self) -> None:
        while (item := self._queue.get()) is not None:
            digest, data = item
            target = self.path(digest)
            partial = target.with_name(f".{target.name}.partial")
            try:
                with lzma.open(partial, "wb", preset=XZ_PRESET) as stream:
                    stream.write(data)
                os.replace(partial, target)
                self._log.write("archived", sha256=digest, compressed_size=target.stat().st_size)
            except OSError as error:
                partial.unlink(missing_ok=True)
                self._log.write("archive_failed", sha256=digest, error=type(error).__name__)
            finally:
                self._pending.discard(digest)


def read_bytes(path: Path) -> bytes:
    with open(path, "rb") as stream:
        return stream.read()


class Observer:
    """The poll loop's state: the last listing and the files to read again."""

    def __init__(
        self,
        directory: Path,
        log: Log,
        archive: Archive,
        read: Callable[[Path], bytes] = read_bytes,
    ) -> None:
        self.directory = directory
        self.log = log
        self.archive = archive
        self.read = read
        self.listing: dict[str, Entry] = {}
        self.retry: dict[str, int] = {}

    def start(self, interval: float) -> None:
        self.log.write(
            "start",
            tool_version=TOOL_VERSION,
            interval=interval,
            platform=platform.system(),
            python=platform.python_version(),
            directory=real_case(self.directory),
        )
        self.listing = scan(self.directory)
        for name in sorted(self.listing):
            self.describe("present", name, self.listing[name])

    def poll(self, notes: queue.Queue[tuple[int, str]] | None = None) -> None:
        if notes is not None:
            self.drain(notes)
        current = scan(self.directory)
        found = changes(self.listing, current)
        changed = {name for _, name in found}
        found += [("reread", name) for name in sorted(self.retry) if name in current and name not in changed]
        self.listing = current
        for kind, name in found:
            if kind == "removed":
                self.retry.pop(name, None)
                self.log.write("removed", name=name)
            else:
                self.describe(kind, name, current[name])

    def drain(self, notes: queue.Queue[tuple[int, str]]) -> None:
        while True:
            try:
                nanoseconds, text = notes.get_nowait()
            except queue.Empty:
                return
            stamp = datetime.fromtimestamp(nanoseconds / 1_000_000_000, UTC).isoformat(timespec="microseconds")
            self.log.write("note", (stamp, nanoseconds), text=text)

    def describe(self, kind: str, name: str, entry: Entry) -> None:
        """Log one file: listing fields, and for a regular file its hash, game time and archive outcome."""
        observed = now()
        fields = entry.fields()
        if not entry.is_file:
            self.log.write(kind, observed, name=name, **fields)
            return
        path = self.directory / name
        settled = False
        try:
            data = self.read(path)
            after = os.stat(path)
        except FileNotFoundError:
            self.retry.pop(name, None)
            self.log.write(kind, observed, name=name, **fields, error="FileNotFoundError")
            return
        except OSError as error:
            fields["error"] = type(error).__name__
            archived = "error"
        else:
            digest = hashlib.sha256(data).hexdigest()
            fields["sha256"] = digest
            if is_save(name) and (time_string := game_time(data)) is not None:
                fields["game_time"] = time_string
            settled = (after.st_size, after.st_mtime_ns) == (entry.size, entry.mtime_ns) and len(data) == entry.size
            if not settled:
                fields["unstable"] = True
                fields["size_after"] = after.st_size
                fields["mtime_ns_after"] = after.st_mtime_ns
                archived = "unstable"
            elif not is_save(name):
                archived = "not_save"
            else:
                archived = self.archive.submit(digest, data)
        if settled:
            self.retry.pop(name, None)
        else:
            attempts = self.retry.get(name, 0) + 1
            if attempts <= RETRIES:
                self.retry[name] = attempts
            else:
                self.retry.pop(name, None)
                fields["gave_up"] = True
        self.log.write(kind, observed, name=name, **fields, archive=archived)


def read_notes(stream: TextIO, notes: queue.Queue[tuple[int, str]]) -> None:
    for line in stream:
        if text := line.strip():
            notes.put((time.time_ns(), text))


def inside(path: Path, directory: Path) -> bool:
    return path.resolve().is_relative_to(directory.resolve())


def observe(
    directory: Path,
    out: Path,
    archive_directory: Path,
    interval: float,
    notes: queue.Queue[tuple[int, str]] | None = None,
    stop: Callable[[], bool] = lambda: False,
) -> None:
    """Poll until ``stop`` says so or the user interrupts, then drain the archive and log the stop."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as stream:
        log = Log(stream)
        archive = Archive(archive_directory, log)
        observer = Observer(directory, log, archive)
        reason = "stopped"
        try:
            observer.start(interval)
            while not stop():
                time.sleep(interval)
                observer.poll(notes)
            if notes is not None:
                observer.drain(notes)
        except KeyboardInterrupt:
            reason = "interrupted"
        finally:
            archive.close()
            log.write("stop", reason=reason)


def interrupt(signum: int, frame: object) -> None:
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("directory", type=Path, help="The game's save directory (read only).")
    parser.add_argument("--out", type=Path, required=True, help="The JSON-lines log, appended to.")
    parser.add_argument("--archive", type=Path, required=True, help="Where save versions are kept.")
    parser.add_argument(
        "--interval", type=float, default=DEFAULT_INTERVAL, help=f"Seconds between polls (default {DEFAULT_INTERVAL})."
    )
    parser.add_argument("--no-notes", action="store_true", help="Do not read notes from standard input.")
    arguments = parser.parse_args(argv)
    directory: Path = arguments.directory
    if not directory.is_dir():
        print(f"observe_saves: not a directory: {directory}", file=sys.stderr)
        return 2
    for option, path in (("--out", arguments.out), ("--archive", arguments.archive)):
        if inside(path, directory):
            print(f"observe_saves: {option} must lie outside the save directory", file=sys.stderr)
            return 2
    if arguments.interval <= 0:
        print("observe_saves: --interval must be positive", file=sys.stderr)
        return 2
    notes: queue.Queue[tuple[int, str]] | None = None
    if not arguments.no_notes:
        notes = queue.Queue()
        threading.Thread(target=read_notes, args=(sys.stdin, notes), name="notes", daemon=True).start()
        print("observe_saves: observing; type a note and press Enter, Ctrl+C to stop", file=sys.stderr)
    signal.signal(signal.SIGTERM, interrupt)
    observe(directory, arguments.out, arguments.archive, arguments.interval, notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
