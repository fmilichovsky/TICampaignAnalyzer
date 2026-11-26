"""Read, verify, decompress and rebuild the benchmark samples and their manifest."""

from __future__ import annotations

import hashlib
import json
import lzma
import os
import shutil
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .profile import PROFILE_FIELDS, read_samples, sample_profile

MANIFEST = "samples.json"
SAMPLE_SUFFIX = ".json.xz"


def sample_files(samples: Path) -> dict[str, list[Path]]:
    """The compressed saves of every campaign directory under ``samples``, by campaign, in name order."""
    return {
        directory.name: sorted(path for path in directory.iterdir() if path.name.endswith(SAMPLE_SUFFIX))
        for directory in sorted(path for path in samples.iterdir() if path.is_dir())
    }


def decompress_samples(files: Iterable[Path], directory: Path) -> None:
    """Decompress compressed saves into ``directory``, each under its name without ``.xz``."""
    paths = list(files)
    if not paths:
        return
    # lzma releases the GIL while decoding, so threads give real parallelism.
    with ThreadPoolExecutor(max_workers=min(len(paths), os.cpu_count() or 1)) as pool:
        for _ in pool.map(lambda file: _decompress_one(file, directory), paths):
            pass


def _decompress_one(file: Path, directory: Path) -> None:
    with lzma.open(file) as source, (directory / file.name.removesuffix(".xz")).open("wb") as target:
        shutil.copyfileobj(source, target, 1 << 20)


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
        errors.extend(_profile_errors(campaign, entry.get("profile"), len(files)))
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


def _profile_errors(campaign: str, profile: object, listed: int) -> list[str]:
    fix = "run benchmark metrics samples --update"
    if not isinstance(profile, dict):
        return [f"{campaign}: no profile; {fix}"]
    if tuple(profile) != PROFILE_FIELDS:
        return [f"{campaign}: profile fields are not {', '.join(PROFILE_FIELDS)}; {fix}"]
    if profile["saves"] != listed:
        return [f"{campaign}: profile counts {profile['saves']} saves, {listed} listed; {fix}"]
    return []


def campaign_entry(description: str, files: Sequence[Path], previous: object) -> dict[str, Any]:
    """The manifest entry of one campaign's compressed ``files``: its profile and each file's size and SHA-256,
    keeping the ``prefix_of`` of the ``previous`` entry."""
    saves = read_samples(files)
    entry: dict[str, Any] = {"description": description}
    if isinstance(previous, dict) and isinstance(previous.get("prefix_of"), str):
        entry["prefix_of"] = previous["prefix_of"]
    entry["profile"] = sample_profile(saves)
    entry["files"] = {
        file.name: {"sha256": sha256_file(file), "bytes": file.stat().st_size, "raw_bytes": save.raw_bytes}
        for file, save in zip(files, saves, strict=True)
    }
    return entry


def update_samples(samples: Path) -> dict[str, Any]:
    """The manifest for the files under ``samples``, keeping the limit and the descriptions of the current one."""
    path = samples / MANIFEST
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    previous = current.get("campaigns", {})
    campaigns = {
        campaign: campaign_entry(previous.get(campaign, {}).get("description", ""), files, previous.get(campaign))
        for campaign, files in sample_files(samples).items()
    }
    return {"max_file_bytes": current.get("max_file_bytes", 5_000_000), "campaigns": campaigns}


def extractable_campaigns(samples: Path) -> dict[str, list[Path]]:
    """The campaigns worth extracting: every sample campaign that is not a ``prefix_of`` another."""
    manifest = json.loads((samples / MANIFEST).read_text(encoding="utf-8"))
    prefixes = {name for name, entry in manifest["campaigns"].items() if entry.get("prefix_of")}
    return {name: files for name, files in sample_files(samples).items() if name not in prefixes}


def raw_sizes(samples: Path, campaign: str, files: Iterable[Path]) -> dict[str, int]:
    """The decompressed size of each of ``files`` of ``campaign``, by decompressed name, as the manifest lists it; a
    file it lists without one counts as its compressed size."""
    manifest = json.loads((samples / MANIFEST).read_text(encoding="utf-8"))
    listed = manifest["campaigns"].get(campaign, {}).get("files", {})
    sizes: dict[str, int] = {}
    for file in files:
        raw = listed.get(file.name, {}).get("raw_bytes")
        sizes[file.name.removesuffix(".xz")] = raw if isinstance(raw, int) else file.stat().st_size
    return sizes


def prefix_of(samples: Path, campaign: str) -> str | None:
    """The campaign ``campaign`` is a leading slice of, or None."""
    manifest = json.loads((samples / MANIFEST).read_text(encoding="utf-8"))
    value = manifest["campaigns"].get(campaign, {}).get("prefix_of")
    return value if isinstance(value, str) else None


def sha256_file(path: Path) -> str:
    """Return a file's SHA-256 digest without reading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
