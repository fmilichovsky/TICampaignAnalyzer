"""The geopolitical narrative rules: takeovers, wars, federations, territorial changes.

No rule names a motive or a public framing; that stays with the narrator (ADR-0014).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace

from ..analyzers.military.armies import APPEARED as ARMY_APPEARED
from ..analyzers.military.armies import DEPLOYMENT_TYPE_CHANGED
from ..analyzers.military.armies import DISAPPEARED as ARMY_DISAPPEARED
from ..analyzers.politics.bands import BANDS, band
from ..analyzers.politics.control_points import DISAPPEARED as POINT_DISAPPEARED
from ..analyzers.politics.control_points import LOSS_RECORDED as POINT_LOSS_RECORDED
from ..config import GeopoliticsSettings
from ..kinds import control as control_kinds
from ..kinds import nations as nation_kinds
from ..kinds.faction import TRANSACTION_RECORDED
from ..kinds.federations import APPEARED as FEDERATION_APPEARED
from ..kinds.federations import DISAPPEARED as FEDERATION_DISAPPEARED
from ..kinds.federations import LIFECYCLE as FEDERATION_LIFECYCLE_KIND
from ..kinds.federations import MEMBERS_CHANGED as FEDERATION_MEMBERS_CHANGED
from ..kinds.federations import RENAMED as FEDERATION_RENAMED
from ..kinds.wars import ALLIANCE_CHANGED, LAST_FIGHTING_CHANGED
from ..kinds.wars import APPEARED as WAR_APPEARED
from ..kinds.wars import ARC as WAR_ARC_KIND
from ..kinds.wars import DISAPPEARED as WAR_DISAPPEARED
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import DateBasis, Event, Role, Significance
from ..model.values import FieldValue, FrozenMap, Observed, Unknown
from .aggregation import Join, NarrativeBuilder, days_between, interval_reports
from .chronology import TIE_SEPARATOR, interval_of, interval_sort_key
from .rulekit import (
    NATION_ARMIES_CHANGED,
    DatedEvents,
    anchored,
    army_home,
    by_subject,
    by_type,
    chained,
    earliest,
    entity_of,
    event_order,
    intervals_of,
    last_date,
    latest,
    mentions,
    overlaps,
    ref_attribute,
    refs_attribute,
    shifted,
    sorted_keys,
    subject,
    subject_id,
    unique_refs,
    within,
)
from .situation import NationSituation, SituationReport, WarSituation
from .stream import EventStream

TAKEOVER = control_kinds.TAKEOVER.event_type
TAKEOVER_WAVE = control_kinds.TAKEOVER_WAVE.event_type
WAR_ARC = WAR_ARC_KIND.event_type
FEDERATION_LIFECYCLE = FEDERATION_LIFECYCLE_KIND.event_type
EXPANSION = nation_kinds.EXPANSION.event_type
CESSION = nation_kinds.CESSION.event_type
MERGER = nation_kinds.MERGER.event_type
RELEASE = nation_kinds.RELEASE.event_type
BREAKAWAY = nation_kinds.BREAKAWAY.event_type
CLAIMS_DECLARED = nation_kinds.CLAIMS_DECLARED.event_type

NATION_CONTROL = control_kinds.NATION_CONTROL_CHANGED.event_type
BREAKAWAY_PARENT_CHANGED = nation_kinds.BREAKAWAY_PARENT_CHANGED.event_type
CONTROLLER_CHANGED = control_kinds.CONTROL_POINT_CONTROLLER_CHANGED.event_type
EXECUTIVE_RECORDED = nation_kinds.EXECUTIVE_CHANGE_RECORDED.event_type
UNREST_ATTEMPTS = nation_kinds.UNREST_ATTEMPTS_CHANGED.event_type
STATISTIC_SHIFTED = nation_kinds.STATISTIC_SHIFTED.event_type
TRANSACTION = TRANSACTION_RECORDED.event_type
TERRITORY_GAINED = nation_kinds.TERRITORY_GAINED.event_type
TERRITORY_LOST = nation_kinds.TERRITORY_LOST.event_type
UNIFICATION = nation_kinds.UNIFICATION.event_type
ANNEXATION = nation_kinds.ANNEXATION.event_type
INDEPENDENCE = nation_kinds.INDEPENDENCE.event_type
NATION_DISAPPEARED = nation_kinds.DISAPPEARED.event_type
RELATION_CHANGED = nation_kinds.RELATION_CHANGED.event_type
RENAMED = nation_kinds.RENAMED.event_type
PCGDP_TREND = nation_kinds.PCGDP_TREND.event_type
POPULATION_CHANGED = nation_kinds.POPULATION_CHANGED.event_type
RANK_CHANGED = nation_kinds.RANK_CHANGED.event_type
SPACE_ASSETS_CHANGED = nation_kinds.SPACE_ASSETS_CHANGED.event_type

TAKEOVER_SCOPES = ("executive", "sole")
"""The ``faction.nation_control_changed`` scopes that anchor a takeover; a plurality is not control."""
INDEPENDENCE_CAUSE = "Independence"
"""A control change with this cause belongs to the release and breakaway rule, not to a takeover."""
TAKEOVER_COUNCILOR_TYPES = tuple(
    kind.event_type
    for kind in (
        control_kinds.COUNCILOR_FACTION_CHANGED,
        control_kinds.COUNCILOR_DISAPPEARED,
        control_kinds.COUNCILOR_DETAINING_FACTION_CHANGED,
    )
)
PRECURSOR_STATISTICS = frozenset({"unrest", "publicOpinion"})
TAKEOVER_LEDGER_LABELS = frozenset({"Coup", "Purge", "Crackdown"})
"""Mission charges that corroborate a takeover under the bounds of ADR-0010."""
READINGS = (UNIFICATION, ANNEXATION, INDEPENDENCE)
"""A gain without one of these readings is a cession candidate."""
LEADING_STATISTICS = frozenset({"numNuclearWeapons"})
"""Rank ahead of any relative change when shifts are bounded: a shift from zero has no relative change but is the
story."""
MERGED_EITHER = frozenset({TERRITORY_GAINED, TERRITORY_LOST, RENAMED, SPACE_ASSETS_CHANGED})
"""Events of either merged nation that are the merger's exclusive constituents in its interval."""
MERGED_ABSORBED = frozenset({RANK_CHANGED, NATION_DISAPPEARED, NATION_CONTROL, POPULATION_CHANGED, PCGDP_TREND})
"""Events of the absorbed nation only that are the merger's exclusive constituents in its interval."""
MERGED_POINTS = frozenset({CONTROLLER_CHANGED, POINT_DISAPPEARED, POINT_LOSS_RECORDED})
MERGED_ARMIES = frozenset({ARMY_APPEARED, ARMY_DISAPPEARED, DEPLOYMENT_TYPE_CHANGED, NATION_ARMIES_CHANGED})
MERGER_CONSTITUENT_TYPES = tuple(
    sorted(
        MERGED_EITHER
        | MERGED_ABSORBED
        | MERGED_POINTS
        | MERGED_ARMIES
        | {RELATION_CHANGED, STATISTIC_SHIFTED, BREAKAWAY_PARENT_CHANGED}
    )
)
"""Every event type ``_merger_constituent`` can accept."""


