"""Diff entry point; result types live in the model layer."""

from ..model.changes import StateChange, StateDiff
from ..model.snapshot import SaveSnapshot

__all__ = ["StateChange", "StateDiff", "diff_states"]


def diff_states(before: SaveSnapshot, after: SaveSnapshot) -> StateDiff:
    """Create an empty deterministic diff until normalized domains are implemented."""
    return StateDiff(before=before, after=after)
