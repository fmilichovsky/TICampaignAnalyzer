"""References to logical game entities."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EntityRef:
    kind: str
    id: str
    name: str | None = None
