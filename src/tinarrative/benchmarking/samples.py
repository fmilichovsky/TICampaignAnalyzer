"""Import campaign saves into the package-size benchmark samples."""

from __future__ import annotations

import hashlib
import json
import lzma
import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..grouping import CampaignGroup, group_saves
from ..io.save_discovery import SaveInput, expand_inputs
from ..parsing.errors import SaveLoadError
from ..sequence import SaveRef, SkippedSave, survey
from .manifest import MANIFEST

DEFAULT_MAX_FILE_BYTES = 5_000_000
CHUNK_BYTES = 1 << 20


class ProgressReporter(Protocol):
    """The progress interface a benchmark operation needs from the CLI."""

    def update(self, phase: str, completed: int, total: int | None = None, filename: str | None = None) -> None: ...

    def finish(self, activity: str = "parsing and processing") -> None: ...


class SampleImportError(Exception):
    """A user-facing sample import failure and its CLI exit status."""

    def __init__(self, message: str, exit_code: int, *, reported: bool = False) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.reported = reported


@dataclass(frozen=True)
class SampleImportResult:
    """The campaign successfully imported and any unusable directory entries skipped along the way."""

    name: str
    files: int
    description: str
    skipped: tuple[SkippedSave, ...]


CampaignChooser = Callable[[Sequence[CampaignGroup], str | None], CampaignGroup | int]
ProgressFactory = Callable[[int], ProgressReporter]


def import_sample_campaign(
    name: str,
    paths: Sequence[Path],
    *,
    description: str | None,
    selector: str | None,
    samples_dir: Path,
    progress_factory: ProgressFactory,
    choose_campaign: CampaignChooser,
) -> SampleImportResult:
    """Validate, survey, select, compress, and install one benchmark sample campaign."""
    validate_sample_inputs(name, paths, selector)
    inputs = expand_inputs(paths)
    progress = progress_factory(len(inputs))
    try:
        surveyed, skipped = _survey_sample_inputs(inputs, progress)
        if not surveyed:
            raise SampleImportError("no usable saves", 4)
        sources = _select_source_files(paths, surveyed, selector, choose_campaign)
        manifest, previous_campaigns = _read_manifest(samples_dir)
        campaign_description = _description(name, description, previous_campaigns)
        file_names = _sample_file_names(sources)
        max_file_bytes = _max_file_bytes(manifest)

        try:
            samples_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".sample-", dir=samples_dir) as temporary:
                temporary_root = Path(temporary)
                staged_campaign = _compress_sources(sources, file_names, temporary_root, max_file_bytes, progress)
                file_entries = _sample_entries(staged_campaign)
                updated_manifest = _updated_manifest(
                    name, campaign_description, file_entries, previous_campaigns, max_file_bytes
                )
                manifest_temp = temporary_root / MANIFEST
                _write_manifest(updated_manifest, manifest_temp, progress)
                _replace_campaign(
                    samples_dir / name,
                    staged_campaign,
                    manifest_temp,
                    samples_dir / MANIFEST,
                    temporary_root / "previous",
                )
        except SampleImportError:
            raise
        except (OSError, lzma.LZMAError) as error:
            raise SampleImportError(f"cannot import samples: {error}", 9) from error
        progress.update("Updating manifest", 1, 1, MANIFEST)
        return SampleImportResult(name, len(sources), campaign_description, tuple(skipped))
    finally:
        progress.finish("import")


def validate_sample_inputs(name: str, paths: Sequence[Path], selector: str | None) -> None:
    """Reject unsafe campaign names and path/selector combinations before reading saves."""
    if not name or name in {".", "..", MANIFEST} or Path(name).name != name or "/" in name or "\\" in name:
        raise SampleImportError("NAME must be one directory name", 2)
    if len(paths) > 1 and any(path.is_dir() for path in paths):
        raise SampleImportError("pass one directory or a list of save files", 2)
    if selector is not None and (len(paths) != 1 or not paths[0].is_dir()):
        raise SampleImportError("--campaign requires one directory input", 2)


def _survey_sample_inputs(
    inputs: Sequence[SaveInput], progress: ProgressReporter
) -> tuple[list[SaveRef], list[SkippedSave]]:
    """Survey named files strictly and directory members as skippable candidates."""
    surveyed: list[SaveRef] = []
    skipped: list[SkippedSave] = []
    usable: dict[Path, int] = {}
    for index, item in enumerate(inputs, start=1):
        progress.update("Scanning saves", index, filename=item.path.name)
        if item.empty_directory:
            raise SampleImportError(f"{item.path}: the directory holds no files", 4)
        try:
            save = survey(item.path)
        except OSError as error:
            reason = error.strerror or str(error)
            if item.directory is None:
                raise SampleImportError(f"cannot read {item.path}: {reason}", 4) from error
            skipped.append(SkippedSave(str(item.path), type(error).__name__, reason))
            continue
        except SaveLoadError as error:
            if item.directory is None:
                raise SampleImportError(f"{item.path}: {error}", 5) from error
            skipped.append(SkippedSave(str(item.path), type(error).__name__, str(error)))
            continue
        surveyed.append(save)
        if item.directory is not None:
            usable[item.directory] = usable.get(item.directory, 0) + 1

    for directory in {item.directory for item in inputs if item.directory is not None}:
        if usable.get(directory, 0) == 0:
            raise SampleImportError(f"{directory}: the directory holds no usable save", 4)
    return surveyed, skipped


