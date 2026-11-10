"""The councilor dossier: who is worth an article and the facts about them, independent of the campaign narrative."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from ..analyzers.campaign.notifications import LOG, PREFIX
from ..analyzers.common import ALIEN_FACTION_TEMPLATE, Lookup, Side
from ..analyzers.politics.councilors import DETAINING_FACTION_CHANGED, FACTION_CHANGED, STATUS_CHANGED
from ..analyzers.politics.organizations import COUNCILOR_ORGS_CHANGED
from ..config import CouncilorSettings
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import Event
from ..model.records import NotificationEntry
from ..model.snapshot import EntityState, SaveSnapshot
from ..model.values import FrozenMap, Observed, Unknown, to_jsonable
from .org_catalog import NAMED_ORG_CATEGORIES
from .prominence import organization_shares, total
from .trait_catalog import (
    DETECTION_BONUS,
    EASILY_VISIBLE,
    ESPIONAGE_MODS,
    KEPT_GROUPS,
    LOW_PROFILE,
    TRAITS,
    WITHHELD_GROUPS,
)

CAREER_EVENT_TYPES = frozenset({FACTION_CHANGED, DETAINING_FACTION_CHANGED, STATUS_CHANGED, COUNCILOR_ORGS_CHANGED})
SKILLS = ("Persuasion", "Investigation", "Espionage", "Command", "Administration", "Science", "Security")
"""The councilor attributes a dossier carries; ``Loyalty`` and ``ApparentLoyalty`` are never emitted."""
SKILL_CAP = 25
"""The game's limit on a councilor attribute: personal value and organization bonuses together."""
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
"""The public cause an organization's priority or space bonus stands for, so the article never reads a field name."""
POLICY_MIN = 0.03
"""A cause's summed bonus below this is a token tie of one small organization, not advocacy."""
POLICY_RELATIVE = 0.5
"""A cause below this share of the councilor's strongest one is overshadowed and left out."""
POLICY_STRENGTHS = ((0.10, "leading"), (0.05, "strong"), (0.0, "modest"))
"""The strength of a kept cause by its summed bonus, the first threshold it reaches."""
POLICY_FOCUS = ((1.5, "single-issue"), (2.5, "focused"))
"""The focus by the effective number of causes, the first bound it stays under; anything above is ``broad``."""
_EPSILON = 1e-9
DAYS_PER_YEAR = 365.25
SHARE_DIGITS = 4
"""Significant digits of the organization share in the dossier."""

PUBLIC_MAX = 5
"""The highest concealment of a ``public`` councilor; one above ``PRIVATE_MAX`` is ``shadow``."""
PRIVATE_MAX = 17
LOW_PROFILE_WEIGHT = 3
EASILY_VISIBLE_WEIGHT = 2
"""Multipliers of the detection bonus: a trait of public profile moves the public view more than the game's."""
EASILY_VISIBLE_DEFAULT = -4
"""The weight of an always-revealed trait without a detection bonus of its own."""

GENERATED_ORG_CATEGORIES = {
    "Aerospace": "aerospace",
    "BusinessManagement": "commercial",
    "Commercial": "commercial",
    "Criminal": "criminal",
    "Engineering": "engineering_industry",
    "Influence": "media_influence",
    "InformationTechnology": "technology",
    "Investigations": "security_intelligence",
    "NGO": "ngo",
    "Research": "research",
    "Resource": "mining_resources",
    "Security": "security_intelligence",
    "SpaceMining": "mining_resources",
    "Vigilante": "vigilante",
}
"""Organization category of a generated organization by the word after ``Random`` in its ``templateName``."""
_GENERATED_TEMPLATE = re.compile(r"Random([A-Za-z]+?)\d")

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
"""The public profession of a councilor type, so the article never has to interpret a template name."""
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")

MISSION_OUTCOME_PREFIX = "LogMissionOutcome"
"""Template prefix of the notification log entries that record a resolved mission."""
REGIONS_PER_MISSION = 3
_MARKUP = re.compile(r"<[^>]+>")
_MISSION_TEXT = re.compile(
    r"(?:rolled an? \w+ for the|completed their) (?P<mission>.+?) mission(?: in the (?P<region>.+?) region of )?"
)
"""The two summary phrasings of a resolved mission; an aborted mission has another and is skipped."""


