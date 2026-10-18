"""Fuzzy matching and the scripted dialogue of the interactive campaign picker."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from tests.sequence.campaign_variants import write_campaign
from tinarrative.grouping import CampaignGroup, group_saves
from tinarrative.picker import PROMPT, fuzzy_filter, fuzzy_score, pick_campaign
from tinarrative.sequence import survey


def test_a_query_matches_only_as_an_in_order_subsequence() -> None:
    assert fuzzy_score("prot", "protectorate") is not None
    assert fuzzy_score("ptr", "protectorate") is not None
    assert fuzzy_score("tp", "protectorate") is None
    assert fuzzy_score("xyz", "protectorate") is None
    assert fuzzy_score("", "protectorate") is None


def test_case_is_ignored_and_every_term_must_match() -> None:
    assert fuzzy_score("PROT", "protectorate") == fuzzy_score("prot", "Protectorate")
    assert fuzzy_score("res 2026", "resistance-20260104") is not None
    assert fuzzy_score("res 2027", "resistance-20260104") is None


def test_consecutive_and_word_start_matches_rank_higher() -> None:
    contiguous = fuzzy_score("prot", "protectorate")
    scattered = fuzzy_score("prot", "pirate-route")
    inner = fuzzy_score("tect", "protectorate")
    at_word = fuzzy_score("tect", "pro tectorate")
    assert contiguous is not None and scattered is not None and contiguous > scattered
    assert inner is not None and at_word is not None and at_word > inner


@pytest.fixture
def groups(tmp_path: Path) -> tuple[CampaignGroup, ...]:
    directory = tmp_path / "saves"
    write_campaign(directory, "r", faction_name="The Resistance", started=datetime(2026, 1, 4, 11, 37, 51))
    write_campaign(directory, "p", faction_name="The Protectorate", started=datetime(2026, 10, 14, 15, 26, 24))
    write_campaign(directory, "a", faction_name="The Prospectors", started=datetime(2026, 12, 1, 9, 0, 0))
    return group_saves(survey(path) for path in sorted(directory.iterdir()))


def test_fuzzy_filter_searches_names_and_orders_best_first(groups: tuple[CampaignGroup, ...]) -> None:
    assert [group.key for group in fuzzy_filter(groups, "protector")] == [
        "protectorate-20261014-152624",
        "prospectors-20261201-090000",
    ]
    assert [group.index for group in fuzzy_filter(groups, "2026")] == [1, 2, 3]
    assert fuzzy_filter(groups, "initiative") == []


class Dialogue:
    """Scripted answers for ``read`` and everything written, prompts included."""

    def __init__(self, *answers: str | type[BaseException]) -> None:
        self._answers: Iterator[str | type[BaseException]] = iter(answers)
        self.transcript: list[str] = []

    def read(self, prompt: str) -> str:
        self.transcript.append(prompt)
        answer = next(self._answers)
        if isinstance(answer, str):
            return answer
        raise answer

    def write(self, text: str) -> None:
        self.transcript.append(text)

    @property
    def text(self) -> str:
        return "".join(self.transcript)

    def pick(self, groups: tuple[CampaignGroup, ...], initial: str | None = None) -> CampaignGroup | None:
        return pick_campaign(groups, read=self.read, write=self.write, file_time=lambda _: 0.0, initial=initial)


@pytest.mark.parametrize(
    ("answer", "key"),
    [
        ("2", "protectorate-20261014-152624"),
        ("prospectors-20261201-090000", "prospectors-20261201-090000"),
        ("res", "resistance-20260104-113751"),
        ("  protect 10-14  ", "protectorate-20261014-152624"),
    ],
)
def test_a_number_key_prefix_or_unique_search_selects(answer: str, key: str, groups: tuple[CampaignGroup, ...]) -> None:
    dialogue = Dialogue(answer)

    picked = dialogue.pick(groups)

    assert picked is not None and picked.key == key
    assert dialogue.text.startswith("3 campaigns:\n")
    assert PROMPT in dialogue.text


def test_an_ambiguous_search_narrows_the_listing_and_keeps_its_numbers(groups: tuple[CampaignGroup, ...]) -> None:
    dialogue = Dialogue("pro", "3")

    picked = dialogue.pick(groups)

    assert picked is not None and picked.index == 3
    narrowed = dialogue.text.split("2 of 3 campaigns match 'pro':\n", 1)[1]
    assert "\n3. prospectors-20261201-090000\n" in narrowed
    assert "\n2. protectorate-20261014-152624\n" in narrowed
    assert "resistance" not in narrowed.split(PROMPT)[0]


def test_a_search_without_match_shows_the_full_listing_again(groups: tuple[CampaignGroup, ...]) -> None:
    dialogue = Dialogue("initiative", "1")

    picked = dialogue.pick(groups)

    assert picked is not None and picked.index == 1
    assert "no campaign matches 'initiative'\n\n3 campaigns:\n" in dialogue.text


@pytest.mark.parametrize("answer", ["", "   ", EOFError, KeyboardInterrupt])
def test_an_empty_answer_or_end_of_input_cancels(
    answer: str | type[BaseException], groups: tuple[CampaignGroup, ...]
) -> None:
    assert Dialogue(answer).pick(groups) is None


def test_the_initial_selector_is_resolved_before_anything_is_read(groups: tuple[CampaignGroup, ...]) -> None:
    dialogue = Dialogue()

    picked = dialogue.pick(groups, initial="prosp")

    assert picked is not None and picked.key.startswith("prospectors")
    assert PROMPT not in dialogue.text


def test_an_ambiguous_initial_selector_opens_a_narrowed_listing(groups: tuple[CampaignGroup, ...]) -> None:
    dialogue = Dialogue("2")

    picked = dialogue.pick(groups, initial="pro")

    assert picked is not None and picked.index == 2
    assert dialogue.text.startswith("2 of 3 campaigns match 'pro':\n")