def _select_source_files(
    paths: Sequence[Path],
    surveyed: Sequence[SaveRef],
    selector: str | None,
    choose_campaign: CampaignChooser,
) -> list[Path]:
    """Return every input file for the explicit list or the chosen directory campaign."""
    if len(paths) == 1 and paths[0].is_dir():
        selected = choose_campaign(group_saves(surveyed), selector)
        if isinstance(selected, int):
            raise SampleImportError("campaign selection failed", selected, reported=True)
        return sorted({Path(path) for save in selected.members for path in (save.source, *save.aliases)})
    return [Path(save.source) for save in surveyed]


def _read_manifest(samples_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read manifest settings and the existing campaign map, or raise a clear file error."""
    manifest_path = samples_dir / MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    except (OSError, json.JSONDecodeError) as error:
        raise SampleImportError(f"cannot read sample manifest: {error}", 9) from error
    if not isinstance(manifest, dict):
        raise SampleImportError(f"{MANIFEST} must contain a JSON object", 9)
    campaigns = manifest.get("campaigns", {})
    if not isinstance(campaigns, dict):
        raise SampleImportError(f"{MANIFEST} campaigns must be an object", 9)
    return manifest, campaigns


def _description(name: str, supplied: str | None, campaigns: dict[str, Any]) -> str:
    """Use an explicit description or retain the one already recorded for the campaign."""
    if supplied is not None:
        return supplied
    entry = campaigns.get(name, {})
    description = entry.get("description", "") if isinstance(entry, dict) else ""
    return description if isinstance(description, str) else ""


def _sample_file_names(sources: Sequence[Path]) -> list[str]:
    """Map every input to the manifest's ``.json.xz`` naming convention and reject collisions."""
    names = [f"{source.stem}.json.xz" for source in sources]
    if len(set(names)) != len(names):
        raise SampleImportError("input saves produce colliding sample file names", 9)
    return names


def _max_file_bytes(manifest: dict[str, Any]) -> int:
    """Read and validate the compressed-save size limit from the manifest."""
    limit = manifest.get("max_file_bytes", DEFAULT_MAX_FILE_BYTES)
    if not isinstance(limit, int) or limit <= 0:
        raise SampleImportError(f"{MANIFEST} max_file_bytes must be a positive integer", 9)
    return limit


def _compress_sources(
    sources: Sequence[Path],
    names: Sequence[str],
    temporary_root: Path,
    max_file_bytes: int,
    progress: ProgressReporter,
) -> Path:
    """Write all saves to a staged campaign with the documented xz extreme preset."""
    staged_campaign = temporary_root / "campaign"
    staged_campaign.mkdir()
    for index, (source, name) in enumerate(zip(sources, names, strict=True), start=1):
        progress.update("Compressing saves", index, len(sources), source.name)
        destination = staged_campaign / name
        with source.open("rb") as input_file, destination.open("wb") as output_file:
            compressor = lzma.LZMACompressor(format=lzma.FORMAT_XZ, preset=9 | lzma.PRESET_EXTREME)
            while block := input_file.read(CHUNK_BYTES):
                output_file.write(compressor.compress(block))
            output_file.write(compressor.flush())
        size = destination.stat().st_size
        if size > max_file_bytes:
            raise SampleImportError(f"{name}: {size} bytes exceeds max_file_bytes {max_file_bytes}", 9)
    return staged_campaign


def _sample_entries(staged_campaign: Path) -> dict[str, dict[str, int | str]]:
    """Describe compressed files using the manifest's byte counts and SHA-256 digests."""
    entries: dict[str, dict[str, int | str]] = {}
    for path in sorted(staged_campaign.iterdir()):
        raw_size = 0
        with lzma.open(path, "rb") as stream:
            while block := stream.read(CHUNK_BYTES):
                raw_size += len(block)
        entries[path.name] = {
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
            "raw_bytes": raw_size,
        }
    return entries


def _sha256(path: Path) -> str:
    """Hash a file in bounded-memory chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def _updated_manifest(
    name: str,
    description: str,
    entries: dict[str, dict[str, int | str]],
    existing_campaigns: dict[str, Any],
    max_file_bytes: int,
) -> dict[str, Any]:
    """Replace one campaign entry while preserving the other manifest entries."""
    campaigns = dict(existing_campaigns)
    campaigns[name] = {"description": description, "files": entries}
    return {"max_file_bytes": max_file_bytes, "campaigns": campaigns}


def _write_manifest(manifest: dict[str, Any], path: Path, progress: ProgressReporter) -> None:
    """Write the staged manifest and report its pending file operation."""
    progress.update("Updating manifest", 0, 1, MANIFEST)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _replace_campaign(
    campaign_dir: Path,
    staged_campaign: Path,
    staged_manifest: Path,
    manifest_path: Path,
    backup: Path,
) -> None:
    """Swap the campaign directory and manifest together, restoring the old directory on failure."""
    if campaign_dir.exists():
        campaign_dir.rename(backup)
    try:
        staged_campaign.rename(campaign_dir)
        staged_manifest.replace(manifest_path)
    except OSError:
        if campaign_dir.exists():
            shutil.rmtree(campaign_dir)
        if backup.exists():
            backup.rename(campaign_dir)
        raise