# --- Mergers -----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MergerParties:
    """The nations of every ``nation.unification`` by interval, for lookups such as a merged nation's gainer."""

    unifications: Mapping[tuple[EntityId, str], Event]

    @classmethod
    def of(cls, stream: Iterable[Event]) -> MergerParties:
        found: dict[tuple[EntityId, str], Event] = {}
        for event in by_type(stream, UNIFICATION):
            key = interval_of(event.id)
            for ref in (event.entities[0], *refs_attribute(event, "unified")):
                found[(ref.entity_id, key)] = event
        return cls(found)

    def gainer(self, nation: EntityRef | EntityId | None, key: str) -> EntityRef | None:
        """The nation that absorbed ``nation`` in interval ``key``."""
        nation_id = _id(nation)
        found = self.unifications.get((nation_id, key)) if nation_id is not None else None
        if found is None or found.entities[0].entity_id == nation_id:
            return None
        return found.entities[0]


def _id(nation: EntityRef | EntityId | None) -> EntityId | None:
    return nation.entity_id if isinstance(nation, EntityRef) else nation


# --- Situation context -------------------------------------------------------------------------------------------


def _nation(report: SituationReport, nation_id: EntityId) -> NationSituation | None:
    return next((item for item in report.nations if item.nation.entity_id == nation_id), None)


def _refs(value: Observed) -> tuple[EntityRef, ...]:
    return tuple(item for item in value if isinstance(item, EntityRef)) if isinstance(value, tuple) else ()


def _members(value: Observed) -> set[EntityId]:
    return {item.entity_id for item in _refs(value)}


def opposed(report: SituationReport, first: EntityId, second: EntityId) -> list[WarSituation]:
    found = []
    for war in report.wars:
        attackers, defenders = _members(war.attacking_alliance), _members(war.defending_alliance)
        if (first in attackers and second in defenders) or (first in defenders and second in attackers):
            found.append(war)
    return found


def _rank(report: SituationReport, nation_id: EntityId, value: Callable[[NationSituation], Observed]) -> int | None:
    """1 is the largest; nations without a known value are not ranked."""
    known = [
        (number, item.nation.entity_id)
        for item in report.nations
        if isinstance(number := value(item), int | float) and not isinstance(number, bool)
    ]
    ordered = sorted(known, key=lambda pair: (-pair[0], pair[1].sort_key))
    return next((position for position, (_, key) in enumerate(ordered, start=1) if key == nation_id), None)


def gdp_rank(report: SituationReport, nation_id: EntityId) -> int | None:
    """1 is the largest."""
    return _rank(report, nation_id, lambda item: dict(item.statistics).get("GDP"))


def strength_rank(report: SituationReport, nation_id: EntityId) -> int | None:
    """1 is the strongest."""
    return _rank(report, nation_id, lambda item: item.strength)


# --- Metric shifts -----------------------------------------------------------------------------------------------


def _number(value: Observed) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _literal(value: Observed) -> FieldValue:
    return None if isinstance(value, Unknown) else value


def metric_shifts(
    stream: Iterable[Event],
    nations: Iterable[EntityId],
    intervals: Iterable[str],
    windows: Mapping[EntityId, Collection[str]] | None = None,
) -> tuple[FrozenMap, ...]:
    """One net entry per nation, statistic and key over the ``nation.statistic_shifted`` events in ``intervals``.

    The net covers the reported shifts only: an interval whose change stayed below the analyzer's threshold is missing
    from it. ``relative_change`` is unsigned. ``windows`` limits a nation to its own intervals; a nation without a
    window keeps all of ``intervals``. Shifts are context, never constituents.
    """
    wanted, keys = set(nations), set(intervals)
    groups: dict[tuple[EntityId, str, str], list[Event]] = defaultdict(list)
    for event in EventStream.of(stream).of_subject(wanted, STATISTIC_SHIFTED):
        nation = subject_id(event)
        if nation is None or interval_of(event.id) not in keys:
            continue
        if windows is not None and nation in windows and interval_of(event.id) not in windows[nation]:
            continue
        key = event.attribute("key")
        groups[(nation, str(event.attribute("statistic")), key if isinstance(key, str) else "")].append(event)
    entries = []
    for (_, statistic, key), shifts in sorted(groups.items(), key=lambda item: (item[0][0].sort_key, item[0][1:])):
        shifts.sort(key=lambda event: interval_sort_key(interval_of(event.id)))
        before, after = _literal(shifts[0].attribute("before")), _literal(shifts[-1].attribute("after"))
        low, high = _number(before), _number(after)
        relative = abs(high - low) / abs(low) if low is not None and high is not None and low != 0 else None
        items: list[tuple[str, FieldValue]] = [
            ("nation", shifts[0].entities[0]),
            ("statistic", statistic),
            ("before", before),
            ("after", after),
            ("relative_change", relative),
            ("not_before", _literal(shifts[0].not_before)),
            ("date", _literal(shifts[-1].date)),
            ("date_basis", shifts[-1].date_basis.value),
            ("events", tuple(event.id for event in shifts)),
        ]
        if key:
            items.append(("key", key))
        if statistic in BANDS and low is not None and high is not None:
            items.extend((("from_band", band(statistic, low)), ("to_band", band(statistic, high))))
        causes = _summed_causes(shifts)
        if causes is not None:
            items.append(("causes", causes))
        entries.append(FrozenMap(tuple(items)))
    return tuple(entries)


def _summed_causes(shifts: Sequence[Event]) -> FrozenMap | None:
    maps = [value for value in (event.attribute("causes") for event in shifts) if isinstance(value, FrozenMap)]
    if not maps:
        return None
    totals: dict[str, float] = defaultdict(float)
    for causes in maps:
        for reason, delta in causes.items:
            number = _number(delta)
            if number is not None:
                totals[reason] += number
    return FrozenMap(tuple((reason, total) for reason, total in totals.items() if total != 0))


