"""Nation statistics crossing a game value band (``bands``) by its margin, with the tracked causes.

``rest_value_share`` states how much of the move is the game's drift to the rest value; whether that makes the
crossing a story is the narrative stage's call. Placeholder nations are skipped.
"""

from __future__ import annotations

from ...kinds.nations import BAND_CROSSED
from ...model.changes import ChangeIndex, ChangeKind, StateChange, StateDiff
from ...model.entities import EntityDomain
from ...model.events import Event, EventSource, SourceRole
from ...model.snapshot import SaveSnapshot
from ...model.values import FrozenMap, Observed, Unknown
from ..common import EventBuilder, Lookup, primary
from .bands import BANDS, margin_crossing, rest_value_delta
from .nation_metrics import TRACKERS, cause_deltas, interval_days, number, placeholder


class NationBandAnalyzer:
    def analyze(self, before: SaveSnapshot, after: SaveSnapshot, diff: StateDiff) -> list[Event]:
        index = diff.index
        lookup = Lookup(before, after)
        build = EventBuilder(before, after, lookup)
        days = interval_days(before, after)
        events: list[Event] = []
        for statistic in BANDS:
            for change in index.fields(EntityDomain.NATION, statistic):
                event = _band_crossed(change, days, index, lookup, build)
                if event is not None:
                    events.append(event)
        return events


def _band_crossed(
    change: StateChange, days: float | None, index: ChangeIndex, lookup: Lookup, build: EventBuilder
) -> Event | None:
    nation = change.entity_id
    if change.kind is not ChangeKind.VALUE or nation is None or change.field is None:
        return None
    before, after = number(change.before), number(change.after)
    if before is None or after is None or placeholder(nation, lookup):
        return None
    crossing = margin_crossing(change.field, before, after)
    if crossing is None:
        return None
    sources = [primary(change)]
    attributes: list[tuple[str, Observed]] = [
        ("statistic", change.field),
        ("before", before),
        ("after", after),
        ("from_band", crossing.from_band),
        ("to_band", crossing.to_band),
        ("bands_crossed", crossing.bands_crossed),
        ("margin", crossing.margin),
        ("interval_days", days),
    ]
    tracker = TRACKERS.get(change.field)
    if tracker is not None:
        tracker_change = index.field(nation, tracker)
        causes: FrozenMap | Unknown = FrozenMap()
        if tracker_change is not None:
            sources.append(EventSource(tracker_change, SourceRole.CORROBORATING))
            causes = cause_deltas(tracker_change.before, tracker_change.after)
        attributes.extend((("causes", causes), ("rest_value_share", rest_value_share(causes))))
    return build.event(
        BAND_CROSSED,
        id_parts=(nation, change.field),
        sources=sources,
        entities=(lookup.ref(nation),),
        attributes=attributes,
    )


def rest_value_share(causes: FrozenMap | Unknown) -> float | Unknown:
    """The rest-value delta's share of all cause deltas, by magnitude; ``Unknown`` without readable causes."""
    if isinstance(causes, Unknown) or not causes.items:
        return Unknown()
    total = sum(abs(value) for _, value in causes.items if isinstance(value, int | float))
    return abs(rest_value_delta(causes)) / total if total else Unknown()
