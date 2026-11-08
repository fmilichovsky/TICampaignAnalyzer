"""Acceptance over the global-values fixture pair: expected events, provenance, war corroboration, wording."""

from tests.analyzers.support import fixture_pair
from tinarrative.analyzers import ALL_ANALYZERS, CAMPAIGN_ANALYZERS, run_analyzers
from tinarrative.analyzers.render import describe_event
from tinarrative.model.entities import EntityRef
from tinarrative.model.events import Event, SourceRole

PAIR = ("global_values_before.json", "global_values_after.json")
SINGLETON = "global values:70"
STATE_PATH = "/gamestates/PavonisInteractive.TerraInvicta.TIGlobalValuesState/0/Value"


def run_all() -> tuple[Event, ...]:
    return run_analyzers(ALL_ANALYZERS, *fixture_pair(*PAIR))


def by_id(events: tuple[Event, ...]) -> dict[str, Event]:
    return {event.id: event for event in events}


def test_global_values_pair_yields_the_expected_campaign_events() -> None:
    events = run_analyzers(CAMPAIGN_ANALYZERS, *fixture_pair(*PAIR))
    assert [event.id for event in events] == [
        f"campaign.global_milestone_recorded/{SINGLETON}/FirstBaseOnLuna",
        f"campaign.global_value_changed/{SINGLETON}/earthAtmosphericCO2_ppm",
        f"campaign.narrative_event_triggered/{SINGLETON}/campaign/1",
        f"campaign.narrative_event_triggered/{SINGLETON}/target/event_FixtureTarget",
        f"campaign.nuclear_strikes_changed/{SINGLETON}",
        f"campaign.sea_level_rise_triggered/{SINGLETON}/1",
    ]


def test_a_new_milestone_cites_its_record_entry_and_names_the_faction() -> None:
    event = by_id(run_all())[f"campaign.global_milestone_recorded/{SINGLETON}/FirstBaseOnLuna"]
    (source,) = event.sources
    assert source.entry is not None and source.entry.path == f"{STATE_PATH}/globalMilestones/FirstBaseOnLuna"
    assert source.member == "FirstBaseOnLuna"
    assert [str(ref.entity_id) for ref in event.entities] == [SINGLETON, "faction:15"]
    assert event.entities[1].name == "Fixture Resistance"


def test_war_presence_cites_the_interstate_wars_entry_as_corroboration() -> None:
    events = by_id(run_all())
    for event_id, war in (("war.disappeared/war:91", "war:91"), ("war.appeared/war:92", "war:92")):
        cited = [source for source in events[event_id].sources if source.change.field == "interstateWars"]
        assert len(cited) == 1
        assert cited[0].role is SourceRole.CORROBORATING
        member = cited[0].member
        assert isinstance(member, EntityRef) and str(member.entity_id) == war
        assert str(cited[0].change.entity_id) == SINGLETON
    assert not [event for event in events.values() if event.event_type == "campaign.interstate_wars_changed"]


def test_campaign_events_are_described_literally() -> None:
    lines = {describe_event(event) for event in run_analyzers(CAMPAIGN_ANALYZERS, *fixture_pair(*PAIR))}
    assert lines == {
        f"{SINGLETON} records global milestone FirstBaseOnLuna for Fixture Resistance (faction:15)",
        f"{SINGLETON} earthAtmosphericCO2_ppm: 420.0 -> 421.5",
        f"{SINGLETON} lists narrative event event_FixtureSecond as triggered once per campaign",
        f"{SINGLETON} lists narrative event event_FixtureTarget as triggered for [Fixture Resistance (faction:15)]",
        f"{SINGLETON} nuclear strikes: 0 -> 2",
        f"{SINGLETON} sea level rise 1 flag set",
    }
    assert all(line.isascii() for line in lines)