def bounded_shifts(
    entries: Sequence[FrozenMap], roles: Iterable[tuple[Role, EntityRef]], limit: int
) -> tuple[tuple[str, FieldValue], ...]:
    """At most ``limit`` entries, with ``metric_shifts_omitted`` counting the cut.

    Selection prefers role nations, then ``LEADING_STATISTICS``, then the largest ``relative_change``; the kept entries
    keep their original order.
    """
    first = {ref.entity_id for _, ref in roles if ref.entity_id.domain is EntityDomain.NATION}

    def rank(position: int) -> tuple[bool, bool, bool, float, int]:
        entry = dict(entries[position].items)
        relative = _number(entry.get("relative_change"))
        nation = entry.get("nation")
        return (
            not (isinstance(nation, EntityRef) and nation.entity_id in first),
            entry.get("statistic") not in LEADING_STATISTICS,
            relative is None,
            -(relative or 0.0),
            position,
        )

    kept = sorted(sorted(range(len(entries)), key=rank)[:limit])
    attributes: tuple[tuple[str, FieldValue], ...] = (("metric_shifts", tuple(entries[index] for index in kept)),)
    if len(kept) < len(entries):
        attributes += (("metric_shifts_omitted", len(entries) - len(kept)),)
    return attributes


# --- Rules -------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TakeoverRule:
    """``faction.takeover``: a faction took a nation's executive or every control point, and what came with it.

    Executive, then sole control within the consolidation window is one takeover. Ledger charges corroborate only
    when no other faction carries the label in the window (ADR-0010, bound 4). Open while the faction holds
    the executive but not every point.
    """

    settings: GeopoliticsSettings
    name: str = TAKEOVER
    emitted_types: frozenset[str] = frozenset({TAKEOVER})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()

    @property
    def window_days(self) -> int:
        return self.settings.takeover_consolidation_days

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        reports = interval_reports(situations)
        by_nation = by_subject(by_type(stream, NATION_CONTROL))
        charges = DatedEvents(
            event for event in by_type(stream, TRANSACTION) if event.attribute("label") in TAKEOVER_LEDGER_LABELS
        )
        built: list[Event] = []
        for nation_id in sorted_keys(by_nation):
            nation_built = [
                (run, self._takeover(stream, charges, situations, reports, build, run))
                for run in self._runs(by_nation[nation_id])
            ]
            built.extend(_with_succession(nation_built))
        return built

    def _runs(self, changes: Sequence[Event]) -> list[list[Event]]:
        runs: list[list[Event]] = []
        holder: EntityId | None = None
        for change in sorted(changes, key=event_order):
            if change.attribute("scope") not in TAKEOVER_SCOPES:
                continue
            before, after = ref_attribute(change, "before"), ref_attribute(change, "after")
            if holder is not None and before is not None and before.entity_id == holder:
                if after is None or after.entity_id != holder:
                    holder = None
            if after is None or after.entity_id.domain is not EntityDomain.FACTION:
                continue
            if change.attribute("cause") == INDEPENDENCE_CAUSE:
                continue
            window = self.settings.takeover_consolidation_days
            if runs and holder == after.entity_id and within(latest(runs[-1][0]), earliest(change), window):
                runs[-1].append(change)
            else:
                runs.append([change])
            holder = after.entity_id
        return runs

    def _takeover(
        self,
        stream: EventStream,
        charges: DatedEvents,
        situations: Sequence[SituationReport],
        reports: Mapping[str, tuple[SituationReport, SituationReport]],
        build: NarrativeBuilder,
        anchors: list[Event],
    ) -> Event:
        settings = self.settings
        nation = anchors[0].entities[0]
        actor = ref_attribute(anchors[0], "after")
        assert actor is not None
        executive = [anchor for anchor in anchors if anchor.attribute("scope") == "executive"]
        loser = next(
            (ref for ref in (ref_attribute(anchor, "before") for anchor in (*executive, *anchors)) if ref is not None),
            None,
        )
        start = min((date for date in map(earliest, anchors) if date is not None), default=None)
        end = max((date for date in map(latest, anchors) if date is not None), default=None)
        before_start = shifted(start, -settings.takeover_precursor_days)
        anchor_intervals = set(intervals_of(anchors))
        attached: list[Event] = []
        candidates = stream.union(
            stream.mentioning(nation.entity_id, CONTROLLER_CHANGED),
            stream.of_subject(nation.entity_id, EXECUTIVE_RECORDED, UNREST_ATTEMPTS, STATISTIC_SHIFTED),
            stream.mentioning(loser.entity_id, *TAKEOVER_COUNCILOR_TYPES) if loser is not None else (),
        )
        for event in candidates:
            if event.event_type == CONTROLLER_CHANGED:
                point_nation = entity_of(event, EntityDomain.NATION)
                gained = ref_attribute(event, "after")
                if (
                    point_nation is not None
                    and point_nation.entity_id == nation.entity_id
                    and gained is not None
                    and gained.entity_id == actor.entity_id
                    and overlaps(event, before_start, shifted(end, settings.takeover_consolidation_days))
                ):
                    attached.append(event)
            elif event.event_type == EXECUTIVE_RECORDED:
                if subject_id(event) == nation.entity_id and interval_of(event.id) in anchor_intervals:
                    attached.append(event)
            elif event.event_type in TAKEOVER_COUNCILOR_TYPES:
                if loser is not None and interval_of(event.id) in anchor_intervals and mentions(event, loser.entity_id):
                    attached.append(event)
            elif event.event_type == UNREST_ATTEMPTS:
                attempts = ref_attribute(event, "faction")
                if (
                    subject_id(event) == nation.entity_id
                    and attempts is not None
                    and attempts.entity_id == actor.entity_id
                    and overlaps(event, before_start, end)
                ):
                    attached.append(event)
            elif event.event_type == STATISTIC_SHIFTED:
                if (
                    subject_id(event) == nation.entity_id
                    and event.attribute("statistic") in PRECURSOR_STATISTICS
                    and overlaps(event, before_start, end)
                ):
                    attached.append(event)
        corroborating = self._ledger(charges, anchors, actor)
        record = min(
            (event for event in attached if event.event_type == EXECUTIVE_RECORDED), key=event_order, default=None
        )
        recorded = {} if record is None else dict(record.attributes)
        constituents = [*anchors, *attached]
        intervals = intervals_of([*constituents, *corroborating])
        anchored = intervals_of(anchors[:1])[0]
        first_after = reports.get(anchored)
        rank = gdp_rank(first_after[1], nation.entity_id) if first_after is not None else None
        cause = next(
            (value for value in (anchor.attribute("cause") for anchor in anchors) if isinstance(value, str)), None
        )
        defining = rank is not None and rank <= settings.top_gdp_nations
        roles = [(Role.ACTOR, actor), (Role.TARGET, nation)]
        if loser is not None:
            roles.append((Role.LOSER, loser))
        return build.event(
            control_kinds.TAKEOVER,
            id_parts=[nation.entity_id, actor.entity_id],
            id_interval=anchored,
            constituents=constituents,
            corroborating=corroborating,
            roles=roles,
            join=Join.HEURISTIC,
            attributes=(
                ("scopes", tuple(sorted({str(anchor.attribute("scope")) for anchor in anchors}))),
                ("cause", cause),
                ("executive_recorded_on", recorded.get("recorded_on")),
                ("previous_executive", recorded.get("previous_executive")),
                ("consolidated", any(anchor.attribute("scope") == "sole" for anchor in anchors)),
                ("gdp_rank", rank),
                *bounded_shifts(
                    metric_shifts(stream, [nation.entity_id], intervals), roles, settings.metric_shifts_max
                ),
            ),
            significance=Significance.CAMPAIGN_DEFINING if defining else Significance.MAJOR,
            open=_holds_executive_only(situations, nation.entity_id, actor.entity_id),
        )

    def _ledger(self, charges: DatedEvents, anchors: Sequence[Event], actor: EntityRef) -> list[Event]:
        """``charges`` are the stream's transactions with a takeover label."""
        found: dict[str, Event] = {}
        for anchor in anchors:
            low = shifted(earliest(anchor), -self.settings.ledger_window_days)
            window = charges.overlapping(low, latest(anchor))
            for label in sorted(TAKEOVER_LEDGER_LABELS):
                labelled = [charge for charge in window if charge.attribute("label") == label]
                candidates = {ref.entity_id for ref in map(subject, labelled) if ref is not None}
                if candidates == {actor.entity_id}:
                    found.update((charge.id, charge) for charge in labelled)
        return list(found.values())