@dataclass(frozen=True)
class _Outcome:
    councilor: EntityId
    date: datetime
    mission: str
    region: str | None


@dataclass(frozen=True)
class _Org:
    org_id: EntityId
    name: str | None
    tier: int
    state: EntityState | None


@dataclass(frozen=True)
class _Candidate:
    state: EntityState
    faction: EntityRef
    tenure_days: int
    org_share: float
    """The summed prominence share of the councilor's organizations."""
    skill_sum: int
    org_skill_sum: int
    xp: int


def build_dossier(
    snapshot: SaveSnapshot,
    player: EntityId | None,
    career: Iterable[Event],
    settings: CouncilorSettings,
    source: str,
    *,
    player_only: bool = False,
    tier_exponent: int,
) -> dict[str, Any]:
    """The selected councilors of ``snapshot`` with the facts an article may use, as a JSON-ready document.

    ``career`` is the event stream of the sequence the snapshot ends (empty for a single save). The dossier may use
    everything in the save; it never carries loyalty. ``tier_exponent`` weighs the organizations' tiers
    (``narrative.significance.tier_exponent``).
    """
    lookup = Lookup(snapshot, snapshot)
    now = _datetime(snapshot.date)
    candidates = _candidates(snapshot, lookup, now, settings, organization_shares(snapshot, tier_exponent))
    by_faction: dict[EntityId, list[_Candidate]] = {}
    for candidate in sorted(candidates, key=_rank_key):
        by_faction.setdefault(candidate.faction.entity_id, []).append(candidate)

    selected: list[_Candidate] = []
    for faction_id, ranked in by_faction.items():
        if faction_id == player:
            selected.extend(ranked)
        elif not player_only:
            selected.extend(ranked[: settings.rivals_per_faction])
    selected.sort(key=lambda item: (item.faction.entity_id != player, _rank_key(item)))

    career = list(career)
    events = _career_by_councilor(career)
    outcomes = _mission_outcomes(career, snapshot, now, settings.missions_window_years)
    ranks = {
        candidate.state.ref.entity_id: place
        for ranked in by_faction.values()
        for place, candidate in enumerate(ranked, start=1)
    }
    return {
        "as_of": to_jsonable(snapshot.date),
        "source": source,
        "player_faction": _faction_name(lookup, player),
        "factions": _faction_templates(snapshot),
        "selection": {
            "player_only": player_only,
            "rivals_per_faction": settings.rivals_per_faction,
            "min_tenure_days": settings.min_tenure_days,
            "missions_per_councilor": settings.missions_per_councilor,
            "missions_window_years": settings.missions_window_years,
            "article_words": settings.article_words,
        },
        "councilors": [
            _entry(snapshot, lookup, item, item.faction.entity_id == player, ranks, now, events, outcomes, settings)
            for item in selected
        ],
    }


def _candidates(
    snapshot: SaveSnapshot,
    lookup: Lookup,
    now: datetime | None,
    settings: CouncilorSettings,
    org_shares: Mapping[EntityId, float],
) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for state in snapshot.councilors:
        faction = state.get("faction")
        if not isinstance(faction, EntityRef) or state.get("archived") is True or state.get("exists") is False:
            continue  # the unemployed pool has no faction; an archived or non-existent councilor has left
        if lookup.faction_kind(faction.entity_id) != "human":
            continue
        recruited = _datetime(state.get("recruitDate"))
        if now is None or recruited is None or (now - recruited).days < settings.min_tenure_days:
            continue
        skills = _skills(state)
        orgs = _orgs(lookup, state)
        candidates.append(
            _Candidate(
                state=state,
                faction=lookup.resolve(faction) or faction,
                tenure_days=(now - recruited).days,
                org_share=total(org_shares, (org.org_id for org in orgs)),
                skill_sum=sum(skills.values()),
                org_skill_sum=sum(_org_skills(orgs, skills).values()),
                xp=_int(state.get("XP")),
            )
        )
    return candidates


