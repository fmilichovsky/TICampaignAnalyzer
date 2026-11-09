"""Event kinds: one declaration per event type, one module per family (ADR-0001)."""

from .describe import describe_event, known_event_types
from .registry import KINDS, attributes
from .text import render_event_value

__all__ = ["KINDS", "attributes", "describe_event", "known_event_types", "render_event_value"]
