"""The councilor brief: the model-facing rendering of the dossier header and one entry (ADR-0020).

The dossier stays the audit artifact; only the brief omits, rewords or bands what the model reads. No faction name
reaches the brief: the person's faction becomes a stance, career events become plain dated lines, and missions
become activities as the public would see them.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from ..analyzers.politics.councilors import DETAINING_FACTION_CHANGED, FACTION_CHANGED
from ..trait_names import TRAITS

HEADER_KEYS = ("as_of",)
"""The dossier header the brief keeps; ``source``, ``player_faction``, ``factions`` and ``selection`` are audit data."""
AUDIT_KEYS = frozenset({"id", "player", "xp", "prominence"})
"""Entry fields the brief drops."""
VISIBILITY_AUDIT_KEYS = frozenset({"concealment", "easily_visible", "low_profile"})
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

PROFESSIONS = {
    "Activist": "activist",
    "Astronaut": "astronaut",
    "Attorney": "attorney",
    "Celebrity": "celebrity",
    "Commando": "special forces officer",
    "Diplomat": "diplomat",
    "Engineer": "engineer",
    "Evangelist": "preacher",
    "Executive": "corporate executive",
    "Fixer": "political operator",
    "Hacker": "computer security specialist",
    "Inspector": "police inspector",
    "Investigator": "private investigator",
    "Journalist": "journalist",
    "Judge": "judge",
    "Kingpin": "crime boss",
    "Officer": "military officer",
    "Operative": "security contractor",
    "Politician": "politician",
    "Professor": "professor",
    "Rebel": "insurgent leader",
    "Scientist": "scientist",
    "Spy": "intelligence officer",
    "TechMogul": "technology entrepreneur",
    "Tycoon": "business magnate",
}
POLICY_LABELS = {
    "economyBonus": "economic growth",
    "welfareBonus": "welfare spending",
    "knowledgeBonus": "education and research",
    "governmentBonus": "government reform",
    "unityBonus": "national unity",
    "militaryBonus": "military strength",
    "oppressionBonus": "law and order",
    "environmentBonus": "environmental protection",
    "spoilsBonus": "patronage",
    "miningBonus": "space mining",
    "spaceDevBonus": "space program development",
    "spaceflightBonus": "launch capacity",
    "MCBonus": "spaceflight ground control",
}
POLICY_STRENGTHS = ((0.10, "leading"), (0.05, "strong"), (0.0, "modest"))
POLICY_FOCUS = ((1.5, "single-issue"), (2.5, "focused"))
NATION = "nation"
REGION = "region"
_MISSION_PHRASE_ROWS: tuple[tuple[tuple[str, ...], str, str, str], ...] = (
    # Seen in the logs, keyed by their log wording; the game's other names follow where they differ.
    (("Advise",), "advising the government", "of", NATION),
    (("Public Campaign", "Propaganda"), "public campaigning", "in", NATION),
    (("Stabilize Nation", "Stabilize"), "working to calm unrest", "in", NATION),
    (("Control Nation", "GainInfluence"), "lobbying at the highest levels of government", "in", NATION),
    (("Set National Policy", "SetNationalPolicy"), "steering national policy", "in", NATION),
    (("Defend Interests", "DefendInterests"), "shoring up officials and institutions under pressure", "in", NATION),
    (("Crackdown",), "pressing investigations and scandals against sitting officials", "in", REGION),
    (("Purge",), "pushing for changes of leadership in government posts", "in", REGION),
    (
        ("Investigate Councilor", "InvestigateCouncilor"),
        "looking into the affairs of other public figures",
        "in",
        REGION,
    ),
    (
        ("Inspire", "Inspire Councilor"),
        "holding long discussions of principle with like-minded public figures",
        "in",
        REGION,
    ),
    (("Hostile Takeover", "HostileTakeover"), "buying up control of organizations", "in", REGION),
    (("Turn Councilor", "Turn"), "holding private meetings with public figures of differing views", "in", REGION),
    (("Detain Councilor", "Detain"), "pressing for the arrest of other public figures", "in", REGION),
    (("Extract Councilor", "Extract"), "securing the release of detained public figures", "in", REGION),
    (("Increase Unrest", "Unrest"), "stirring public discontent", "in", REGION),
    (("Assassinate", "Assassinate Councilor"), "being nearby when prominent figures died suddenly", "in", REGION),
    (("Go To Ground", "GoToGround"), "dropping out of public view", "in", REGION),
    (("Surveil Location", "DetectCouncilActivity"), "staying on for unexplained lengths of time", "in", REGION),
    (
        ("Investigate Alien Activity", "InvestigateAlienActivity"),
        "looking into reports of alien activity",
        "in",
        REGION,
    ),
    (("Assault Alien Asset", "AssaultAlienAsset"), "leading armed operations against alien sites", "in", REGION),
    (("Contact", "Contact Councilor"), "holding unexplained private meetings", "in", REGION),
    # Not seen yet: the log wording is unknown, so both of the game's names are keys.
    (("Coup d'Etat", "Coup"), "backing a sudden seizure of power", "in", NATION),
    (("Protect Councilor", "Protect"), "guarding other public figures", "in", REGION),
    (
        ("Sabotage Facilities", "SabotageFacilities"),
        "being present around incidents at launch and control facilities",
        "in",
        REGION,
    ),
    (
        ("Sabotage Hab Module", "SabotageHabModule"),
        "being present around accidents aboard space stations",
        "in",
        REGION,
    ),
    (
        ("Sabotage Project", "SabotageProject"),
        "being around private labs when their research suffered setbacks",
        "in",
        REGION,
    ),
    (("Steal Project", "StealProject"), "snooping around private research labs", "in", REGION),
    (("Control Space Asset", "ControlSpaceAsset"), "lobbying the crews of spacecraft and stations", "in", REGION),
    (("Seize Space Asset", "SeizeSpaceAsset"), "leading boarding operations in space", "in", REGION),
    (("Orbit",), "travelling to orbit", "from", REGION),
    (("Deorbit",), "returning from orbit to Earth", "near", REGION),
    (("Transfer",), "travelling in space", "from", REGION),
    # Alien missions, which Protectorate and Servant councilors can come to run.
    (("Abductions",), "being present in areas struck by mass disappearances", "in", REGION),
    (("Enthrall Elites", "EnthrallElites"), "gaining an unusual hold over officials", "in", REGION),
    (("Enthrall Unaligned Elites", "EnthrallUnalignedElites"), "gaining an unusual hold over officials", "in", NATION),
    (("Enthrall Org", "EnthrallOrg"), "gaining unusual sway over organizations", "in", REGION),
    (("Enthrall Public", "EnthrallPublic"), "drawing an unusually devoted public following", "in", REGION),
    (("Xenoform",), "being present where unfamiliar plant life spread", "in", REGION),
    (("Terrorize Region", "TerrorizeRegion"), "being present during waves of fear and violence", "in", REGION),
    (
        ("Pass Technology", "PassTechnology"),
        "sharing unexplained technical knowledge with other public figures",
        "in",
        REGION,
    ),
    (
        ("Grant Alien Control", "AssumeControl"),
        "brokering the handover of government authority to the visitors",
        "in",
        NATION,
    ),
    (("Build Facility", "BuildFacility"), "overseeing construction of an alien installation", "in", REGION),
    (("Dominate Nation", "DominateNation"), "tightening an unusual grip on the government", "of", NATION),
)
MISSION_PHRASES: dict[str, tuple[str, str, str]] = {
    name: (phrase, preposition, scope) for names, phrase, preposition, scope in _MISSION_PHRASE_ROWS for name in names
}
"""What the public would see of a mission type, by its name in the log: a phrase, the preposition before its place,
and whether the place is the nation or the region.

