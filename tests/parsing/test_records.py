"""Save-carried records: typed decoding with provenance, the missing case, and shape findings."""

import logging

import pytest

from tests.fixtures import fixture_path
from tinarrative.identity import STATE_PREFIX
from tinarrative.io.save_loader import load_raw_save
from tinarrative.model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from tinarrative.model.records import (
    CombatEntry,
    DestructionEntry,
    ItemEntry,
    KeyedEntry,
    LedgerEntry,
    NotificationEntry,
    RecordKind,
    RecordSet,
)
from tinarrative.model.snapshot import SaveSnapshot
from tinarrative.model.values import FrozenMap, Unknown, UnknownReason
from tinarrative.parsing.fields import RECORD_FIELDS
from tinarrative.parsing.normalization import normalize
from tinarrative.parsing.raw_save import RawSave
from tinarrative.parsing.unknowns import UnknownCollector, UnknownReport

FIXTURE_SET = ("io", "terra_invicta_json_v1")
FACTION_TYPE = STATE_PREFIX + "TIFactionState"
NATION_TYPE = STATE_PREFIX + "TINationState"
DATE = {"year": 2031, "month": 4, "day": 2, "hour": 0, "minute": 0, "second": 0, "millisecond": 0}
ISO = "2031-04-02T00:00:00"


def load(name: str) -> SaveSnapshot:
    return normalize(load_raw_save(fixture_path(*FIXTURE_SET, name)))


def fragment_raw(gamestates: dict[str, object]) -> RawSave:
    root: dict[str, object] = {"currentID": {"value": 1}, "gamestates": gamestates}
    return RawSave(source="fragment.json", format="terra_invicta_json_v1", game_version=None, root=root, size_bytes=1)


def collect(gamestates: dict[str, object]) -> tuple[SaveSnapshot, UnknownReport]:
    collector = UnknownCollector()
    snapshot = normalize(fragment_raw(gamestates), collector=collector)
    return snapshot, collector.report()


def keys(report: UnknownReport) -> list[tuple[str, str, str, str]]:
    return [finding.key for finding in report.findings]


def pair(map_id: int, **members: object) -> dict[str, object]:
    return {"Key": {"value": map_id}, "Value": {"ID": {"value": map_id}, **members}}


def ref(domain: EntityDomain, key: str, state_type: str) -> EntityRef:
    return EntityRef(EntityId(domain, key), IdentityConfidence.IN_SAVE_ID, state_type=state_type)


def unresolved(map_id: int, type_suffix: str | None = None) -> Unknown:
    raw: dict[str, object] = {"value": map_id}
    if type_suffix:
        raw["$type"] = STATE_PREFIX + type_suffix
    return Unknown(UnknownReason.UNRESOLVED_REFERENCE, FrozenMap(tuple(sorted(raw.items()))))


def record(snapshot: SaveSnapshot, key: str, field: str) -> RecordSet:
    return next(r for r in snapshot.records if r.owner.entity_id.key == key and r.field == field)


def faction_fragment(**fields: object) -> dict[str, object]:
    return {
        FACTION_TYPE: [pair(15, displayName="Fixture Resistance", **fields), pair(16, displayName="Fixture Servants")],
        NATION_TYPE: [pair(20)],
    }


FACTION_15 = ref(EntityDomain.FACTION, "15", "TIFactionState")
FACTION_16 = ref(EntityDomain.FACTION, "16", "TIFactionState")


@pytest.fixture(scope="module")
def before() -> SaveSnapshot:
    return load("records_before.json")


@pytest.fixture(scope="module")
def after() -> SaveSnapshot:
    return load("records_after.json")


