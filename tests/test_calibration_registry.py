"""Coverage for scripts/calibration_registry.py on recorded `gh` output: the two lines, the filters and the sections."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import pytest

from scripts.calibration_registry import (
    EXIT_GH_FAILED,
    EXIT_OK,
    GROUPS,
    KINDS,
    PARENT_TITLE,
    main,
    parse_body,
    parse_touches,
)
from tests.fixtures import fixture_path

NOW = datetime(2026, 11, 26, tzinfo=UTC)


def _recorded(name: str) -> str:
    return fixture_path("calibration_registry", name).read_text(encoding="utf-8")


class RecordedGh:
    """Answers the three `gh` calls the script makes from the recorded fixtures, and remembers them."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, arguments: Sequence[str]) -> str:
        self.calls.append(list(arguments))
        if arguments[:2] == ["issue", "list"]:
            return _recorded("gh_issue_list.json")
        if arguments[:2] == ["pr", "list"]:
            return _recorded("gh_pr_list.json")
        if arguments[0] == "api" and "sub_issues" in arguments[2]:
            return _recorded("gh_sub_issues.jsonl")
        raise AssertionError(f"unexpected gh call {arguments}")


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> dict[str, Any]:
    assert main(["--json", *argv], run=RecordedGh(), now=NOW) == EXIT_OK
    result: dict[str, Any] = json.loads(capsys.readouterr().out)
    return result


def _numbers(entries: list[dict[str, Any]]) -> set[int]:
    return {entry["number"] for entry in entries}


def test_a_body_with_both_lines_gives_its_kind_and_groups() -> None:
    kind, touches, problems = parse_body(
        "Intro.\n\nCalibration: value proposal\nTouches: types=a.b, c.d; themes=Wars and conflicts\n"
    )
    assert kind == "value proposal"
    assert touches == {"types": ("a.b", "c.d"), "themes": ("Wars and conflicts",)}
    assert problems == ()


@pytest.mark.parametrize("kind", KINDS)
def test_every_kind_is_accepted(kind: str) -> None:
    assert parse_body(f"Calibration: {kind}\nTouches: types=x")[0] == kind


def test_every_group_is_accepted_and_any_may_be_absent() -> None:
    for group in GROUPS:
        assert parse_touches(f"{group}=x") == {group: ("x",)}


@pytest.mark.parametrize(
    "touches",
    ["types=a; stakes=b", "types", "types=a,,b", "types=a; types=b", "", " ; "],
    ids=["unknown group", "no equals", "empty value", "repeated group", "empty", "only separators"],
)
def test_a_malformed_touches_line_is_a_problem_not_a_crash(touches: str) -> None:
    kind, parsed, problems = parse_body(f"Calibration: review\nTouches: {touches}")
    assert kind == "review"
    assert parsed is None
    assert any("malformed Touches line" in problem for problem in problems)


def test_an_unknown_kind_and_missing_lines_are_problems() -> None:
    assert parse_body("Calibration: tier (a)\nTouches: types=x")[0] is None
    assert len(parse_body("Calibration: tier (a)\nTouches: types=x")[2]) == 1
    assert len(parse_body("No machine lines here.")[2]) == 2


def test_lines_inside_a_fenced_example_are_not_the_items_own() -> None:
    _, _, problems = parse_body("```\nCalibration: review\nTouches: types=x\n```\n")
    assert len(problems) == 2


def test_the_listing_holds_open_and_recently_closed_complete_items(capsys: pytest.CaptureFixture[str]) -> None:
    registry = _run(capsys)
    assert _numbers(registry["items"]) == {701, 702, 703, 710}
    pr = next(item for item in registry["items"] if item["number"] == 710)
    assert pr["pr"] and pr["state"] == "merged"
    scoring = next(item for item in registry["items"] if item["number"] == 702)
    assert scoring["kind"] == "scoring proposal"
    assert scoring["touches"] == {"types": ["war.arc"], "measures": ["power"]}