def _role(event: Event, role: Role) -> EntityId | None:
    return next((ref.entity_id for found, ref in event.roles if found is role), None)


def _with_succession(built: Sequence[tuple[list[Event], Event]]) -> list[Event]:
    """Takeovers sharing an anchor interval have no date order: derive one from actor and loser, else mark both
    ``ambiguous``."""
    anchor_intervals = [set(intervals_of(anchors)) for anchors, _ in built]
    result = []
    for index, (_, event) in enumerate(built):
        rivals = [
            other
            for other_index, (_, other) in enumerate(built)
            if other_index != index and anchor_intervals[index] & anchor_intervals[other_index]
        ]
        if not rivals:
            result.append(event)
            continue
        actor, loser = _role(event, Role.ACTOR), _role(event, Role.LOSER)
        earlier = [r for r in rivals if _role(r, Role.ACTOR) == loser and loser is not None]
        later = [r for r in rivals if _role(r, Role.LOSER) == actor and actor is not None]
        # An order is derived only when every rival agrees and none names the other direction too.
        if len(rivals) == 1 and (earlier == rivals) != (later == rivals):
            key = "succeeds" if earlier else "succeeded_by"
            result.append(replace(event, attributes=(*event.attributes, (key, rivals[0].id))))
        else:
            ids = tuple(sorted(r.id for r in rivals))
            result.append(replace(event, attributes=(*event.attributes, ("ambiguous", True), ("alternatives", ids))))
    return result


def _holds_executive_only(situations: Sequence[SituationReport], nation_id: EntityId, faction_id: EntityId) -> bool:
    if not situations:
        return False
    nation = _nation(situations[-1], nation_id)
    if nation is None or not isinstance(nation.executive, EntityRef) or nation.executive.entity_id != faction_id:
        return False
    if not isinstance(nation.shares, FrozenMap) or not isinstance(nation.control_points, int):
        return False
    held = dict(nation.shares.items).get(str(faction_id))
    return isinstance(held, int) and held < nation.control_points


@dataclass(frozen=True)
class TakeoverWaveRule:
    """``faction.takeover_wave``: one faction took several nations below the top GDP ranks in a short period.

    A takeover of a top-ranked nation stays a headline narrative event of its own and never joins a wave.
    """

    settings: GeopoliticsSettings
    name: str = TAKEOVER_WAVE
    emitted_types: frozenset[str] = frozenset({TAKEOVER_WAVE})
    reads: frozenset[str] = frozenset({TAKEOVER})
    explains: frozenset[str] = frozenset()

    @property
    def window_days(self) -> int:
        return self.settings.takeover_wave_window_days

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        days = self.settings.takeover_wave_window_days
        by_actor: dict[EntityId, list[Event]] = defaultdict(list)
        for takeover in by_type(stream, TAKEOVER):
            actor, rank = _role(takeover, Role.ACTOR), takeover.attribute("gdp_rank")
            top = isinstance(rank, int) and rank <= self.settings.top_gdp_nations
            if actor is not None and not top:
                by_actor[actor].append(takeover)
        last = last_date(situations)
        built = []
        for faction_id in sorted_keys(by_actor):
            for run in anchored(by_actor[faction_id], days):
                nations = unique_refs(ref for event in run for role, ref in event.roles if role is Role.TARGET)
                if len(nations) < self.settings.takeover_wave_min_nations:
                    continue
                faction = next(ref for role, ref in run[0].roles if role is Role.ACTOR)
                built.append(
                    build.event(
                        control_kinds.TAKEOVER_WAVE,
                        id_parts=[faction_id],
                        id_interval=interval_of(run[0].id),
                        constituents=run,
                        roles=[(Role.ACTOR, faction), *((Role.TARGET, nation) for nation in nations)],
                        join=Join.ENTITY,
                        attributes=(("nations", nations), ("count", len(run))),
                        # TODO(#199): scale by the members' stakes.
                        significance=Significance.MAJOR,
                        open=within(latest(run[0]), last, days),
                    )
                )
        return built


def _membership_windows(
    reports: Mapping[str, tuple[SituationReport, SituationReport]], federation_id: EntityId, nations: Iterable[EntityId]
) -> dict[EntityId, set[str]]:
    """Intervals with the nation a member at either end, so the interval of a join or leave counts."""
    windows: dict[EntityId, set[str]] = {nation: set() for nation in nations}
    for key, pair in reports.items():
        for report in pair:
            for item in report.federations:
                if item.federation.entity_id == federation_id:
                    for member in _members(item.members):
                        if member in windows:
                            windows[member].add(key)
    return windows


