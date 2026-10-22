"""The geopolitical narrative rules of architecture 11.3, over the qualified stream and the situation reports.

Each rule emits only from its anchor and attaches further events by entity, and by a window in game days from
``config.GeopoliticsSettings``. Two kinds of window are used:

- *anchored*: an event joins when its earliest possible date (its record date, else its ``not_before``) is within
  the window after the first member's date, so the span is bounded (takeover, release, transformation);
- *chained*: an event joins when its earliest possible date is within the window after the latest member's date, so
  a sequence of gains can run for years (expansion).

A rule whose window can still take events from a later save says so with ``open``; a one-interval rule is never
open. Every rule carries ``metric_shifts`` (``metric_shifts``), the nation statistic shifts of its nations in the
intervals it spans, as literal values: no band label ("democratic") is ever assigned. The shifts are named by event
ID and are not constituents, so they never widen a span or change status, confidence or significance.

Order 0 builds on the atomic stream; ``nation.expansion`` (order 1) nests the cessions it is made of; ``war.arc``
and ``nation.transformation`` (order 2) nest the expansions fought out between belligerents and step aside for a
development that already carries the shifts. No rule names a motive, an assistance without army evidence or a public
framing: that stays with the narrator (architecture 20).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass

from ..config import GeopoliticsSettings
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import DateBasis, Event, Role, Significance
from ..model.values import FieldValue, FrozenMap, Observed, Unknown
from .aggregation import Join, NarrativeBuilder, days_between, interval_reports
from .chronology import interval_of, interval_sort_key
from .rulekit import (
    anchored,
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

TAKEOVER = "faction.takeover"
WAR_ARC = "war.arc"
FEDERATION_LIFECYCLE = "federation.lifecycle"
EXPANSION = "nation.expansion"
CESSION = "nation.cession"
RELEASE = "nation.release"
BREAKAWAY = "nation.breakaway"
CLAIMS_DECLARED = "nation.claims_declared"
TRANSFORMATION = "nation.transformation"

NATION_CONTROL = "faction.nation_control_changed"
CONTROLLER_CHANGED = "control_point.controller_changed"
EXECUTIVE_RECORDED = "nation.executive_change_recorded"
UNREST_ATTEMPTS = "nation.unrest_attempts_changed"
STATISTIC_SHIFTED = "nation.statistic_shifted"
TRANSACTION = "faction.transaction_recorded"
TERRITORY_GAINED = "nation.territory_gained"
TERRITORY_LOST = "nation.territory_lost"
UNIFICATION = "nation.unification"
ANNEXATION = "nation.annexation"
INDEPENDENCE = "nation.independence"

TAKEOVER_SCOPES = ("executive", "sole")
"""The ``faction.nation_control_changed`` scopes that anchor a takeover; a plurality is not control."""
INDEPENDENCE_CAUSE = "Independence"
"""A control change with this executive cause is the new nation's own; ``nation.release``/``breakaway`` reports it."""
TAKEOVER_COUNCILOR_TYPES = ("councilor.faction_changed", "councilor.disappeared", "councilor.detaining_faction_changed")
PRECURSOR_STATISTICS = frozenset({"unrest", "publicOpinion"})
TAKEOVER_LEDGER_LABELS = frozenset({"Coup", "Purge", "Crackdown"})
"""Mission charges that corroborate a takeover under the bounds of architecture 11.3."""
TRANSFORMATION_STATISTICS = frozenset({"democracy", "GDP", "inequality", "cohesion", "unrest"})
"""The regime and economy statistics whose joint movement is a transformation (architecture 11.3)."""
READINGS = (UNIFICATION, ANNEXATION, INDEPENDENCE)
"""The territorial readings that explain a gain; a gain without one is a cession candidate."""
SHIFT_CARRIERS = frozenset({TAKEOVER, EXPANSION, CESSION, RELEASE, BREAKAWAY})
"""Developments whose ``metric_shifts`` already state a transformation of their nations."""


