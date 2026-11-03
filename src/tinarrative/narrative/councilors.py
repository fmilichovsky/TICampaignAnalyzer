"""The councilor dossier: who is worth an article and the facts about them, independent of the campaign narrative."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..analyzers.common import Lookup, Side
from ..analyzers.politics.councilors import DETAINING_FACTION_CHANGED, FACTION_CHANGED, STATUS_CHANGED
from ..analyzers.politics.organizations import COUNCILOR_ORGS_CHANGED
from ..config import CouncilorSettings
from ..model.entities import EntityDomain, EntityId, EntityRef
from ..model.events import Event
from ..model.snapshot import EntityState, SaveSnapshot
from ..model.values import FrozenMap, Observed, Unknown, to_jsonable
from .org_catalog import NAMED_ORG_CATEGORIES

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

    events = _career_by_councilor(career)
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
            "article_words": settings.article_words,
        },
        "councilors": [
            _entry(snapshot, lookup, item, item.faction.entity_id == player, ranks, now, events, settings)
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
    settings: CouncilorSettings,
) -> dict[str, Any]:
    state = candidate.state
    councilor_id = state.ref.entity_id
    born = _datetime(state.get("dateBorn"))
    traits = state.get("traitTemplateNames")
    orgs = _orgs(lookup, state)
    entry: dict[str, Any] = {
        "id": str(councilor_id),
        "name": state.ref.name,
        "faction": _faction_name(lookup, candidate.faction.entity_id),
        "player": is_player,
        "career_type": to_jsonable(state.get("typeTemplateName")),
        "traits": to_jsonable(traits) if isinstance(traits, tuple) else [],
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
        entry["missions"] = _missions(snapshot, lookup, councilor_id, settings.missions_per_councilor)
    return entry


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


def _missions(snapshot: SaveSnapshot, lookup: Lookup, councilor_id: EntityId, limit: int) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, EntityId | None]] = Counter()
    targets: dict[EntityId, EntityRef] = {}
    for mission in snapshot.missions:
        owner = mission.get("councilor")
        if not isinstance(owner, EntityRef) or owner.entity_id != councilor_id:
            continue
        template = mission.get("templateName")
        target = lookup.resolve(mission.get("target"))
        counts[
            (template if isinstance(template, str) else "unknown", None if target is None else target.entity_id)
        ] += 1
        if target is not None:
            targets[target.entity_id] = target
    ordered = sorted(
        counts.items(), key=lambda item: (-item[1], item[0][0], "" if item[0][1] is None else str(item[0][1]))
    )
    return [
        {"mission": template, "target": _named(targets.get(target_id)) if target_id else None, "count": count}
        for (template, target_id), count in ordered[:limit]
    ]


def _career_by_councilor(career: Iterable[Event]) -> dict[EntityId, list[Event]]:
    grouped: dict[EntityId, list[Event]] = {}
    for event in career:
        if event.event_type in CAREER_EVENT_TYPES and event.entities:
            first = event.entities[0].entity_id
            if first.domain is EntityDomain.COUNCILOR:
                grouped.setdefault(first, []).append(event)
    return grouped


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
