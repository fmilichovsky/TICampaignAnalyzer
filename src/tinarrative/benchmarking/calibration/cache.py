"""The calibration cache under ``--out``: its key, its ``status.js``, and the atomic rebuild of the table."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

import tinarrative
from tinarrative.benchmarking.calibration import table
from tinarrative.benchmarking.manifest import MANIFEST

Status = Literal["fresh", "rebuilding", "failed"]
REBUILD_PREFIX: Final = ".rebuild-"
RETIRED_PREFIX: Final = ".retired-"


class CalibrationCacheError(ValueError):
    """The rebuild of the calibration table failed; the previous table, if any, is left in place."""


@dataclass(frozen=True)
class CacheCheck:
    """What ``check`` found under ``out``: the key the samples and the package give, and the cached one."""

    out: Path
    key: str
    existing: str | None
    """The key in ``index.js``; None when there is no readable table."""

    @property
    def fresh(self) -> bool:
        return self.existing == self.key


def package_directory() -> Path:
    return Path(tinarrative.__file__).parent


def cache_key(samples: Path, *, package: Path | None = None) -> str:
    """sha256 over every package file (path and bytes, ``__pycache__`` skipped) and the bytes of ``samples.json``.

    A dirty working tree is part of the key: an edit gives a new key, and reverting it gives the old one back.
    """
    root = package or package_directory()
    digest = hashlib.sha256()
    files = sorted(
        (path.relative_to(root).as_posix(), path)
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.relative_to(root).parts
    )
    for name, path in [*files, (MANIFEST, samples / MANIFEST)]:
        content = path.read_bytes()
        digest.update(name.encode("utf-8") + b"\0" + len(content).to_bytes(8, "big") + content)
    return digest.hexdigest()


def check(samples: Path, out: Path) -> CacheCheck:
    """The key for ``samples`` against the one cached under ``out``; a missing or broken ``index.js`` is stale."""
    try:
        existing = table.read_index(out / "index.js").get("key")
    except (OSError, table.CalibrationTableError):
        existing = None
    return CacheCheck(out, cache_key(samples), existing if isinstance(existing, str) else None)


def refresh(
    samples: Path,
    out: Path,
    *,
    rebuild: bool = False,
    on_stale: Callable[[CacheCheck], None] | None = None,
) -> CacheCheck:
    """Make the table under ``out`` current for ``samples`` and write ``status.js``; the check it acted on.

    ``on_stale`` runs after a stale (or ``rebuild``) table is found and before the rebuild starts, so a caller can
    show the old table first. Raises ``CalibrationCacheError`` when the extraction fails, after writing ``failed``;
    an ``OSError`` means ``out`` cannot be written.
    """
    out.mkdir(parents=True, exist_ok=True)
    found = check(samples, out)
    if found.fresh and not rebuild:
        _status(out, found.key, "fresh")
        return found
    if on_stale is not None:
        on_stale(found)
    _status(out, found.key, "rebuilding")
    scratch = Path(tempfile.mkdtemp(prefix=REBUILD_PREFIX, dir=out))
    try:
        try:
            table.extract_all(samples, scratch, key=found.key)
        except Exception as error:  # any pipeline failure is reported as a failed rebuild (exit 2)
            message = f"{type(error).__name__}: {error}"
            _status(out, found.key, "failed", message)
            raise CalibrationCacheError(f"cannot extract the calibration table: {message}") from error
        _swap(scratch, out)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    _status(out, found.key, "fresh")
    return found


def _swap(scratch: Path, out: Path) -> None:
    """Move the new tables into place, then ``index.js``: its key changes only once the tables it names are there."""
    tables = out / "tables"
    retired = Path(tempfile.mkdtemp(prefix=RETIRED_PREFIX, dir=out))
    (scratch / "tables").mkdir(exist_ok=True)
    try:
        if tables.exists():
            tables.rename(retired / "tables")
        try:
            (scratch / "tables").rename(tables)
        except OSError:
            if (retired / "tables").exists():
                (retired / "tables").rename(tables)
            raise
        (scratch / "index.js").replace(out / "index.js")
    finally:
        shutil.rmtree(retired, ignore_errors=True)


def _status(out: Path, key: str, state: Status, message: str = "") -> None:
    written_at = datetime.now(UTC).isoformat(timespec="seconds")
    table.write_status(out, {"key": key, "state": state, "message": message, "written_at": written_at})
