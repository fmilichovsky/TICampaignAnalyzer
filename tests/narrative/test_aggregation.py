"""The narrative aggregation framework: the builder's shared policy and the rule runner, with trivial test rules."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace

import pytest

from tests.analyzers.support import fixture_kind
from tests.narrative.support import CitingRule, GroupRule, atomic, faction, nation, situation, state_change
from tinarrative.kinds.narrative import narrative_kind
from tinarrative.kinds.space import FLEET_BUILDUP
from tinarrative.model.entities import EntityRef
from tinarrative.model.events import Confidence, DateBasis, Event, EventSource, EventStatus, Role, Significance
from tinarrative.model.kinds import EventKind
from tinarrative.model.values import Unknown
from tinarrative.narrative.aggregation import Join, NarrativeBuilder, aggregate, days_between, present_in
from tinarrative.narrative.situation import SituationReport
from tinarrative.narrative.stream import EventStream

K1 = "2032-04-01T00:00:00"
K2 = "2032-07-01T00:00:00"
K3 = "2032-10-01T00:00:00"
GERMANY = nation("1", "Germany")
FRANCE = nation("2", "France")
RULE = GroupRule("changes", "nation.changed")
CHANGED_ARC = fixture_kind("nation.changed.arc")
SCORED_ARC = narrative_kind("nation.scored.arc", lambda event: event.id, frozenset(), base=Significance.MAJOR)


def changed(key: str, subject: EntityRef = GERMANY, **overrides: object) -> Event:
    previous = {K1: "2032-01-01T00:00:00", K2: K1, K3: K2}[key]
    fields: dict[str, object] = {"not_before": previous, "entities": (subject,)}
    fields.update(overrides)
    return atomic(f"nation.changed/{subject.entity_id}", key, **fields)  # type: ignore[arg-type]


def only(stream: Sequence[Event], rule: GroupRule = RULE, situations: Sequence[SituationReport] = ()) -> Event:
    [event] = aggregate(stream, situations, [rule])
    return event


def test_no_rules_build_no_narrative_events() -> None:
    assert aggregate([changed(K1)], [situation(K1)], ()) == []


def test_span_runs_from_the_earliest_not_before_to_the_latest_date_with_their_bases() -> None:
    event = only([changed(K1), changed(K2, date="2032-05-15T00:00:00", date_basis=DateBasis.RECORD)])

    assert (event.start, event.start_basis) == ("2032-01-01T00:00:00", DateBasis.INTERVAL)
    assert (event.end, event.end_basis) == ("2032-05-15T00:00:00", DateBasis.RECORD)
    assert (event.date, event.date_basis, event.not_before) == (event.end, event.end_basis, event.start)
    assert event.is_narrative


def test_a_record_dated_constituent_narrows_the_start() -> None:
    event = only([changed(K2, date="2032-05-15T00:00:00", date_basis=DateBasis.RECORD)])

    assert (event.start, event.start_basis) == ("2032-05-15T00:00:00", DateBasis.RECORD)
    assert event.not_before == K1


def test_a_rule_can_start_the_span_at_a_record_date_before_every_constituent() -> None:
    event = NarrativeBuilder([]).event(
        CHANGED_ARC,
        id_parts=[GERMANY.entity_id],
        constituents=[changed(K1)],
        roles=[],
        join=Join.ENTITY,
        starts_on="2031-06-01T00:00:00",
    )

    assert (event.start, event.start_basis) == ("2031-06-01T00:00:00", DateBasis.RECORD)
    assert event.not_before == "2032-01-01T00:00:00"


def test_a_narrative_event_of_a_kind_takes_its_type_and_has_its_attributes_checked() -> None:
    def build(attributes: tuple[tuple[str, object], ...]) -> Event:
        return NarrativeBuilder([]).event(
            FLEET_BUILDUP,
            id_parts=[GERMANY.entity_id],
            constituents=[changed(K1)],
            roles=[],
            join=Join.ENTITY,
            attributes=attributes,  # type: ignore[arg-type]
        )

    event = build((("hull", "Frigate"), ("count", 3)))

    assert event.event_type == FLEET_BUILDUP.event_type
    assert event.id.startswith(f"{FLEET_BUILDUP.event_type}/")
    assert dict(event.attributes) == {"hull": "Frigate", "count": 3}
    with pytest.raises(ValueError, match="missing"):
        build((("hull", "Frigate"),))
    with pytest.raises(ValueError, match="undeclared"):
        build((("hull", "Frigate"), ("count", 3), ("extra", 1)))


def test_a_corroborating_event_is_cited_and_may_narrow_the_start_but_never_sets_the_end() -> None:
    anchor = changed(K2)
    charge = atomic("nation.charge", K2, date=K2, date_basis=DateBasis.RECORD, entities=(GERMANY,))
    early = atomic("nation.charge", K1, date="2032-03-20T00:00:00", date_basis=DateBasis.RECORD, entities=(GERMANY,))

    event = NarrativeBuilder([]).event(
        CHANGED_ARC,
        id_parts=[GERMANY.entity_id],
        constituents=[anchor],
        corroborating=[charge, early],
        roles=[],
        join=Join.ENTITY,
    )

    assert (event.end, event.end_basis) == (anchor.date, anchor.date_basis)
    assert event.end_basis is not DateBasis.RECORD
    assert (event.start, event.start_basis) == ("2032-03-20T00:00:00", DateBasis.RECORD)
    assert set(event.constituents) == {anchor.id, charge.id, early.id}


def test_unknown_dates_are_skipped_and_an_undated_span_is_unknown() -> None:
    undated = changed(K1, date=Unknown(), not_before=Unknown())
    assert only([undated, changed(K2)]).start == K1
    alone = only([undated])
    assert (alone.start, alone.start_basis, alone.end, alone.end_basis) == (Unknown(), None, Unknown(), None)
    assert isinstance(alone.date, Unknown)


def test_the_id_is_qualified_by_the_first_interval_and_the_intervals_are_in_sequence_order() -> None:
    stream = [changed(K2), changed(K1)]
    event = only(stream)

    assert event.id == f"nation.changed.arc/nation:1@{K1}"
    assert event.intervals == (K1, K2)
    assert event.constituents == tuple(sorted(item.id for item in stream))
    assert event.entities == (GERMANY,)
    assert event.roles == ((Role.ACTOR, GERMANY),)


def test_a_tied_interval_key_sorts_after_its_bare_time_and_by_tie_position() -> None:
    builder = NarrativeBuilder(())
    keys = [f"{K1}#10", f"{K1}#2", K1]
    constituents = [atomic(f"nation.changed/{position}", key) for position, key in enumerate(keys)]

    event = builder.event(
        fixture_kind("test.arc"), id_parts=["x"], constituents=constituents, roles=(), join=Join.ENTITY
    )

    assert event.intervals == (K1, f"{K1}#2", f"{K1}#10")


def test_an_event_is_open_when_its_anchor_is_present_in_the_last_save() -> None:
    reports = [situation(K1, nations=[GERMANY]), situation(K2, nations=[FRANCE], factions=[faction("7")])]
    stream = [changed(K1, GERMANY), changed(K2, FRANCE)]

    built = {event.entities[0]: event.open for event in aggregate(stream, reports, [RULE])}

    assert built == {GERMANY: False, FRANCE: True}
    assert present_in(reports[-1], faction("7"))
    assert not aggregate(stream, (), [RULE])[0].open


def test_a_kind_with_a_base_level_scores_it_never_below_the_highest_cited_score_nor_their_sum() -> None:
    def scored(*constituents: Event) -> Event:
        return NarrativeBuilder(()).event(
            SCORED_ARC, id_parts=[GERMANY.entity_id], constituents=constituents, roles=[], join=Join.ENTITY
        )

    assert (scored(changed(K1)).score, scored(changed(K1)).significance) == (
        Significance.MAJOR.base,
        Significance.MAJOR,
    )
    cited = [
        changed(K1, significance=Significance.CAMPAIGN_DEFINING, score=80),
        changed(K2, significance=Significance.CAMPAIGN_DEFINING, score=78),
    ]
    assert (scored(*cited).score, scored(*cited).significance) == (80, Significance.CAMPAIGN_DEFINING)


def test_a_rule_passing_a_level_for_a_kind_that_declares_one_is_a_code_bug() -> None:
    with pytest.raises(ValueError, match="declares its base level"):
        NarrativeBuilder(()).event(
            SCORED_ARC,
            id_parts=[GERMANY.entity_id],
            constituents=[changed(K1)],
            roles=[],
            join=Join.ENTITY,
            significance=Significance.MINOR,
        )


def test_confidence_is_the_minimum_lowered_once_for_a_heuristic_join() -> None:
    stream = [changed(K1), changed(K2, confidence=Confidence.MEDIUM)]

    assert only(stream).confidence is Confidence.MEDIUM
    assert only(stream, GroupRule("h", "nation.changed", join=Join.HEURISTIC)).confidence is Confidence.LOW
    low = [changed(K1, confidence=Confidence.LOW)]
    assert only(low, GroupRule("h", "nation.changed", join=Join.HEURISTIC)).confidence is Confidence.LOW
    claimed = GroupRule("c", "nation.changed", join=Join.HEURISTIC, confidence=Confidence.HIGH)
    assert only(stream, claimed).confidence is Confidence.HIGH


def test_significance_is_the_rule_level_but_never_below_the_most_significant_constituent() -> None:
    stream = [changed(K1), changed(K2, significance=Significance.MAJOR)]

    assert only(stream).significance is Significance.MAJOR
    assert only(stream, GroupRule("t", "nation.changed", significance=Significance.TRIVIAL)).significance is (
        Significance.MAJOR
    )
    defining = GroupRule("d", "nation.changed", significance=Significance.CAMPAIGN_DEFINING)
    assert only(stream, defining).significance is Significance.CAMPAIGN_DEFINING


def test_the_score_is_the_highest_of_the_rule_base_and_the_cited_scores_never_their_sum() -> None:
    stream = [changed(K1), changed(K2, significance=Significance.MAJOR)]
    assert only(stream).score == Significance.MAJOR.base
    assert only(stream, GroupRule("d", "nation.changed", significance=Significance.CAMPAIGN_DEFINING)).score == (
        Significance.CAMPAIGN_DEFINING.base
    )

    scaled = [changed(K1, significance=Significance.CAMPAIGN_DEFINING, score=80), changed(K2)]
    narrative_event = only(scaled, GroupRule("m", "nation.changed", significance=Significance.MAJOR))
    assert (narrative_event.score, narrative_event.significance) == (80, Significance.CAMPAIGN_DEFINING)
    assert narrative_event.to_dict()["score"] == 80

    low = [
        changed(K1, significance=Significance.MAJOR, score=50),
        changed(K2, significance=Significance.MAJOR, score=51),
    ]
    assert only(low, GroupRule("m", "nation.changed", significance=Significance.MAJOR)).score == Significance.MAJOR.base
    assert only(low).score == 51


@pytest.mark.parametrize(
    ("join", "constituent_status", "expected"),
    [
        (Join.ENTITY, EventStatus.OBJECTIVE, EventStatus.OBJECTIVE),
        (Join.HEURISTIC, EventStatus.OBJECTIVE, EventStatus.INFERRED),
        (Join.ENTITY, EventStatus.INFERRED, EventStatus.INFERRED),
    ],
)
def test_status_is_objective_only_for_objective_constituents_joined_by_entity(
    join: Join, constituent_status: EventStatus, expected: EventStatus
) -> None:
    stream = [changed(K1), changed(K2, status=constituent_status)]

    assert only(stream, GroupRule("s", "nation.changed", join=join)).status is expected


def test_sources_are_the_union_of_the_constituents_with_roles_kept() -> None:
    source = EventSource(state_change(GERMANY))
    event = only([changed(K1, sources=[source]), changed(K2, sources=[source])])

    assert event.sources == (source,)


ARC = "nation.changed.arc"


@dataclass(frozen=True)
class LookupRule:
    """Emits one ``test.lookup`` citing every event of ``looked_up`` that a typed lookup finds."""

    name: str
    looked_up: str
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()
    emitted_types: frozenset[str] = frozenset({"test.lookup"})
    window_days: int | None = None

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        found = stream.of_type(self.looked_up)
        return [
            build.event(
                fixture_kind("test.lookup"), id_parts=[self.name], constituents=found, roles=(), join=Join.ENTITY
            )
        ]


@dataclass(frozen=True)
class SilentRule:
    """Emits nothing; fails if it runs."""

    name: str
    emitted_types: frozenset[str]
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()
    window_days: int | None = None

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        raise AssertionError(f"{self.name} ran")


def test_a_rule_builds_on_the_narrative_events_of_a_type_it_reads() -> None:
    nested = GroupRule("nested", ARC, reads=frozenset({ARC}))
    stream = [changed(K1), changed(K2)]

    first, second = aggregate(stream, (), [nested, RULE])

    assert (first.event_type, second.event_type) == (ARC, "nation.changed.arc.arc")
    assert second.constituents == (first.id,)
    assert (second.start, second.end, second.intervals) == (first.start, first.end, first.intervals)


def test_an_explainer_is_seen_like_a_read_type() -> None:
    explained = GroupRule("explained", ARC, explains=frozenset({ARC}))

    built = aggregate([changed(K1)], (), [explained, RULE])

    assert [event.event_type for event in built] == [ARC, "nation.changed.arc.arc"]


def test_a_rule_never_sees_a_narrative_type_it_does_not_read() -> None:
    blind = GroupRule("blind", ARC)

    assert [event.event_type for event in aggregate([changed(K1)], (), [blind, RULE])] == [ARC]


def test_a_typed_lookup_of_a_narrative_type_the_rule_does_not_read_is_rejected() -> None:
    with pytest.raises(ValueError, match=f"narrative rule lookup reads \\['{ARC}'\\], which it does not declare"):
        aggregate([changed(K1)], (), [RULE, LookupRule("lookup", ARC)])
    [arc, lookup] = aggregate([changed(K1)], (), [RULE, LookupRule("lookup", ARC, reads=frozenset({ARC}))])
    assert lookup.constituents == (arc.id,)


def test_narrative_events_already_in_the_stream_are_hidden_unless_read() -> None:
    [arc] = RULE.apply([changed(K1)], (), NarrativeBuilder(()))
    stream = [changed(K1), arc]

    with pytest.raises(ValueError, match="does not declare"):
        aggregate(stream, (), [LookupRule("lookup", ARC)])
    [lookup] = aggregate(stream, (), [LookupRule("lookup", ARC, reads=frozenset({ARC}))])
    assert lookup.constituents == (arc.id,)


def test_rules_reading_each_other_in_a_cycle_are_rejected_before_any_rule_runs() -> None:
    first = SilentRule("first", frozenset({"test.first"}), reads=frozenset({"test.second"}))
    second = SilentRule("second", frozenset({"test.second"}), explains=frozenset({"test.first"}))

    with pytest.raises(ValueError, match="cycle"):
        aggregate([changed(K1)], (), [first, second])
    with pytest.raises(ValueError, match="cycle"):
        aggregate([changed(K1)], (), [SilentRule("own", frozenset({"test.own"}), reads=frozenset({"test.own"}))])


def test_a_read_type_no_rule_emits_orders_nothing() -> None:
    reader = GroupRule("reader", "nation.changed", reads=frozenset({"war.arc"}))

    assert [event.event_type for event in aggregate([changed(K1)], (), [reader])] == [ARC]


def test_citing_a_narrative_event_of_the_same_layer_is_rejected() -> None:
    [sibling] = RULE.apply([changed(K1)], (), NarrativeBuilder(()))

    with pytest.raises(ValueError, match="of its own layer"):
        aggregate([changed(K1)], (), [RULE, CitingRule("citing", (sibling,))])
    later = GroupRule("later", "nation.changed", reads=frozenset({"test.citing"}))
    with pytest.raises(ValueError, match="neither in the stream"):
        aggregate([changed(K1)], (), [later, CitingRule("citing", (sibling,))])


def test_citing_a_narrative_event_of_a_type_the_rule_does_not_read_is_rejected() -> None:
    [arc] = RULE.apply([changed(K1)], (), NarrativeBuilder(()))

    with pytest.raises(ValueError, match="neither in the stream"):
        aggregate([changed(K1), arc], (), [CitingRule("citing", (arc,))])
    [citing] = aggregate([changed(K1), arc], (), [CitingRule("citing", (arc,), reads=frozenset({ARC}))])
    assert citing.constituents == (arc.id,)


def test_citing_an_event_outside_the_stream_is_rejected() -> None:
    with pytest.raises(ValueError, match="neither in the stream"):
        aggregate([changed(K1)], (), [CitingRule("citing", (changed(K2),))])


def test_a_rule_must_emit_narrative_events_of_a_type_it_declares() -> None:
    @dataclass(frozen=True)
    class Passthrough:
        name: str = "passthrough"
        emitted_types: frozenset[str] = frozenset()
        reads: frozenset[str] = frozenset()
        explains: frozenset[str] = frozenset()
        window_days: int | None = 0

        def apply(
            self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
        ) -> list[Event]:
            return list(stream)

    with pytest.raises(ValueError, match="non-narrative"):
        aggregate([changed(K1)], (), [Passthrough()])
    with pytest.raises(ValueError, match="emitted test.citing, which it does not declare"):
        aggregate([changed(K1)], (), [CitingRule("citing", (changed(K1),), emitted_types=frozenset({"test.other"}))])


def test_duplicate_ids_and_duplicate_rule_names_are_programming_errors() -> None:
    with pytest.raises(ValueError, match="duplicate event IDs"):
        aggregate([changed(K1)], (), [RULE, GroupRule("again", "nation.changed")])
    with pytest.raises(ValueError, match="share a name"):
        aggregate([changed(K1)], (), [RULE, GroupRule("changes", "nation.other")])


def test_the_result_does_not_depend_on_stream_or_rule_order() -> None:
    stream = [changed(K1), changed(K2, FRANCE), changed(K3), changed(K3, FRANCE)]
    rules = [RULE, GroupRule("nested", ARC, reads=frozenset({ARC}))]
    reports = [situation(K1, nations=[GERMANY])]

    forward = aggregate(stream, reports, rules)

    assert aggregate(list(reversed(stream)), reports, list(reversed(rules))) == forward
    assert [event.sort_key for event in forward] == sorted(event.sort_key for event in forward)
    assert len(forward) == 4


def exclusive(*event_types: str) -> Callable[[str], EventKind | None]:
    """The kind lookup ``aggregate`` takes: ``event_types`` declare their constituents exclusive, nothing else does."""
    kinds = {event_type: replace(fixture_kind(event_type), exclusive_constituents=True) for event_type in event_types}
    return kinds.get


@dataclass(frozen=True)
class CitableRule:
    """Emits one ``test.citable`` citing every atomic event the stream lets it cite, and records every one it read."""

    name: str
    reads: frozenset[str] = frozenset()
    explains: frozenset[str] = frozenset()
    emitted_types: frozenset[str] = frozenset({"test.citable"})
    window_days: int | None = None
    read: list[str] = field(default_factory=list)

    def apply(self, stream: EventStream, situations: Sequence[SituationReport], build: NarrativeBuilder) -> list[Event]:
        found = [event for event in stream if not event.is_narrative]
        self.read.extend(event.id for event in found)
        cited = [event for event in found if stream.citable(event)]
        if not cited:
            return []
        return [
            build.event(
                fixture_kind("test.citable"), id_parts=[self.name], constituents=cited, roles=(), join=Join.ENTITY
            )
        ]


def other(key: str) -> Event:
    return atomic(f"nation.other/{GERMANY.entity_id}", key, entities=(GERMANY,))


def test_a_rule_runs_after_every_owner_it_does_not_feed_and_reads_but_may_not_cite_its_constituents() -> None:
    owned, free = changed(K1), other(K1)
    reader = CitableRule("a-reader")

    arc, citable = aggregate([owned, free], (), [RULE, reader], kinds=exclusive(ARC))

    assert arc.constituents == (owned.id,)
    assert sorted(reader.read) == sorted([owned.id, free.id])
    assert citable.constituents == (free.id,)


def test_a_rule_feeding_an_owner_runs_before_it_and_an_overlap_with_the_owner_is_rejected() -> None:
    owned = changed(K1)
    reader = CitableRule("reader")
    owner = GroupRule("owner", "nation.changed", reads=frozenset({"test.citable"}))

    with pytest.raises(ValueError, match="exclusive constituent"):
        aggregate([owned], (), [owner, reader], kinds=exclusive(ARC))
    assert reader.read == [owned.id]


def test_a_narrative_event_of_another_kind_citing_an_exclusive_constituent_is_rejected_at_any_order() -> None:
    owned = changed(K1)
    later = CitingRule("citing", (owned,))
    with pytest.raises(ValueError, match=f"cites {owned.id}, an exclusive constituent of {ARC}/"):
        aggregate([owned], (), [RULE, later], kinds=exclusive(ARC))
    with pytest.raises(ValueError, match="exclusive constituent"):
        aggregate([owned], (), [RULE, later], kinds=exclusive(ARC, "test.citing"))


def test_events_of_the_same_kind_may_share_an_exclusive_constituent() -> None:
    owned = changed(K1)
    first, second = CitingRule("first", (owned,)), CitingRule("second", (owned,))

    built = aggregate([owned], (), [first, second], kinds=exclusive("test.citing"))

    assert [event.constituents for event in built] == [(owned.id,), (owned.id,)]


def test_days_between_measures_game_days() -> None:
    assert days_between(K1, K2) == 91
    assert days_between(K1, Unknown()) is None
    assert days_between("not a date", K1) is None
