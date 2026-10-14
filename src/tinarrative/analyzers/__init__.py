"""Modular, domain-specific atomic-event analyzers."""

from .base import Analyzer
from .common import run_analyzers
from .politics import ControlPointAnalyzer, CouncilorAnalyzer, NationAnalyzer

POLITICS_ANALYZERS: tuple[Analyzer, ...] = (ControlPointAnalyzer(), NationAnalyzer(), CouncilorAnalyzer())
"""The analyzers of the politics family, in the order they run (the output is sorted regardless)."""

__all__ = ["POLITICS_ANALYZERS", "Analyzer", "run_analyzers"]
