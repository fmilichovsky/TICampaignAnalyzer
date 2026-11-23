"""Draft shares: shares tried on the events of existing narrative types before a kind declares them.

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
from tinarrative.model.kinds import Measure, Scaling
from tinarrative.narrative.scalings import SCALINGS, ScalingSpec
from tinarrative.narrative.significance import ShareReading

ROW_PREFIX: Final = "draft:"
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class DraftShareError(ValueError):
    """A draft share that cannot be scored: an unknown or atomic event type, a repeated or malformed name, no
    reading, no single base to default to, or a scaling on a measure no reading reads or on a measure twice."""


@dataclass(frozen=True)
class DraftShare:
    """A share tried before its kind declares it, for example::

    DraftShare(
        name="space-program",
        label="Space program share",
        issue=361,
        event_types=("nation.space_program_growth",),
        readings=(ShareReading(Measure.BOOST, actor), ShareReading(Measure.MISSION_CONTROL, actor)),
        scalings=(ScalingSpec(Measure.BOOST, rise=0.2, reason=UNEXAMINED), Scaling.MISSION_CONTROL),
    )

    A reading's measure without a scaling here takes that measure's starting scaling.
    """

    name: str
    """A slug: the prefix of its rows' ids and its key in the state hash."""
    label: str
    issue: int
    """The issue the draft calibrates for."""
    event_types: tuple[str, ...]
    """Existing narrative event types."""
    readings: tuple[ShareReading, ...]
    """Each is a candidate of the rows' shares; the highest scale wins."""
    base: Significance | None = None
    """The hypothetical base level; by default the base of the types' kind."""
    scalings: tuple[Scaling | ScalingSpec, ...] = ()
    """The scaling of each measure its readings read: a shared one, or its own (``ScalingSpec``), unexamined or
    with a reason."""


DRAFT_SHARES: tuple[DraftShare, ...] = ()
"""The declared draft shares; read at call time, so tests patch it."""


def validate_drafts(drafts: Sequence[DraftShare]) -> None:
    """Raises ``DraftShareError`` for the first draft that cannot be scored, naming it."""
    seen: set[str] = set()
    for draft in drafts:
        if not _SLUG.fullmatch(draft.name):
            raise DraftShareError(f"draft share name {draft.name!r} is not a lowercase slug (a-z, 0-9 and -)")
        if draft.name in seen:
            raise DraftShareError(f"draft share name {draft.name!r} is repeated")
        seen.add(draft.name)
        if not draft.event_types:
            raise DraftShareError(f"draft share {draft.name!r} names no event type")
        if not draft.readings:
            raise DraftShareError(f"draft share {draft.name!r} has no reading")
        for event_type in draft.event_types:
            kind = kind_for(event_type)
            if kind is None:
                raise DraftShareError(f"draft share {draft.name!r}: event type {event_type!r} is declared by no kind")
            if not kind.narrative:
                raise DraftShareError(
                    f"draft share {draft.name!r}: event type {event_type!r} is not a narrative event type"
                )
        draft_base(draft)
        draft_scalings(draft)


def draft_scalings(draft: DraftShare) -> dict[Measure, tuple[str, ScalingSpec]]:
    """The name and scaling of each measure the draft's readings read, in reading order: its own scaling is named
    ``<draft>-<measure>``, a shared one by its own name. ``DraftShareError`` for a scaling on a measure no reading
    reads or a measure given two."""
    declared: dict[Measure, tuple[str, ScalingSpec]] = {}
    for item in draft.scalings:
        spec = SCALINGS[item] if isinstance(item, Scaling) else item
        if spec.measure in declared:
            raise DraftShareError(f"draft share {draft.name!r} gives the measure {spec.measure} two scalings")
        name = item.value if isinstance(item, Scaling) else own_scaling_name(draft.name, spec.measure)
        declared[spec.measure] = (name, spec)
    measures = list(dict.fromkeys(reading.measure for reading in draft.readings))
    unread = sorted(set(declared) - set(measures))
    if unread:
        raise DraftShareError(
            f"draft share {draft.name!r} has a scaling on {', '.join(unread)}, which no reading reads"
        )
    return {measure: declared.get(measure) or (measure.value, SCALINGS[Scaling(measure.value)]) for measure in measures}


def own_scaling_name(draft: str, measure: Measure) -> str:
    """The name of a draft's own scaling on ``measure``: never a measure's, a split type's or another draft's."""
    return f"{draft}-{measure.value}"


def draft_base(draft: DraftShare) -> Significance:
    """The draft's base, else the one base its types' kinds share; ``DraftShareError`` when they differ."""
    if draft.base is not None:
        return draft.base
    bases = {kind.base for event_type in draft.event_types if (kind := kind_for(event_type)) is not None}
    if len(bases) != 1:
        levels = ", ".join(sorted(level.value for level in bases))
        raise DraftShareError(f"draft share {draft.name!r} needs a base: its event types' kinds differ ({levels})")
    return next(iter(bases))


def draft_row_id(name: str, event_id: str) -> str:
    return f"{ROW_PREFIX}{name}:{event_id}"


def draft_name(row_id: str) -> str:
    """The draft a row id of ``draft_row_id`` belongs to; ``""`` for any other id."""
    if not row_id.startswith(ROW_PREFIX):
        return ""
    return row_id[len(ROW_PREFIX) :].partition(":")[0]
