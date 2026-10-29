"""Per-capita GDP booms and slumps from the save's quarterly series (``tracker_PCGDP_ByQuarter``).

A trend is the change over the trailing ``TREND_QUARTERS``; an event fires at the quarter it first leaves the
``BOOM``/``-SLUMP`` band and is record-dated by that quarter. A zero value or negative key breaks the window, so no
trend spans a quarter with nothing held or the template history before the start. See
``docs/game-data-notes/nation-metrics.md`` ("Per-capita GDP by quarter").
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from ...model.changes import ChangeKind, StateChange, StateDiff
from ...model.entities import EntityDomain
from ...model.events import Event
from ...model.snapshot import SaveSnapshot
from ...model.values import FrozenMap
from ..common import ChangeIndex, EventBuilder, Lookup, primary
from .nation_metrics import number, placeholder

PCGDP_TREND = "nation.pcgdp_trend"
SERIES = "tracker_PCGDP_ByQuarter"
TREND_QUARTERS = 20
"""The trailing window of a trend: five years."""
BOOM = 0.5
"""A trend above +50 % is a boom, well beyond the routine five-year change (notes, "Per-capita GDP by quarter")."""
SLUMP = 0.25
"""A trend below -25 % is a slump, as far beyond the routine five-year fall."""
BOOM_DIRECTION = "boom"
SLUMP_DIRECTION = "slump"
MONTHS_PER_QUARTER = 3


@dataclass(frozen=True)
class NationEconomyAnalyzer:
    before_sequence: bool = False
    """Judge the quarters already in the earlier save instead of the ones added in the interval.

    For the first interval of a sequence that starts late; it judges quarters disjoint from the default instance's,
    so event IDs never collide.
    """

    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = ChangeIndex(diff)
        lookup = Lookup(before, after)
        build = EventBuilder(before, after)
        start = campaign_start(after)
        events: list[Event] = []
        for change in index.fields(EntityDomain.NATION, SERIES):
            events.extend(self._trends(change, start, lookup, build))
        return events

    def _trends(self, change: StateChange, start: datetime | None, lookup: Lookup, build: EventBuilder) -> list[Event]:
        nation = change.entity_id
        if change.kind is not ChangeKind.MAP or nation is None or placeholder(nation, lookup):
            return []
        earlier, later = quarter_series(change.before), quarter_series(change.after)
        judged = earlier.keys() if self.before_sequence else later.keys() - earlier.keys()
        events: list[Event] = []
        for quarter in sorted(judged):
            direction = new_trend(later, quarter)
            if direction is None:
                continue
            first = quarter - TREND_QUARTERS
            events.append(
                build.event(
                    PCGDP_TREND,
                    id_parts=(nation, quarter),
                    sources=(primary(change, member=str(quarter)),),
                    entities=(lookup.ref(nation),),
                    attributes=(
                        ("direction", direction),
                        ("quarter", quarter),
                        ("window_quarters", TREND_QUARTERS),
                        ("window_start", quarter_date(start, first)),
                        ("before", later[first]),
                        ("after", later[quarter]),
                        ("change", later[quarter] / later[first] - 1),
                        ("before_sequence", self.before_sequence),
                    ),
                    recorded_on=quarter_date(start, quarter),
                )
            )
        return events


def quarter_series(value: object) -> dict[int, float]:
    """The numeric entries of a quarter map by integer quarter; keys that are not integers are left out."""
    if not isinstance(value, FrozenMap):
        return {}
    series: dict[int, float] = {}
    for key, item in value.items:
        amount = number(item)
        try:
            quarter = int(key)
        except ValueError:
            continue
        if amount is not None:
            series[quarter] = float(amount)
    return series


def trend(series: Mapping[int, float], quarter: int) -> float | None:
    """The relative change over the ``TREND_QUARTERS`` quarters ending at ``quarter``; ``None`` when the window is
    not whole: a key missing or negative, or a value zero."""
    first = quarter - TREND_QUARTERS
    if first < 0:
        return None
    window = [series.get(key) for key in range(first, quarter + 1)]
    if any(value is None or value == 0 for value in window):
        return None
    return series[quarter] / series[first] - 1


def _direction(change: float | None) -> str | None:
    if change is None:
        return None
    if change > BOOM:
        return BOOM_DIRECTION
    if change < -SLUMP:
        return SLUMP_DIRECTION
    return None


def new_trend(series: Mapping[int, float], quarter: int) -> str | None:
    """``boom`` or ``slump`` when the trend at ``quarter`` is one and the trend of the quarter before was not."""
    direction = _direction(trend(series, quarter))
    if direction is None or _direction(trend(series, quarter - 1)) == direction:
        return None
    return direction


def campaign_start(snapshot: SaveSnapshot) -> datetime | None:
    """The save's date minus its ``campaign_day``; ``None`` when either is unknown."""
    days = number(snapshot.campaign_day)
    moment = snapshot.timestamp
    if moment is None and isinstance(snapshot.date, str):
        try:
            moment = datetime.fromisoformat(snapshot.date)
        except ValueError:
            moment = None
    if moment is None or days is None:
        return None
    return moment - timedelta(days=days)


def quarter_date(start: datetime | None, quarter: int) -> str | None:
    """The ISO date quarter ``quarter`` begins on: the campaign start for quarter 0, else the first day of the
    ``quarter``-th calendar quarter after the start's; ``None`` without a start."""
    if start is None:
        return None
    if quarter == 0:
        return start.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    months = start.year * 12 + (start.month - 1) // MONTHS_PER_QUARTER * MONTHS_PER_QUARTER
    year, month = divmod(months + MONTHS_PER_QUARTER * quarter, 12)
    return datetime(year, month + 1, 1).isoformat()