# --- Situation context -------------------------------------------------------------------------------------------


def _nation(report: SituationReport, nation_id: EntityId) -> NationSituation | None:
    return next((item for item in report.nations if item.nation.entity_id == nation_id), None)


def _refs(value: Observed) -> tuple[EntityRef, ...]:
    """The references of a known list; nothing for an unknown or non-list value."""
    return tuple(item for item in value if isinstance(item, EntityRef)) if isinstance(value, tuple) else ()


def _members(value: Observed) -> set[EntityId]:
    return {item.entity_id for item in _refs(value)}


def opposed(report: SituationReport, first: EntityId, second: EntityId) -> list[WarSituation]:
    """The wars of the report with the two nations on opposite sides."""
    found = []
    for war in report.wars:
        attackers, defenders = _members(war.attacking_alliance), _members(war.defending_alliance)
        if (first in attackers and second in defenders) or (first in defenders and second in attackers):
            found.append(war)
    return found


def gdp_rank(report: SituationReport, nation_id: EntityId) -> int | None:
    """The nation's place by ``GDP`` among the report's nations with a known value (1 is the largest)."""
    known = [
        (value, item.nation.entity_id)
        for item in report.nations
        if isinstance(value := dict(item.statistics).get("GDP"), int | float) and not isinstance(value, bool)
    ]
    ordered = sorted(known, key=lambda pair: (-pair[0], pair[1].sort_key))
    return next((position for position, (_, key) in enumerate(ordered, start=1) if key == nation_id), None)


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
    """The ``nation.statistic_shifted`` events of ``nations`` in ``intervals``, one entry per nation, statistic and key.

    An entry holds ``nation``, ``statistic``, ``key`` (public opinion only), ``before`` (the earliest shift's value),
    ``after`` (the latest shift's), the unsigned ``relative_change`` between them, ``not_before`` (the earliest shift's)
    and ``date`` with its ``date_basis`` (the latest shift's), which bound when the net change happened, the summed
    per-reason ``causes`` when the shifts carry them, and the shift ``events`` by ID. The net covers the reported
    shifts only: an interval in between whose change stayed below the analyzer's threshold is not reported.
    ``windows`` limits a nation to its own intervals; a nation without a window keeps all of ``intervals``.
    """
    wanted, keys = set(nations), set(intervals)
    groups: dict[tuple[EntityId, str, str], list[Event]] = defaultdict(list)
    for event in stream:
        nation = subject_id(event)
        if event.event_type != STATISTIC_SHIFTED or nation not in wanted or interval_of(event.id) not in keys:
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


