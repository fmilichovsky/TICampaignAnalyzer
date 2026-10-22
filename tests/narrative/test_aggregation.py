"""The narrative aggregation framework: the builder's shared policy and the rule runner, with trivial test rules."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pytest

from tests.narrative.support import CitingRule, GroupRule, atomic, faction, nation, situation, state_change
from tinarrative.model.entities import EntityRef
from tinarrative.model.events import Confidence, DateBasis, Event, EventSource, EventStatus, Role, Significance
from tinarrative.model.values import Unknown
from tinarrative.narrative.aggregation import Join, NarrativeBuilder, aggregate, days_between, present_in
from tinarrative.narrative.situation import SituationReport

K1 = "2032-04-01T00:00:00"
K2 = "2032-07-01T00:00:00"
K3 = "2032-10-01T00:00:00"
GERMANY = nation("1", "Germany")
FRANCE = nation("2", "France")
RULE = GroupRule("changes", "nation.changed")


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
        "nation.changed.arc",
        id_parts=[GERMANY.entity_id],
        constituents=[changed(K1)],
        roles=[],
        join=Join.ENTITY,
        starts_on="2031-06-01T00:00:00",
    )

    assert (event.start, event.start_basis) == ("2031-06-01T00:00:00", DateBasis.RECORD)
    assert event.not_before == "2032-01-01T00:00:00"


def test_a_corroborating_event_is_cited_and_may_narrow_the_start_but_never_sets_the_end() -> None:
    anchor = changed(K2)
    charge = atomic("nation.charge", K2, date=K2, date_basis=DateBasis.RECORD, entities=(GERMANY,))
    early = atomic("nation.charge", K1, date="2032-03-20T00:00:00", date_basis=DateBasis.RECORD, entities=(GERMANY,))

    event = NarrativeBuilder([]).event(
        "nation.changed.arc",
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

    event = builder.event("test.arc", id_parts=["x"], constituents=constituents, roles=(), join=Join.ENTITY)

    assert event.intervals == (K1, f"{K1}#2", f"{K1}#10")


def test_an_event_is_open_when_its_anchor_is_present_in_the_last_save() -> None:
    reports = [situation(K1, nations=[GERMANY]), situation(K2, nations=[FRANCE], factions=[faction("7")])]
    stream = [changed(K1, GERMANY), changed(K2, FRANCE)]

    built = {event.entities[0]: event.open for event in aggregate(stream, reports, [RULE])}

    assert built == {GERMANY: False, FRANCE: True}
    assert present_in(reports[-1], faction("7"))
    assert not aggregate(stream, (), [RULE])[0].open


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


def test_a_higher_order_rule_builds_on_lower_order_narrative_events() -> None:
    nested = GroupRule("nested", "nation.changed.arc", order=1)
    stream = [changed(K1), changed(K2)]

    first, second = aggregate(stream, (), [nested, RULE])

    assert (first.event_type, second.event_type) == ("nation.changed.arc", "nation.changed.arc.arc")
    assert second.constituents == (first.id,)
    assert (second.start, second.end, second.intervals) == (first.start, first.end, first.intervals)


def test_a_rule_never_sees_narrative_events_of_its_own_order() -> None:
    same = GroupRule("same", "nation.changed.arc")

    assert [event.event_type for event in aggregate([changed(K1)], (), [same, RULE])] == ["nation.changed.arc"]


def test_citing_a_narrative_event_of_the_same_order_is_rejected() -> None:
    [sibling] = RULE.apply([changed(K1)], (), NarrativeBuilder(()))

    with pytest.raises(ValueError, match="same order"):
        aggregate([changed(K1)], (), [RULE, CitingRule("citing", (sibling,))])
    with pytest.raises(ValueError, match="neither in the stream"):
        aggregate([changed(K1)], (), [GroupRule("later", "nation.changed", order=1), CitingRule("citing", (sibling,))])


def test_citing_an_event_outside_the_stream_is_rejected() -> None:
    with pytest.raises(ValueError, match="neither in the stream"):
        aggregate([changed(K1)], (), [CitingRule("citing", (changed(K2),))])


def test_a_rule_must_emit_narrative_events() -> None:
    @dataclass(frozen=True)
    class Passthrough:
        name: str = "passthrough"
        order: int = 0
        window_days: int | None = 0

        def apply(
            self, stream: Sequence[Event], situations: Sequence[SituationReport], build: NarrativeBuilder
        ) -> list[Event]:
            return list(stream)

    with pytest.raises(ValueError, match="non-narrative"):
        aggregate([changed(K1)], (), [Passthrough()])


def test_duplicate_ids_and_duplicate_rule_names_are_programming_errors() -> None:
    with pytest.raises(ValueError, match="duplicate event IDs"):
        aggregate([changed(K1)], (), [RULE, GroupRule("again", "nation.changed")])
    with pytest.raises(ValueError, match="share a name"):
        aggregate([changed(K1)], (), [RULE, GroupRule("changes", "nation.other")])


def test_the_result_does_not_depend_on_stream_or_rule_order() -> None:
    stream = [changed(K1), changed(K2, FRANCE), changed(K3), changed(K3, FRANCE)]
    rules = [RULE, GroupRule("nested", "nation.changed.arc", order=1)]
    reports = [situation(K1, nations=[GERMANY])]

    forward = aggregate(stream, reports, rules)

    assert aggregate(list(reversed(stream)), reports, list(reversed(rules))) == forward
    assert [event.sort_key for event in forward] == sorted(event.sort_key for event in forward)
    assert len(forward) == 4


def test_days_between_measures_game_days() -> None:
    assert days_between(K1, K2) == 91
    assert days_between(K1, Unknown()) is None
    assert days_between("not a date", K1) is None
