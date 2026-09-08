"""Protocol shared by independently testable analyzers."""

from typing import Protocol

from ..diff.state_diff import StateDiff
from ..model.events import Event
from ..model.snapshot import SaveSnapshot


class Analyzer(Protocol):
    def analyze(
        self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff
    ) -> list[Event]: ...