# --- Rules -------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TakeoverRule:
    """``faction.takeover``: a faction took a nation's executive or every control point, and what came with it.

    Anchors are ``faction.nation_control_changed`` events of scope executive or sole with a faction as the new holder;
    those of one nation and faction within the consolidation window after the first are one takeover (an executive
    change, then every point, is its consolidation), until the faction loses the seat again. A control change caused
    by ``Independence`` is left to the release and breakaway rule. Attached: the nation's control-point gains by the
    faction from the precursor window before to the consolidation window after, its executive records, councilor
    changes naming the losing faction in the anchor intervals, the faction's unrest attempts and the nation's unrest
    and opinion shifts in the precursor window, and the faction's ``Coup``/``Purge``/``Crackdown`` charges dated from
    the ledger window before an anchor to its date, only when no other faction carries the label then (architecture
    11.3, bound 4). Open while the last report has the faction holding the executive but not every point.
    """

    settings: GeopoliticsSettings
    name: str = TAKEOVER
    order: int = 0

    @property
    def window_days(self) -> int:
        return self.settings.takeover_consolidation_days

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        reports = interval_reports(situations)
        by_nation = by_subject(by_type(stream, NATION_CONTROL))
        built = []
        for nation_id in sorted_keys(by_nation):
            for run in self._runs(by_nation[nation_id]):
                built.append(self._takeover(stream, situations, reports, build, run))
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
        stream: Sequence[Event],
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
        for event in stream:
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
        corroborating = self._ledger(stream, anchors, actor)
        constituents = [*anchors, *attached]
        intervals = intervals_of([*constituents, *corroborating])
        first_after = reports.get(intervals_of(anchors[:1])[0])
        rank = gdp_rank(first_after[1], nation.entity_id) if first_after is not None else None
        cause = next(
            (value for value in (anchor.attribute("cause") for anchor in anchors) if isinstance(value, str)), None
        )
        defining = rank is not None and rank <= settings.top_gdp_nations
        roles = [(Role.ACTOR, actor), (Role.TARGET, nation)]
        if loser is not None:
            roles.append((Role.LOSER, loser))
        return build.event(
            TAKEOVER,
            id_parts=[nation.entity_id, actor.entity_id],
            constituents=constituents,
            corroborating=corroborating,
            roles=roles,
            join=Join.HEURISTIC,
            attributes=(
                ("scopes", tuple(sorted({str(anchor.attribute("scope")) for anchor in anchors}))),
                ("cause", cause),
                ("consolidated", any(anchor.attribute("scope") == "sole" for anchor in anchors)),
                ("gdp_rank", rank),
                ("metric_shifts", metric_shifts(stream, [nation.entity_id], intervals)),
            ),
            significance=Significance.CAMPAIGN_DEFINING if defining else Significance.MAJOR,
            open=_holds_executive_only(situations, nation.entity_id, actor.entity_id),
        )

    def _ledger(self, stream: Sequence[Event], anchors: Sequence[Event], actor: EntityRef) -> list[Event]:
        charges = [
            event for event in by_type(stream, TRANSACTION) if event.attribute("label") in TAKEOVER_LEDGER_LABELS
        ]
        found: dict[str, Event] = {}
        for anchor in anchors:
            low = shifted(earliest(anchor), -self.settings.ledger_window_days)
            window = [charge for charge in charges if overlaps(charge, low, latest(anchor))]
            for label in sorted(TAKEOVER_LEDGER_LABELS):
                labelled = [charge for charge in window if charge.attribute("label") == label]
                candidates = {ref.entity_id for ref in map(subject, labelled) if ref is not None}
                if candidates == {actor.entity_id}:
                    found.update((charge.id, charge) for charge in labelled)
        return list(found.values())


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


