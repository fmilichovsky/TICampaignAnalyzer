"""How much of each event type and measure the sample campaigns cover.

``coverage_label`` is the one place that decides *thin*; the report, and later the evidence block and sample
admission, reuse it. The campaigns counted are the table's, which holds the reviewable ones only (a campaign that is
a ``prefix_of`` another is never extracted).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, Final

THIN_TOTAL: Final = 5
"""Fewer occurrences than this in total read thin, as does a count in one campaign only."""
THIN: Final = "thin"
COVERED: Final = "covered"

Tables = Mapping[str, Sequence[Mapping[str, Any]]]


def coverage_label(campaigns: Mapping[str, int]) -> str:
    """``thin`` when the occurrences, per campaign, fall in one campaign only or total fewer than ``THIN_TOTAL``."""
    present = sum(1 for count in campaigns.values() if count > 0)
    return THIN if present < 2 or sum(campaigns.values()) < THIN_TOTAL else COVERED


def coverage(index: Mapping[str, Any], tables: Tables) -> dict[str, dict[str, dict[str, Any]]]:
    """Each event type's and each measure's occurrences per campaign, their total and label, in the index's order.

    A measure occurs once in each row that carries a share on it. A type or measure no row has still appears, thin.
    """
    types = {name: Counter[str]() for name in index["kinds"]}
    measures = {name: Counter[str]() for name in index["measures"]}
    for campaign, rows in tables.items():
        for item in rows:
            types.setdefault(item["type"], Counter())[campaign] += 1
            for measure in {share["measure"] for share in item["shares"]}:
                measures.setdefault(measure, Counter())[campaign] += 1
    return {"types": _entries(types, tables), "measures": _entries(measures, tables)}


def _entries(counts: Mapping[str, Counter[str]], tables: Tables) -> dict[str, dict[str, Any]]:
    entries = {}
    for name, counter in counts.items():
        campaigns = {campaign: counter[campaign] for campaign in tables}
        entries[name] = {"campaigns": campaigns, "total": sum(campaigns.values()), "label": coverage_label(campaigns)}
    return entries
