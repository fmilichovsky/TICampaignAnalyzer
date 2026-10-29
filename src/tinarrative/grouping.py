"""Campaign grouping: split surveyed saves into campaigns before a sequence is planned (architecture 15).

The format has no campaign ID (``docs/game-data-notes/campaign-grouping.md``), so saves group by equal
``CampaignProfile.identity`` only, never by file name, file time or ``currentID``. A save whose human player does not
resolve forms a group of its own and is never merged silently. File times are used only by the ``latest`` selector.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .log import fields, get_logger
from .narrative.chronology import TIE_SEPARATOR
from .parsing.continuity import CampaignIdentity
from .sequence import SaveRef, SkippedSave, merge_identical

logger = get_logger(__name__)

LATEST = "latest"
"""Selects the campaign holding the most recently modified save file."""

UNKNOWN_FACTION = "unknown"
"""The key slug of a group without a readable faction name."""

_LEADING_ARTICLE = re.compile(r"^the\s+", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slug(name: str | None) -> str:
    """Lowercase, without a leading "the", every run of other characters turned into one ``-``."""
    text = _NON_ALNUM.sub("-", _LEADING_ARTICLE.sub("", (name or "").strip()).lower()).strip("-")
    return text or UNKNOWN_FACTION


@dataclass(frozen=True)
class CampaignGroup:
    """The saves of one campaign and the signals they were grouped on.

    ``members`` include byte-identical copies; ``saves`` are the distinct ones in chronological order.
    """

    index: int
    key: str
    members: tuple[SaveRef, ...]
    saves: tuple[SaveRef, ...]
    faction_name: str | None
    scenario: tuple[str | None, str | None]
    started: datetime | None
    unclassified: bool
    human_players: int

    @property
    def first_date(self) -> str:
        return self.saves[0].date

    @property
    def last_date(self) -> str:
        return self.saves[-1].date

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(path for save in self.saves for path in (save.source, *save.aliases))

    @property
    def scenario_label(self) -> str:
        master, scenario = self.scenario
        return "/".join(part or "?" for part in (master, scenario))

    @property
    def unclassified_reason(self) -> str:
        if self.human_players == 1:
            return "the human player's faction does not resolve"
        return f"{self.human_players} human players"

    def to_dict(self) -> dict[str, Any]:
        master, scenario = self.scenario
        return {
            "index": self.index,
            "key": self.key,
            "faction": self.faction_name,
            "scenario": {"master": master, "scenario": scenario},
            "started": None if self.started is None else self.started.isoformat(),
            "unclassified": self.unclassified,
            "inputs": len(self.members),
            "saves": len(self.saves),
            "first_date": self.first_date,
            "last_date": self.last_date,
            "sources": [save.source for save in self.saves],
        }


def _bucket(save: SaveRef) -> tuple[str, CampaignIdentity | str]:
    identity = None if save.profile is None else save.profile.identity
    return ("campaign", identity) if identity is not None else ("unclassified", save.sha256)


def _order(saves: Sequence[SaveRef]) -> tuple[bool, bool, datetime, datetime, str]:
    """Campaigns before unclassified saves, then by real-world start (unknown last), first game time and path."""
    profile = saves[0].profile
    unclassified = profile is None or profile.identity is None
    started = None if profile is None else profile.started
    return (unclassified, started is None, started or datetime.min, saves[0].timestamp, saves[0].source)


def group_saves(saves: Iterable[SaveRef]) -> tuple[CampaignGroup, ...]:
    """Split surveyed saves into campaigns; unclassified saves come last (see ``_order``)."""
    buckets: dict[tuple[str, CampaignIdentity | str], list[SaveRef]] = {}
    for save in saves:
        buckets.setdefault(_bucket(save), []).append(save)
    ordered = sorted(
        ((members, merge_identical(members)) for members in buckets.values()), key=lambda pair: _order(pair[1])
    )
    groups: list[CampaignGroup] = []
    used: dict[str, int] = {}
    for index, (members, distinct) in enumerate(ordered, start=1):
        profile = distinct[0].profile
        faction_name = None if profile is None else profile.faction_name
        started = None if profile is None else profile.started
        key = slug(faction_name) + ("" if started is None else started.strftime("-%Y%m%d-%H%M%S"))
        used[key] = used.get(key, 0) + 1
        if used[key] > 1:
            key = f"{key}{TIE_SEPARATOR}{used[key]}"
        groups.append(
            CampaignGroup(
                index=index,
                key=key,
                members=tuple(members),
                saves=tuple(distinct),
                faction_name=faction_name,
                scenario=(None, None) if profile is None else profile.scenario,
                started=started,
                unclassified=profile is None or profile.identity is None,
                human_players=0 if profile is None else profile.human_players,
            )
        )
    logger.info(
        "campaigns grouped %s",
        fields(
            groups=len(groups),
            unclassified=sum(group.unclassified for group in groups),
            without_start=sum(group.started is None for group in groups),
        ),
    )
    return tuple(groups)


def select_campaign(
    groups: Sequence[CampaignGroup], selector: str, file_time: Callable[[str], float]
) -> CampaignGroup | str:
    """The group named by ``selector``, or the reason none is selected.

    ``file_time`` returns a path's modification time; it is called only for ``latest``.
    """
    if selector == LATEST:
        newest = max(
            groups, key=lambda group: (max(file_time(path) for path in group.paths), -group.index), default=None
        )
        return newest if newest is not None else "no campaign was found"
    if selector.isdigit():
        position = int(selector)
        if 1 <= position <= len(groups):
            return groups[position - 1]
        return f"there is no campaign {position}; the listing has {len(groups)}"
    for group in groups:
        if group.key == selector:
            return group
    matches = [group for group in groups if group.key.startswith(selector)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        keys = ", ".join(group.key for group in matches)
        return f"campaign {selector!r} is ambiguous; it matches {keys}"
    return f"no campaign matches {selector!r}"


def render_listing(groups: Sequence[CampaignGroup], heading: str | None = None) -> str:
    """One block per group: index and key, then its signals, then its saves and game-time span.

    ``heading`` replaces the ``N campaigns:`` first line, for a listing narrowed to some of the groups.
    """
    lines = [heading if heading is not None else f"{len(groups)} {'campaign' if len(groups) == 1 else 'campaigns'}:"]
    for group in groups:
        started = "real-world start unknown" if group.started is None else f"started {group.started:%Y-%m-%d %H:%M:%S}"
        count = len(group.saves)
        lines.extend(
            [
                "",
                f"{group.index}. {group.key}",
                f"   {group.faction_name or 'unknown faction'}, scenario {group.scenario_label}, {started}",
                f"   {count} {'save' if count == 1 else 'saves'}, {group.first_date} to {group.last_date}",
            ]
        )
        if group.unclassified:
            lines.append(f"   unclassified ({group.unclassified_reason}); never grouped with another save")
        elif group.started is None:
            lines.append("   grouped by faction and scenario only (no real-world start)")
    return "\n".join(lines) + "\n"


def listing_document(groups: Sequence[CampaignGroup], skipped: Sequence[SkippedSave]) -> dict[str, Any]:
    inputs = sum(len(group.members) for group in groups)
    return {
        "inputs": inputs,
        "duplicates": inputs - sum(len(group.saves) for group in groups),
        "skipped": [save.to_dict() for save in skipped],
        "campaigns": [group.to_dict() for group in groups],
    }
