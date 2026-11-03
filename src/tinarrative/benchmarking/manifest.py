"""Read, verify, and rebuild the benchmark sample manifest."""

from __future__ import annotations

import hashlib
import json
import lzma
from pathlib import Path
from typing import Any

MANIFEST = "samples.json"
SAMPLE_SUFFIX = ".json.xz"


def sample_files(samples: Path) -> dict[str, list[Path]]:
    """The compressed saves of every campaign directory under ``samples``, by campaign, in name order."""
    return {
        directory.name: sorted(path for path in directory.iterdir() if path.name.endswith(SAMPLE_SUFFIX))
        for directory in sorted(path for path in samples.iterdir() if path.is_dir())
    }


def verify_samples(samples: Path) -> list[str]:
    """Human-readable differences between ``samples`` and its manifest; empty when they match."""
    try:
        manifest = json.loads((samples / MANIFEST).read_text(encoding="utf-8"))
        limit = manifest["max_file_bytes"]
        listed: dict[str, Any] = manifest["campaigns"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        return [f"cannot read {MANIFEST}: {error}"]
    errors: list[str] = []
    found = sample_files(samples)
    for campaign in sorted(set(listed) | set(found)):
        entry = listed.get(campaign)
        if entry is None:
            errors.append(f"{campaign}: not listed in {MANIFEST}")
            continue
        if not str(entry.get("description", "")).strip():
            errors.append(f"{campaign}: no description")
        files = entry.get("files", {})
        paths = {path.name: path for path in found.get(campaign, [])}
        if not paths:
            errors.append(f"{campaign}: no {SAMPLE_SUFFIX} files")
        for name in sorted(set(files) | set(paths)):
            if name not in paths:
                errors.append(f"{campaign}/{name}: listed but missing")
            elif name not in files:
                errors.append(f"{campaign}/{name}: not listed in {MANIFEST}")
            else:
                size = paths[name].stat().st_size
                if size > limit:
                    errors.append(f"{campaign}/{name}: {size} bytes, over max_file_bytes {limit}")
                if size != files[name].get("bytes") or sha256_file(paths[name]) != files[name].get("sha256"):
                    errors.append(f"{campaign}/{name}: does not match its size and SHA-256 in {MANIFEST}")
    return errors


def update_samples(samples: Path) -> dict[str, Any]:
    """The manifest for the files under ``samples``, keeping the limit and the descriptions of the current one."""
    path = samples / MANIFEST
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    descriptions = {name: entry.get("description", "") for name, entry in current.get("campaigns", {}).items()}
    campaigns: dict[str, Any] = {}
    for campaign, files in sample_files(samples).items():
        entries = {}
        for file in files:
            with lzma.open(file) as handle:
                raw = sum(len(block) for block in iter(lambda: handle.read(1 << 20), b""))
            entries[file.name] = {"sha256": sha256_file(file), "bytes": file.stat().st_size, "raw_bytes": raw}
        campaigns[campaign] = {"description": descriptions.get(campaign, ""), "files": entries}
    return {"max_file_bytes": current.get("max_file_bytes", 5_000_000), "campaigns": campaigns}


def sha256_file(path: Path) -> str:
    """Return a file's SHA-256 digest without reading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
