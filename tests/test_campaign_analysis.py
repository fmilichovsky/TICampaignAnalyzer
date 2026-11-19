"""The survey step of the campaign analysis, driven directly over synthetic fixture saves."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.fixtures import fixture_path
from tests.sequence.campaign_variants import POLITICS
from tinarrative.campaign_analysis import (
    EmptyDirectory,
    NoUsableSave,
    Survey,
    UnreadableInput,
    UnsupportedSave,
    resolve_jobs,
    survey_inputs,
)
from tinarrative.config import DEFAULT_SETTINGS, ProcessingSettings, Settings
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
