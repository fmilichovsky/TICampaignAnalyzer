from __future__ import annotations

from tinarrative.narrative.councilors import GENERATED_ORG_CATEGORIES
from tinarrative.narrative.org_catalog import _BY_CATEGORY, NAMED_ORG_CATEGORIES


def test_every_template_has_one_category() -> None:
    assert len(NAMED_ORG_CATEGORIES) == sum(len(templates) for templates in _BY_CATEGORY.values())


def test_categories_share_the_generated_vocabulary() -> None:
    extra = {"military", "government", "public_interest", "militant", "other"}
    assert set(_BY_CATEGORY) <= set(GENERATED_ORG_CATEGORIES.values()) | extra


def test_no_generated_template_is_catalogued() -> None:
    assert not [template for template in NAMED_ORG_CATEGORIES if template.startswith("Random")]
