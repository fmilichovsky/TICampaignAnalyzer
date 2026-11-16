"""Draft stakes: stakes tried on the events of existing narrative types before a kind declares them.

Extraction scores each as shadow rows beside the real events (``table.extract_campaign``); nothing in the product
path reads this module.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from tinarrative.kinds.registry import kind_for
from tinarrative.model.events import Significance
from tinarrative.narrative.significance import NarrativeScaling

ROW_PREFIX: Final = "draft:"
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class DraftStakeError(ValueError):
    """A draft stake that cannot be scored: an unknown or atomic event type, a repeated or malformed name, no
    scaling, or no single base to default to."""


@dataclass(frozen=True)
class DraftStake:
    """A stake tried before its kind declares it, for example::

    DraftStake(
        name="space-program",
        label="Space program share",
        issue=361,
        event_types=("nation.space_program_growth",),
        scalings=(NarrativeScaling(StakeMeasure.BOOST, actor), NarrativeScaling(StakeMeasure.MISSION_CONTROL, actor)),
    )
    """

    name: str
    """A slug: the prefix of its rows' ids and its key in the state hash."""
    label: str
    issue: int
    """The issue the draft calibrates for."""
    event_types: tuple[str, ...]
    """Existing narrative event types."""
    scalings: tuple[NarrativeScaling, ...]
    """Each is a candidate of the rows' stakes; the highest scale wins."""
    base: Significance | None = None
    """The hypothetical base level; by default the base of the types' kind."""


DRAFT_STAKES: tuple[DraftStake, ...] = ()
"""The declared draft stakes; read at call time, so tests patch it."""


def validate_drafts(drafts: Sequence[DraftStake]) -> None:
    """Raises ``DraftStakeError`` for the first draft that cannot be scored, naming it."""
    seen: set[str] = set()
    for draft in drafts:
        if not _SLUG.fullmatch(draft.name):
            raise DraftStakeError(f"draft stake name {draft.name!r} is not a lowercase slug (a-z, 0-9 and -)")
        if draft.name in seen:
            raise DraftStakeError(f"draft stake name {draft.name!r} is repeated")
        seen.add(draft.name)
        if not draft.event_types:
            raise DraftStakeError(f"draft stake {draft.name!r} names no event type")
        if not draft.scalings:
            raise DraftStakeError(f"draft stake {draft.name!r} has no scaling")
        for event_type in draft.event_types:
            kind = kind_for(event_type)
            if kind is None:
                raise DraftStakeError(f"draft stake {draft.name!r}: event type {event_type!r} is declared by no kind")
            if not kind.narrative:
                raise DraftStakeError(
                    f"draft stake {draft.name!r}: event type {event_type!r} is not a narrative event type"
                )
        draft_base(draft)


def draft_base(draft: DraftStake) -> Significance:
    """The draft's base, else the one base its types' kinds share; ``DraftStakeError`` when they differ."""
    if draft.base is not None:
        return draft.base
    bases = {kind.base for event_type in draft.event_types if (kind := kind_for(event_type)) is not None}
    if len(bases) != 1:
        levels = ", ".join(sorted(level.value for level in bases))
        raise DraftStakeError(f"draft stake {draft.name!r} needs a base: its event types' kinds differ ({levels})")
    return next(iter(bases))


def draft_row_id(name: str, event_id: str) -> str:
    return f"{ROW_PREFIX}{name}:{event_id}"


def draft_name(row_id: str) -> str:
    """The draft a row id of ``draft_row_id`` belongs to; ``""`` for any other id."""
    if not row_id.startswith(ROW_PREFIX):
        return ""
    return row_id[len(ROW_PREFIX) :].partition(":")[0]
