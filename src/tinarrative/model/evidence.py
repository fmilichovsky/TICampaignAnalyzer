"""Evidence retained through every analysis stage."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Evidence:
    save_id: str
    domain: str
    description: str
    before: Any = None
    after: Any = None
    path: str | None = None