def _membership_windows(
    reports: Mapping[str, tuple[SituationReport, SituationReport]], federation_id: EntityId, nations: Iterable[EntityId]
) -> dict[EntityId, set[str]]:
    """The intervals in which each nation was a member of the federation at either end of the interval.

    The interval of a join or leave counts, as the change happened somewhere inside it; intervals wholly before a
    join or after a leave do not.
    """
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

    Anchored by ``federation.appeared`` or by presence in the first report; a federation no event mentions is not
    reported. Objective when every constituent is; open while the federation exists in the last report; ``major``,
    like the federation's presence.
    """

    settings: GeopoliticsSettings
    name: str = FEDERATION_LIFECYCLE
    order: int = 0
    window_days: int | None = None

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        types = ("federation.appeared", "federation.members_changed", "federation.renamed", "federation.disappeared")
        by_federation = by_subject(by_type(stream, *types))
        first = {item.federation.entity_id for item in situations[0].federations} if situations else set()
        reports = interval_reports(situations)
        built = []
        for federation_id in sorted_keys(by_federation):
            events = sorted(by_federation[federation_id], key=event_order)
            if federation_id not in first and not any(event.event_type == "federation.appeared" for event in events):
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
                FrozenMap(
                    (
                        ("date", _literal(event.date)),
                        ("nation", ref_attribute(event, "member")),
                        ("transition", _literal(event.attribute("transition"))),
                    )
                )
                for event in events
                if event.event_type == "federation.members_changed" and ref_attribute(event, "member") is not None
            )
            members = {ref.entity_id for ref in initial} | {ref.entity_id for ref in final}
            members |= {ref.entity_id for event in events for ref in event.entities[1:]}
            windows = _membership_windows(reports, federation_id, members)
            federation = events[0].entities[0]
            built.append(
                build.event(
                    FEDERATION_LIFECYCLE,
                    id_parts=[federation_id],
                    constituents=events,
                    roles=[(Role.ACTOR, federation)],
                    join=Join.ENTITY,
                    attributes=(
                        ("members_initial", initial),
                        ("member_changes", changes),
                        ("members_final", final),
                        ("metric_shifts", metric_shifts(stream, members, intervals_of(events), windows)),
                    ),
                    anchor=federation,
                    significance=Significance.MAJOR,
                )
            )
        return built


@dataclass(frozen=True)
class CessionRule:
    """``nation.cession``: in one interval, a nation's regions went to another with no reading that explains it.

    The pair is a ``nation.territory_gained`` of the gainer listing the loser and a ``nation.territory_lost`` of the
    loser listing the gainer, with no unification, annexation or independence reading of the gainer in the interval
    and no war with the two on opposite sides in either report around it. A conquest without a war looks the same,
    so the heuristic join keeps the confidence at medium at most. Allies and a shared federation, from the earlier
    report, are context.
    """

    settings: GeopoliticsSettings
    name: str = CESSION
    order: int = 0
    window_days: int | None = 0

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
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
        self, stream: Sequence[Event], build: NarrativeBuilder, gain: Event, loss: Event, before: SituationReport | None
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
        return build.event(
            CESSION,
            id_parts=[loser.entity_id, gainer.entity_id],
            constituents=constituents,
            roles=[(Role.ACTOR, loser), (Role.BENEFICIARY, gainer), *((Role.LOCATION, region) for region in regions)],
            join=Join.HEURISTIC,
            attributes=(
                ("regions", regions),
                ("region_count", len(regions)),
                ("allied", allied),
                ("shared_federation", shared),
                (
                    "metric_shifts",
                    metric_shifts(stream, [gainer.entity_id, loser.entity_id], intervals_of(constituents)),
                ),
            ),
            significance=Significance.MAJOR,
            open=False,
        )


def _readings(stream: Iterable[Event]) -> set[tuple[EntityId, str]]:
    """The (gainer, interval) pairs with a unification, annexation or independence reading."""
    return {
        (key, interval_of(event.id)) for event in by_type(stream, *READINGS) if (key := subject_id(event)) is not None
    }


@dataclass(frozen=True)
class IndependenceRule:
    """``nation.release`` / ``nation.breakaway``: a nation became independent, with its own events that follow.

    Anchored by ``nation.independence``; ``released`` decides the type. Attached within the release window: the new
    nation's ``nation.appeared``, ``nation.breakaway_parent_changed`` and ``faction.nation_control_changed``. The
    faction holding its executive afterwards is context (``executive_faction``), never a claim that it acted. Open
    while a later save could still fall in the window.
    """

    settings: GeopoliticsSettings
    name: str = "nation.independence_arc"
    order: int = 0

    @property
    def window_days(self) -> int:
        return self.settings.release_window_days

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        reports = interval_reports(situations)
        days = self.settings.release_window_days
        own_types = ("nation.appeared", "nation.breakaway_parent_changed", NATION_CONTROL)
        own = by_subject(by_type(stream, *own_types))
        built = []
        for anchor in sorted(by_type(stream, INDEPENDENCE), key=lambda event: event.id):
            nation = anchor.entities[0]
            high = shifted(latest(anchor), days)
            attached = [event for event in own.get(nation.entity_id, []) if overlaps(event, earliest(anchor), high)]
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
                    RELEASE if released else BREAKAWAY,
                    id_parts=[nation.entity_id],
                    constituents=constituents,
                    roles=roles,
                    join=Join.ENTITY,
                    attributes=(
                        ("parents", parents),
                        ("releasing_nation", releasing),
                        ("executive_faction", _executive_after(attached, reports, anchor, nation.entity_id)),
                        (
                            "metric_shifts",
                            metric_shifts(
                                stream, [nation.entity_id, *(p.entity_id for p in parents)], intervals_of(constituents)
                            ),
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
    """``nation.claims_declared``: a nation's claim list gained regions held by other nations (``added_owners``).

    Additions on regions the claimant holds itself name no target and emit nothing.
    """

    settings: GeopoliticsSettings
    name: str = CLAIMS_DECLARED
    order: int = 0
    window_days: int | None = 0

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        built = []
        for anchor in sorted(by_type(stream, "nation.claims_changed"), key=lambda event: event.id):
            nation = anchor.entities[0]
            regions = refs_attribute(anchor, "added")
            targets = [ref for ref in refs_attribute(anchor, "added_owners") if ref.entity_id != nation.entity_id]
            if not regions or not targets:
                continue
            built.append(
                build.event(
                    CLAIMS_DECLARED,
                    id_parts=[nation.entity_id],
                    constituents=[anchor],
                    roles=[(Role.ACTOR, nation), *((Role.TARGET, target) for target in targets)],
                    join=Join.ENTITY,
                    attributes=(
                        ("regions", regions),
                        ("metric_shifts", metric_shifts(stream, [nation.entity_id], intervals_of([anchor]))),
                    ),
                    open=False,
                )
            )
        return built


@dataclass(frozen=True)
class ExpansionRule:
    """``nation.expansion``: one nation gained from others two or more times, each gain soon after the previous.

    A gain is a ``nation.unification``, a ``nation.annexation``, a ``nation.cession`` to the nation (nested, order 0)
    or a ``nation.territory_gained`` no cession covers in an interval without an independence reading for the
    gainer; a territory aggregate in an interval with a unification or annexation reading is part of that reading,
    not a gain of its own. Attached: the gainer's territory aggregates in the run's intervals, the losers'
    ``nation.disappeared`` and the gainer's ``nation.renamed`` in the span. ``mode`` is ``unification`` or
    ``annexation`` when the readings are of one kind, ``mixed`` when they are not, ``None`` with no reading.
    """

    settings: GeopoliticsSettings
    name: str = EXPANSION
    order: int = 1

    @property
    def window_days(self) -> int:
        return self.settings.expansion_gap_days

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        explained = _readings(stream)
        cessions = [event for event in stream if event.event_type == CESSION]
        covered = {constituent for event in cessions for constituent in event.constituents}
        gains: dict[EntityId, list[Event]] = defaultdict(list)
        for event in by_type(stream, UNIFICATION, ANNEXATION):
            key = subject_id(event)
            if key is not None:
                gains[key].append(event)
        for event in cessions:
            gains[_gainer(event).entity_id].append(event)
        aggregates = by_subject(by_type(stream, TERRITORY_GAINED))
        for gainer_id, events in aggregates.items():
            for event in events:
                if (gainer_id, interval_of(event.id)) not in explained and event.id not in covered:
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
        stream: Sequence[Event],
        build: NarrativeBuilder,
        run: list[Event],
        aggregates: Sequence[Event],
        last: str | None,
    ) -> Event:
        gainer = _gainer(run[0])
        losers = unique_refs(loser for gain in run for loser in _losers(gain))
        keys = set(intervals_of(run))
        inside = {constituent for gain in run for constituent in gain.constituents}
        territory = [event for event in aggregates if interval_of(event.id) in keys and event.id not in inside]
        start = min((date for date in map(earliest, run) if date is not None), default=None)
        end = max((date for date in map(latest, run) if date is not None), default=None)
        loser_ids = {ref.entity_id for ref in losers}
        attached = [
            event
            for event in stream
            if (
                (event.event_type == "nation.disappeared" and subject_id(event) in loser_ids)
                or (event.event_type == "nation.renamed" and subject_id(event) == gainer.entity_id)
            )
            and overlaps(event, start, end)
        ]
        constituents = [*run, *(event for event in territory if event not in run), *attached]
        regions = unique_refs(region for event in (*run, *territory) for region in refs_attribute(event, "regions"))
        kinds = {gain.event_type for gain in run}
        readings = kinds & {UNIFICATION, ANNEXATION}
        mode = None
        if readings:
            mode = (
                ("unification" if readings == {UNIFICATION} else "annexation")
                if kinds == readings and len(readings) == 1
                else "mixed"
            )
        intervals = intervals_of(constituents)
        return build.event(
            EXPANSION,
            id_parts=[gainer.entity_id],
            constituents=constituents,
            roles=[(Role.ACTOR, gainer), *((Role.TARGET, loser) for loser in losers)],
            join=Join.HEURISTIC,
            attributes=(
                ("losers", losers),
                ("regions", regions),
                ("region_count", len(regions)),
                ("mode", mode),
                ("metric_shifts", metric_shifts(stream, [gainer.entity_id, *loser_ids], intervals)),
            ),
            significance=Significance.MAJOR,
            open=within(end, last, self.settings.expansion_gap_days),
        )


def _gainer(gain: Event) -> EntityRef:
    if gain.is_narrative:
        return next(ref for role, ref in gain.roles if role is Role.BENEFICIARY)
    return gain.entities[0]


def _losers(gain: Event) -> tuple[EntityRef, ...]:
    if gain.event_type == UNIFICATION:
        return refs_attribute(gain, "unified")
    if gain.event_type == ANNEXATION:
        return tuple(ref for ref in gain.entities[1:2] if ref.entity_id.domain is EntityDomain.NATION)
    if gain.event_type == CESSION:
        return tuple(ref for role, ref in gain.roles if role is Role.ACTOR)
    return refs_attribute(gain, "counterparts")


@dataclass(frozen=True)
class WarArcRule:
    """``war.arc``: a war from its start (or the first save) to its end (or the last save), joined by the war's ID.

    Anchored by ``war.appeared`` or by presence in the first report. Attached: its alliance, last-fighting and
    disappearance events; every ``nation.annexation`` in an interval the war spans whose gainer and loser are on
    opposite sides in a report around it; and every ``nation.expansion`` with such a pair in an interval both span,
    nested, in place of the annexations it already holds. Sides are the union over the reports and the alliance
    events. ``nuclear_strikes`` is the campaign-wide counter's change between the reports bounding the war's
    intervals: it is not attributed to the war. Objective when every constituent is; open while the war exists in
    the last report; ``major``, like the war's presence, even when only its last-fighting date moved.
    """

    settings: GeopoliticsSettings
    name: str = WAR_ARC
    order: int = 2
    window_days: int | None = None

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        reports = interval_reports(situations)
        types = ("war.appeared", "war.alliance_changed", "war.last_fighting_changed", "war.disappeared")
        by_war = by_subject(by_type(stream, *types))
        listed: dict[EntityId, EntityRef] = {war.war.entity_id: war.war for report in situations for war in report.wars}
        first = {war.war.entity_id for war in situations[0].wars} if situations else set()
        built = []
        for war_id in sorted(set(by_war) | first, key=lambda entity_id: entity_id.sort_key):
            events = by_war.get(war_id, [])
            if war_id not in first and not any(event.event_type == "war.appeared" for event in events):
                continue
            ref = events[0].entities[0] if events else listed[war_id]
            event = self._arc(stream, situations, reports, build, ref, events)
            if event is not None:
                built.append(event)
        return built

    def _arc(
        self,
        stream: Sequence[Event],
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
            for expansion in stream
            if expansion.event_type == EXPANSION
            and any(
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
        constituents = [*events, *(event for event in annexations if event.id not in nested), *expansions]
        if not constituents:
            return None
        attackers, defenders = self._sides(situations, war.entity_id, events)
        by_id = {event.id: event for event in stream}
        regions = unique_refs(
            region
            for event in (
                *annexations,
                *(by_id[key] for key in nested if key in by_id and by_id[key].event_type == ANNEXATION),
            )
            for region in refs_attribute(event, "regions")
        )
        appeared = next((event for event in events if event.event_type == "war.appeared"), None)
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
        disappeared = next((event for event in events if event.event_type == "war.disappeared"), None)
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
        return build.event(
            WAR_ARC,
            id_parts=[war.entity_id],
            constituents=constituents,
            roles=[*((Role.ACTOR, ref) for ref in attackers), *((Role.TARGET, ref) for ref in defenders)],
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
                ("metric_shifts", metric_shifts(stream, sides, intervals_of(constituents))),
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
            if event.event_type == "war.alliance_changed" and member is not None:
                (attackers if event.attribute("side") == "attacking" else defenders).append(member)
        return unique_refs(attackers), unique_refs(defenders)


def _war_in(report: SituationReport, war_id: EntityId) -> bool:
    return any(war.war.entity_id == war_id for war in report.wars)


def _counter_delta(before: SituationReport, after: SituationReport, name: str) -> int | None:
    first, last = dict(before.world.nuclear).get(name), dict(after.world.nuclear).get(name)
    if isinstance(first, int) and isinstance(last, int) and not isinstance(first, bool) and not isinstance(last, bool):
        return last - first
    return None


@dataclass(frozen=True)
class TransformationRule:
    """``nation.transformation``: two or more of one nation's regime and economy statistics shifted together.

    The shifts (``TRANSFORMATION_STATISTICS``) of one nation within the transformation window after the first form one
    run; a run with two or more distinct statistics is a transformation, unless a takeover, expansion, cession,
    release or breakaway naming the nation spans one of its intervals: that development already carries the shifts
    as ``metric_shifts``. Literal values and relative changes only. Open while a later save could still fall in the
    window.
    """

    settings: GeopoliticsSettings
    name: str = TRANSFORMATION
    order: int = 2

    @property
    def window_days(self) -> int:
        return self.settings.transformation_window_days

    def apply(
        self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
    ) -> list[Event]:
        shifts = [
            event
            for event in by_type(stream, STATISTIC_SHIFTED)
            if event.attribute("statistic") in TRANSFORMATION_STATISTICS
        ]
        carriers = [event for event in stream if event.event_type in SHIFT_CARRIERS]
        days = self.settings.transformation_window_days
        last = last_date(situations)
        built = []
        by_nation = by_subject(shifts)
        for nation_id in sorted_keys(by_nation):
            for run in anchored(by_nation[nation_id], days):
                statistics = sorted({str(event.attribute("statistic")) for event in run})
                if len(statistics) < 2:
                    continue
                keys = set(intervals_of(run))
                if any(
                    keys & set(carrier.intervals) and any(ref.entity_id == nation_id for _, ref in carrier.roles)
                    for carrier in carriers
                ):
                    continue
                nation = run[0].entities[0]
                built.append(
                    build.event(
                        TRANSFORMATION,
                        id_parts=[nation_id],
                        constituents=run,
                        roles=[(Role.ACTOR, nation)],
                        join=Join.ENTITY,
                        attributes=(
                            ("statistics", tuple(statistics)),
                            ("metric_shifts", metric_shifts(stream, [nation_id], keys)),
                        ),
                        open=within(latest(run[0]), last, days),
                    )
                )
        return built


def geopolitical_rules(
    settings: GeopoliticsSettings,
) -> tuple[
    TakeoverRule,
    FederationLifecycleRule,
    CessionRule,
    IndependenceRule,
    ClaimsDeclaredRule,
    ExpansionRule,
    WarArcRule,
    TransformationRule,
]:
    """The geopolitical rules under ``settings``."""
    return (
        TakeoverRule(settings),
        FederationLifecycleRule(settings),
        CessionRule(settings),
        IndependenceRule(settings),
        ClaimsDeclaredRule(settings),
        ExpansionRule(settings),
        WarArcRule(settings),
        TransformationRule(settings),
    )
