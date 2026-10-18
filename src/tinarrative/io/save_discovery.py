"""Discover candidate save files and expand the paths given on a command line."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SaveInput:
    """One candidate file: given on the command line (``explicit``) or found inside a given ``directory``."""

    path: Path
    explicit: bool
    empty_directory: bool = False
    directory: Path | None = None
    """The given directory a found file came from; ``None`` for a path given on the command line."""


def discover_saves(directory: Path) -> list[Path]:
    """Return files in a deterministic order until save naming is understood."""
    return sorted(path for path in directory.iterdir() if path.is_file())


def expand_inputs(paths: Sequence[Path]) -> tuple[SaveInput, ...]:
    """Files stay as given; a directory contributes its files in ``discover_saves`` order, one level deep.

    A directory that holds no files yields one ``empty_directory`` input; one that cannot be listed stays as an
    explicit input, so reading it fails like any unreadable path.
    """
    inputs: list[SaveInput] = []
    for path in paths:
        if path.is_dir():
            try:
                files = discover_saves(path)
            except OSError:
                inputs.append(SaveInput(path, explicit=True))
                continue
            if not files:
                inputs.append(SaveInput(path, explicit=True, empty_directory=True))
            inputs.extend(SaveInput(file, explicit=False, directory=path) for file in files)
        else:
            inputs.append(SaveInput(path, explicit=True))
    return tuple(inputs)
