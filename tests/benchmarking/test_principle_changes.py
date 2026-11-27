"""What a change to the calibration principles does to the reasons that cite them: the report `make docs` prints and
the pull request comment."""

from __future__ import annotations

from pathlib import Path

from tinarrative.benchmarking.calibration.principles import (
    COMMENT_MARKER,
    Citation,
    PrincipleRecord,
    citations,
    compare,
    load_records,
    records_of,
    render_comment,
    render_lines,
)
from tinarrative.kinds.registry import KINDS
from tinarrative.model.kinds import Reason
from tinarrative.model.principles import Principle

ROLE = PrincipleRecord("trivial-is-a-role", "Trivial is a role", 1, "aaaa")
BOTH = PrincipleRecord("both-ways", "Both ways", 1, "bbbb")
CITED = (
    Citation("kind control.org_churn", "trivial-is-a-role", 1),
    Citation("kind campaign.log", "trivial-is-a-role", 2),
    Citation("scaling power", "both-ways", 1),
)


def _records(*records: PrincipleRecord) -> dict[str, PrincipleRecord]:
    return {record.identifier: record for record in records}


def test_a_raised_revision_lists_the_reasons_it_made_stale() -> None:
    raised = PrincipleRecord("trivial-is-a-role", "Trivial is a role", 3, "cccc")
    changes = compare(_records(ROLE, BOTH), _records(raised, BOTH), CITED)

    assert [(change.before, change.after, change.stale) for change in changes.raised] == [
        (ROLE, raised, ("kind campaign.log", "kind control.org_churn"))
    ]
    assert changes.reworded == () and changes.added == () and changes.removed == ()
    (line,) = render_lines(changes)
    assert all(
        part in line for part in ("trivial-is-a-role", "r1", "r3", "kind campaign.log", "kind control.org_churn")
    )


def test_a_text_change_without_a_raised_revision_is_reported_apart() -> None:
    reworded = PrincipleRecord("both-ways", "Both ways", 1, "dddd")
    changes = compare(_records(ROLE, BOTH), _records(ROLE, reworded), CITED)

    assert changes.raised == ()
    assert changes.reworded == (reworded,)
    (line,) = render_lines(changes)
    assert "both-ways" in line and "scaling power" not in line


def test_a_removed_principle_names_the_reasons_still_citing_it_and_an_added_one_is_listed() -> None:
    added = PrincipleRecord("no-density", "No density", 1, "eeee")
    changes = compare(_records(ROLE, BOTH), _records(ROLE, added), CITED)

    assert [(change.record, change.citing) for change in changes.removed] == [(BOTH, ("scaling power",))]
    assert changes.added == (added,)
    added_line, removed_line = render_lines(changes)
    assert "no-density" in added_line
    assert "both-ways" in removed_line and "scaling power" in removed_line


def test_no_change_reports_nothing() -> None:
    changes = compare(_records(ROLE), _records(ROLE), CITED)
    assert changes.empty and render_lines(changes) == []


def test_the_comment_starts_with_its_marker_and_says_when_nothing_changed() -> None:
    raised = PrincipleRecord("trivial-is-a-role", "Trivial is a role", 2, "cccc")
    comment = render_comment(compare(_records(ROLE), _records(raised), CITED), base="main abc1234", head="pr def5678")

    assert comment.startswith(COMMENT_MARKER + "\n")
    assert all(part in comment for part in ("Trivial is a role", "r1", "r2", "kind control.org_churn", "main abc1234"))
    quiet = render_comment(compare(_records(ROLE), _records(ROLE), CITED), base="b", head="h")
    assert quiet.startswith(COMMENT_MARKER + "\n") and "kind" not in quiet


def test_the_codes_citations_are_its_stated_reasons() -> None:
    reason = KINDS["organization.appeared"].reason
    assert isinstance(reason, Reason)
    cited = citations()
    assert Citation("kind organization.appeared", reason.principle.identifier, reason.revision) in cited
    assert not any(citation.owner == "kind war.arc" for citation in cited)  # unexamined


def test_loading_the_generated_module_from_a_path_reads_its_records(tmp_path: Path) -> None:
    module = Path(__file__).resolve().parents[2] / "src" / "tinarrative" / "model" / "principles.py"
    assert load_records(module) == records_of(Principle)
    assert load_records(tmp_path / "missing.py") == {}
