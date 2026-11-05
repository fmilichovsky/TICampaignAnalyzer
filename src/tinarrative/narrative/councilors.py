"""The councilor dossier: who is worth an article and the facts about them, independent of the campaign narrative."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from ..analyzers.campaign.notifications import LOG, PREFIX
from ..analyzers.common import Lookup, Side
from ..analyzers.politics.councilors import DETAINING_FACTION_CHANGED, FACTION_CHANGED, STATUS_CHANGED
from ..analyzers.politics.organizations import COUNCILOR_ORGS_CHANGED
from ..config import CouncilorSettings
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import Event
from ..model.records import NotificationEntry
from ..model.snapshot import EntityState, SaveSnapshot
from ..model.values import FrozenMap, Observed, Unknown, to_jsonable
from .org_catalog import NAMED_ORG_CATEGORIES
from .trait_catalog import KEPT_GROUPS, TRAITS, WITHHELD_GROUPS

CAREER_EVENT_TYPES = frozenset({FACTION_CHANGED, DETAINING_FACTION_CHANGED, STATUS_CHANGED, COUNCILOR_ORGS_CHANGED})
SKILLS = ("Persuasion", "Investigation", "Espionage", "Command", "Administration", "Science", "Security")
"""The councilor attributes a dossier carries; ``Loyalty`` and ``ApparentLoyalty`` are never emitted."""
DAYS_PER_YEAR = 365.25

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
class _Candidate:
    state: EntityState
    faction: EntityRef
    tenure_days: int
    org_tier2: int
    skill_sum: int
    xp: int


def build_dossier(
    snapshot: SaveSnapshot,
    player: EntityId | None,
    career: Iterable[Event],
    settings: CouncilorSettings,
    source: str,
    *,
    player_only: bool = False,
) -> dict[str, Any]:
    """The selected councilors of ``snapshot`` with the facts an article may use, as a JSON-ready document.

    ``career`` is the event stream of the sequence the snapshot ends (empty for a single save). The dossier may use
    everything in the save; it never carries loyalty.
    """
    lookup = Lookup(snapshot, snapshot)
    now = _datetime(snapshot.date)
    candidates = _candidates(snapshot, lookup, now, settings)
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
    snapshot: SaveSnapshot, lookup: Lookup, now: datetime | None, settings: CouncilorSettings
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
        xp = state.get("XP")
        candidates.append(
            _Candidate(
                state=state,
                faction=lookup.resolve(faction) or faction,
                tenure_days=(now - recruited).days,
                # TODO(#197): use the organization prominence share once it exists.
                org_tier2=sum(tier * tier for _, _, tier in _orgs(lookup, state)),
                skill_sum=sum(skills.values()),
                xp=xp if isinstance(xp, int) and not isinstance(xp, bool) else 0,
            )
        )
    return candidates


def _rank_key(candidate: _Candidate) -> tuple[int, int, int, tuple[str, int, int, str]]:
    return (-candidate.org_tier2, -candidate.skill_sum, -candidate.xp, candidate.state.ref.entity_id.sort_key)


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
    entry: dict[str, Any] = {
        "id": str(councilor_id),
        "name": state.ref.name,
        "faction": _faction_name(lookup, candidate.faction.entity_id),
        "player": is_player,
        "profession": _profession(state.get("typeTemplateName")),
        "gender": _gender(state.get("gender")),
        "traits": _traits(state.get("traitTemplateNames")),
        "skills": _skills(state),
        "xp": candidate.xp,
        "born": to_jsonable(state.get("dateBorn")),
        "age": None if born is None or now is None else _years(now, born),
        "home": _home(lookup, state),
        "recruited": to_jsonable(state.get("recruitDate")),
        "tenure_years": round(candidate.tenure_days / DAYS_PER_YEAR, 1),
        "orgs": [_org_entry(lookup, org_id, name, tier) for org_id, name, tier in orgs],
        "prominence": {
            "org_tier2": candidate.org_tier2,
            "skill_sum": candidate.skill_sum,
            "rank_in_faction": ranks[councilor_id],
        },
        "career": [_career_entry(event) for event in career.get(councilor_id, [])],
    }
    if is_player:
        entry["missions"] = _missions(outcomes.get(councilor_id, []), now, settings)
        entry["active_mission"] = _active_mission(lookup, state)
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


def _gender(value: Observed) -> str | None:
    """``male`` or ``female``; ``None`` for the save's ``"None"`` and anything else, so the article avoids pronouns."""
    return value.lower() if isinstance(value, str) and value in ("Male", "Female") else None


def _skills(state: EntityState) -> dict[str, int]:
    attributes = state.get("attributes")
    values = dict(attributes.items) if isinstance(attributes, FrozenMap) else {}
    return {
        name: value for name in SKILLS if isinstance(value := values.get(name), int) and not isinstance(value, bool)
    }


def _orgs(lookup: Lookup, state: EntityState) -> list[tuple[EntityId, str | None, int]]:
    members = state.get("orgs")
    found: list[tuple[EntityId, str | None, int]] = []
    for member in members if isinstance(members, tuple) else ():
        if not isinstance(member, EntityRef):
            continue
        org = lookup.state(member.entity_id, Side.AFTER)
        tier = org.get("tier") if org is not None else None
        found.append(
            (
                member.entity_id,
                org.ref.name if org is not None else member.name,
                tier if isinstance(tier, int) and not isinstance(tier, bool) else 0,
            )
        )
    return found


def _org_entry(lookup: Lookup, org_id: EntityId, name: str | None, tier: int) -> dict[str, Any]:
    org = lookup.state(org_id, Side.AFTER)
    template = org.get("templateName") if org is not None else None
    origin, category, basis = org_nature(org)
    return {
        "id": str(org_id),
        "name": name,
        "tier": tier,
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
        value = org.get(name)
        return value if isinstance(value, int | float) and not isinstance(value, bool) else 0

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
    nation: EntityRef | None = None
    if region is not None:
        region_state = lookup.state(region.entity_id, Side.AFTER)
        nation = lookup.resolve(region_state.get("nation")) if region_state is not None else None
    return {"region": _named(region), "nation": _named(nation)}


def _named(ref: EntityRef | None) -> dict[str, Any] | None:
    return None if ref is None else {"id": str(ref.entity_id), "name": ref.name}


def _faction_name(lookup: Lookup, faction_id: EntityId | None) -> str | None:
    ref = lookup.ref(faction_id) if faction_id is not None else None
    return ref.name if ref is not None else None


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


def _active_mission(lookup: Lookup, state: EntityState) -> dict[str, Any] | None:
    """The mission the councilor is on now; the only use of ``TIMissionState``, whose other entries are leftovers."""
    reference = state.get("activeMission")
    mission = lookup.state(reference.entity_id, Side.AFTER) if isinstance(reference, EntityRef) else None
    if mission is None:
        return None
    template = mission.get("templateName")
    target = lookup.resolve(mission.get("target"))
    return {"mission": template if isinstance(template, str) else None, "target": _named(target)}


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


def _datetime(value: Observed) -> datetime | None:
    if isinstance(value, Unknown) or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _years(now: datetime, then: datetime) -> int:
    return now.year - then.year - ((now.month, now.day) < (then.month, then.day))