@dataclass(frozen=True)
class FederationLifecycleRule:
    """``federation.lifecycle``: a federation's formation, member changes, renames and dissolution, by its ID.

    A federation no event mentions is not reported.
    """

    settings: GeopoliticsSettings
    name: str = FEDERATION_LIFECYCLE
    emitted_types: frozenset[str] = frozenset({FEDERATION_LIFECYCLE})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()
    window_days: int | None = None

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        types = tuple(
            kind.event_type
            for kind in (
                FEDERATION_APPEARED,
                FEDERATION_MEMBERS_CHANGED,
                FEDERATION_RENAMED,
                FEDERATION_DISAPPEARED,
            )
        )
        by_federation = by_subject(by_type(stream, *types))
        first = {item.federation.entity_id for item in situations[0].federations} if situations else set()
        reports = interval_reports(situations)
        parties = MergerParties.of(stream)
        built = []
        for federation_id in sorted_keys(by_federation):
            events = sorted(by_federation[federation_id], key=event_order)
            if federation_id not in first and not any(
                event.event_type == FEDERATION_APPEARED.event_type for event in events
            ):
                continue
            listed = [
                item
                for report in situations
                for item in report.federations
                if item.federation.entity_id == federation_id
            ]
            initial = unique_refs(_refs(listed[0].members)) if listed else ()
            final = unique_refs(_refs(listed[-1].members)) if listed else ()
            changes = tuple(
                _member_change(event, parties)
                for event in events
                if event.event_type == FEDERATION_MEMBERS_CHANGED.event_type
                and ref_attribute(event, "member") is not None
            )
            members = {ref.entity_id for ref in initial} | {ref.entity_id for ref in final}
            members |= {ref.entity_id for event in events for ref in event.entities[1:]}
            windows = _membership_windows(reports, federation_id, members)
            federation = events[0].entities[0]
            roles = [(Role.ACTOR, federation)]
            shifts = metric_shifts(stream, members, intervals_of(events), windows)
            built.append(
                build.event(
                    FEDERATION_LIFECYCLE_KIND,
                    id_parts=[federation_id],
                    constituents=events,
                    roles=roles,
                    join=Join.ENTITY,
                    attributes=(
                        ("members_initial", initial),
                        ("member_changes", changes),
                        ("members_final", final),
                        *bounded_shifts(shifts, roles, self.settings.metric_shifts_max),
                    ),
                    anchor=federation,
                    significance=Significance.MAJOR,
                )
            )
        return built


def _member_change(event: Event, parties: MergerParties) -> FrozenMap:
    """A member that left by merging into another nation names it in ``merged_into``."""
    member = ref_attribute(event, "member")
    items: list[tuple[str, FieldValue]] = [
        ("date", _literal(event.date)),
        ("nation", member),
        ("transition", _literal(event.attribute("transition"))),
    ]
    gainer = parties.gainer(member, interval_of(event.id)) if event.attribute("transition") == "removed" else None
    if gainer is not None:
        items.append(("merged_into", gainer))
    return FrozenMap(tuple(items))


@dataclass(frozen=True)
class CessionRule:
    """``nation.cession``: in one interval, a nation's regions went to another with no reading or war explaining it.

    A conquest without a war looks the same, hence the heuristic join.
    """

    settings: GeopoliticsSettings
    name: str = CESSION
    emitted_types: frozenset[str] = frozenset({CESSION})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()
    window_days: int | None = 0

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        reports = interval_reports(situations)
        explained = _readings(stream)
        lost = {(subject_id(event), interval_of(event.id)): event for event in by_type(stream, TERRITORY_LOST)}
        built = []
        for gain in sorted(by_type(stream, TERRITORY_GAINED), key=lambda event: event.id):
            gainer, key = gain.entities[0], interval_of(gain.id)
            if (gainer.entity_id, key) in explained:
                continue
            for loser in refs_attribute(gain, "counterparts"):
                loss = lost.get((loser.entity_id, key))
                if loss is None or not any(
                    ref.entity_id == gainer.entity_id for ref in refs_attribute(loss, "counterparts")
                ):
                    continue
                around = reports.get(key, ())
                if any(opposed(report, gainer.entity_id, loser.entity_id) for report in around):
                    continue
                built.append(self._cession(stream, build, gain, loss, around[0] if around else None))
        return built

    def _cession(
        self, stream: EventStream, build: NarrativeBuilder, gain: Event, loss: Event, before: SituationReport | None
    ) -> Event:
        gainer, loser = gain.entities[0], loss.entities[0]
        lost_regions = {ref.entity_id for ref in refs_attribute(loss, "regions")}
        regions = tuple(ref for ref in refs_attribute(gain, "regions") if ref.entity_id in lost_regions)
        allied, shared = None, None
        if before is not None:
            first, second = _nation(before, gainer.entity_id), _nation(before, loser.entity_id)
            if first is not None and second is not None:
                allied = loser.entity_id in _members(first.allies) or gainer.entity_id in _members(second.allies)
                if isinstance(first.federation, EntityRef) and isinstance(second.federation, EntityRef):
                    if first.federation.entity_id == second.federation.entity_id:
                        shared = first.federation
        constituents = [gain, loss]
        roles = [(Role.ACTOR, loser), (Role.BENEFICIARY, gainer), *((Role.LOCATION, region) for region in regions)]
        shifts = metric_shifts(stream, [gainer.entity_id, loser.entity_id], intervals_of(constituents))
        return build.event(
            nation_kinds.CESSION,
            id_parts=[loser.entity_id, gainer.entity_id],
            constituents=constituents,
            roles=roles,
            join=Join.HEURISTIC,
            attributes=(
                ("regions", regions),
                ("region_count", len(regions)),
                ("allied", allied),
                ("shared_federation", shared),
                *bounded_shifts(shifts, roles, self.settings.metric_shifts_max),
            ),
            significance=Significance.MAJOR,
            open=False,
        )


