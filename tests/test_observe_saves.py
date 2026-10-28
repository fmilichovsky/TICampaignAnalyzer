"""Coverage for scripts/observe_saves.py: listings, change records, the archive, notes and the read-only guarantee."""

from __future__ import annotations

import io
import json
import lzma
import os
import queue
from pathlib import Path
from typing import Any

import pytest

from scripts.observe_saves import Archive, Log, Observer, changes, game_time, main, observe, scan

HEADER = '{\r\n  "currentID": {"value": 1},\r\n  "gamestates": {"TIMetadataState": [{"gameTimeString": "%s"}]}\r\n}\r\n'
RECORD_KEYS = {
    "event",
    "observed",
    "observed_ns",
    "name",
    "size",
    "mtime_ns",
    "ctime_ns",
    "inode",
    "birthtime_ns",
    "is_file",
    "sha256",
    "game_time",
    "unstable",
    "size_after",
    "mtime_ns_after",
    "error",
    "gave_up",
    "archive",
}


def _save(path: Path, when: str, padding: str = "") -> bytes:
    data = (HEADER % when + padding).encode()
    path.write_bytes(data)
    return data


def _records(stream: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def _observer(tmp_path: Path, **kwargs: Any) -> tuple[Observer, io.StringIO, Archive]:
    saves = tmp_path / "Saves"
    saves.mkdir(exist_ok=True)
    stream = io.StringIO()
    log = Log(stream)
    archive = Archive(tmp_path / "archive", log)
    return Observer(saves, log, archive, **kwargs), stream, archive


def test_added_save_has_hash_game_time_and_no_other_value(tmp_path: Path) -> None:
    observer, stream, archive = _observer(tmp_path)
    observer.start(0.2)
    _save(observer.directory / "Autosave.json", "2/22/2046 12:00:00 AM", '"playerFactionName": "Secret"')
    observer.poll()
    archive.close()
    added = [record for record in _records(stream) if record["event"] == "added"]
    assert len(added) == 1
    assert added[0]["name"] == "Autosave.json"
    assert added[0]["game_time"] == "2/22/2046 12:00:00 AM"
    assert len(added[0]["sha256"]) == 64
    assert added[0]["archive"] == "queued"
    assert set(added[0]) <= RECORD_KEYS
    assert "Secret" not in stream.getvalue()


def test_rewrite_keeps_the_inode_and_rename_moves_it(tmp_path: Path) -> None:
    saves = tmp_path / "Saves"
    saves.mkdir()
    _save(saves / "Autosave.json", "1/1/2030 12:00:00 AM")
    first = scan(saves)
    _save(saves / "Autosave.json", "1/8/2030 12:00:00 AM", " " * 10)
    rewritten = scan(saves)
    assert changes(first, rewritten) == [("changed", "Autosave.json")]
    assert rewritten["Autosave.json"].inode == first["Autosave.json"].inode
    os.replace(saves / "Autosave.json", saves / "Autosave2.json")
    renamed = scan(saves)
    assert changes(rewritten, renamed) == [("removed", "Autosave.json"), ("added", "Autosave2.json")]
    assert renamed["Autosave2.json"].inode == rewritten["Autosave.json"].inode


def test_other_files_are_hashed_but_neither_dated_nor_archived(tmp_path: Path) -> None:
    observer, stream, archive = _observer(tmp_path)
    (observer.directory / "PlayerOptions.TIProfile").write_text('"gameTimeString": "1/1/2030 12:00:00 AM"')
    observer.start(0.2)
    archive.close()
    (present,) = [record for record in _records(stream) if record["event"] == "present"]
    assert "game_time" not in present
    assert present["archive"] == "not_save"
    assert list(archive.directory.iterdir()) == []


def test_a_settled_version_is_archived_once(tmp_path: Path) -> None:
    observer, stream, archive = _observer(tmp_path)
    data = _save(observer.directory / "Quicksave.json", "3/1/2031 12:00:00 AM")
    observer.start(0.2)
    (observer.directory / "Exitsave.json").write_bytes(data)
    observer.poll()
    archive.close()
    records = _records(stream)
    assert [record["archive"] for record in records if "archive" in record] == ["queued", "duplicate"]
    (stored,) = archive.directory.iterdir()
    assert stored.name == f"{records[1]['sha256']}.json.xz"
    assert lzma.decompress(stored.read_bytes()) == data
    assert [record["event"] for record in records].count("archived") == 1


def test_a_read_that_overlaps_a_write_is_unstable_and_read_again(tmp_path: Path) -> None:
    writes = iter([" " * 100])

    def read(path: Path) -> bytes:
        data = path.read_bytes()
        padding = next(writes, None)
        if padding is not None:
            with open(path, "a", encoding="utf-8") as stream:
                stream.write(padding)
            os.utime(path, ns=(1, path.stat().st_mtime_ns + 1_000_000))
        return data

    observer, stream, archive = _observer(tmp_path, read=read)
    observer.start(0.2)
    _save(observer.directory / "Autosave.json", "1/1/2030 12:00:00 AM")
    observer.poll()
    observer.poll()
    observer.poll()
    archive.close()
    described = [record for record in _records(stream) if "archive" in record]
    assert [(record["event"], record["archive"]) for record in described] == [
        ("added", "unstable"),
        ("changed", "queued"),
    ]
    assert described[0]["unstable"] is True
    assert observer.retry == {}


def test_a_failed_read_is_retried_while_the_listing_is_unchanged(tmp_path: Path) -> None:
    failures = iter([PermissionError(), PermissionError()])

    def read(path: Path) -> bytes:
        failure = next(failures, None)
        if failure is not None:
            raise failure
        return path.read_bytes()

    observer, stream, archive = _observer(tmp_path, read=read)
    _save(observer.directory / "Autosave.json", "1/1/2030 12:00:00 AM")
    observer.start(0.2)
    observer.poll()
    observer.poll()
    observer.poll()
    archive.close()
    described = [record for record in _records(stream) if "archive" in record]
    assert [(record["event"], record["archive"]) for record in described] == [
        ("present", "error"),
        ("reread", "error"),
        ("reread", "queued"),
    ]
    assert described[0]["error"] == "PermissionError"


def test_notes_are_logged_with_their_time(tmp_path: Path) -> None:
    observer, stream, archive = _observer(tmp_path)
    notes: queue.Queue[tuple[int, str]] = queue.Queue()
    notes.put((1_700_000_000_000_000_000, "loaded Resistsave00075"))
    observer.start(0.2)
    observer.poll(notes)
    archive.close()
    (note,) = [record for record in _records(stream) if record["event"] == "note"]
    assert note["text"] == "loaded Resistsave00075"
    assert note["observed_ns"] == 1_700_000_000_000_000_000


def test_game_time_is_read_from_the_header_only() -> None:
    assert game_time(b'{"gameTimeString": "1/1/2030 12:00:00 AM"}') == "1/1/2030 12:00:00 AM"
    assert game_time(b" " * 70_000 + b'"gameTimeString": "1/1/2030 12:00:00 AM"') is None


def test_observe_leaves_the_save_directory_untouched(tmp_path: Path) -> None:
    saves = tmp_path / "Saves"
    saves.mkdir()
    _save(saves / "Autosave.json", "1/1/2030 12:00:00 AM")
    before = {name: (entry.size, entry.mtime_ns) for name, entry in scan(saves).items()}
    polls = iter(range(3))
    out = tmp_path / "private" / "log.jsonl"
    observe(saves, out, tmp_path / "private" / "archive", 0.001, stop=lambda: next(polls, None) is None)
    assert {name: (entry.size, entry.mtime_ns) for name, entry in scan(saves).items()} == before
    events = [json.loads(line)["event"] for line in out.read_text(encoding="utf-8").splitlines()]
    assert events[0] == "start"
    assert events[-1] == "stop"
    assert "archived" in events


@pytest.mark.parametrize("option", ["--out", "--archive"])
def test_outputs_inside_the_save_directory_are_refused(tmp_path: Path, option: str) -> None:
    saves = tmp_path / "Saves"
    saves.mkdir()
    paths = {"--out": tmp_path / "log.jsonl", "--archive": tmp_path / "archive"}
    paths[option] = saves / "inside"
    arguments = [str(saves), "--out", str(paths["--out"]), "--archive", str(paths["--archive"])]
    assert main(arguments) == 2
    assert list(saves.iterdir()) == []


def test_a_missing_directory_is_refused(tmp_path: Path) -> None:
    arguments = [str(tmp_path / "absent"), "--out", str(tmp_path / "log"), "--archive", str(tmp_path / "a")]
    assert main(arguments) == 2
