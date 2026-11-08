"""Tests for selecting benchmark campaigns in sample tests."""

import pytest

from tests.samples import CAMPAIGNS, selected_campaigns


def test_empty_selection_uses_every_campaign() -> None:
    assert selected_campaigns("", CAMPAIGNS) == sorted(CAMPAIGNS)


def test_selection_accepts_comma_separated_campaign_names() -> None:
    requested = sorted(CAMPAIGNS)[:2]
    selection = f"{requested[1]}, {requested[0]}"
    assert selected_campaigns(selection, CAMPAIGNS) == requested


def test_selection_rejects_unknown_campaign_names() -> None:
    unknown = "campaign-not-in-manifest"
    assert unknown not in CAMPAIGNS
    with pytest.raises(pytest.UsageError, match=rf"unknown sample campaign\(s\): {unknown}"):
        selected_campaigns(unknown, CAMPAIGNS)
