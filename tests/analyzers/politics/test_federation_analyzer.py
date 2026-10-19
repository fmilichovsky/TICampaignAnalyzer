"""Federation events: presence, members (corroborated by the members' federation references) and renames."""

from tests.analyzers.support import AFTER, BEFORE, analyze, federation_ref, named, nation_ref, snapshot, state
from tinarrative.analyzers.politics import FederationAnalyzer
from tinarrative.analyzers.politics.federations import APPEARED, FEDERATION_CHANGED, MEMBERS_CHANGED, RENAMED
from tinarrative.model.entities import EntityDomain
from tinarrative.model.events import Confidence, SourceRole
from tinarrative.model.values import Unknown, UnknownReason, freeze

ANALYZER = FederationAnalyzer()
NATION = EntityDomain.NATION
FEDERATION = EntityDomain.FEDERATION


def federation(save: str, *members: str, key: str = "80") -> object:
    return state(FEDERATION, key, save, members=tuple(nation_ref(n) for n in members))


def nation(save: str, key: str, federation_key: str | None) -> object:
    return state(NATION, key, save, federation=federation_ref(federation_key) if federation_key else None)


def sources(event: object) -> list[tuple[SourceRole, str, str | None]]:
    return [(s.role, str(s.change.entity_id), s.change.field) for s in event.sources]  # type: ignore[attr-defined]


def test_members_added_and_removed_cite_the_mirrored_nation_reference() -> None:
    before = snapshot(BEFORE, federation(BEFORE, "20", "21"), nation(BEFORE, "20", "80"), nation(BEFORE, "21", "80"))
    after = snapshot(
        AFTER,
        federation(AFTER, "20", "22"),
        nation(AFTER, "20", "80"),
        nation(AFTER, "21", None),
        nation(AFTER, "22", "80"),
    )
    events = analyze(ANALYZER, before, after)
    assert [event.id for event in events] == [
        "federation.members_changed/federation:80/nation:22/added",
        "federation.members_changed/federation:80/nation:21/removed",
    ]
    added, removed = events
    assert added.event_type == MEMBERS_CHANGED and added.confidence is Confidence.HIGH
    assert dict(removed.attributes) == {"member": named(nation_ref("21")), "transition": "removed"}
    assert sources(removed) == [
        (SourceRole.PRIMARY, "federation:80", "members"),
        (SourceRole.CORROBORATING, "nation:21", "federation"),
    ]
    assert [str(ref.entity_id) for ref in removed.entities] == ["federation:80", "nation:21"]


def test_a_new_federation_cites_its_members_references_and_a_switch_is_cited_on_both_sides() -> None:
    before = snapshot(BEFORE, federation(BEFORE, "20"), nation(BEFORE, "20", "80"), nation(BEFORE, "21", None))
    after = snapshot(
        AFTER,
        federation(AFTER),
        federation(AFTER, "20", "21", key="81"),
        nation(AFTER, "20", "81"),
        nation(AFTER, "21", "81"),
    )
    events = analyze(ANALYZER, before, after)
    assert sorted(event.id for event in events) == [
        "federation.appeared/federation:81",
        "federation.members_changed/federation:80/nation:20/removed",
    ]
    appeared = next(event for event in events if event.event_type == APPEARED)
    assert sources(appeared) == [
        (SourceRole.PRIMARY, "federation:81", None),
        (SourceRole.CORROBORATING, "nation:20", "federation"),
        (SourceRole.CORROBORATING, "nation:21", "federation"),
    ]
    left = next(event for event in events if event.event_type == MEMBERS_CHANGED)
    assert sources(left)[1] == (SourceRole.CORROBORATING, "nation:20", "federation")


def test_unexplained_federation_references_and_unresolved_member_lists_are_reported() -> None:
    unresolved = Unknown(UnknownReason.UNRESOLVED_REFERENCE, freeze([{"value": 999}]))
    before = snapshot(BEFORE, federation(BEFORE, "20"), nation(BEFORE, "21", None))
    after = snapshot(AFTER, state(FEDERATION, "80", AFTER, members=unresolved), nation(AFTER, "21", "80"))
    events = analyze(ANALYZER, before, after)
    assert sorted(event.id for event in events) == [
        "federation.members_changed/federation:80/unresolved",
        "nation.federation_changed/nation:21",
    ]
    reference = next(event for event in events if event.event_type == FEDERATION_CHANGED)
    assert dict(reference.attributes) == {"transition": "set", "before": None, "after": named(federation_ref("80"))}
    leftover = next(event for event in events if event.event_type == MEMBERS_CHANGED)
    assert leftover.confidence is Confidence.LOW


def named_federation(save: str, display: str, name: str | None) -> object:
    return state(FEDERATION, "80", save, members=(), displayName=display, federationName=name)


def test_a_rename_is_one_event_citing_every_changed_name_field() -> None:
    before = snapshot(BEFORE, named_federation(BEFORE, "Old", "Old"))
    after = snapshot(AFTER, named_federation(AFTER, "New", "New Formal"))
    (event,) = analyze(ANALYZER, before, after)
    assert (event.id, event.event_type) == ("federation.renamed/federation:80", RENAMED)
    assert sources(event) == [
        (SourceRole.PRIMARY, "federation:80", "displayName"),
        (SourceRole.PRIMARY, "federation:80", "federationName"),
    ]
    assert dict(event.attributes) == {
        "transition": "changed",
        "before": "Old",
        "after": "New",
        "federation_name_before": "Old",
        "federation_name_after": "New Formal",
    }


def test_a_federation_name_set_alone_is_a_rename_by_that_field() -> None:
    before = snapshot(BEFORE, named_federation(BEFORE, "Same", None))
    after = snapshot(AFTER, named_federation(AFTER, "Same", "Formal"))
    (event,) = analyze(ANALYZER, before, after)
    assert sources(event) == [(SourceRole.PRIMARY, "federation:80", "federationName")]
    assert dict(event.attributes) == {"transition": "set", "before": None, "after": "Formal"}
