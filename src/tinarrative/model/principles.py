"""The calibration principles, generated from docs/calibration-principles.md (ADR-0024).

Do not edit: change the page and run ``make docs``.
"""

from __future__ import annotations

from enum import Enum


class Principle(Enum):
    """A calibration principle: its identifier, its name as the page writes it, its revision and a hash of its text."""

    identifier: str
    title: str
    revision: int
    text_hash: str

    def __init__(self, identifier: str, title: str, revision: int, text_hash: str) -> None:
        self.identifier = identifier
        self.title = title
        self.revision = revision
        self.text_hash = text_hash

    THE_ORDINARY_INSTANCE = (
        "the-ordinary-instance",
        "The ordinary instance",
        1,
        "b1275740858cecf9",
    )

    NO_COMPROMISE_LEVEL = (
        "no-compromise-level",
        "No compromise level",
        1,
        "79164fea8a4ebbd5",
    )

    THREE_SOURCES_OF_VARIATION = (
        "three-sources-of-variation",
        "Three sources of variation",
        1,
        "7d4636ffe06e13b4",
    )

    ATOMIC_KINDS_ARE_JUDGED_ALONE = (
        "atomic-kinds-are-judged-alone",
        "Atomic kinds are judged alone",
        1,
        "c053ba45a92aaf4c",
    )

    ONE_JUDGE_PER_FACT = (
        "one-judge-per-fact",
        "One judge per fact",
        1,
        "21cbc186fbbc2ad1",
    )

    EVIDENCE_NEVER_OUTRANKS_ITS_READING = (
        "evidence-never-outranks-its-reading",
        "Evidence never outranks its reading",
        1,
        "38220f1321aa44bb",
    )

    CAMPAIGN_DEFINING_BY_CONSEQUENCE = (
        "campaign-defining-by-consequence",
        "Campaign-defining by consequence",
        1,
        "b11ada3d7d09f13f",
    )

    TRIVIAL_IS_A_ROLE = (
        "trivial-is-a-role",
        "Trivial is a role",
        1,
        "545a502ca9803e5a",
    )

    BOTH_WAYS = (
        "both-ways",
        "Both ways",
        1,
        "9fd2d47278b95667",
    )

    A_SHARE_IS_A_GAME_QUANTITY = (
        "a-share-is-a-game-quantity",
        "A share is a game quantity",
        1,
        "d4c009321bffdc42",
    )

    A_SCALING_BELONGS_TO_THE_KIND = (
        "a-scaling-belongs-to-the-kind",
        "A scaling belongs to the kind",
        1,
        "98a20aa4b2c16956",
    )

    SHARE_SHAPING_CONSTANTS = (
        "share-shaping-constants",
        "Share-shaping constants",
        1,
        "be7bcff0350d3ac1",
    )

    NO_DENSITY = (
        "no-density",
        "No density",
        1,
        "6155b61f2d1ab2e4",
    )

    SMELLS_ARE_TRIGGERS = (
        "smells-are-triggers",
        "Smells are triggers",
        1,
        "a0774848b2ac4417",
    )

    A_REASON_OF_ITS_OWN = (
        "a-reason-of-its-own",
        "A reason of its own",
        1,
        "53658ce82ebac9a2",
    )

    SAMPLES_CONFIRM_OR_VETO = (
        "samples-confirm-or-veto",
        "Samples confirm or veto",
        1,
        "1eda19ea757e473c",
    )

    A_MISPLACED_EVENT_IS_A_TRIGGER = (
        "a-misplaced-event-is-a-trigger",
        "A misplaced event is a trigger",
        1,
        "4eefabf0d0368d9a",
    )

    FITTING_TO_THE_GAMES_DISTRIBUTION = (
        "fitting-to-the-games-distribution",
        "Fitting to the game's distribution",
        1,
        "f4b09a79743deb84",
    )

    THIN_COVERAGE_IS_LABELLED = (
        "thin-coverage-is-labelled",
        "Thin coverage is labelled",
        1,
        "4a5d406dc618c478",
    )

    ONE_REASON_PER_KIND_AND_SCALING = (
        "one-reason-per-kind-and-scaling",
        "One reason per kind and scaling",
        1,
        "7f51d02b71733590",
    )
