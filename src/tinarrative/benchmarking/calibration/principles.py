"""What a change to the calibration principles does to the reasons citing them (ADR-0024).

``make docs`` prints it when it regenerates the principles; ``main`` writes the pull request comment.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

COMMENT_MARKER: Final = "<!-- principle-changes -->"


@dataclass(frozen=True)
class PrincipleRecord:
    """One principle as the page or a generated module states it."""

    identifier: str
    title: str
    revision: int
    text_hash: str


@dataclass(frozen=True)
class Citation:
    """A stated reason: what owns it (``kind <type>`` or ``scaling <name>``), its principle and its revision."""

    owner: str
    principle: str
    revision: int


@dataclass(frozen=True)
class Raised:
    before: PrincipleRecord
    after: PrincipleRecord
    stale: tuple[str, ...]
    """The owners of the reasons judged under a revision below ``after``'s."""


@dataclass(frozen=True)
class Removed:
    record: PrincipleRecord
    citing: tuple[str, ...]
    """The owners of the reasons still citing it: they no longer resolve."""


@dataclass(frozen=True)
class PrincipleChanges:
    raised: tuple[Raised, ...]
    reworded: tuple[PrincipleRecord, ...]
    """Principles whose text changed while their revision did not."""
    added: tuple[PrincipleRecord, ...]
    removed: tuple[Removed, ...]

    @property
    def empty(self) -> bool:
        return not (self.raised or self.reworded or self.added or self.removed)


class _Member(Protocol):
    identifier: str
    title: str
    revision: int
    text_hash: str


def records_of(principles: Iterable[_Member]) -> dict[str, PrincipleRecord]:
    """The records of a generated ``Principle`` enum, by identifier."""
    return {
        member.identifier: PrincipleRecord(member.identifier, member.title, member.revision, member.text_hash)
        for member in principles
    }


def load_records(path: Path) -> dict[str, PrincipleRecord]:
    """The records of the generated module at ``path``, imported apart from this package; none when it is missing."""
    if not path.is_file():
        return {}
    spec = importlib.util.spec_from_file_location("_principles_at_path", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return records_of(module.Principle)


def citations() -> list[Citation]:
    """Every stated reason of the code's kinds and scalings."""
    from tinarrative.kinds.registry import KINDS
    from tinarrative.model.kinds import Reason
    from tinarrative.narrative.scalings import SCALINGS

    owned = [(f"kind {event_type}", kind.reason) for event_type, kind in KINDS.items()]
    owned += [(f"scaling {scaling.value}", spec.reason) for scaling, spec in SCALINGS.items()]
    return [
        Citation(owner, reason.principle.identifier, reason.revision)
        for owner, reason in owned
        if isinstance(reason, Reason)
    ]


def compare(
    before: Mapping[str, PrincipleRecord], after: Mapping[str, PrincipleRecord], cited: Sequence[Citation]
) -> PrincipleChanges:
    """How ``after`` differs from ``before``, with the citations each raised or removed principle affects."""

    def owners(identifier: str, below: int | None = None) -> tuple[str, ...]:
        return tuple(
            sorted(
                citation.owner
                for citation in cited
                if citation.principle == identifier and (below is None or citation.revision < below)
            )
        )

    raised, reworded = [], []
    for identifier, new in after.items():
        old = before.get(identifier)
        if old is None:
            continue
        if new.revision > old.revision:
            raised.append(Raised(old, new, owners(identifier, below=new.revision)))
        elif new.text_hash != old.text_hash or new.title != old.title:
            reworded.append(new)
    return PrincipleChanges(
        raised=tuple(raised),
        reworded=tuple(reworded),
        added=tuple(record for identifier, record in after.items() if identifier not in before),
        removed=tuple(
            Removed(record, owners(identifier)) for identifier, record in before.items() if identifier not in after
        ),
    )


def render_lines(changes: PrincipleChanges) -> list[str]:
    """One line per change, for ``make docs``."""
    lines = [
        f"principle {change.after.identifier} rose r{change.before.revision}→r{change.after.revision}; "
        f"stale: {', '.join(change.stale) or 'nothing'}"
        for change in changes.raised
    ]
    lines += [
        f"principle {record.identifier} changed its text at r{record.revision}; raise its revision if a reason "
        "judged under the old text could now be wrong"
        for record in changes.reworded
    ]
    lines += [f"principle {record.identifier} added at r{record.revision}" for record in changes.added]
    lines += [
        f"principle {change.record.identifier} removed; still cited by: {', '.join(change.citing) or 'nothing'}"
        for change in changes.removed
    ]
    return lines


def _title(record: PrincipleRecord) -> str:
    return f"**{record.title}** (`{record.identifier}`)"


def _owners(owners: Sequence[str], none: str) -> list[str]:
    return [f"  - {owner}" for owner in owners] if owners else [f"  - {none}"]


def render_comment(changes: PrincipleChanges, *, base: str, head: str) -> str:
    """The pull request comment: every change, the kinds and scalings each one touches; it starts with the marker."""
    lines = [COMMENT_MARKER, "## Calibration principles", "", f"Comparing {base} with {head}.", ""]
    if changes.empty:
        lines.append("No principle changed its revision, text or presence.")
    if changes.raised:
        lines += ["### Revision raised", ""]
        for change in changes.raised:
            lines.append(f"- {_title(change.after)} r{change.before.revision} → r{change.after.revision}; stale:")
            lines += _owners(change.stale, "no reason cites an earlier revision")
        lines.append("")
    if changes.reworded:
        lines += ["### Text changed, revision kept", ""]
        lines += [
            f"- {_title(record)} r{record.revision}: raise the revision if a reason judged under the old text could "
            "now be wrong"
            for record in changes.reworded
        ]
        lines.append("")
    if changes.added:
        lines += ["### Added", ""]
        lines += [f"- {_title(record)} r{record.revision}" for record in changes.added]
        lines.append("")
    if changes.removed:
        lines += ["### Removed", ""]
        for gone in changes.removed:
            lines.append(f"- {_title(gone.record)}; still cited by:")
            lines += _owners(gone.citing, "nothing")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tinarrative.benchmarking.calibration.principles",
        description="Compare a base revision's generated principles with this package's and write the comment.",
    )
    parser.add_argument("--base", type=Path, required=True, help="The base revision's generated principles module.")
    parser.add_argument("--base-label", default="base", help="How the comment names the base revision.")
    parser.add_argument("--head-label", default="head", help="How the comment names this revision.")
    parser.add_argument("--out", type=Path, required=True, help="Where to write the comment.")
    args = parser.parse_args(argv)
    from tinarrative.model.principles import Principle

    changes = compare(load_records(args.base), records_of(Principle), citations())
    args.out.write_text(render_comment(changes, base=args.base_label, head=args.head_label), encoding="utf-8")
    for line in render_lines(changes):
        print(line, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
