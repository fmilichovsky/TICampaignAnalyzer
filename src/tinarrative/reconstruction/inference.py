"""Combine objective evidence into conservative inferred events."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable

from ..log import fields as log_fields
from ..log import get_logger
from ..model.changes import StateDiff
from ..model.events import Confidence, Event
from ..model.snapshot import SaveSnapshot
from .rules import territorial_events

logger = get_logger(__name__)


def infer_events(events: Iterable[Event], before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
    """The inferred events the rules reconstruct from one interval's objective events, sorted by date, type and ID.

    The snapshots and the diff are context, as for an analyzer; inferred events in ``events`` are ignored, so a
    rule never builds on another inference. A duplicate ID is a programming error.
    """
    inferred = territorial_events(events, before, after, diff)
    ids = Counter(event.id for event in inferred)
    duplicates = sorted(event_id for event_id, count in ids.items() if count > 1)
    if duplicates:
        raise ValueError(f"reconstruction produced duplicate event IDs: {duplicates[:3]}")
    if logger.isEnabledFor(logging.DEBUG):
        counts = Counter(event.confidence.value for event in inferred)
        logger.debug(
            "reconstruction done %s",
            log_fields(events=len(inferred), **{level.value: counts.get(level.value, 0) for level in Confidence}),
        )
    return sorted(inferred, key=lambda event: event.sort_key)
