"""Event impact is independent from confidence."""

from enum import StrEnum


class Significance(StrEnum):
    TRIVIAL = "trivial"
    MINOR = "minor"
    MAJOR = "major"
    CAMPAIGN_DEFINING = "campaign_defining"