def test_since_widens_the_window_of_closed_items(capsys: pytest.CaptureFixture[str]) -> None:
    assert 704 in _numbers(_run(capsys, "--since", "365")["items"])


def test_items_without_usable_lines_are_listed_apart(capsys: pytest.CaptureFixture[str]) -> None:
    registry = _run(capsys)
    assert _numbers(registry["needs_lines"]) == {705, 706}
    assert not _numbers(registry["needs_lines"]) & _numbers(registry["items"])


def test_the_parent_is_found_by_exact_title_and_is_no_item(capsys: pytest.CaptureFixture[str]) -> None:
    registry = _run(capsys)
    assert registry["parent"]["title"] == PARENT_TITLE
    parent = registry["parent"]["number"]
    assert parent not in _numbers(registry["items"]) | _numbers(registry["needs_lines"])


def test_open_reviews_come_from_the_parents_sub_issues(capsys: pytest.CaptureFixture[str]) -> None:
    assert _numbers(_run(capsys)["reviews"]) == {701, 711}


def test_an_item_matches_when_any_group_overlaps(capsys: pytest.CaptureFixture[str]) -> None:
    registry = _run(capsys, "--measure", "power", "--scaling", "fleet")
    assert _numbers(registry["items"]) == {702, 703}


def test_filters_repeat_split_on_commas_and_ignore_case(capsys: pytest.CaptureFixture[str]) -> None:
    by_repeat = _run(capsys, "--type", "war.declared", "--type", "WAR.ARC")
    by_comma = _run(capsys, "--type", "war.declared,war.arc")
    assert _numbers(by_repeat["items"]) == _numbers(by_comma["items"]) == {701, 702, 710}


def test_a_filter_narrows_the_reviews_but_never_the_items_needing_lines(
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = _run(capsys, "--theme", "alien spread")
    assert _numbers(registry["items"]) == set()
    assert _numbers(registry["reviews"]) == {711}
    assert _numbers(registry["needs_lines"]) == {705, 706}


def test_text_output_names_every_listed_item(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([], run=RecordedGh(), now=NOW) == EXIT_OK
    text = capsys.readouterr().out
    for number in (701, 702, 703, 705, 706, 710, 711):
        assert f"#{number}" in text


def test_without_a_parent_there_are_no_reviews_and_no_sub_issue_call(capsys: pytest.CaptureFixture[str]) -> None:
    gh = RecordedGh()

    def no_parent(arguments: Sequence[str]) -> str:
        output = gh(arguments)
        if arguments[:2] == ["issue", "list"]:
            return json.dumps([record for record in json.loads(output) if record["title"] != PARENT_TITLE])
        return output

    assert main(["--json"], run=no_parent, now=NOW) == EXIT_OK
    registry = json.loads(capsys.readouterr().out)
    assert registry["parent"] is None and registry["reviews"] == []
    assert not any(call[0] == "api" for call in gh.calls)


def test_a_given_repo_reaches_every_gh_call(capsys: pytest.CaptureFixture[str]) -> None:
    gh = RecordedGh()
    assert main(["--json", "--repo", "owner/name"], run=gh, now=NOW) == EXIT_OK
    capsys.readouterr()
    assert all("owner/name" in " ".join(call) for call in gh.calls)


def test_a_gh_failure_is_reported_with_its_exit_code(capsys: pytest.CaptureFixture[str]) -> None:
    def failing(arguments: Sequence[str]) -> str:
        raise RuntimeError("gh issue list failed: not logged in")

    assert main([], run=failing, now=NOW) == EXIT_GH_FAILED
    assert "not logged in" in capsys.readouterr().err


def test_a_principle_filter_lists_the_items_standing_on_it(capsys: pytest.CaptureFixture[str]) -> None:
    assert parse_touches("principles=trivial-is-a-role") == {"principles": ("trivial-is-a-role",)}
    assert _numbers(_run(capsys, "--principle", "Trivial-Is-A-Role")["items"]) == {703}
    assert _numbers(_run(capsys, "--principle", "the-ordinary-instance")["items"]) == set()