@dataclass(frozen=True)
class MergerRule:
    """``nation.merger``: a nation absorbed others by unification, with what the merge did to both in that interval.

    Its kind's constituents are exclusive: the rules running after it may read them, never cite them.
    """

    settings: GeopoliticsSettings
    name: str = MERGER
    emitted_types: frozenset[str] = frozenset({MERGER})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()
    window_days: int | None = 0

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        built = []
        for anchor in sorted(by_type(stream, UNIFICATION), key=lambda event: event.id):
            key = interval_of(anchor.id)
            gainer, absorbed = anchor.entities[0], refs_attribute(anchor, "unified")
            absorbed_ids = {ref.entity_id for ref in absorbed}
            attached = [
                event
                for event in stream.in_intervals(key, *MERGER_CONSTITUENT_TYPES)
                if event is not anchor
                and not event.is_narrative
                and _merger_constituent(event, gainer.entity_id, absorbed_ids)
            ]
            regions = unique_refs(
                region
                for event in attached
                if event.event_type == TERRITORY_LOST and subject_id(event) in absorbed_ids
                for region in refs_attribute(event, "regions")
            )
            roles = [
                (Role.ACTOR, gainer),
                *((Role.TARGET, ref) for ref in absorbed),
                *((Role.LOCATION, region) for region in regions),
            ]
            shifts = metric_shifts(stream, [gainer.entity_id, *absorbed_ids], [key])
            built.append(
                build.event(
                    nation_kinds.MERGER,
                    id_parts=[gainer.entity_id],
                    constituents=[anchor, *attached],
                    roles=roles,
                    join=Join.ENTITY,
                    attributes=(
                        ("absorbed", absorbed),
                        ("regions", regions),
                        ("region_count", len(regions)),
                        ("unifying_faction", anchor.attribute("unifying_faction")),
                        ("bases", anchor.attribute("bases")),
                        ("executive_since", anchor.attribute("executive_since")),
                        *bounded_shifts(shifts, roles, self.settings.metric_shifts_max),
                    ),
                    significance=Significance.MAJOR,
                    open=False,
                )
            )
        return built


def _merger_constituent(event: Event, gainer: EntityId, absorbed: Collection[EntityId]) -> bool:
    nation = subject_id(event)
    if event.event_type in MERGED_EITHER:
        return nation == gainer or nation in absorbed
    if event.event_type in MERGED_ABSORBED:
        return nation in absorbed
    if event.event_type in MERGED_POINTS:
        point_nation = entity_of(event, EntityDomain.NATION)
        return point_nation is not None and point_nation.entity_id in absorbed
    if event.event_type == RELATION_CHANGED:
        return any(ref.entity_id == gainer or ref.entity_id in absorbed for ref in event.entities)
    if event.event_type in MERGED_ARMIES:
        home = army_home(event)
        return home is not None and (home.entity_id == gainer or home.entity_id in absorbed)
    if event.event_type == STATISTIC_SHIFTED:
        return event.attribute("statistic") == "numNuclearWeapons" and (nation == gainer or nation in absorbed)
    if event.event_type == BREAKAWAY_PARENT_CHANGED:
        return nation in absorbed
    return False


def _readings(stream: Iterable[Event]) -> set[tuple[EntityId, str]]:
    return {
        (key, interval_of(event.id)) for event in by_type(stream, *READINGS) if (key := subject_id(event)) is not None
    }


@dataclass(frozen=True)
class IndependenceRule:
    """``nation.release`` / ``nation.breakaway``: a nation became independent, with its own events that follow.

    ``executive_faction`` is context, never a claim that the faction acted.
    """

    settings: GeopoliticsSettings
    name: str = "nation.independence_arc"
    emitted_types: frozenset[str] = frozenset({RELEASE, BREAKAWAY})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()

    @property
    def window_days(self) -> int:
        return self.settings.release_window_days

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        reports = interval_reports(situations)
        days = self.settings.release_window_days
        own_types = (nation_kinds.APPEARED.event_type, BREAKAWAY_PARENT_CHANGED, NATION_CONTROL)
        own = by_subject(by_type(stream, *own_types))
        built = []
        for anchor in sorted(by_type(stream, INDEPENDENCE), key=lambda event: event.id):
            nation = anchor.entities[0]
            high = shifted(latest(anchor), days)
            attached = [
                event
                for event in own.get(nation.entity_id, [])
                if overlaps(event, earliest(anchor), high) and stream.citable(event)
            ]
            constituents = [anchor, *attached]
            released = anchor.attribute("released") is True
            parents = refs_attribute(anchor, "parents")
            releasing = ref_attribute(anchor, "releasing_nation")
            if released:
                roles = [(Role.BENEFICIARY, nation)] + ([(Role.ACTOR, releasing)] if releasing is not None else [])
            else:
                roles = [(Role.ACTOR, nation), *((Role.TARGET, parent) for parent in parents)]
            built.append(
                build.event(
                    nation_kinds.RELEASE if released else nation_kinds.BREAKAWAY,
                    id_parts=[nation.entity_id],
                    constituents=constituents,
                    roles=roles,
                    join=Join.ENTITY,
                    attributes=(
                        ("parents", parents),
                        ("releasing_nation", releasing),
                        ("executive_faction", _executive_after(attached, reports, anchor, nation.entity_id)),
                        *bounded_shifts(
                            metric_shifts(
                                stream, [nation.entity_id, *(p.entity_id for p in parents)], intervals_of(constituents)
                            ),
                            roles,
                            self.settings.metric_shifts_max,
                        ),
                    ),
                    open=within(latest(anchor), last_date(situations), days),
                )
            )
        return built


def _executive_after(
    attached: Sequence[Event],
    reports: Mapping[str, tuple[SituationReport, SituationReport]],
    anchor: Event,
    nation_id: EntityId,
) -> EntityRef | None:
    controls = [
        event for event in attached if event.event_type == NATION_CONTROL and event.attribute("scope") == "executive"
    ]
    for control in sorted(controls, key=event_order, reverse=True):
        holder = ref_attribute(control, "after")
        if holder is not None:
            return holder
    around = reports.get(interval_of(anchor.id))
    nation = _nation(around[1], nation_id) if around is not None else None
    return nation.executive if nation is not None and isinstance(nation.executive, EntityRef) else None


