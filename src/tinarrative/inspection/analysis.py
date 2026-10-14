"""Assemble an :class:`InspectReport` from a save's bytes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from tinarrative.identity import IdentityReport, analyze_identity
from tinarrative.log import fields, get_logger

from .decode import decode_save, file_facts
from .pointer import resolve_pointer, truncate_value, type_label, value_length
from .report import Diagnostic, InspectReport, KeySummary, PathResult, RenderLimits, Status

ENVELOPE_KEYS = ("currentID", "gamestates")
"""Top-level keys documented in docs/game-data-notes/terra_invicta_json_v1.md."""

logger = get_logger(__name__)


def summarize_children(value: dict[str, Any]) -> tuple[KeySummary, ...]:
    return tuple(KeySummary(key, type_label(item), value_length(item)) for key, item in value.items())


def inspect_bytes(
    data: bytes,
    file_name: str,
    pointers: Sequence[str] = (),
    limits: RenderLimits | None = None,
) -> InspectReport:
    """Produce a deterministic structural report for one save's bytes."""
    if limits is None:
        limits = RenderLimits()
    decoded = decode_save(data)
    facts = file_facts(data, decoded.text)
    diagnostics = list(decoded.diagnostics)

    if not decoded.ok:
        paths = tuple(PathResult(pointer, False, None, None, None, "not evaluated") for pointer in pointers)
        return InspectReport(
            file_name=file_name,
            file=facts,
            status="unsupported_input",
            root_type=None,
            top_level=(),
            second_level={},
            paths=paths,
            diagnostics=tuple(diagnostics),
        )

    root = decoded.value
    identity: IdentityReport | None = None
    top_level: tuple[KeySummary, ...] = ()
    second_level: dict[str, tuple[KeySummary, ...]] = {}
    if isinstance(root, dict):
        top_level = summarize_children(root)
        second_level = {key: summarize_children(item) for key, item in root.items() if isinstance(item, dict)}
        logger.debug(
            "root shape %s",
            fields(root="object", top_level_keys=len(top_level), second_level_objects=len(second_level)),
        )
        for key in ENVELOPE_KEYS:
            if key not in root:
                logger.debug("envelope key missing %s", fields(key=key))
                diagnostics.append(
                    Diagnostic(
                        "missing_key",
                        f"top-level key {key!r} from the documented envelope is absent",
                    )
                )
        identity = analyze_identity(root)
        if identity is None:
            logger.debug("identity census skipped %s", fields(reason="gamestates is not an object"))
        else:
            logger.debug(
                "identity census %s",
                fields(
                    domains=len(identity.domains),
                    types=sum(len(domain.types) for domain in identity.domains),
                    ids=identity.total_ids,
                    shared_ids=identity.ids_shared_across_types,
                    max_id=identity.max_observed_id,
                    current_id=identity.current_id,
                ),
            )
            diagnostics.extend(_identity_diagnostics(identity))
    else:
        logger.debug("root shape %s", fields(root=type_label(root)))
        diagnostics.append(
            Diagnostic(
                "root_not_object",
                f"the JSON root is {type_label(root)}, not an object; the documented envelope has an object root",
            )
        )

    status: Status = "ok"
    results: list[PathResult] = []
    for pointer in pointers:
        lookup = resolve_pointer(root, pointer)
        if lookup.found:
            logger.debug(
                "pointer resolved %s",
                fields(pointer=pointer, type=type_label(lookup.value), length=value_length(lookup.value)),
            )
            results.append(
                PathResult(
                    pointer,
                    True,
                    type_label(lookup.value),
                    value_length(lookup.value),
                    truncate_value(lookup.value, limits),
                    None,
                )
            )
        else:
            logger.debug("pointer unresolved %s", fields(pointer=pointer, code=lookup.code, reason=lookup.reason))
            status = "path_not_found"
            results.append(PathResult(pointer, False, None, None, None, lookup.reason))
            diagnostics.append(Diagnostic(lookup.code or "pointer_not_found", f"{pointer}: {lookup.reason}"))

    return InspectReport(
        file_name=file_name,
        file=facts,
        status=status,
        root_type=type_label(root),
        top_level=top_level,
        second_level=second_level,
        paths=tuple(results),
        diagnostics=tuple(diagnostics),
        identity=identity,
    )


def _identity_diagnostics(identity: IdentityReport) -> list[Diagnostic]:
    findings: list[Diagnostic] = []
    for domain in identity.domains:
        for item in domain.types:
            for code, count, what in (
                ("id_key_mismatch", item.id_mismatches, "entries whose Key.value differs from Value.ID.value"),
                ("id_missing", item.id_missing, "entries without an integer Key.value or Value.ID.value"),
                ("id_duplicate", item.id_duplicates, "repeated Key.value entries"),
            ):
                if count:
                    findings.append(Diagnostic(code, f"{item.state_type}: {count} {what}"))
    if identity.ids_shared_across_types:
        findings.append(
            Diagnostic(
                "id_shared_across_types",
                f"{identity.ids_shared_across_types} IDs occur in more than one state type",
            )
        )
    if identity.current_id is not None and identity.max_observed_id is not None:
        if identity.current_id < identity.max_observed_id:
            findings.append(
                Diagnostic(
                    "current_id_behind",
                    f"currentID {identity.current_id} is below the largest observed ID {identity.max_observed_id}",
                )
            )
    return findings