@pytest.mark.fixture
def test_every_record_field_becomes_one_typed_set_per_entity(before: SaveSnapshot) -> None:
    by_owner: dict[str, set[str]] = {}
    for item in before.records:
        by_owner.setdefault(item.owner.entity_id.key, set()).add(item.field)
    assert by_owner == {
        "15": set(RECORD_FIELDS["TIFactionState"]),
        "16": set(RECORD_FIELDS["TIFactionState"]),
        "20": set(RECORD_FIELDS["TINationState"]),
    }
    for item in before.records:
        assert item.kind is RECORD_FIELDS[item.owner.state_type or ""][item.field].kind
        assert item.location.state_type == item.owner.state_type
        assert item.location.map_id == int(item.owner.entity_id.key)
        assert item.location.path is not None and item.location.path.endswith(f"/Value/{item.field}")
    assert [r.field for r in before.records if r.owner.entity_id.key == "15"] == sorted(RECORD_FIELDS["TIFactionState"])


@pytest.mark.fixture
def test_ledger_and_destruction_log_are_dated_entries_with_resolved_references(before: SaveSnapshot) -> None:
    ledger = record(before, "15", "Transactions")
    assert ledger.kind is RecordKind.LEDGER
    assert ledger.location.path == f"/gamestates/{FACTION_TYPE}/0/Value/Transactions"
    assert ledger.entries == (
        LedgerEntry(0, "1234567890", "Influence", -2.5, "2031-02-01T00:00:00"),
        LedgerEntry(0, "FixtureCause", "Money", 10.0, "2031-01-01T00:00:00"),
    )
    assert ledger.entry_location(ledger.entries[1]).path == f"{ledger.location.path}/FixtureCause/0"
    assert ledger.entry_location(ledger.entries[1]).provenance_key == "TIFactionState:15"
    destruction = record(before, "15", "HabDestructionLog")
    assert destruction.entries == (
        DestructionEntry(
            0,
            "Station",
            ref(EntityDomain.SPACE_OBJECT, "50", "TISpaceBodyState"),
            "2031-01-15T00:00:00",
            FACTION_16,
        ),
    )


@pytest.mark.fixture
def test_pair_maps_decode_from_both_forms_and_keys_resolve_against_their_domains(before: SaveSnapshot) -> None:
    assert record(before, "15", "Kills").entries == ()
    assert record(before, "15", "factionAssassinations").entries == ()
    assert record(before, "15", "lostControlPoints").entries == ()
    assert record(before, "15", "factionHate").entries == (KeyedEntry(0, FACTION_16, 0.5),)
    sites = record(before, "15", "knownAlienSites")
    assert sites.entries == (
        KeyedEntry(0, ref(EntityDomain.REGION, "40", "TIRegionState"), "2030-12-01T00:00:00"),
        KeyedEntry(1, ref(EntityDomain.SPACE_OBJECT, "140", "TIHabState"), "2031-01-05T00:00:00"),
        KeyedEntry(2, ref(EntityDomain.SHIP, "130", "TISpaceShipState"), "2031-01-20T00:00:00"),
        KeyedEntry(3, unresolved(999, "TIRegionState"), "2031-02-14T00:00:00"),
    )
    assert sites.entry_location(sites.entries[3]).path == f"{sites.location.path}/3"


