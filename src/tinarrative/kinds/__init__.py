"""Event kinds: one declaration per event type, one module per family (ADR-0001)."""

from .describe import describe_event, known_event_types
from .registry import KINDS, attributes, kind_for
from .text import render_event_value

__all__ = ["KINDS", "attributes", "describe_event", "known_event_types", "kind_for", "render_event_value"]
