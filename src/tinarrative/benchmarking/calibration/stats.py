"""Percentiles for the calibration report: how a share, or a world quantity, is spread."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

PERCENTILES: Final = (10, 25, 50, 75, 90)
"""The percentiles the distribution view prints, as ``p10`` .. ``p90``."""


def percentiles(values: Sequence[float]) -> dict[str, float | int] | None:
    """``n`` and the ``PERCENTILES`` of ``values`` by linear interpolation between the closest ranks; ``None`` for no
    values."""
    ordered = sorted(values)
    if not ordered:
        return None
    found: dict[str, float | int] = {"n": len(ordered)}
    for percent in PERCENTILES:
        position = (len(ordered) - 1) * percent / 100
        low = math.floor(position)
        high = math.ceil(position)
        found[f"p{percent}"] = ordered[low] + (ordered[high] - ordered[low]) * (position - low)
    return found