@pytest.mark.fixture
def test_label_maps_counters_dates_and_reference_lists(before: SaveSnapshot, after: SaveSnapshot) -> None:
    assert record(before, "15", "boostAccounts").entries == (
        KeyedEntry(0, "Base", "2031-02-10T00:00:00"),
        KeyedEntry(1, "Station", None),
        KeyedEntry(2, "Probe", None),
        KeyedEntry(3, "Org", None),
    )
    armies = record(before, "15", "armiesLost")
    assert armies.entries == (
        KeyedEntry(0, "Human", 0),
        KeyedEntry(1, "AlienMegafauna", 0),
        KeyedEntry(2, "AlienInvader", 0),
    )
    assert armies.entry_location(armies.entries[0]).path == f"{armies.location.path}/Human"
    assert record(before, "15", "objectiveNames").entries == (
        KeyedEntry(0, "FixtureObjectiveA", "Locked"),
        KeyedEntry(1, "FixtureObjectiveB", "Completed"),
    )
    assert record(before, "15", "milestones").entries == (ItemEntry(0, "FixtureMilestoneA"),)
    counter = record(before, "15", "abductions")
    assert counter.entries == (ItemEntry(0, 0),)
    assert counter.entry_location(counter.entries[0]) == counter.location
    assert record(before, "15", "intelSharingFactions").entries == (ItemEntry(0, ()),)
    assert record(after, "15", "intelSharingFactions").entries == (ItemEntry(0, (FACTION_16,)),)
    assert record(after, "15", "lostControlPoints").entries == (
        KeyedEntry(0, ref(EntityDomain.CONTROL_POINT, "9", "TIControlPoint"), "2031-04-10T00:00:00"),
    )
    assert record(after, "15", "HabDestructionLog").entries[1:] == (
        DestructionEntry(1, "Base", unresolved(999), "2031-04-02T00:00:00", FACTION_16),
        DestructionEntry(
            2, "Station", ref(EntityDomain.SPACE_OBJECT, "50", "TISpaceBodyState"), "2031-05-20T00:00:00", None
        ),
    )


@pytest.mark.fixture
def test_nation_records_hold_the_executive_change_as_a_struct(before: SaveSnapshot, after: SaveSnapshot) -> None:
    assert record(before, "20", "dateOfNewGovernment").entries == (ItemEntry(0, None),)
    assert record(after, "20", "dateOfNewGovernment").entries == (ItemEntry(0, "2031-04-20T00:00:00"),)
    assert record(before, "20", "lastExecutiveChange").entries == (
        KeyedEntry(0, "cause", "None"),
        KeyedEntry(1, "date", None),
        KeyedEntry(2, "newExecutive", None),
    )
    change = record(after, "20", "lastExecutiveChange")
    assert change.entries == (
        KeyedEntry(0, "cause", "Coup"),
        KeyedEntry(1, "date", "2031-04-20T00:00:00"),
        KeyedEntry(2, "newExecutive", FACTION_15),
    )
    assert change.entry_location(change.entries[2]).path == f"{change.location.path}/newExecutive"


@pytest.mark.fixture
def test_an_entity_without_record_fields_has_unknown_sets_and_the_fixtures_are_schema_clean(
    before: SaveSnapshot,
) -> None:
    for field in RECORD_FIELDS["TIFactionState"]:
        missing = record(before, "16", field)
        assert missing.entries == Unknown()
        assert missing.location.path == f"/gamestates/{FACTION_TYPE}/1/Value/{field}"
    for name in ("records_before.json", "records_after.json"):
        collector = UnknownCollector()
        snapshot = normalize(load_raw_save(fixture_path(*FIXTURE_SET, name)), collector=collector)
        assert collector.report().total == 0
        assert snapshot.to_dict()["records"][0]["entries"] is not None
        assert normalize(load_raw_save(fixture_path(*FIXTURE_SET, name))) == snapshot


def test_record_fields_are_not_copied_into_the_entity_state() -> None:
    snapshot, report = collect(faction_fragment(abductions=3, milestones=["A"]))
    faction = next(state for state in snapshot.factions if state.ref.entity_id.key == "15")
    assert faction.get("abductions") == Unknown()
    assert faction.get("milestones") == Unknown()
    assert record(snapshot, "15", "abductions").entries == (ItemEntry(0, 3),)
    assert record(snapshot, "15", "milestones").entries == (ItemEntry(0, "A"),)
    assert record(snapshot, "15", "Transactions").entries == Unknown()
    assert report.total == 0