@dataclass(frozen=True)
class ClaimsDeclaredRule:
    """``nation.claims_declared``: a nation's claim list gained regions held by other nations.

    The alien administration is skipped: its claims cover every region implicitly.
    """

    settings: GeopoliticsSettings
    name: str = CLAIMS_DECLARED
    emitted_types: frozenset[str] = frozenset({CLAIMS_DECLARED})
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()
    window_days: int | None = 0

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        built = []
        reports = interval_reports(situations)
        for anchor in sorted(by_type(stream, nation_kinds.CLAIMS_CHANGED.event_type), key=lambda event: event.id):
            nation = anchor.entities[0]
            around = reports.get(interval_of(anchor.id))
            claimant = _nation(around[1], nation.entity_id) if around is not None else None
            if claimant is not None and claimant.alien:
                continue
            regions = refs_attribute(anchor, "added")
            targets = [ref for ref in refs_attribute(anchor, "added_owners") if ref.entity_id != nation.entity_id]
            if not regions or not targets:
                continue
            roles = [(Role.ACTOR, nation), *((Role.TARGET, target) for target in targets)]
            shifts = metric_shifts(stream, [nation.entity_id], intervals_of([anchor]))
            built.append(
                build.event(
                    nation_kinds.CLAIMS_DECLARED,
                    id_parts=[nation.entity_id],
                    constituents=[anchor],
                    roles=roles,
                    join=Join.ENTITY,
                    attributes=(
                        ("regions", regions),
                        *bounded_shifts(shifts, roles, self.settings.metric_shifts_max),
                    ),
                    open=False,
                )
            )
        return built


@dataclass(frozen=True)
class ExpansionRule:
    """``nation.expansion``: one nation gained from others two or more times, each gain soon after the previous.

    A territory aggregate in an interval with a reading is part of that reading, not a gain of its own.
    """

    settings: GeopoliticsSettings
    name: str = EXPANSION
    emitted_types: frozenset[str] = frozenset({EXPANSION})
    reads: frozenset[str] = frozenset({CESSION, MERGER})
    explains: frozenset[str] = frozenset()

    @property
    def window_days(self) -> int:
        return self.settings.expansion_gap_days

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        explained = _readings(stream)
        nested = by_type(stream, CESSION, MERGER)
        gains: dict[EntityId, list[Event]] = defaultdict(list)
        for event in by_type(stream, ANNEXATION):
            key = subject_id(event)
            if key is not None:
                gains[key].append(event)
        for event in nested:
            gains[_gainer(event).entity_id].append(event)
        aggregates = by_subject(by_type(stream, TERRITORY_GAINED))
        for gainer_id, events in aggregates.items():
            for event in events:
                if (gainer_id, interval_of(event.id)) not in explained and stream.citable(event):
                    gains[gainer_id].append(event)
        days = self.settings.expansion_gap_days
        last = last_date(situations)
        built = []
        for gainer_id in sorted_keys(gains):
            for run in chained(gains[gainer_id], days):
                if len(run) >= 2:
                    built.append(self._expansion(stream, build, run, aggregates.get(gainer_id, []), last))
        return built

    def _expansion(
        self,
        stream: EventStream,
        build: NarrativeBuilder,
        run: list[Event],
        aggregates: Sequence[Event],
        last: str | None,
    ) -> Event:
        gainer = _gainer(run[0])
        losers = unique_refs(loser for gain in run for loser in _losers(gain))
        keys = set(intervals_of(run))
        territory = [event for event in aggregates if interval_of(event.id) in keys and stream.citable(event)]
        start = min((date for date in map(earliest, run) if date is not None), default=None)
        end = max((date for date in map(latest, run) if date is not None), default=None)
        loser_ids = {ref.entity_id for ref in losers}
        candidates = stream.union(
            stream.of_subject(loser_ids, NATION_DISAPPEARED), stream.of_subject(gainer.entity_id, RENAMED)
        )
        attached = [
            event
            for event in candidates
            if (
                (event.event_type == NATION_DISAPPEARED and subject_id(event) in loser_ids)
                or (event.event_type == RENAMED and subject_id(event) == gainer.entity_id)
            )
            and overlaps(event, start, end)
            and stream.citable(event)
        ]
        constituents = [*run, *(event for event in territory if event not in run), *attached]
        regions = unique_refs(region for event in (*run, *territory) for region in refs_attribute(event, "regions"))
        kinds = {gain.event_type for gain in run}
        readings = kinds & {MERGER, ANNEXATION}
        mode = None
        if readings:
            mode = (
                ("unification" if readings == {MERGER} else "annexation")
                if kinds == readings and len(readings) == 1
                else "mixed"
            )
        roles = [(Role.ACTOR, gainer), *((Role.TARGET, loser) for loser in losers)]
        shifts = metric_shifts(stream, [gainer.entity_id, *loser_ids], intervals_of(constituents))
        return build.event(
            nation_kinds.EXPANSION,
            id_parts=[gainer.entity_id],
            constituents=constituents,
            roles=roles,
            join=Join.HEURISTIC,
            attributes=(
                ("losers", losers),
                ("regions", regions),
                ("region_count", len(regions)),
                ("mode", mode),
                *bounded_shifts(shifts, roles, self.settings.metric_shifts_max),
            ),
            significance=Significance.MAJOR,
            open=within(end, last, self.settings.expansion_gap_days),
        )


def _gainer(gain: Event) -> EntityRef:
    if gain.event_type == CESSION:
        return next(ref for role, ref in gain.roles if role is Role.BENEFICIARY)
    return gain.entities[0]


def _losers(gain: Event) -> tuple[EntityRef, ...]:
    if gain.event_type == MERGER:
        return refs_attribute(gain, "absorbed")
    if gain.event_type == ANNEXATION:
        return tuple(ref for ref in gain.entities[1:2] if ref.entity_id.domain is EntityDomain.NATION)
    if gain.event_type == CESSION:
        return tuple(ref for role, ref in gain.roles if role is Role.ACTOR)
    return refs_attribute(gain, "counterparts")


def _since(keys: Iterable[str], started: str | None) -> list[str]:
    """All keys when ``started`` is unknown."""
    return [key for key in keys if (gap := days_between(started, key.partition(TIE_SEPARATOR)[0])) is None or gap >= 0]


def _closed_before(event: Event, started: str | None) -> bool:
    """Such an event cannot belong to a war begun later."""
    keys = intervals_of([event])
    return bool(keys) and not _since(keys, started) and event.event_type != WAR_APPEARED.event_type


