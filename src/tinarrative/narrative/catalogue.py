"""The narrative rules ``aggregate`` runs by default."""

from __future__ import annotations

from ..config import DEFAULT_SETTINGS, NarrativeSettings
from .aggregation import NarrativeRule
from .assets import asset_rules
from .diplomacy import diplomacy_rules
from .geopolitics import geopolitical_rules
from .nation_metrics import nation_metric_rules
from .space import space_rules


def narrative_rules(settings: NarrativeSettings) -> tuple[NarrativeRule, ...]:
    return (
        *geopolitical_rules(settings.geopolitics),
        *diplomacy_rules(settings.geopolitics),
        *nation_metric_rules(settings),
        *asset_rules(settings),
        *space_rules(settings.space),
    )


NARRATIVE_RULES: tuple[NarrativeRule, ...] = narrative_rules(DEFAULT_SETTINGS.narrative)
