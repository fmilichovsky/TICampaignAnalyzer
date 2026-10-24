"""The narrative rules ``aggregate`` runs by default: the catalogue of architecture 11.3 under runtime settings."""

from __future__ import annotations

from ..config import DEFAULT_SETTINGS, NarrativeSettings
from .aggregation import NarrativeRule
from .geopolitics import geopolitical_rules
from .nation_metrics import nation_metric_rules
from .space import space_rules


def narrative_rules(settings: NarrativeSettings) -> tuple[NarrativeRule, ...]:
    """Every implemented narrative rule, with its thresholds and windows from ``settings``."""
    return (*geopolitical_rules(settings.geopolitics), *nation_metric_rules(settings), *space_rules(settings.space))


NARRATIVE_RULES: tuple[NarrativeRule, ...] = narrative_rules(DEFAULT_SETTINGS.narrative)
"""The catalogue under the default settings."""