def test_a_record_field_of_the_wrong_shape_is_unparseable_and_reported() -> None:
    snapshot, report = collect(
        faction_fragment(
            Transactions=[],
            Kills="text",
            HabDestructionLog={"a": 1},
            milestones=5,
            armiesLost=[1],
            boostAccounts=None,
        )
    )
    assert record(snapshot, "15", "Transactions").entries == Unknown(UnknownReason.UNPARSEABLE, ())
    assert record(snapshot, "15", "Kills").entries == Unknown(UnknownReason.UNPARSEABLE, "text")
    assert record(snapshot, "15", "HabDestructionLog").entries == Unknown(
        UnknownReason.UNPARSEABLE, FrozenMap((("a", 1),))
    )
    assert record(snapshot, "15", "milestones").entries == Unknown(UnknownReason.UNPARSEABLE, 5)
    assert record(snapshot, "15", "armiesLost").entries == Unknown(UnknownReason.UNPARSEABLE, (1,))
    assert record(snapshot, "15", "boostAccounts").entries == Unknown(UnknownReason.UNPARSEABLE, None)
    assert keys(report) == [
        ("unexpected_field_shape", "TIFactionState", "HabDestructionLog", "array"),
        ("unexpected_field_shape", "TIFactionState", "Kills", "pair_map"),
        ("unexpected_field_shape", "TIFactionState", "Transactions", "object"),
        ("unexpected_field_shape", "TIFactionState", "armiesLost", "object"),
        ("unexpected_field_shape", "TIFactionState", "boostAccounts", "object"),
        ("unexpected_field_shape", "TIFactionState", "milestones", "array"),
    ]
    shapes = {finding.key[2]: finding.shape for finding in report.findings}
    assert shapes["Kills"] is not None and shapes["Kills"].types == ("string",)
    assert all(finding.occurrences == 1 for finding in report.findings)


def test_problems_inside_one_element_stay_inside_that_entry() -> None:
    snapshot, report = collect(
        faction_fragment(
            HabDestructionLog=[
                {"HabType": "Base", "SpaceBody": None, "Date": {"year": 2031}, "Destroyer": {"value": 20}},
                "not an object",
                {"HabType": "Station"},
            ],
            Transactions={"Good": [{"Resource": "Money", "Amount": 1.0, "Date": DATE}, 7], "Bad": "text"},
            knownAlienSites=[{"Key": {"value": 16}, "Value": DATE}, {"Key": "oops", "Value": None}],
            intelSharingFactions={"value": 16},
        )
    )
    bad_item = Unknown(UnknownReason.UNPARSEABLE, "not an object")
    assert record(snapshot, "15", "HabDestructionLog").entries == (
        DestructionEntry(
            0, "Base", None, Unknown(UnknownReason.UNPARSEABLE, FrozenMap((("year", 2031),))), unresolved(20)
        ),
        DestructionEntry(1, bad_item, bad_item, bad_item, bad_item),
        DestructionEntry(2, "Station", Unknown(), Unknown(), Unknown()),
    )
    bad_ledger_item = Unknown(UnknownReason.UNPARSEABLE, 7)
    assert record(snapshot, "15", "Transactions").entries == (
        LedgerEntry(0, "Good", "Money", 1.0, ISO),
        LedgerEntry(1, "Good", bad_ledger_item, bad_ledger_item, bad_ledger_item),
    )
    assert record(snapshot, "15", "knownAlienSites").entries == (
        KeyedEntry(0, unresolved(16), ISO),
        KeyedEntry(1, Unknown(UnknownReason.UNRESOLVED_REFERENCE, "oops"), None),
    )
    assert record(snapshot, "15", "intelSharingFactions").entries == (
        ItemEntry(0, Unknown(UnknownReason.UNPARSEABLE, FrozenMap((("value", 16),)))),
    )
    assert keys(report) == [
        ("unexpected_field_shape", "TIFactionState", "HabDestructionLog", "array_of_objects"),
        ("unexpected_field_shape", "TIFactionState", "HabDestructionLog", "componentized_date"),
        ("unexpected_field_shape", "TIFactionState", "Transactions", "array"),
        ("unexpected_field_shape", "TIFactionState", "Transactions", "array_of_objects"),
        ("unexpected_field_shape", "TIFactionState", "intelSharingFactions", "array_of_references"),
        ("unexpected_field_shape", "TIFactionState", "knownAlienSites", "reference_object"),
        ("unexpected_reference_domain", "TIFactionState", "HabDestructionLog.Destroyer", "TINationState"),
        ("unexpected_reference_domain", "TIFactionState", "knownAlienSites", "TIFactionState"),
    ]