def _comparable(share: float) -> float:
    """Equal tier sums reached through different organizations can differ in the last bits of a float sum; the
    rounding keeps them tied, far below the gap between any two distinct sums."""
    return round(share, 12)


def _rank_key(candidate: _Candidate) -> tuple[float, int, int, tuple[str, int, int, str]]:
    return (
        -_comparable(candidate.org_share),
        -candidate.skill_sum,
        -candidate.xp,
        candidate.state.ref.entity_id.sort_key,
    )


def _entry(
    snapshot: SaveSnapshot,
    lookup: Lookup,
    candidate: _Candidate,
    is_player: bool,
    ranks: Mapping[EntityId, int],
    now: datetime | None,
    career: Mapping[EntityId, list[Event]],
    outcomes: Mapping[EntityId, list[_Outcome]],
    settings: CouncilorSettings,
) -> dict[str, Any]:
    state = candidate.state
    councilor_id = state.ref.entity_id
    born = _datetime(state.get("dateBorn"))
    orgs = _orgs(lookup, state)
    skills = _skills(state)
    entry: dict[str, Any] = {
        "id": str(councilor_id),
        "name": state.ref.name,
        "faction": _faction_name(lookup, candidate.faction.entity_id),
        "player": is_player,
        "profession": _profession(state.get("typeTemplateName")),
        "gender": _gender(state.get("gender")),
        "traits": _traits(state.get("traitTemplateNames")),
        "skills": skills,
        "org_skills": _org_skills(orgs, skills),
        "xp": candidate.xp,
        "born": to_jsonable(state.get("dateBorn")),
        "age": None if born is None or now is None else _years(now, born),
        "home": _home(lookup, state),
        "recruited": to_jsonable(state.get("recruitDate")),
        "tenure_years": round(candidate.tenure_days / DAYS_PER_YEAR, 1),
        "orgs": [_org_entry(lookup, org) for org in orgs],
        "policy_influence": _policy_influence(orgs),
        "visibility": _visibility(state.get("traitTemplateNames"), skills, _org_skills(orgs, skills)),
        "prominence": {
            "org_share": float(f"{candidate.org_share:.{SHARE_DIGITS}g}"),
            "skill_sum": candidate.skill_sum,
            "org_skill_sum": candidate.org_skill_sum,
            "rank_in_faction": ranks[councilor_id],
        },
        "career": [_career_entry(event) for event in career.get(councilor_id, [])],
    }
    if is_player:
        entry["missions"] = _missions(outcomes.get(councilor_id, []), now, settings)
    return entry


def _profession(value: Observed) -> str | None:
    """The plain-language profession of a councilor type; an unknown type is its name split into words."""
    if not isinstance(value, str) or not value:
        return None
    return PROFESSIONS.get(value, _CAMEL.sub(" ", value).lower())


def _traits(value: Observed) -> dict[str, list[str]]:
    """Display names of the public traits by group; an uncatalogued template is its name split into words."""
    grouped: dict[str, list[str]] = {}
    for template in value if isinstance(value, tuple) else ():
        if not isinstance(template, str) or not template:
            continue
        group, name = TRAITS.get(template, ("other", _CAMEL.sub(" ", template)))
        if group not in WITHHELD_GROUPS:
            grouped.setdefault(group, []).append(name)
    return {group: grouped[group] for group in (*KEPT_GROUPS, "other") if group in grouped}


def _visibility(value: Observed, skills: Mapping[str, int], org_skills: Mapping[str, int]) -> dict[str, Any]:
    """How visible the councilor is to the public: ``public``, ``private`` or ``shadow``, with its score.

    The score (``concealment``) is the espionage the game detects against plus the traits' detection bonuses, those
    of public profile weighted up. An always-revealed trait is never ``shadow``, a low-profile one never ``public``.
    """
    templates = [item for item in value if isinstance(item, str)] if isinstance(value, tuple) else []
    espionage = skills.get("Espionage", 0) + org_skills.get("Espionage", 0)
    espionage = min(SKILL_CAP, espionage + sum(ESPIONAGE_MODS.get(template, 0) for template in templates))
    concealment = espionage + sum(_visibility_weight(template) for template in templates)
    level = "public" if concealment <= PUBLIC_MAX else "private" if concealment <= PRIVATE_MAX else "shadow"
    if level == "shadow" and EASILY_VISIBLE.intersection(templates):
        level = "private"
    elif level == "public" and LOW_PROFILE.intersection(templates):
        level = "private"
    return {"level": level, "concealment": concealment}


