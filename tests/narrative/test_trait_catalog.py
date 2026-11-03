from __future__ import annotations

from tinarrative.narrative.trait_catalog import _BY_GROUP, KEPT_GROUPS, TRAITS, WITHHELD_GROUPS


def test_every_template_is_in_one_group() -> None:
    listed = [template for traits in _BY_GROUP.values() for template, _ in traits]
    assert len(listed) == len(set(listed)) == len(TRAITS)


def test_every_group_is_kept_or_withheld() -> None:
    assert set(_BY_GROUP) == set(KEPT_GROUPS) | WITHHELD_GROUPS
    assert not set(KEPT_GROUPS) & WITHHELD_GROUPS


def test_display_names_are_given() -> None:
    assert all(name.strip() for _, name in TRAITS.values())


def test_loyalty_monitor_is_withheld() -> None:
    assert TRAITS["LoyaltyMonitor"][0] in WITHHELD_GROUPS
