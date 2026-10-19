"""Modular, domain-specific atomic-event analyzers."""

from .aliens import RegionAlienAnalyzer
from .base import Analyzer
from .campaign import GlobalValuesAnalyzer, NotificationAnalyzer
from .common import run_analyzers
from .faction import LedgerAnalyzer
from .military import ArmyAnalyzer
from .politics import (
    ControlPointAnalyzer,
    CouncilorAnalyzer,
    FederationAnalyzer,
    NationAnalyzer,
    NationMetricAnalyzer,
    OrganizationAnalyzer,
    WarAnalyzer,
)
from .space import CombatAnalyzer, FleetAnalyzer, HabAnalyzer, ShipAnalyzer
from .technology import ProjectAnalyzer, TechnologyAnalyzer

POLITICS_ANALYZERS: tuple[Analyzer, ...] = (
    ControlPointAnalyzer(),
    NationAnalyzer(),
    NationMetricAnalyzer(),
    WarAnalyzer(),
    FederationAnalyzer(),
    CouncilorAnalyzer(),
    OrganizationAnalyzer(),
)
"""The analyzers of the politics family, in the order they run (the output is sorted regardless)."""
MILITARY_ANALYZERS: tuple[Analyzer, ...] = (ArmyAnalyzer(),)
SPACE_ANALYZERS: tuple[Analyzer, ...] = (FleetAnalyzer(), ShipAnalyzer(), HabAnalyzer(), CombatAnalyzer())
TECHNOLOGY_ANALYZERS: tuple[Analyzer, ...] = (TechnologyAnalyzer(), ProjectAnalyzer())
ALIEN_ANALYZERS: tuple[Analyzer, ...] = (RegionAlienAnalyzer(),)
CAMPAIGN_ANALYZERS: tuple[Analyzer, ...] = (GlobalValuesAnalyzer(), NotificationAnalyzer())
FACTION_ANALYZERS: tuple[Analyzer, ...] = (LedgerAnalyzer(),)
"""The faction records read by date: the ``Transactions`` ledger (issue #98)."""
ALL_ANALYZERS: tuple[Analyzer, ...] = (
    POLITICS_ANALYZERS
    + MILITARY_ANALYZERS
    + SPACE_ANALYZERS
    + TECHNOLOGY_ANALYZERS
    + ALIEN_ANALYZERS
    + CAMPAIGN_ANALYZERS
    + FACTION_ANALYZERS
)
"""Every family; each handled reference list is owned by exactly one analyzer, so IDs never collide."""

__all__ = [
    "ALIEN_ANALYZERS",
    "ALL_ANALYZERS",
    "CAMPAIGN_ANALYZERS",
    "FACTION_ANALYZERS",
    "MILITARY_ANALYZERS",
    "POLITICS_ANALYZERS",
    "SPACE_ANALYZERS",
    "TECHNOLOGY_ANALYZERS",
    "Analyzer",
    "run_analyzers",
]
