"""The councilor brief: the model-facing rendering of the dossier header and one entry (ADR-0020).

The dossier stays the audit artifact; only the brief omits, rewords or bands what the model reads. No faction name
reaches the brief: the person's faction becomes a stance, and career events become plain dated lines.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..analyzers.politics.councilors import DETAINING_FACTION_CHANGED, FACTION_CHANGED

HEADER_KEYS = ("as_of",)
"""The dossier header the brief keeps; ``source``, ``player_faction``, ``factions`` and ``selection`` are audit data."""
AUDIT_KEYS = frozenset({"id", "player", "xp", "prominence"})
"""Entry fields the brief drops."""
VISIBILITY_AUDIT_KEYS = frozenset({"concealment"})
ORG_AUDIT_KEYS = frozenset({"id", "template", "basis"})
NAMED_AUDIT_KEYS = frozenset({"id"})
"""Dropped from the named references of ``home``."""

STANCES = {
    "ResistCouncil": "defence-minded",
    "DestroyCouncil": "hard-line",
    "CooperateCouncil": "pro-contact",
    "ExploitCouncil": "opportunist",
    "EscapeCouncil": "emigrationist",
    "AppeaseCouncil": "accommodationist",
    "SubmitCouncil": "devotional",
}
"""The public stance of each human faction by ``templateName``; the councilor prompt's Stances section explains each."""

DETENTION_LINES = {"set": "detained", "cleared": "released", "changed": "transferred to other captors"}
"""A detention milestone by its transition; the captor is never named."""


def councilor_brief(dossier: Mapping[str, Any], entry: Mapping[str, Any]) -> dict[str, Any]:
    """The header and ``entry`` without audit fields or faction names; every other value is the dossier's own."""
    current = stance_of(dossier, entry.get("faction"))
    councilor: dict[str, Any] = {}
    for key, value in entry.items():
        if key in AUDIT_KEYS:
            continue
        if key == "faction":
            if current is not None:
                councilor["stance"] = current
            continue
        if key == "visibility" and isinstance(value, Mapping):
            value = _without(value, VISIBILITY_AUDIT_KEYS)
        elif key == "orgs" and isinstance(value, list):
            value = [_without(org, ORG_AUDIT_KEYS) if isinstance(org, Mapping) else org for org in value]
        elif key == "career" and isinstance(value, list):
            items = [item for item in value if isinstance(item, Mapping)]
            former = _former_stances(dossier, items, current)
            if former:
                councilor["former_stances"] = former
            value = [line for item in items if (line := _career_line(dossier, item)) is not None]
        elif key == "home" and isinstance(value, Mapping):
            value = {
                name: _without(ref, NAMED_AUDIT_KEYS) if isinstance(ref, Mapping) else ref
                for name, ref in value.items()
            }
        councilor[key] = value
    return {**{key: dossier.get(key) for key in HEADER_KEYS}, "councilor": councilor}


def stance_of(dossier: Mapping[str, Any], faction: object) -> str | None:
    """The stance of the faction named ``faction`` (a name or a dossier reference); ``None`` when unknown."""
    name = faction.get("name") if isinstance(faction, Mapping) else faction
    templates = dossier.get("factions")
    if not isinstance(name, str) or not isinstance(templates, Mapping):
        return None
    template = templates.get(name)
    return STANCES.get(template) if isinstance(template, str) else None


def _former_stances(dossier: Mapping[str, Any], career: list[Mapping[str, Any]], current: str | None) -> list[str]:
    former: list[str] = []
    for item in career:
        if item.get("type") != FACTION_CHANGED:
            continue
        stance = stance_of(dossier, _attributes(item).get("before"))
        if stance is not None and stance != current and stance not in former:
            former.append(stance)
    return former


def _career_line(dossier: Mapping[str, Any], item: Mapping[str, Any]) -> str | None:
    """A milestone as one plain line, or ``None`` for one the brief leaves out (status and organization changes)."""
    attributes = _attributes(item)
    transition = attributes.get("transition")
    text: str | None = None
    if item.get("type") == FACTION_CHANGED:
        if transition == "cleared":
            text = "withdrew from public life"
        elif transition == "changed":
            before = stance_of(dossier, attributes.get("before"))
            after = stance_of(dossier, attributes.get("after"))
            if before is not None and after is not None:
                text = f"changed stance from {before} to {after}"
            elif after is not None:
                text = f"took up {_article(after)} {after} stance"
            elif before is not None:
                text = f"gave up {_article(before)} {before} stance"
            else:
                text = "changed stance"
    elif item.get("type") == DETAINING_FACTION_CHANGED and isinstance(transition, str):
        text = DETENTION_LINES.get(transition)
    if text is None:
        return None
    date = item.get("date")
    return f"{date[:10]}: {text}" if isinstance(date, str) else text


def _attributes(item: Mapping[str, Any]) -> Mapping[str, Any]:
    attributes = item.get("attributes")
    return attributes if isinstance(attributes, Mapping) else {}


def _article(word: str) -> str:
    return "an" if word[0] in "aeiou" else "a"


def _without(mapping: Mapping[str, Any], keys: frozenset[str]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if key not in keys}