def test_executive_reference_to_an_unexpected_type_is_reported_under_its_member_name() -> None:
    gamestates: dict[str, object] = {
        NATION_TYPE: [
            pair(20, lastExecutiveChange={"newExecutive": {"value": 21}, "date": DATE, "cause": "Coup"}),
            pair(21),
        ],
    }
    snapshot, report = collect(gamestates)
    assert record(snapshot, "20", "lastExecutiveChange").entries == (
        KeyedEntry(0, "cause", "Coup"),
        KeyedEntry(1, "date", ISO),
        KeyedEntry(2, "newExecutive", unresolved(21)),
    )
    assert record(snapshot, "20", "dateOfNewGovernment").entries == Unknown()
    assert keys(report) == [
        ("unexpected_reference_domain", "TINationState", "lastExecutiveChange.newExecutive", "TINationState"),
    ]


def test_debug_log_counts_records_without_naming_labels_or_values(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="tinarrative"):
        collect(
            faction_fragment(
                Transactions={"SecretLabel": [{"Resource": "Money", "Amount": 1.0, "Date": DATE}]},
                Kills=[{"Key": {"value": 16}, "Value": ["Secret Ship"]}],
            )
        )
    lines = [record.getMessage() for record in caplog.records if record.name == "tinarrative.parsing.records"]
    assert lines == [
        "records normalized state_type=TIFactionState fields=18 entities=2 sets=36 known_sets=2 missing=34 entries=2 "
        "unparseable_dates=0 unresolved_references=0 shape_findings=0",
        "records normalized state_type=TINationState fields=2 entities=1 sets=2 known_sets=0 missing=2 entries=0 "
        "unparseable_dates=0 unresolved_references=0 shape_findings=0",
        "records normalized state_type=TIWarState fields=2 entities=0 sets=0 known_sets=0 missing=0 entries=0 "
        "unparseable_dates=0 unresolved_references=0 shape_findings=0",
        "records normalized state_type=TIRegionUFOCrashdownState fields=1 entities=0 sets=0 known_sets=0 missing=0 "
        "entries=0 unparseable_dates=0 unresolved_references=0 shape_findings=0",
        "records normalized state_type=TIGlobalValuesState fields=5 entities=0 sets=0 known_sets=0 missing=0 "
        "entries=0 unparseable_dates=0 unresolved_references=0 shape_findings=0",
        "records normalized state_type=TINotificationQueueState fields=1 entities=0 sets=0 known_sets=0 missing=0 "
        "entries=0 unparseable_dates=0 unresolved_references=0 shape_findings=0",
    ]
    assert "Secret" not in caplog.text and "Fixture" not in caplog.text


GLOBAL_VALUES_TYPE = STATE_PREFIX + "TIGlobalValuesState"


def test_labelled_references_hold_one_reference_or_a_list_per_label() -> None:
    gamestates: dict[str, object] = {
        **faction_fragment(),
        GLOBAL_VALUES_TYPE: [
            pair(
                70,
                globalMilestones={"FirstWarship": {"value": 15}, "FirstBase": {"value": 20}},
                triggeredOncePerTargetEvents={"event_A": [{"value": 15}, {"value": 16}], "event_B": []},
            )
        ],
    }
    snapshot, report = collect(gamestates)
    milestones = record(snapshot, "70", "globalMilestones")
    assert milestones.kind is RecordKind.LABELLED_REFERENCES
    assert milestones.entries == (KeyedEntry(0, "FirstWarship", FACTION_15), KeyedEntry(1, "FirstBase", unresolved(20)))
    assert isinstance(milestones.entries, tuple)
    assert milestones.entry_location(milestones.entries[0]).path == (
        f"/gamestates/{GLOBAL_VALUES_TYPE}/0/Value/globalMilestones/FirstWarship"
    )
    assert record(snapshot, "70", "triggeredOncePerTargetEvents").entries == (
        KeyedEntry(0, "event_A", (FACTION_15, FACTION_16)),
        KeyedEntry(1, "event_B", ()),
    )
    assert keys(report) == [("unexpected_reference_domain", "TIGlobalValuesState", "globalMilestones", "TINationState")]


