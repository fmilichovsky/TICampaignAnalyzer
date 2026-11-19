"""The steps of the campaign analysis, driven directly over synthetic fixture saves."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures import fixture_path
from tests.sequence.campaign_variants import POLITICS, write_campaign
from tinarrative.campaign_analysis import (
    CampaignAnalysis,
    CampaignNotChosen,
    Depth,
    EmptyDirectory,
    LoadFailed,
    NoUsableSave,
    Survey,
    UnreadableInput,
    UnsupportedSave,
    analyze_campaign,
    choose_campaign,
    resolve_jobs,
    survey_inputs,
)
from tinarrative.config import DEFAULT_SETTINGS, ProcessingSettings, Settings
from tinarrative.grouping import CampaignGroup, group_saves
from tinarrative.io.save_discovery import expand_inputs

FIXTURE_SET = "terra_invicta_json_v1"
BAD = "malformed_truncated.json"


class RecordingProgress:
    def __init__(self) -> None:
        self.updates: list[tuple[str, int, int | None, str | None]] = []
        self.finished: list[str] = []

    def update(self, phase: str, completed: int, total: int | None = None, filename: str | None = None) -> None:
        self.updates.append((phase, completed, total, filename))

    def finish(self, activity: str = "parsing and processing") -> None:
        self.finished.append(activity)


def fixture(name: str) -> Path:
    return fixture_path("io", FIXTURE_SET, name)


def survey(*paths: Path, jobs: int | None = 1, progress: RecordingProgress | None = None) -> object:
    return survey_inputs(expand_inputs(paths), DEFAULT_SETTINGS, command="test", jobs=jobs, progress=progress)


def directory_of(tmp_path: Path, *names: str) -> Path:
    directory = tmp_path / "saves"
    directory.mkdir()
    for name in names:
        shutil.copy(fixture(name), directory / name)
    return directory


def test_named_saves_are_surveyed_with_no_minimum_count() -> None:
    outcome = survey(fixture(POLITICS[0]))

    assert isinstance(outcome, Survey)
    assert [Path(save.source).name for save in outcome.saves] == [POLITICS[0]]
    assert outcome.skipped == []


def test_an_unusable_file_inside_a_directory_is_skipped(tmp_path: Path) -> None:
    outcome = survey(directory_of(tmp_path, POLITICS[0], BAD))

    assert isinstance(outcome, Survey)
    assert [Path(save.source).name for save in outcome.saves] == [POLITICS[0]]
    assert [Path(skipped.source).name for skipped in outcome.skipped] == [BAD]


def test_an_unusable_file_named_directly_fails_with_its_sentence() -> None:
    outcome = survey(fixture(POLITICS[0]), fixture(BAD))

    assert isinstance(outcome, UnsupportedSave)
    assert outcome.message.startswith(f"{fixture(BAD)}: ")


def test_a_missing_file_is_unreadable(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    outcome = survey(missing)

    assert isinstance(outcome, UnreadableInput)
    assert outcome.message.startswith(f"cannot read {missing}: ")


def test_an_empty_directory_fails(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    outcome = survey(empty)

    assert outcome == EmptyDirectory(str(empty))
    assert str(empty) in outcome.message


def test_a_directory_without_a_usable_save_fails(tmp_path: Path) -> None:
    directory = directory_of(tmp_path, BAD)

    outcome = survey(directory)

    assert outcome == NoUsableSave(str(directory))
    assert str(directory) in outcome.message


def test_the_first_failure_in_input_order_is_returned_whatever_the_jobs(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    paths = [fixture(BAD), missing]

    serial = survey(*paths, jobs=1)
    parallel = survey(*paths, jobs=2)

    assert serial == parallel
    assert isinstance(serial, UnsupportedSave)


def test_progress_reports_each_survey() -> None:
    progress = RecordingProgress()

    survey(*(fixture(name) for name in POLITICS), progress=progress)

    assert progress.updates == [("Scanning saves", n, None, name) for n, name in enumerate(POLITICS, start=1)]


def test_jobs_flag_beats_the_setting_which_beats_the_default() -> None:
    configured = Settings(processing=ProcessingSettings(jobs=3))

    assert resolve_jobs(5, configured, []) == 5
    assert resolve_jobs(None, configured, []) == 3
    assert resolve_jobs(None, DEFAULT_SETTINGS, []) == 1
    assert resolve_jobs(None, DEFAULT_SETTINGS, [fixture(POLITICS[0])]) == 1


def test_unreadable_sources_do_not_stop_the_default_jobs(tmp_path: Path) -> None:
    assert resolve_jobs(None, DEFAULT_SETTINGS, [tmp_path / "missing.json"]) == 1


@pytest.mark.parametrize("jobs", [1, 2])
def test_directory_members_survey_the_same_in_workers(tmp_path: Path, jobs: int) -> None:
    outcome = survey(directory_of(tmp_path, *POLITICS, BAD), jobs=jobs)

    assert isinstance(outcome, Survey)
    assert len(outcome.saves) == 3
    assert len(outcome.skipped) == 1


def groups_of(*paths: Path) -> list[CampaignGroup]:
    outcome = survey(*paths)
    assert isinstance(outcome, Survey)
    return group_saves(outcome.saves)


def two_campaigns(tmp_path: Path) -> list[CampaignGroup]:
    directory = tmp_path / "two"
    directory.mkdir()
    write_campaign(directory, "first", faction_name="Humanity First")
    write_campaign(directory, "second", faction_name="Academy")
    groups = groups_of(directory)
    assert len(groups) == 2
    return groups


def one_campaign() -> CampaignGroup:
    (group,) = groups_of(*(fixture(name) for name in POLITICS))
    return group


def test_the_only_campaign_is_chosen_without_a_selector() -> None:
    group = one_campaign()

    assert choose_campaign([group]) is group


def test_several_campaigns_without_a_selector_are_not_chosen(tmp_path: Path) -> None:
    outcome = choose_campaign(two_campaigns(tmp_path))

    assert outcome == CampaignNotChosen("the input holds 2 campaigns; choose one with --campaign")
    assert outcome.message == outcome.reason


def test_no_campaign_without_a_selector_is_not_chosen() -> None:
    assert choose_campaign([]) == CampaignNotChosen("the input holds 0 campaigns; choose one with --campaign")


def test_a_selector_chooses_by_position_key_and_key_prefix(tmp_path: Path) -> None:
    groups = two_campaigns(tmp_path)

    assert choose_campaign(groups, "2") is groups[1]
    assert choose_campaign(groups, groups[0].key) is groups[0]
    assert choose_campaign(groups, groups[1].key[:4]) is groups[1]


def test_a_selector_that_matches_none_gives_its_reason(tmp_path: Path) -> None:
    groups = two_campaigns(tmp_path)

    assert choose_campaign(groups, "3") == CampaignNotChosen("there is no campaign 3; the listing has 2")
    assert choose_campaign(groups, "nowhere") == CampaignNotChosen("no campaign matches 'nowhere'")


def test_latest_chooses_the_campaign_with_the_newest_file(tmp_path: Path) -> None:
    groups = two_campaigns(tmp_path)
    for path in groups[0].paths:
        os.utime(path, (1, 1))

    assert choose_campaign(groups, "latest") is groups[1]


def analyze(depth: Depth, **options: Any) -> CampaignAnalysis:
    outcome = analyze_campaign(one_campaign(), DEFAULT_SETTINGS, command="test", depth=depth, jobs=1, **options)
    assert isinstance(outcome, CampaignAnalysis)
    return outcome


def test_objective_depth_has_intervals_without_inferred_events_or_narrative() -> None:
    analysis = analyze(Depth.OBJECTIVE)

    assert len(analysis.intervals) == 2
    assert analysis.narrative is None
    assert all(interval.inferred is None or not interval.inferred for interval in analysis.intervals)


def test_inferred_depth_adds_inferred_events() -> None:
    objective, inferred = analyze(Depth.OBJECTIVE), analyze(Depth.INFERRED)

    assert inferred.narrative is None
    assert sum(len(i.inferred or ()) for i in inferred.intervals) > sum(
        len(i.inferred or ()) for i in objective.intervals
    )


def test_narrative_depth_builds_narrative_events_over_inferred_events() -> None:
    analysis = analyze(Depth.NARRATIVE)

    assert analysis.narrative is not None
    assert sum(len(i.inferred or ()) for i in analysis.intervals) == sum(
        len(i.inferred or ()) for i in analyze(Depth.INFERRED).intervals
    )


def test_state_changes_are_kept_only_when_requested() -> None:
    assert all(interval.state_changes is None for interval in analyze(Depth.OBJECTIVE).intervals)
    assert all(
        interval.state_changes is not None for interval in analyze(Depth.OBJECTIVE, state_changes=True).intervals
    )


def test_the_plan_records_the_surveyed_skipped_saves(tmp_path: Path) -> None:
    survey_outcome = survey(directory_of(tmp_path, *POLITICS, BAD))
    assert isinstance(survey_outcome, Survey)
    (group,) = group_saves(survey_outcome.saves)

    analysis = analyze_campaign(group, DEFAULT_SETTINGS, command="test", skipped=survey_outcome.skipped, jobs=1)

    assert isinstance(analysis, CampaignAnalysis)
    assert [Path(skipped.source).name for skipped in analysis.plan.skipped] == [BAD]


def test_one_save_has_a_plan_and_no_intervals() -> None:
    (group,) = groups_of(fixture(POLITICS[0]))

    analysis = analyze_campaign(group, DEFAULT_SETTINGS, command="test", depth=Depth.NARRATIVE, jobs=1)

    assert isinstance(analysis, CampaignAnalysis)
    assert analysis.intervals == []


def test_progress_reports_each_processed_save() -> None:
    progress = RecordingProgress()

    analyze_campaign(one_campaign(), DEFAULT_SETTINGS, command="test", jobs=1, progress=progress)

    assert progress.updates[0] == ("Processing saves", 0, 3, None)
    assert progress.updates[-1] == ("Processing saves", 3, 3, None)


@pytest.mark.parametrize("jobs", [1, 2])
def test_a_save_that_cannot_be_loaded_is_a_returned_failure(
    jobs: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("tinarrative.sequence.MIN_CHUNK_INTERVALS", 1)
    directory = directory_of(tmp_path, *POLITICS)
    (group,) = groups_of(directory)
    vanished = Path(group.saves[-1].source)
    vanished.unlink()  # surveyed, then gone before its chunk loads it

    outcome = analyze_campaign(group, DEFAULT_SETTINGS, command="test", jobs=jobs)

    assert isinstance(outcome, LoadFailed)
    assert isinstance(outcome.cause, UnreadableInput)
    assert outcome.message == f"cannot read {vanished}: No such file or directory"


def test_a_save_that_is_no_longer_a_save_is_an_unsupported_failure(tmp_path: Path) -> None:
    directory = directory_of(tmp_path, *POLITICS)
    (group,) = groups_of(directory)
    Path(group.saves[-1].source).write_text("not a save", encoding="utf-8")

    outcome = analyze_campaign(group, DEFAULT_SETTINGS, command="test", jobs=1)

    assert isinstance(outcome, LoadFailed)
    assert isinstance(outcome.cause, UnsupportedSave)


def test_a_save_without_a_game_time_is_skipped_in_a_directory_and_fails_when_named(tmp_path: Path) -> None:
    unorderable = "representative_campaign.json"

    skipped = survey(directory_of(tmp_path, POLITICS[0], unorderable))
    named = survey(fixture(POLITICS[0]), fixture(unorderable))

    assert isinstance(skipped, Survey)
    assert [(Path(s.source).name, s.error_class) for s in skipped.skipped] == [(unorderable, "UnknownChronologyError")]
    assert isinstance(named, UnsupportedSave)
    assert "cannot be ordered" in named.message


def test_a_named_unusable_file_fails_beside_a_directory(tmp_path: Path) -> None:
    outcome = survey(directory_of(tmp_path, *POLITICS), fixture(BAD))

    assert isinstance(outcome, UnsupportedSave)


def test_files_and_directories_mix_and_identical_copies_merge_into_the_first_source(tmp_path: Path) -> None:
    directory = directory_of(tmp_path, POLITICS[0], POLITICS[1])
    copy = tmp_path / "Exitsave.json"
    shutil.copy(fixture(POLITICS[1]), copy)
    survey_outcome = survey(fixture(POLITICS[2]), directory, copy)
    assert isinstance(survey_outcome, Survey)
    (group,) = group_saves(survey_outcome.saves)

    analysis = analyze_campaign(group, DEFAULT_SETTINGS, command="test", jobs=1)

    assert isinstance(analysis, CampaignAnalysis)
    assert (analysis.plan.inputs, analysis.plan.duplicates, analysis.plan.skipped) == (4, 1, ())
    assert [(Path(s.source).name, [Path(a).name for a in s.aliases]) for s in analysis.plan.saves] == [
        (POLITICS[0], []),
        (copy.name, [POLITICS[1]]),
        (POLITICS[2], []),
    ]