def _visibility_weight(template: str) -> int:
    bonus = DETECTION_BONUS.get(template, 0)
    if template in LOW_PROFILE:
        return bonus * LOW_PROFILE_WEIGHT
    if template in EASILY_VISIBLE:
        return bonus * EASILY_VISIBLE_WEIGHT if bonus else EASILY_VISIBLE_DEFAULT
    return bonus


def _gender(value: Observed) -> str | None:
    """``male`` or ``female``; ``None`` for the save's ``"None"`` and anything else, so the article avoids pronouns."""
    return value.lower() if isinstance(value, str) and value in ("Male", "Female") else None


def _skills(state: EntityState) -> dict[str, int]:
    attributes = state.get("attributes")
    values = dict(attributes.items) if isinstance(attributes, FrozenMap) else {}
    return {
        name: value for name in SKILLS if isinstance(value := values.get(name), int) and not isinstance(value, bool)
    }


def _orgs(lookup: Lookup, state: EntityState) -> list[_Org]:
    members = state.get("orgs")
    found: list[_Org] = []
    for member in members if isinstance(members, tuple) else ():
        if not isinstance(member, EntityRef):
            continue
        org = lookup.state(member.entity_id, Side.AFTER)
        tier = org.get("tier") if org is not None else None
        found.append(
            _Org(
                member.entity_id,
                org.ref.name if org is not None else member.name,
                _int(tier),
                org,
            )
        )
    return found


def _org_skills(orgs: list[_Org], skills: Mapping[str, int]) -> dict[str, int]:
    """The skill bonuses of the councilor's organizations, capped so that ``skills`` plus them never exceed the cap.

    ``attributes`` leaves organization bonuses out, so the two add up.
    """
    found: dict[str, int] = {}
    for name in SKILLS:
        bonus = sum(_int(org.state.get(name.lower())) for org in orgs if org.state is not None)
        capped = min(bonus, max(0, SKILL_CAP - skills.get(name, 0)))
        if capped:
            found[name] = capped
    return found


def _policy_influence(orgs: list[_Org]) -> dict[str, Any]:
    """The causes the councilor's organizations push, strongest summed bonus first, and how focused they are.

    A cause is kept from ``POLICY_MIN`` and from ``POLICY_RELATIVE`` of the strongest. The focus is the effective
    number of causes, (sum)^2 / sum of squares, over all nonzero ones, so the dropped ones still dilute it.
    """
    totals = {
        field: sum(_number(org.state.get(field)) for org in orgs if org.state is not None) for field in POLICY_LABELS
    }
    ranked = sorted((field for field in POLICY_LABELS if totals[field] > 0), key=lambda field: -totals[field])
    top = totals[ranked[0]] if ranked else 0.0
    kept = [
        field
        for field in ranked
        if totals[field] >= POLICY_MIN - _EPSILON and totals[field] >= top * POLICY_RELATIVE - _EPSILON
    ]
    focus = None
    if kept:
        values = [totals[field] for field in ranked]
        effective = sum(values) ** 2 / sum(value * value for value in values)
        focus = next((name for bound, name in POLICY_FOCUS if effective < bound), "broad")
    return {
        "focus": focus,
        "causes": [{"cause": POLICY_LABELS[field], "strength": _policy_strength(totals[field])} for field in kept],
    }


def _policy_strength(value: float) -> str:
    return next(name for floor, name in POLICY_STRENGTHS if value >= floor - _EPSILON)


def _org_entry(lookup: Lookup, org: _Org) -> dict[str, Any]:
    template = org.state.get("templateName") if org.state is not None else None
    origin, category, basis = org_nature(org.state)
    nation = _region_nation(lookup, lookup.resolve(org.state.get("homeRegion"))) if org.state is not None else None
    return {
        "id": str(org.org_id),
        "name": org.name,
        "tier": org.tier,
        "nation": nation.name if nation is not None else None,
        "template": template if isinstance(template, str) else None,
        "origin": origin,
        "category": category,
        "basis": basis,
    }