def test_labelled_references_of_the_wrong_shape_are_unparseable_and_reported() -> None:
    snapshot, report = collect({GLOBAL_VALUES_TYPE: [pair(70, globalMilestones=[{"value": 15}])]})
    entries = record(snapshot, "70", "globalMilestones").entries
    assert isinstance(entries, Unknown) and entries.reason is UnknownReason.UNPARSEABLE
    assert keys(report) == [("unexpected_field_shape", "TIGlobalValuesState", "globalMilestones", "object")]


def test_global_values_name_logs_and_cooldowns_are_records() -> None:
    gamestates: dict[str, object] = {
        GLOBAL_VALUES_TYPE: [
            pair(
                70,
                removedNarrativeEvents=["event_A", "event_A"],
                triggeredOncePerCampaignEvents=[],
                narrativeEventsOnCooldown_months={"event_B": 2.0},
            )
        ]
    }
    snapshot, report = collect(gamestates)
    assert record(snapshot, "70", "removedNarrativeEvents").entries == (
        ItemEntry(0, "event_A"),
        ItemEntry(1, "event_A"),
    )
    assert record(snapshot, "70", "triggeredOncePerCampaignEvents").entries == ()
    assert record(snapshot, "70", "narrativeEventsOnCooldown_months").entries == (KeyedEntry(0, "event_B", 2.0),)
    assert report.findings == ()


QUEUE_TYPE = STATE_PREFIX + "TINotificationQueueState"
REGION_TYPE = STATE_PREFIX + "TIRegionState"
PHASE_TYPE = STATE_PREFIX + "TIMissionPhaseState"
REGION_40 = ref(EntityDomain.REGION, "40", "TIRegionState")


def notice(template: str, subject: object, **members: object) -> dict[str, object]:
    return {
        "$id": "1",
        "templateName": template,
        "itemSummary": "Fixture summary.",
        "dateTimeString": "4/2/2031 12:00:00 AM",
        "dateTime": DATE,
        "outcome": "None",
        "gotoGameState": subject,
        "alienRelated": False,
        "timerFactions": [],
        "newsFeedFactions": [{"value": 15}, {"value": 16}],
        "summaryLogFactions": [{"value": 15}],
        "iconResource": "fixture/icon",
        "iconBackgroundResource": "fixture/background",
        "backgroundColor": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 1.0},
        **members,
    }


def queue_fragment(*entries: object) -> dict[str, object]:
    return {
        **faction_fragment(),
        REGION_TYPE: [pair(40)],
        PHASE_TYPE: [pair(300)],
        QUEUE_TYPE: [pair(80, notificationSummaryQueue=list(entries))],
    }


