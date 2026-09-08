"""Diff result types and the future snapshot comparison entry point."""

from dataclasses import dataclass, field

from ..model.changes import StateChange
from ..model.snapshot import SaveSnapshot


@dataclass(frozen=True)
class StateDiff:
    before: SaveSnapshot
    after: SaveSnapshot
    changes: list[StateChange] = field(default_factory=list)


def diff_states(before: SaveSnapshot, after: SaveSnapshot) -> StateDiff:
    """Create an empty deterministic diff until normalized domains are implemented."""
    return StateDiff(before=before, after=after)
