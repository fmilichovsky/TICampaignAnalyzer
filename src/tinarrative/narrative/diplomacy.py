"""``nation.diplomatic_realignment``: a nation formed or broke alliances and rivalries with several partners in a
period. See architecture 11.3."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from ..analyzers.politics.nations import RELATION_CHANGED
from ..config import GeopoliticsSettings
from ..model.entities import EntityId, EntityRef
from ..model.events import Event, Role, Significance
from ..model.values import Observed
from .aggregation import Join, NarrativeBuilder, interval_reports
from .geopolitics import TAKEOVER, MergerParties, bounded_shifts, gdp_rank, metric_shifts, strength_rank
from .rulekit import (
    by_type,
    chained,
    earliest,
    event_order,
    intervals_of,
    last_date,
    latest,
    overlaps,
    shifted,
    sorted_keys,
    unique_refs,
    within,
)
from .situation import SituationReport
from .stream import EventStream

REALIGNMENT = "nation.diplomatic_realignment"
DIPLOMATIC_RELATIONS = ("allies", "rivals")
"""The ``relation`` values the rule reads; ``wars`` is war evidence and belongs to the war arc."""
ADDED = "added"
REMOVED = "removed"


@dataclass(frozen=True)
class DiplomaticRealignmentRule:
    """``nation.diplomatic_realignment``: one nation gained or lost several partners as allies or rivals, each change
    soon after the previous.

    A pair change is filed under both nations, so either side may realign. Changes a merger carries are left to it.
    A takeover of the nation inside the window is cited as context: it precedes the effect, so it may date the
    start, and its faction is the ``executive`` attribute, never a stated cause.
    """

    settings: GeopoliticsSettings
    name: str = REALIGNMENT
    order: int = 1

    @property
    def window_days(self) -> int:
        return self.settings.realignment_window_days

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        days = self.settings.realignment_window_days
        reports = interval_reports(situations)
        parties = MergerParties.of(stream)
        by_nation: dict[EntityId, list[Event]] = defaultdict(list)
        for event in by_type(stream, RELATION_CHANGED):
            pair = event.entities[:2]
            if event.attribute("relation") not in DIPLOMATIC_RELATIONS or len(pair) < 2:
                continue
            if any(parties.merged(ref, event) for ref in pair):
                continue
            for ref in pair:
                by_nation[ref.entity_id].append(event)
        takeovers = by_type(stream, TAKEOVER)
        last = last_date(situations)
        built = []
        for nation_id in sorted_keys(by_nation):
            for run in chained(by_nation[nation_id], days):
                partners = unique_refs(_partner(nation_id, event) for event in run)
                if len(partners) < self.settings.realignment_min_partners:
                    continue
                bounds = reports.get(intervals_of(run)[-1])
                if bounds is None:
                    continue
                report = bounds[1]
                nation = next(ref for ref in run[0].entities[:2] if ref.entity_id == nation_id)
                low, high = shifted(earliest(run[0]), -days), latest(run[-1])
                context = sorted(
                    (t for t in takeovers if _targets(t, nation_id) and overlaps(t, low, high)), key=event_order
                )
                executive = _actor(context[0]) if context else None
                roles = [(Role.ACTOR, nation), *((Role.TARGET, partner) for partner in partners)]
                rank = gdp_rank(report, nation_id)
                top = rank is not None and rank <= self.settings.top_gdp_nations
                shifts = metric_shifts(stream, [nation_id], intervals_of(run))
                built.append(
                    build.event(
                        REALIGNMENT,
                        id_parts=[nation_id],
                        constituents=run,
                        corroborating=context,
                        roles=roles,
                        join=Join.ENTITY,
                        attributes=(
                            *_lists(nation_id, run),
                            ("partner_count", len(partners)),
                            ("executive", executive),
                            ("gdp_rank", rank),
                            ("strength_rank", strength_rank(report, nation_id)),
                            *bounded_shifts(shifts, roles, self.settings.metric_shifts_max),
                        ),
                        significance=Significance.CAMPAIGN_DEFINING if top else Significance.MAJOR,
                        open=within(high, last, days),
                    )
                )
        return built


def _partner(nation_id: EntityId, event: Event) -> EntityRef:
    return next(ref for ref in event.entities[:2] if ref.entity_id != nation_id)


def _actor(takeover: Event) -> EntityRef | None:
    return next((ref for role, ref in takeover.roles if role is Role.ACTOR), None)


def _targets(takeover: Event, nation_id: EntityId) -> bool:
    return any(role is Role.TARGET and ref.entity_id == nation_id for role, ref in takeover.roles)


def _lists(nation_id: EntityId, run: Iterable[Event]) -> tuple[tuple[str, Observed], ...]:
    """The partners per relation and transition, and those that went from ally to rival or back within the run."""
    groups: dict[tuple[str, str], list[EntityRef]] = defaultdict(list)
    for event in run:
        relation, transition = event.attribute("relation"), event.attribute("transition")
        if isinstance(relation, str) and isinstance(transition, str):
            groups[(relation, transition)].append(_partner(nation_id, event))
    lists = {
        f"{relation}_{label}": unique_refs(groups[(relation, transition)])
        for relation in DIPLOMATIC_RELATIONS
        for transition, label in ((ADDED, "gained"), (REMOVED, "lost"))
    }
    reversed_partners = unique_refs(
        ref
        for lost, gained in (("allies_lost", "rivals_gained"), ("rivals_lost", "allies_gained"))
        for ref in lists[lost]
        if any(other.entity_id == ref.entity_id for other in lists[gained])
    )
    return (*lists.items(), ("reversed_partners", reversed_partners))


def diplomacy_rules(settings: GeopoliticsSettings) -> tuple[DiplomaticRealignmentRule, ...]:
    return (DiplomaticRealignmentRule(settings),)
