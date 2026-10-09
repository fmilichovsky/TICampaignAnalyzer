"""Turn a validated ``RawSave`` into a ``SaveSnapshot``.

Only fields observed in ``docs/game-data-notes/domain-field-map.md`` are copied; a listed field that the
save omits is ``Unknown``, fields the save adds are ignored, and no ownership or cause is inferred.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..identity import STATE_PREFIX, read_id_value
from ..model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from ..model.evidence import SourceLocation
from ..model.snapshot import CampaignMetadata, EntityState, SaveSnapshot
from ..model.values import FieldValue, Observed, Unknown, UnknownReason, freeze
from .containers import StateEntry, decode_state_map, entry_path
from .fields import ENTITY_FIELDS, NORMALIZED_DOMAINS, REFERENCE_FIELDS
from .raw_save import RawSave
from .references import ReferenceIndex

_DATE_COMPONENTS = ("year", "month", "day", "hour", "minute", "second")


def _observed(value: dict[str, Any], name: str) -> Observed:
    return freeze(value[name]) if name in value else Unknown()


def _single_entry(gamestates: dict[str, Any], short_type: str) -> dict[str, Any]:
    """The ``Value`` of a singleton state (metadata, time); ``{}`` when absent."""
    entries = decode_state_map(gamestates, short_type)
    return entries[0].value if entries else {}


def game_datetime(components: Any) -> datetime | None:
    """Build a naive game-calendar datetime from the componentized ``currentDateTime`` object."""
    if not isinstance(components, dict):
        return None
    try:
        parts: list[Any] = [components[name] for name in _DATE_COMPONENTS]
        millisecond: Any = components.get("millisecond", 0)
        if any(isinstance(part, bool) or not isinstance(part, int) for part in [*parts, millisecond]):
            return None
        year, month, day, hour, minute, second = (int(part) for part in parts)
        return datetime(year, month, day, hour, minute, second, int(millisecond) * 1000)
    except (KeyError, TypeError, ValueError):
        return None


def _entity_state(
    domain: EntityDomain, short_type: str, entry: StateEntry, index: ReferenceIndex, source: str
) -> EntityState:
    references = REFERENCE_FIELDS.get(short_type, {})
    fields: list[tuple[str, Observed]] = []
    for name in ENTITY_FIELDS[short_type]:
        if name not in entry.value:
            fields.append((name, Unknown()))
            continue
        raw = entry.value[name]
        if name in references:
            target, is_list = references[name]
            fields.append((name, index.resolve_list(raw, target) if is_list else index.resolve(raw, target)))
        else:
            fields.append((name, freeze(raw)))
    display_name = entry.value.get("displayName")
    ref = EntityRef(
        EntityId(domain, str(entry.map_id)),
        IdentityConfidence.IN_SAVE_ID,
        state_type=short_type,
        name=display_name if isinstance(display_name, str) else None,
    )
    location = SourceLocation(source, short_type, entry.map_id, entry_path(STATE_PREFIX + short_type, entry.index))
    return EntityState(ref=ref, fields=tuple(fields), location=location)


def normalize(raw_save: RawSave) -> SaveSnapshot:
    """Normalize campaign time, metadata, factions, nations, regions, and control points."""
    gamestates: dict[str, Any] = raw_save.root["gamestates"]
    index = ReferenceIndex.from_gamestates(gamestates)

    time_state = _single_entry(gamestates, "TITimeState")
    metadata_state = _single_entry(gamestates, "TIMetadataState")

    timestamp: datetime | None = None
    date: Observed
    if "currentDateTime" not in time_state:
        date = Unknown()
    else:
        timestamp = game_datetime(time_state["currentDateTime"])
        date = (
            timestamp.isoformat()
            if timestamp
            else Unknown(UnknownReason.UNPARSEABLE, freeze(time_state["currentDateTime"]))
        )

    campaign = CampaignMetadata(
        player_faction_name=_observed(metadata_state, "playerFactionName"),
        difficulty=_observed(metadata_state, "difficulty"),
        played_with_mods=_observed(metadata_state, "playedWithMods"),
        game_time_string=_observed(metadata_state, "gameTimeString"),
        scenario_master_template=_observed(time_state, "masterMetaTemplateName"),
        scenario_template=_observed(time_state, "scenarioMetaTemplateName"),
    )

    collections: dict[str, tuple[EntityState, ...]] = {}
    for domain, short_type, attribute in NORMALIZED_DOMAINS:
        entries = decode_state_map(gamestates, short_type)
        collections[attribute] = tuple(
            _entity_state(domain, short_type, entry, index, raw_save.source) for entry in entries
        )

    raw_metadata: tuple[tuple[str, FieldValue], ...] = (
        ("current_id", read_id_value(raw_save.root.get("currentID"))),
        ("state_types", tuple(sorted(gamestates))),
    )
    return SaveSnapshot(
        source=raw_save.source,
        date=date,
        game_version=raw_save.game_version,
        timestamp=timestamp,
        campaign_day=_observed(time_state, "daysInCampaign"),
        campaign_quarter=_observed(time_state, "currentQuarterSinceStart"),
        campaign=campaign,
        raw_metadata=raw_metadata,
        **collections,
    )
