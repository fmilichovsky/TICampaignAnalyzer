"""Interactive campaign picker for ``events``: a line prompt over the campaign listing, with fuzzy search.

Only chooses among the groups ``grouping.group_saves`` formed. Input and output are injected so the prompt can use
stderr (the report owns stdout) and tests can script the answers.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .grouping import CampaignGroup, render_listing, select_campaign

PROMPT = "Campaign (number, key or search text; empty to cancel): "

_BOUNDARY_CHARACTERS = frozenset(" -_/#.,")
_MATCH = 16
_CONSECUTIVE = 8
_BOUNDARY = 8
_GAP = 1


def _term_score(term: str, text: str) -> int | None:
    """The best score of ``term`` as an in-order subsequence of ``text``; both already lowercase."""
    # best[j]: the best score of the term so far with its latest character matched at text[j].
    best: list[int | None] = [None] * len(text)
    for position, character in enumerate(term):
        current: list[int | None] = [None] * len(text)
        gapped: int | None = None  # the best previous score at an index < j - 1, less the gap to j
        for j, candidate in enumerate(text):
            if j >= 2:
                skipped = best[j - 2]
                options = [score - _GAP for score in (gapped, skipped) if score is not None]
                gapped = max(options) if options else None
            if candidate != character:
                continue
            bonus = _MATCH + (_BOUNDARY if j == 0 or text[j - 1] in _BOUNDARY_CHARACTERS else 0)
            if position == 0:
                current[j] = bonus
                continue
            adjacent = best[j - 1] if j > 0 else None
            options = [
                score for score in (gapped, None if adjacent is None else adjacent + _CONSECUTIVE) if score is not None
            ]
            if options:
                current[j] = max(options) + bonus
        best = current
    scores = [score for score in best if score is not None]
    return max(scores) if scores else None


def fuzzy_score(query: str, text: str) -> int | None:
    """How well ``query`` matches ``text``, or ``None`` when it does not; higher is better, case is ignored.

    Every whitespace-separated term must occur in ``text`` as an in-order subsequence; the term scores add up. A
    matched character scores more after another matched character or at the start of a word, and every skipped
    character between two matched ones costs a little.
    """
    terms = query.lower().split()
    if not terms:
        return None
    lowered = text.lower()
    total = 0
    for term in terms:
        score = _term_score(term, lowered)
        if score is None:
            return None
        total += score
    return total


def search_text(group: CampaignGroup) -> str:
    """What the fuzzy search reads of a group: its key, faction name, scenario and real-world start; never paths."""
    started = "" if group.started is None else f"{group.started:%Y-%m-%d %H:%M:%S}"
    return " ".join(part for part in (group.key, group.faction_name or "", group.scenario_label, started) if part)


def fuzzy_filter(groups: Sequence[CampaignGroup], query: str) -> list[CampaignGroup]:
    """The groups ``query`` matches, best first; equal scores keep the listing order."""
    scored = [(score, group) for group in groups if (score := fuzzy_score(query, search_text(group))) is not None]
    scored.sort(key=lambda pair: (-pair[0], pair[1].index))
    return [group for _, group in scored]


def pick_campaign(
    groups: Sequence[CampaignGroup],
    *,
    read: Callable[[str], str],
    write: Callable[[str], None],
    file_time: Callable[[str], float],
    initial: str | None = None,
) -> CampaignGroup | None:
    """Ask for a campaign until one is chosen; ``None`` when the user cancels (empty answer, end of input, Ctrl-C).

    An answer ``select_campaign`` accepts selects; otherwise it is a fuzzy search: one match selects, several narrow
    the listing and ask again, none shows the full listing. ``initial`` is resolved before anything is read.
    """
    shown: Sequence[CampaignGroup] = groups
    heading: str | None = None
    answer = initial
    if answer is None:
        write(render_listing(shown))
    while True:
        if answer is None:
            try:
                answer = read("\n" + PROMPT)
            except (EOFError, KeyboardInterrupt):
                write("\n")
                return None
        query = answer.strip()
        answer = None
        if not query:
            return None
        selected = select_campaign(groups, query, file_time)
        if isinstance(selected, CampaignGroup):
            return selected
        matches = fuzzy_filter(groups, query)
        if len(matches) == 1:
            write(f"-> {matches[0].index}. {matches[0].key}\n")
            return matches[0]
        if matches:
            shown, heading = matches, f"{len(matches)} of {len(groups)} campaigns match {query!r}:"
        else:
            shown, heading = groups, None
            write(f"no campaign matches {query!r}\n\n")
        write(render_listing(shown, heading))