@dataclass(frozen=True)
class WarArcRule:
    """``war.arc``: a war from its start (or the first save) to its end (or the last save), joined by the war's ID.

    Expansions between belligerents nest in place of the annexations they hold. ``nuclear_strikes`` is the
    campaign-wide counter over the war's span, not attributed to the war.
    """

    settings: GeopoliticsSettings
    name: str = WAR_ARC
    emitted_types: frozenset[str] = frozenset({WAR_ARC})
    reads: frozenset[str] = frozenset({EXPANSION})
    explains: frozenset[str] = frozenset()
    window_days: int | None = None

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        reports = interval_reports(situations)
        types = tuple(
            kind.event_type for kind in (WAR_APPEARED, ALLIANCE_CHANGED, LAST_FIGHTING_CHANGED, WAR_DISAPPEARED)
        )
        by_war = by_subject(by_type(stream, *types))
        listed: dict[EntityId, EntityRef] = {war.war.entity_id: war.war for report in situations for war in report.wars}
        first = {war.war.entity_id for war in situations[0].wars} if situations else set()
        built = []
        for war_id in sorted(set(by_war) | first, key=lambda entity_id: entity_id.sort_key):
            events = by_war.get(war_id, [])
            if war_id not in first and not any(event.event_type == WAR_APPEARED.event_type for event in events):
                continue
            ref = events[0].entities[0] if events else listed[war_id]
            event = self._arc(stream, situations, reports, build, ref, events)
            if event is not None:
                built.append(event)
        return built

    def _arc(
        self,
        stream: EventStream,
        situations: Sequence[SituationReport],
        reports: Mapping[str, tuple[SituationReport, SituationReport]],
        build: NarrativeBuilder,
        war: EntityRef,
        events: list[Event],
    ) -> Event | None:
        keys = [key for key, pair in reports.items() if any(_war_in(report, war.entity_id) for report in pair)]

        def belligerents(gainer: EntityId, loser: EntityId, key: str) -> bool:
            return any(
                any(found.war.entity_id == war.entity_id for found in opposed(report, gainer, loser))
                for report in reports.get(key, ())
            )

        expansions = [
            expansion
            for expansion in by_type(stream, EXPANSION)
            if any(
                belligerents(expansion.entities[0].entity_id, loser.entity_id, key)
                for key in set(expansion.intervals) & set(keys)
                for role, loser in expansion.roles
                if role is Role.TARGET
            )
        ]
        nested = {constituent for expansion in expansions for constituent in expansion.constituents}
        annexations = [
            event
            for event in by_type(stream, ANNEXATION)
            if interval_of(event.id) in keys
            and len(event.entities) > 1
            and belligerents(event.entities[0].entity_id, event.entities[1].entity_id, interval_of(event.id))
        ]
        constituents = [*events, *(event for event in annexations if stream.citable(event)), *expansions]
        if not constituents:
            return None
        attackers, defenders = self._sides(situations, war.entity_id, events)
        nested_annexations = [
            event for event in map(stream.get, nested) if event is not None and event.event_type == ANNEXATION
        ]
        regions = unique_refs(
            region for event in (*annexations, *nested_annexations) for region in refs_attribute(event, "regions")
        )
        appeared = next((event for event in events if event.event_type == WAR_APPEARED.event_type), None)
        started = appeared.attribute("started_on") if appeared is not None else None
        if not isinstance(started, str):
            started = next(
                (
                    w.start_date
                    for r in situations
                    for w in r.wars
                    if w.war.entity_id == war.entity_id and isinstance(w.start_date, str)
                ),
                None,
            )
        constituents = [event for event in constituents if not _closed_before(event, started)]
        if not constituents:
            return None
        disappeared = next((event for event in events if event.event_type == WAR_DISAPPEARED.event_type), None)
        duration = days_between(started, None if disappeared is None else latest(disappeared))
        # An interval-dated end is the save by which the war had ended, so the span is only an upper bound; an open war
        # has no length yet.
        recorded = disappeared is not None and disappeared.date_basis is DateBasis.RECORD
        measured = None if duration is None else round(duration, 1)
        ordered = sorted(keys, key=interval_sort_key)
        strikes = None
        if ordered:
            strikes = _counter_delta(reports[ordered[0]][0], reports[ordered[-1]][1], "nuclearStrikes")
        sides = {ref.entity_id for ref in (*attackers, *defenders)}
        roles = [*((Role.ACTOR, ref) for ref in attackers), *((Role.TARGET, ref) for ref in defenders)]
        shifts = metric_shifts(stream, sides, _since(intervals_of(constituents), started))
        return build.event(
            WAR_ARC_KIND,
            id_parts=[war.entity_id],
            constituents=constituents,
            roles=roles,
            join=Join.ENTITY,
            attributes=(
                ("war", war),
                ("started_on", started),
                ("duration_days", measured if recorded else None),
                ("duration_days_at_most", None if recorded else measured),
                ("attackers", attackers),
                ("defenders", defenders),
                ("regions_transferred", regions),
                ("nuclear_strikes", strikes),
                *bounded_shifts(shifts, roles, self.settings.metric_shifts_max),
            ),
            anchor=war,
            significance=Significance.MAJOR,
            starts_on=started,
        )

    @staticmethod
    def _sides(
        situations: Sequence[SituationReport], war_id: EntityId, events: Sequence[Event]
    ) -> tuple[tuple[EntityRef, ...], tuple[EntityRef, ...]]:
        attackers: list[EntityRef] = []
        defenders: list[EntityRef] = []
        for report in situations:
            for war in report.wars:
                if war.war.entity_id == war_id:
                    for side, value in ((attackers, war.attacking_alliance), (defenders, war.defending_alliance)):
                        side.extend(_refs(value))
        for event in events:
            member = ref_attribute(event, "member")
            if event.event_type == ALLIANCE_CHANGED.event_type and member is not None:
                (attackers if event.attribute("side") == "attacking" else defenders).append(member)
        return unique_refs(attackers), unique_refs(defenders)


def _war_in(report: SituationReport, war_id: EntityId) -> bool:
    return any(war.war.entity_id == war_id for war in report.wars)


def _counter_delta(before: SituationReport, after: SituationReport, name: str) -> int | None:
    first, last = dict(before.world.nuclear).get(name), dict(after.world.nuclear).get(name)
    if isinstance(first, int) and isinstance(last, int) and not isinstance(first, bool) and not isinstance(last, bool):
        return last - first
    return None


def geopolitical_rules(
    settings: GeopoliticsSettings,
) -> tuple[
    TakeoverRule,
    TakeoverWaveRule,
    FederationLifecycleRule,
    CessionRule,
    MergerRule,
    IndependenceRule,
    ClaimsDeclaredRule,
    ExpansionRule,
    WarArcRule,
]:
    return (
        TakeoverRule(settings),
        TakeoverWaveRule(settings),
        FederationLifecycleRule(settings),
        CessionRule(settings),
        MergerRule(settings),
        IndependenceRule(settings),
        ClaimsDeclaredRule(settings),
        ExpansionRule(settings),
        WarArcRule(settings),
    )
