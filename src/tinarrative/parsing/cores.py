"""A hab's core module (``TIHabModuleState``) copied onto the hab as the ``HAB_CORE_FIELDS``.

Sectors and modules are not normalized; only the core's construction state and dates reach the model.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ..identity import read_id_value
from ..model.values import Observed, Unknown, UnknownReason, freeze
from .containers import decode_state_map
from .dates import iso_date
from .fields import HAB_CORE_FIELDS
from .unknowns import UnknownCollector

HAB_STATE_TYPE = "TIHabState"
MODULE_STATE_TYPE = "TIHabModuleState"
CHAIN_FIELD = "sectors"
"""Core findings are filed under the hab's ``sectors``: module findings would be pruned, modules being unschemed."""
CORE_MODULE = "core_module"
"""``field_shape`` detail for a hab whose ``sectors`` do not lead to a core module."""
MODULE_DATE = "module_date"
"""``field_shape`` detail for a core date string that is not ISO-8601 text."""

_MODULE_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?$")
_NO_DATE_YEAR = 1
"""Module date strings use ``0001-01-01T00:00:00`` for "no date" (modules created from a template)."""


class HabCores:
    """The sectors and modules of one save by map ID, read once."""

    def __init__(self, gamestates: dict[str, Any]) -> None:
        self._sectors = {entry.map_id: entry.value for entry in decode_state_map(gamestates, "TISectorState")}
        self._modules = {entry.map_id: entry.value for entry in decode_state_map(gamestates, MODULE_STATE_TYPE)}

    def fields(self, hab: dict[str, Any], collector: UnknownCollector) -> list[tuple[str, Observed]]:
        """The ``HAB_CORE_FIELDS`` of one hab; all ``Unknown`` when it has no sectors or the chain is broken."""
        sectors = hab.get("sectors")
        if not isinstance(sectors, list) or not sectors:
            return [(name, Unknown()) for name in HAB_CORE_FIELDS]
        module = self._core(sectors)
        if module is None:
            collector.field_shape(HAB_STATE_TYPE, CHAIN_FIELD, CORE_MODULE, sectors)
            return [(name, Unknown(UnknownReason.UNRESOLVED_REFERENCE)) for name in HAB_CORE_FIELDS]
        completed = module.get("constructionCompleted")
        return [
            ("coreConstructionCompleted", completed if isinstance(completed, bool) else Unknown()),
            ("coreStartBuildDate", _module_date(module, "startBuildDate", collector)),
            ("coreCompletionDate", _module_date(module, "completionDate", collector)),
            ("corePriorCompletionDate", _prior_date(module, collector)),
        ]

    def _core(self, sectors: list[Any]) -> dict[str, Any] | None:
        sector_id = read_id_value(sectors[0])
        sector = self._sectors.get(sector_id) if sector_id is not None else None
        modules = sector.get("habModules") if sector is not None else None
        if not isinstance(modules, list) or not modules:
            return None
        module_id = read_id_value(modules[0])
        module = self._modules.get(module_id) if module_id is not None else None
        if module is None or module.get("slot") != 0:
            return None
        return module


def _module_date(module: dict[str, Any], name: str, collector: UnknownCollector) -> Observed:
    if name not in module:
        return Unknown()
    raw = module[name]
    if raw is None:
        return None
    match = _MODULE_DATE.match(raw) if isinstance(raw, str) else None
    if match is None:
        collector.field_shape(HAB_STATE_TYPE, CHAIN_FIELD, MODULE_DATE, raw)
        return Unknown(UnknownReason.UNPARSEABLE, freeze(raw))
    timestamp = datetime.fromisoformat(match.group(1))
    if timestamp.year == _NO_DATE_YEAR:
        return None
    fraction = match.group(2)
    if fraction:
        timestamp = timestamp.replace(microsecond=int(fraction[:6].ljust(6, "0")))
    return timestamp.isoformat()


def _prior_date(module: dict[str, Any], collector: UnknownCollector) -> Observed:
    if "priorModuleCompletionDate" not in module:
        return Unknown()
    return iso_date(module["priorModuleCompletionDate"], HAB_STATE_TYPE, CHAIN_FIELD, collector)
