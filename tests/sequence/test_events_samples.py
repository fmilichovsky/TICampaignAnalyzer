"""Invariants of ``events`` on the committed benchmark campaigns.

The narrator package covers each whole campaign. The audit report, with every event and its sources, covers the
campaign's first two saves only: for a whole campaign it runs to gigabytes.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from tests.samples import run_cli, run_json, save_paths

pytestmark = pytest.mark.samples

PACKAGE = ("--format", "json", "--narrative", "--constituents", "evidence")


@pytest.fixture(scope="session")
def package_text(sample_campaign: Path) -> str:
    """The narrator package of the whole campaign, as printed with one job."""
    return run_cli("events", sample_campaign, *PACKAGE, "--jobs", "1")


@pytest.fixture(scope="session")
def package(package_text: str) -> Any:
    return json.loads(package_text)


@pytest.fixture(scope="session")
def audit_saves(sample_campaign: Path) -> list[Path]:
    return save_paths(sample_campaign)[:2]


@pytest.fixture(scope="session")
def audit(audit_saves: list[Path]) -> Any:
    """The report of two saves with every event, its sources and its constituents."""
    return run_json("events", *audit_saves, "--inferred", "--format", "json", "--jobs", "1")


def interval_events(report: Mapping[str, Any]) -> Iterator[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Every event a report lists under an interval, with that interval."""
    for interval in report["intervals"]:
        for event in (*interval["events"], *(interval["inferred"] or ())):
            yield interval, event


def test_events_output_is_identical_across_runs_and_job_counts(sample_campaign: Path, package_text: str) -> None:
    first = run_cli("events", sample_campaign, *PACKAGE, "--jobs", "2")
    second = run_cli("events", sample_campaign, *PACKAGE, "--jobs", "2")
    assert first == second == package_text


def test_event_ids_are_unique(package: Any, audit: Any) -> None:
    for document in (package, audit):
        ids = [event["id"] for _, event in interval_events(document)]
        ids += [event["id"] for event in document["narrative"] or ()]
        assert ids
        assert [event_id for event_id, count in Counter(ids).items() if count > 1] == []


def test_every_event_is_dated_inside_its_interval(package: Any, audit: Any) -> None:
    for document in (package, audit):
        for interval, event in interval_events(document):
            assert event["id"].endswith("@" + interval["key"]), event["id"]
            assert event["not_before"] == interval["not_before"], event["id"]
            assert event["date"][:10] <= interval["date"][:10], event["id"]
            # The first interval also reports what the saves record from before the sequence began.
            history = interval["index"] == 0 and event["attributes"].get("before_sequence") is True
            assert history or interval["not_before"][:10] <= event["date"][:10], event["id"]
    keys = {interval["key"] for interval in package["intervals"]}
    last = package["campaign"]["last_date"][:10]
    for event in package["narrative"]:
        assert event["intervals"] and set(event["intervals"]) <= keys, event["id"]
        assert event["start"][:10] <= event["end"][:10] <= last, event["id"]


def test_every_narrative_event_rests_on_events_of_the_campaign(package: Any) -> None:
    keys = {interval["key"] for interval in package["intervals"]}
    narrative = {event["id"]: event for event in package["narrative"]}
    behind: set[str] = set()
    for event in narrative.values():
        if "member_of" in event:
            assert event["member_of"] in narrative, event["id"]
            continue
        assert event["constituents"], event["id"]
        for constituent in event["constituents"]:
            assert constituent.rpartition("@")[2] in keys, (event["id"], constituent)
        behind.update(event["constituents"])
    # The listed interval events are evidence behind the narrative events, directly or through other events.
    listed = {event["id"]: event for _, event in interval_events(package)}
    pending = list(behind)
    while pending:
        event = listed.get(pending.pop())
        if event is not None:
            cited = set(event["constituents"]) - behind
            behind |= cited
            pending.extend(cited)
    assert set(listed) <= behind


def test_every_event_carries_sources_in_its_saves(audit: Any, audit_saves: list[Path]) -> None:
    saves = {str(path) for path in audit_saves}
    for interval, event in interval_events(audit):
        assert any(source["role"] == "primary" for source in event["sources"]), event["id"]
        for source in event["sources"]:
            change = source["change"]
            for location in (change["before_location"], change["after_location"]):
                assert location is None or location["save_id"] in saves, event["id"]
        if event["status"] == "inferred":
            own = {other["id"] for other in interval["events"]}
            assert event["constituents"] and set(event["constituents"]) <= own, event["id"]
        else:
            assert event["status"] == "objective" and event["constituents"] == [], event["id"]


def test_grouping_finds_one_campaign_per_sample_directory(sample_campaign: Path, package: Any) -> None:
    listing = run_json("campaigns", sample_campaign, "--format", "json")
    [campaign] = listing["campaigns"]
    assert listing["skipped"] == []
    assert not campaign["unclassified"]
    assert campaign["saves"] == len(save_paths(sample_campaign))
    assert package["campaign"]["key"] == campaign["key"]