def test_the_notification_log_decodes_each_entry_with_provenance_and_resolved_references() -> None:
    region = {"$type": REGION_TYPE, "value": 40}
    snapshot, report = collect(queue_fragment(notice("LogFleetDetected", region), notice("LogNationJoinsWar", None)))
    log = record(snapshot, "80", "notificationSummaryQueue")
    assert log.kind is RecordKind.NOTIFICATION_LOG
    assert log.owner.entity_id == EntityId(EntityDomain.NOTIFICATION_QUEUE, "80")
    assert log.entries == (
        NotificationEntry(
            0,
            "LogFleetDetected",
            ISO,
            "Fixture summary.",
            "None",
            REGION_40,
            False,
            (FACTION_15, FACTION_16),
            (FACTION_15,),
        ),
        NotificationEntry(
            1,
            "LogNationJoinsWar",
            ISO,
            "Fixture summary.",
            "None",
            None,
            False,
            (FACTION_15, FACTION_16),
            (FACTION_15,),
        ),
    )
    assert isinstance(log.entries, tuple)
    assert log.entry_location(log.entries[1]).path == f"/gamestates/{QUEUE_TYPE}/0/Value/notificationSummaryQueue/1"
    assert report.findings == ()


def test_a_subject_without_a_domain_or_absent_from_the_save_is_unresolved_without_a_finding() -> None:
    phase = {"$type": PHASE_TYPE, "value": 300}
    gone = {"$type": STATE_PREFIX + "TIHabState", "value": 999}
    snapshot, report = collect(queue_fragment(notice("LogProjectComplete", phase), notice("LogHabDestroyed", gone)))
    entries = record(snapshot, "80", "notificationSummaryQueue").entries
    assert isinstance(entries, tuple)
    subjects = [entry.subject for entry in entries if isinstance(entry, NotificationEntry)]
    assert subjects == [unresolved(300, "TIMissionPhaseState"), unresolved(999, "TIHabState")]
    assert report.findings == ()


def test_a_subject_of_an_unexpected_type_and_an_unknown_entry_member_are_reported() -> None:
    timed = notice("LogFleetDetected", {"value": 500})  # a TITimeEvent: no domain, not an observed target
    extended = notice("LogFleetDetected", {"value": 15}, fixtureMember=1)
    gamestates = {**queue_fragment(timed, extended), STATE_PREFIX + "TITimeEvent": [pair(500)]}
    snapshot, report = collect(gamestates)
    assert keys(report) == [
        (
            "unexpected_reference_domain",
            "TINotificationQueueState",
            "notificationSummaryQueue.gotoGameState",
            "TITimeEvent",
        ),
        ("unknown_field", "TINotificationQueueState", "notificationSummaryQueue[].fixtureMember", ""),
    ]
    entries = record(snapshot, "80", "notificationSummaryQueue").entries
    assert isinstance(entries, tuple) and isinstance(entries[1], NotificationEntry)
    assert entries[1].subject == FACTION_15  # a faction is an expected subject


def test_a_notification_log_of_the_wrong_shape_is_unparseable_and_reported() -> None:
    snapshot, report = collect({QUEUE_TYPE: [pair(80, notificationSummaryQueue={"0": {}})]})
    entries = record(snapshot, "80", "notificationSummaryQueue").entries
    assert isinstance(entries, Unknown) and entries.reason is UnknownReason.UNPARSEABLE
    assert keys(report) == [("unexpected_field_shape", "TINotificationQueueState", "notificationSummaryQueue", "array")]


def ship(design: str, hull: str) -> dict[str, str]:
    return {"Item1": design, "Item2": hull}


def combat(sides: list[object], **members: object) -> dict[str, object]:
    return {
        "Date": None,
        "Ships": sides,
        "HabFaction": None,
        "Attacks": [],
        "winner": {"value": 15},
        "WasSurprising": "No",
        **members,
    }


def side(faction: int, *ships: dict[str, str]) -> dict[str, object]:
    return {"Key": {"value": faction}, "Value": list(ships)}