def org_nature(org: EntityState | None) -> tuple[str, str, str]:
    """``(origin, category, basis)`` of an organization.

    A generated organization (``Random<Category>…`` template) takes its category from the template. A real-world
    organization has a named template: its category comes from the catalog, or from the effects it grants when the
    template is not catalogued.
    """
    template = org.get("templateName") if org is not None else None
    if org is None or not isinstance(template, str):
        return "unknown", "other", "none"
    match = _GENERATED_TEMPLATE.match(template) if template.startswith("Random") else None
    if match:
        return "generated", GENERATED_ORG_CATEGORIES.get(match.group(1), "other"), "template"
    if template in NAMED_ORG_CATEGORIES:
        return "real", NAMED_ORG_CATEGORIES[template], "catalog"
    return "real", _category_from_stats(org), "stats"


def _category_from_stats(org: EntityState) -> str:
    def number(name: str) -> float:
        return _number(org.get(name))

    money = number("incomeMoney_month")
    if number("spoilsBonus") >= 0.02 and money > 0:
        return "criminal"
    if number("spaceflightBonus") > 0 or number("spaceDevBonus") > 0 or number("MCBonus") > 0:
        return "aerospace"
    if number("miningBonus") > 0:
        return "mining_resources"
    if number("incomeResearch_month") > 0 or number("science") >= 2:
        return "research"
    # Intelligence work is espionage and investigation; `security` alone is what commando units carry.
    if number("espionage") + number("investigation") >= 2 or number("oppressionBonus") > 0:
        return "security_intelligence"
    if number("incomeOps_month") > 0 and (number("command") > 0 or number("security") > 0):
        return "military"
    if number("investigation") > 0:
        return "security_intelligence"
    if number("incomeInfluence_month") > 0 and number("administration") < 4:
        return "media_influence"
    if number("governmentBonus") > 0 or number("unityBonus") > 0 or (number("administration") >= 4 and money <= 0):
        return "government"
    if number("welfareBonus") > 0 or number("environmentBonus") > 0:
        return "public_interest"
    if money > 0 or number("economyBonus") > 0:
        return "commercial"
    return "other"


def _home(lookup: Lookup, state: EntityState) -> dict[str, Any]:
    region = lookup.resolve(state.get("homeRegion"))
    return {"region": _named(region), "nation": _named(_region_nation(lookup, region))}


def _region_nation(lookup: Lookup, region: EntityRef | None) -> EntityRef | None:
    region_state = lookup.state(region.entity_id, Side.AFTER) if region is not None else None
    return lookup.resolve(region_state.get("nation")) if region_state is not None else None


def _named(ref: EntityRef | None) -> dict[str, Any] | None:
    return None if ref is None else {"id": str(ref.entity_id), "name": ref.name}


def _faction_name(lookup: Lookup, faction_id: EntityId | None) -> str | None:
    ref = lookup.ref(faction_id) if faction_id is not None else None
    return ref.name if ref is not None else None


def _faction_templates(snapshot: SaveSnapshot) -> dict[str, str]:
    """Each human faction's display name and its ``templateName``, the identity the councilor brief keys stances on."""
    templates: dict[str, str] = {}
    for state in snapshot.factions:
        template = state.get("templateName")
        if state.ref.name is not None and isinstance(template, str) and template != ALIEN_FACTION_TEMPLATE:
            templates[state.ref.name] = template
    return templates


def _mission_outcomes(
    career: list[Event], snapshot: SaveSnapshot, now: datetime | None, window_years: int
) -> dict[EntityId, list[_Outcome]]:
    """The resolved missions of the last ``window_years`` by councilor.

    The log keeps about two months per save, so with several saves each entry is taken once, from the event of the
    interval it appeared in. A single save has no events and gives the entries of its own log.
    """
    found = [outcome for event in career if (outcome := _event_outcome(event)) is not None]
    if not found:
        found = [
            outcome
            for record in snapshot.records
            if record.field == LOG and not isinstance(record.entries, Unknown)
            for entry in record.entries
            if isinstance(entry, NotificationEntry)
            and (outcome := _outcome(entry.template, entry.summary, entry.outcome, entry.subject, entry.date))
            is not None
        ]
    if now is None:
        return {}
    since = now - timedelta(days=window_years * DAYS_PER_YEAR)
    grouped: dict[EntityId, list[_Outcome]] = {}
    for outcome in found:
        if since <= outcome.date <= now:
            grouped.setdefault(outcome.councilor, []).append(outcome)
    return grouped


