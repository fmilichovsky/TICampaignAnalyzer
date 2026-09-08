"""Normalized state extracted from one save."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SaveSnapshot:
    """A semantic snapshot, deliberately independent of serialized save shape."""

    source: str
    date: str
    game_version: str | None = None
    timestamp: datetime | None = None
    turn: int | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)