def test_the_combat_log_decodes_sides_as_hull_class_counts_with_provenance_and_a_null_date() -> None:
    attack = {
        "WeaponDataName": "FixtureLaser",
        "Range_km": 80.5,
        "ArmorFacing": "Nose",
        "Angle": 1.0,
        "TargetingBonus": 0.0,
    }
    first = combat(
        [
            side(15, ship("Fixture Design A", "FixtureEscort"), ship("Fixture Design B", "FixtureEscort")),
            side(16, ship("Fixture Design C", "FixtureCruiser")),
        ],
        Attacks=[attack],
    )
    second = combat(
        [side(16, ship("Fixture Design C", "FixtureCruiser"))], HabFaction={"value": 16}, winner={"value": 16}
    )
    snapshot, report = collect(faction_fragment(CombatLogs=[first, second]))
    log = record(snapshot, "15", "CombatLogs")
    assert log.kind is RecordKind.COMBAT_LOG
    assert log.entries == (
        CombatEntry(
            0,
            date=None,
            sides=(
                (FACTION_15, FrozenMap((("FixtureEscort", 2),))),
                (FACTION_16, FrozenMap((("FixtureCruiser", 1),))),
            ),
            hab_faction=None,
            winner=FACTION_15,
            attacks=(
                FrozenMap(
                    (
                        ("WeaponDataName", "FixtureLaser"),
                        ("Range_km", 80.5),
                        ("ArmorFacing", "Nose"),
                        ("Angle", 1.0),
                        ("TargetingBonus", 0.0),
                    )
                ),
            ),
            surprising="No",
        ),
        CombatEntry(1, None, ((FACTION_16, FrozenMap((("FixtureCruiser", 1),))),), FACTION_16, FACTION_16, (), "No"),
    )
    assert isinstance(log.entries, tuple)
    assert log.entry_location(log.entries[1]).path == f"/gamestates/{FACTION_TYPE}/0/Value/CombatLogs/1"
    assert "Fixture Design" not in repr(log.entries)  # design names are campaign content and are not kept
    assert report.findings == ()


def test_a_combat_date_is_decoded_and_a_side_absent_from_the_save_makes_the_sides_unresolved() -> None:
    entry = combat([side(15, ship("Fixture Design A", "FixtureEscort")), side(999)], Date=DATE)
    snapshot, report = collect(faction_fragment(CombatLogs=[entry]))
    entries = record(snapshot, "15", "CombatLogs").entries
    assert isinstance(entries, tuple) and isinstance(entries[0], CombatEntry)
    assert entries[0].date == ISO
    keys_only = (FrozenMap((("value", 15),)), FrozenMap((("value", 999),)))  # never the design names
    assert entries[0].sides == Unknown(UnknownReason.UNRESOLVED_REFERENCE, keys_only)
    assert report.findings == ()


def test_an_unknown_combat_member_and_a_ships_value_of_the_wrong_shape_are_reported() -> None:
    extended = combat([side(15, ship("Fixture Design A", "FixtureEscort"))], fixtureMember=1)
    bad_ships = combat([{"Key": {"value": 15}, "Value": ["FixtureEscort"]}])
    snapshot, report = collect(faction_fragment(CombatLogs=[extended, bad_ships, "not an object"]))
    entries = record(snapshot, "15", "CombatLogs").entries
    assert isinstance(entries, tuple) and len(entries) == 3
    assert isinstance(entries[1], CombatEntry) and isinstance(entries[1].sides, Unknown)
    assert entries[1].sides.reason is UnknownReason.UNPARSEABLE and entries[1].winner == FACTION_15
    assert isinstance(entries[2], CombatEntry) and isinstance(entries[2].winner, Unknown)
    assert keys(report) == [
        ("unexpected_field_shape", "TIFactionState", "CombatLogs", "array_of_objects"),
        ("unknown_field", "TIFactionState", "CombatLogs[].fixtureMember", ""),
    ]


def test_a_combat_log_of_the_wrong_shape_is_unparseable_and_reported() -> None:
    snapshot, report = collect(faction_fragment(CombatLogs={"0": {}}))
    entries = record(snapshot, "15", "CombatLogs").entries
    assert isinstance(entries, Unknown) and entries.reason is UnknownReason.UNPARSEABLE
    assert keys(report) == [("unexpected_field_shape", "TIFactionState", "CombatLogs", "array")]