def _event_outcome(event: Event) -> _Outcome | None:
    if not event.event_type.startswith(PREFIX + MISSION_OUTCOME_PREFIX):
        return None
    attributes = dict(event.attributes)
    subject = event.entities[1] if len(event.entities) > 1 else None
    return _outcome(
        attributes.get("template"), attributes.get("summary"), attributes.get("outcome"), subject, event.date
    )


def _outcome(
    template: Observed, summary: Observed, outcome: Observed, subject: Observed, date: Observed
) -> _Outcome | None:
    """A resolved mission of a councilor, or ``None`` for another entry, an abort, an unattributed or unreadable one."""
    when = _datetime(date)
    if (
        not isinstance(template, str)
        or not template.startswith(MISSION_OUTCOME_PREFIX)
        or outcome == "Aborted"
        or not isinstance(subject, EntityRef)
        or subject.entity_id.domain is not EntityDomain.COUNCILOR
        or not isinstance(summary, str)
        or when is None
    ):
        return None
    match = _MISSION_TEXT.search(_MARKUP.sub("", summary))
    if match is None:
        return None
    return _Outcome(subject.entity_id, when, match.group("mission"), match.group("region"))


def _missions(outcomes: list[_Outcome], now: datetime | None, settings: CouncilorSettings) -> dict[str, Any]:
    """Mission types ranked by frequency, each with its most frequent regions.

    The log shows only part of the mission turns, so the result is a sample of the period; it says so itself.
    """
    by_type: dict[str, Counter[str | None]] = {}
    for outcome in outcomes:
        by_type.setdefault(outcome.mission, Counter())[outcome.region] += 1
    ranked = sorted(by_type.items(), key=lambda item: (-item[1].total(), item[0]))
    types = []
    for mission, regions in ranked[: settings.missions_per_councilor]:
        named = sorted(
            ((name, count) for name, count in regions.items() if name is not None), key=lambda i: (-i[1], i[0])
        )
        types.append(
            {
                "mission": mission,
                "count": regions.total(),
                "regions": [{"name": name, "count": count} for name, count in named[:REGIONS_PER_MISSION]],
            }
        )
    return {
        "sample": True,
        "window_years": settings.missions_window_years,
        "period": {
            "from": min(o.date for o in outcomes).date().isoformat() if outcomes else None,
            "to": None if now is None else now.date().isoformat(),
        },
        "outcomes_seen": len(outcomes),
        "types": types,
    }


def _career_by_councilor(career: Iterable[Event]) -> dict[EntityId, list[Event]]:
    grouped: dict[EntityId, list[Event]] = {}
    for event in career:
        if _is_recruitment(event):
            continue  # recruitment from the unemployed pool is dated by ``recruited``, not by the save that shows it
        if event.event_type in CAREER_EVENT_TYPES and event.entities:
            first = event.entities[0].entity_id
            if first.domain is EntityDomain.COUNCILOR:
                grouped.setdefault(first, []).append(event)
    return grouped


def _is_recruitment(event: Event) -> bool:
    return event.event_type == FACTION_CHANGED and dict(event.attributes).get("transition") == "set"


def _career_entry(event: Event) -> dict[str, Any]:
    return {
        "event": event.id,
        "type": event.event_type,
        "date": to_jsonable(event.date),
        "attributes": {key: to_jsonable(value) for key, value in event.attributes},
    }


def _int(value: Observed) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _number(value: Observed) -> float:
    return value if isinstance(value, int | float) and not isinstance(value, bool) else 0


def _datetime(value: Observed) -> datetime | None:
    if isinstance(value, Unknown) or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _years(now: datetime, then: datetime) -> int:
    return now.year - then.year - ((now.month, now.day) < (then.month, then.day))
