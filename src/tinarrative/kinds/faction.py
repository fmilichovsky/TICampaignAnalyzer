"""A faction's resource ledger (``TIFactionState.Transactions``) as dated mission and operation charges."""

from __future__ import annotations

from ..model.events import Event, Significance
from ..model.kinds import EventKind, EvidenceRole
from .text import attribute_label, attribute_text, subject_label


def _transaction_recorded(event: Event) -> str:
    """The label is a mission or operation template name read from the ledger, never a reading of what it did."""
    return (
        f"{subject_label(event)} ledger records a {attribute_text(event, 'label')} charge: "
        f"{attribute_label(event, 'amount')} {attribute_text(event, 'resource')} "
        f"(dated {attribute_text(event, 'recorded_on')})"
    )


TRANSACTION_RECORDED = EventKind(
    "faction.transaction_recorded",
    _transaction_recorded,
    Significance.MINOR,
    EvidenceRole.EVIDENCE,
    required=frozenset({"label", "resource", "amount", "recorded_on"}),
)
"""Corroboration and dating for an effect evidenced elsewhere, never a narrative event on its own (ADR-0010)."""

KINDS = (TRANSACTION_RECORDED,)
