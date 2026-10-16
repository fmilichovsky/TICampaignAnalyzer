"""Modular, domain-specific atomic-event analyzers."""

from .aliens import RegionAlienAnalyzer
from .base import Analyzer
from .campaign import GlobalValuesAnalyzer
from .common import run_analyzers
from .military import ArmyAnalyzer
from .politics import (
    ControlPointAnalyzer,
    CouncilorAnalyzer,
    FederationAnalyzer,
    NationAnalyzer,
    OrganizationAnalyzer,
    WarAnalyzer,
)
from .space import FleetAnalyzer, HabAnalyzer, ShipAnalyzer
from .technology import TechnologyAnalyzer

POLITICS_ANALYZERS: tuple[Analyzer, ...] = (
    ControlPointAnalyzer(),
    NationAnalyzer(),
    WarAnalyzer(),
    FederationAnalyzer(),
    CouncilorAnalyzer(),
    OrganizationAnalyzer(),
)
"""The analyzers of the politics family, in the order they run (the output is sorted regardless)."""
MILITARY_ANALYZERS: tuple[Analyzer, ...] = (ArmyAnalyzer(),)
SPACE_ANALYZERS: tuple[Analyzer, ...] = (FleetAnalyzer(), ShipAnalyzer(), HabAnalyzer())
TECHNOLOGY_ANALYZERS: tuple[Analyzer, ...] = (TechnologyAnalyzer(),)
ALIEN_ANALYZERS: tuple[Analyzer, ...] = (RegionAlienAnalyzer(),)
CAMPAIGN_ANALYZERS: tuple[Analyzer, ...] = (GlobalValuesAnalyzer(),)
ALL_ANALYZERS: tuple[Analyzer, ...] = (
    POLITICS_ANALYZERS
    + MILITARY_ANALYZERS
    + SPACE_ANALYZERS
    + TECHNOLOGY_ANALYZERS
    + ALIEN_ANALYZERS
    + CAMPAIGN_ANALYZERS
)
"""Every family; each handled reference list is owned by exactly one analyzer, so IDs never collide."""

__all__ = [
    "ALIEN_ANALYZERS",
    "ALL_ANALYZERS",
    "CAMPAIGN_ANALYZERS",
    "MILITARY_ANALYZERS",
    "POLITICS_ANALYZERS",
    "SPACE_ANALYZERS",
    "TECHNOLOGY_ANALYZERS",
    "Analyzer",
    "run_analyzers",
]