The game's mission template table (https://wiki.hoodedhorse.com/Terra_Invicta/TIMissionTemplate_CSV) lists every
type; the victory missions have no phrase. A phrase names the visible means, never the game's verb for a covert act,
and holds for a success, the only outcome the dossier counts. A type without a phrase never reaches the brief.
"""
PUBLIC_MAX = 5
PRIVATE_MAX = 17
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")


def councilor_brief(dossier: Mapping[str, Any], entry: Mapping[str, Any]) -> dict[str, Any]:
    """The header and ``entry`` without audit fields or faction names, in public wording."""
    current = stance_of(dossier, entry.get("faction"))
    councilor: dict[str, Any] = {}
    for key, value in entry.items():
        if key in AUDIT_KEYS:
            continue
        if key == "faction":
            if current is not None:
                councilor["stance"] = current
            continue
        if key == "profession":
            value = _profession(value)
        elif key == "traits" and isinstance(value, Mapping):
            value = _traits(value)
        elif key == "policy_influence" and isinstance(value, Mapping):
            value = _policy_influence(value)
        elif key == "missions":
            activities = _activities(value) if isinstance(value, Mapping) else []
            if activities:
                councilor["activities"] = activities
            continue
        if key == "visibility" and isinstance(value, Mapping):
            value = _visibility(value)
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


def _profession(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return PROFESSIONS.get(value, _CAMEL.sub(" ", value).lower())


def _traits(value: Mapping[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for group, templates in value.items():
        if not isinstance(group, str) or not isinstance(templates, list):
            continue
        names = [
            TRAITS.get(template, (group, _CAMEL.sub(" ", template)))[1]
            for template in templates
            if isinstance(template, str)
        ]
        if names:
            result[group] = names
    return result


def _policy_influence(value: Mapping[str, Any]) -> dict[str, Any]:
    effective = value.get("effective_causes")
    focus = None
    causes = value.get("causes")
    if isinstance(causes, list) and causes and isinstance(effective, (int, float)) and not isinstance(effective, bool):
        focus = next((name for bound, name in POLICY_FOCUS if effective < bound), "broad")
    return {
        "focus": focus,
        "causes": [
            {"cause": POLICY_LABELS.get(cause["field"], cause["field"]), "strength": _policy_strength(cause["bonus"])}
            for cause in causes
            if isinstance(cause, Mapping)
            and isinstance(cause.get("field"), str)
            and isinstance(cause.get("bonus"), (int, float))
        ]
        if isinstance(causes, list)
        else [],
    }


def _activities(missions: Mapping[str, Any]) -> list[str]:
    """The phrased mission types in rank order, each with its places; a type seen once only when it stands alone."""
    phrased = [
        (MISSION_PHRASES[item["mission"]], item)
        for item in missions.get("types", ())
        if isinstance(item, Mapping) and isinstance(item.get("mission"), str) and item["mission"] in MISSION_PHRASES
    ]
    if len(phrased) > 1:
        phrased = [(phrase, item) for phrase, item in phrased if item.get("count") != 1]
    return [_activity(phrase, preposition, _places(item, scope)) for (phrase, preposition, scope), item in phrased]


def _places(item: Mapping[str, Any], scope: str) -> list[str]:
    places: list[str] = []
    for place in item.get("nations" if scope == NATION else "regions", ()):
        if not isinstance(place, Mapping) or not isinstance(place.get("name"), str):
            continue
        nation = place.get("nation")
        places.append(f"{place['name']}, {nation}" if isinstance(nation, str) else place["name"])
    return places


def _activity(phrase: str, preposition: str, places: list[str]) -> str:
    if not places:
        return phrase
    separator = "; " if any("," in place for place in places) else ", "
    joined = places[0] if len(places) == 1 else f"{separator.join(places[:-1])} and {places[-1]}"
    return f"{phrase} {preposition} {joined}"


def _policy_strength(value: int | float) -> str:
    return next(name for floor, name in POLICY_STRENGTHS if value >= floor - 1e-9)


def _visibility(value: Mapping[str, Any]) -> dict[str, str]:
    concealment = value.get("concealment")
    level = None
    if isinstance(concealment, int) and not isinstance(concealment, bool):
        level = "public" if concealment <= PUBLIC_MAX else "private" if concealment <= PRIVATE_MAX else "shadow"
        if level == "shadow" and value.get("easily_visible") is True:
            level = "private"
        elif level == "public" and value.get("low_profile") is True:
            level = "private"
    return {"level": level} if level is not None else {}


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
