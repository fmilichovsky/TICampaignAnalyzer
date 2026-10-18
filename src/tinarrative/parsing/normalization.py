"""Turn a validated ``RawSave`` into a ``SaveSnapshot``.

Only fields observed in ``docs/game-data-notes/domain-field-map.md`` are copied; a listed field that the
save omits is ``Unknown``, fields the save adds are not copied, and no ownership or cause is inferred. A list
field in ``KEYED_LIST_FIELDS`` (faction ``shipDesigns``) is copied as a map keyed by a member of its elements.
Save-carried records (dated logs and cumulative counters listed in ``RECORD_FIELDS``) are decoded by
:mod:`tinarrative.parsing.records` into ``SaveSnapshot.records`` next to the entity collections.
A reference to an ID absent from the save (for example a fleet's ``parentFleet`` after a merge) stays an
unresolved ``Unknown`` carrying the raw ID, so fleet-ID lifetime limits remain visible downstream.

Nothing is ignored silently: every structure the schema does not describe (an unlisted field, an unknown
state type, an unexpected shape or reference target) is reported through an
:class:`~tinarrative.parsing.unknowns.UnknownCollector` as a content-free finding, without changing the
snapshot. See ``docs/game-data-notes/unknowns/README.md``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ..identity import STATE_PREFIX, read_id_value
from ..log import fields as log_fields
from ..log import get_logger, shape
from ..model.entities import EntityDomain, EntityId, EntityRef, IdentityConfidence
from ..model.evidence import SourceLocation
from ..model.records import RecordSet, record_counts
from ..model.snapshot import CampaignMetadata, EntityState, ResearchState, SaveSnapshot
from ..model.values import FieldValue, FrozenMap, Observed, Unknown, UnknownReason, freeze
from .containers import StateEntry, decode_pair_map, decode_state_map, entry_path
from .dates import COMPONENTIZED_DATE, game_datetime
from .fields import (
    ENTITY_FIELDS,
    KEYED_LIST_FIELDS,
    METADATA_FIELDS,
    NORMALIZED_DOMAINS,
    PAIR_MAP_FIELDS,
    REFERENCE_FIELDS,
    RESEARCH_STATE_TYPE,
    SINGLETON_ENTITY_TYPES,
    TIME_FIELDS,
)
from .raw_save import RawSave
from .records import decode_records
from .references import ExpectedDomains, ReferenceIndex
from .unknowns import PAIR_MAP, UnknownCollector, check_reference, scan_envelope, scan_fields

__all__ = ["game_datetime", "normalize", "save_timestamp"]

logger = get_logger(__name__)

ARRAY_OF_KEYED_OBJECTS = "array_of_keyed_objects"
"""``field_shape`` detail: expected a list of objects with a unique string key member (``KEYED_LIST_FIELDS``)."""


def _observed(value: dict[str, Any], name: str) -> Observed:
    return freeze(value[name]) if name in value else Unknown()


def _single_entry(gamestates: dict[str, Any], short_type: str, collector: UnknownCollector) -> dict[str, Any]:
    """The ``Value`` of a singleton state (metadata, time); ``{}`` when absent.

    An absent singleton is ordinary missing evidence (its fields become ``Unknown``); more than one entry is
    an unexpected structure and is reported.
    """
    entries = decode_state_map(gamestates, short_type)
    if len(entries) != 1:
        logger.debug("singleton state %s", log_fields(state_type=short_type, entries=len(entries), used="first"))
    if len(entries) > 1:
        collector.singleton_count(short_type, len(entries))
    value = entries[0].value if entries else {}
    scan_fields(short_type, value, collector)
    return value


def _unknown_counts(states: tuple[EntityState, ...]) -> dict[str, int]:
    """How many normalized fields are unknown, by reason; a cheap aggregate for the debug log."""
    counts = {reason.value: 0 for reason in UnknownReason}
    for state in states:
        for _name, value in state.fields:
            if isinstance(value, Unknown):
                counts[value.reason.value] += 1
    return counts


def _keyed_list(short_type: str, name: str, raw: Any, key: str, collector: UnknownCollector) -> Observed:
    """``raw`` as a ``FrozenMap`` from each element's ``key`` member to the whole element.

    Anything else (not a list, an element that is not an object or lacks a string key, a repeated key) is
    reported and kept raw as ``Unknown(unparseable)``; no element is dropped or renamed.
    """
    items: dict[str, FieldValue] = {}
    if isinstance(raw, list):
        for item in raw:
            item_key = item.get(key) if isinstance(item, dict) else None
            if not isinstance(item_key, str) or item_key in items:
                break
            items[item_key] = freeze(item)
        else:
            return FrozenMap(tuple(items.items()))
    collector.field_shape(short_type, name, ARRAY_OF_KEYED_OBJECTS, raw)
    return Unknown(UnknownReason.UNPARSEABLE, freeze(raw))


def _pair_map_field(
    short_type: str,
    name: str,
    raw: Any,
    keys: ExpectedDomains | None,
    index: ReferenceIndex,
    collector: UnknownCollector,
) -> Observed:
    """A ``PAIR_MAP_FIELDS`` value: reference keys resolved like a reference list, integer keys as text, values frozen.

    A value that is not a pair map, that repeats a key, or (``keys is None``) has a key that is not an integer is
    ``Unknown(unparseable)`` and reported as an unexpected shape; reference keys are checked like a reference list.
    """
    pairs = decode_pair_map(raw)
    key_ids: list[int] | None = None
    if pairs is not None and keys is not None:
        key_ids = [key_id for key, _value in pairs if (key_id := read_id_value(key)) is not None]
    elif pairs is not None and all(isinstance(key, int) and not isinstance(key, bool) for key, _value in pairs):
        key_ids = [key for key, _value in pairs]
    if pairs is None or key_ids is None or len(set(key_ids)) != len(key_ids):
        collector.field_shape(short_type, name, PAIR_MAP, raw)
        return Unknown(UnknownReason.UNPARSEABLE, freeze(raw))
    if keys is None:
        return FrozenMap(tuple((str(key), freeze(value)) for key, value in pairs))
    check_reference(short_type, name, [key for key, _value in pairs], keys, True, index, collector)
    return index.resolve_map(pairs, keys, raw)


def _entity_state(
    domain: EntityDomain,
    short_type: str,
    entry: StateEntry,
    index: ReferenceIndex,
    source: str,
    collector: UnknownCollector,
) -> EntityState:
    references = REFERENCE_FIELDS.get(short_type, {})
    keyed_lists = KEYED_LIST_FIELDS.get(short_type, {})
    pair_maps = PAIR_MAP_FIELDS.get(short_type, {})
    fields: list[tuple[str, Observed]] = []
    for name in ENTITY_FIELDS[short_type]:
        if name not in entry.value:
            fields.append((name, Unknown()))
            continue
        raw = entry.value[name]
        if name in references:
            target, is_list = references[name]
            check_reference(short_type, name, raw, target, is_list, index, collector)
            fields.append((name, index.resolve_list(raw, target) if is_list else index.resolve(raw, target)))
        elif name in keyed_lists:
            fields.append((name, _keyed_list(short_type, name, raw, keyed_lists[name], collector)))
        elif name in pair_maps:
            fields.append((name, _pair_map_field(short_type, name, raw, pair_maps[name], index, collector)))
        else:
            fields.append((name, freeze(raw)))
    scan_fields(short_type, entry.value, collector)
    display_name = entry.value.get("displayName")
    ref = EntityRef(
        EntityId(domain, str(entry.map_id)),
        IdentityConfidence.IN_SAVE_ID,
        state_type=short_type,
        name=display_name if isinstance(display_name, str) else None,
    )
    location = SourceLocation(source, short_type, entry.map_id, entry_path(STATE_PREFIX + short_type, entry.index))
    return EntityState(ref=ref, fields=tuple(fields), location=location)


def _technology_state(
    name: str, finished: bool, progress: Observed, entry: StateEntry, index: int, member: str, source: str
) -> EntityState:
    ref = EntityRef(
        EntityId(EntityDomain.TECHNOLOGY, name), IdentityConfidence.NAME_KEY, state_type=RESEARCH_STATE_TYPE, name=name
    )
    value_path = entry_path(STATE_PREFIX + RESEARCH_STATE_TYPE, entry.index)
    location = SourceLocation(source, RESEARCH_STATE_TYPE, entry.map_id, f"{value_path}/{member}/{index}")
    return EntityState(ref=ref, fields=(("finished", finished), ("progress", progress)), location=location)


def _research(
    gamestates: dict[str, Any], source: str, collector: UnknownCollector
) -> tuple[ResearchState, tuple[EntityState, ...]]:
    """The research singleton and the name-keyed technology states derived from it.

    A technology exists for every string in ``finishedTechsNames`` and for every ``techProgress`` element
    with a string ``techTemplateName`` (observed: a finished tech may still carry a progress entry).
    Elements of another shape create no identity; they remain visible raw on the ``ResearchState``.
    """
    entries = decode_state_map(gamestates, RESEARCH_STATE_TYPE)
    if not entries:
        return ResearchState(), ()
    if len(entries) > 1:
        collector.singleton_count(RESEARCH_STATE_TYPE, len(entries))
    entry = entries[0]
    value = entry.value
    scan_fields(RESEARCH_STATE_TYPE, value, collector)
    for list_name in ("finishedTechsNames", "techProgress"):
        if list_name in value and not isinstance(value[list_name], list):
            collector.field_shape(RESEARCH_STATE_TYPE, list_name, "array", value[list_name])
    research = ResearchState(
        finished_techs_names=_observed(value, "finishedTechsNames"),
        finished_one_time_only_project_names=_observed(value, "finishedOneTimeOnlyProjectNames"),
        tech_progress=_observed(value, "techProgress"),
        campaign_start_year=_observed(value, "campaignStartYear"),
        end_game_techs_completed_by_category=_observed(value, "endGameTechsCompletedByCategory"),
        location=SourceLocation(
            source, RESEARCH_STATE_TYPE, entry.map_id, entry_path(STATE_PREFIX + RESEARCH_STATE_TYPE, entry.index)
        ),
    )

    finished_raw = value.get("finishedTechsNames")
    finished_names = [item for item in finished_raw if isinstance(item, str)] if isinstance(finished_raw, list) else []
    progress_raw = value.get("techProgress")
    progress_items = progress_raw if isinstance(progress_raw, list) else []

    progress: dict[str, tuple[int, FieldValue]] = {}
    for position, item in enumerate(progress_items):
        name = item.get("techTemplateName") if isinstance(item, dict) else None
        if isinstance(name, str):
            progress.setdefault(name, (position, freeze(item)))

    technologies: dict[str, EntityState] = {}
    for position, name in enumerate(finished_names):
        if name in technologies:
            continue
        progress_value: Observed = progress[name][1] if name in progress else Unknown()
        technologies[name] = _technology_state(
            name, True, progress_value, entry, position, "finishedTechsNames", source
        )
    for name, (position, frozen) in progress.items():
        if name not in technologies:
            technologies[name] = _technology_state(name, False, frozen, entry, position, "techProgress", source)
    logger.debug(
        "research normalized %s",
        log_fields(
            state_type=RESEARCH_STATE_TYPE,
            entries=len(entries),
            finished=len(finished_names),
            progress=len(progress),
            progress_items_skipped=len(progress_items) - len(progress),
            technologies=len(technologies),
        ),
    )
    return research, tuple(technologies.values())


def save_timestamp(raw_save: RawSave) -> datetime | None:
    """The game time of a save (``TITimeState.currentDateTime``, first entry); ``None`` when absent or unparseable.

    The chronology key of a save sequence (``docs/game-data-notes/chronology-and-deduplication.md``). It reads
    only the time singleton, so ordering saves does not require normalizing them; ``normalize`` derives
    ``SaveSnapshot.timestamp`` from the same field.
    """
    entries = decode_state_map(raw_save.root["gamestates"], "TITimeState")
    if not entries or "currentDateTime" not in entries[0].value:
        return None
    return game_datetime(entries[0].value["currentDateTime"])


def normalize(raw_save: RawSave, *, collector: UnknownCollector | None = None) -> SaveSnapshot:
    """Normalize campaign time and metadata, the entity collections in ``NORMALIZED_DOMAINS``, and research.

    Structures outside the schema are always detected and summarized in the log; pass a ``collector`` to
    receive them as findings. The snapshot does not depend on whether one is passed.
    """
    if collector is None:
        collector = UnknownCollector()
    scan_envelope(raw_save.root, collector)
    gamestates: dict[str, Any] = raw_save.root["gamestates"]
    index = ReferenceIndex.from_gamestates(gamestates, on_skipped=collector.container_shape)

    time_state = _single_entry(gamestates, "TITimeState", collector)
    metadata_state = _single_entry(gamestates, "TIMetadataState", collector)

    timestamp: datetime | None = None
    date: Observed
    if "currentDateTime" not in time_state:
        date = Unknown()
        logger.debug("date missing %s", log_fields(state_type="TITimeState", field="currentDateTime"))
    else:
        timestamp = game_datetime(time_state["currentDateTime"])
        if timestamp:
            date = timestamp.isoformat()
            logger.debug("date parsed %s", log_fields(date=date))
        else:
            date = Unknown(UnknownReason.UNPARSEABLE, freeze(time_state["currentDateTime"]))
            logger.debug("date unparseable %s", log_fields(value=shape(time_state["currentDateTime"])))
            collector.field_shape("TITimeState", "currentDateTime", COMPONENTIZED_DATE, time_state["currentDateTime"])

    metadata = {name: _observed(metadata_state, name) for name in METADATA_FIELDS}
    time_fields = {name: _observed(time_state, name) for name in TIME_FIELDS}
    campaign = CampaignMetadata(
        player_faction_name=metadata["playerFactionName"],
        difficulty=metadata["difficulty"],
        played_with_mods=metadata["playedWithMods"],
        game_time_string=metadata["gameTimeString"],
        scenario_master_template=time_fields["masterMetaTemplateName"],
        scenario_template=time_fields["scenarioMetaTemplateName"],
        selected_factions_for_scenario=metadata["selectedFactionsForScenario"],
    )

    collections: dict[str, tuple[EntityState, ...]] = {}
    records: list[RecordSet] = []
    for domain, short_type, attribute in NORMALIZED_DOMAINS:
        entries = decode_state_map(gamestates, short_type)
        if short_type in SINGLETON_ENTITY_TYPES and len(entries) > 1:
            collector.singleton_count(short_type, len(entries))
        states = tuple(_entity_state(domain, short_type, entry, index, raw_save.source, collector) for entry in entries)
        collections[attribute] = collections.get(attribute, ()) + states
        records.extend(decode_records(short_type, entries, states, index, raw_save.source, collector))
        if logger.isEnabledFor(logging.DEBUG):
            unknown = _unknown_counts(states)
            logger.debug(
                "domain normalized %s",
                log_fields(
                    state_type=short_type,
                    domain=domain.value,
                    entities=len(states),
                    missing_fields=unknown[UnknownReason.MISSING.value],
                    unresolved_references=unknown[UnknownReason.UNRESOLVED_REFERENCE.value],
                    unparseable=unknown[UnknownReason.UNPARSEABLE.value],
                    unknown_fields=collector.field_count(short_type),
                ),
            )
    research, technologies = _research(gamestates, raw_save.source, collector)
    collector.log_summary()
    record_sets, record_entries = record_counts(records)
    logger.info(
        "normalized %s",
        log_fields(
            state_types=len(gamestates),
            entities=sum(len(states) for states in collections.values()),
            technologies=len(technologies),
            record_sets=record_sets,
            record_entries=record_entries,
        ),
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
        campaign_day=time_fields["daysInCampaign"],
        campaign_quarter=time_fields["currentQuarterSinceStart"],
        campaign=campaign,
        research=research,
        technologies=technologies,
        records=tuple(records),
        raw_metadata=raw_metadata,
        **collections,
    )
