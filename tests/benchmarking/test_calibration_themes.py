"""The themes file: its loader, and its coverage of every declared event type."""

from __future__ import annotations

from pathlib import Path

import pytest

from tinarrative.benchmarking.calibration.themes import (
    THEMES_PATH,
    Coverage,
    Theme,
    ThemeFile,
    ThemesError,
    coverage,
    load_themes,
)
from tinarrative.kinds.registry import KINDS

ROOT = Path(__file__).resolve().parents[2]

VALID = """
[[themes]]
name = "Wars"
description = "Wars between nations."
event_types = ["war.appeared", "war.arc"]

[[themes]]
name = "Blocs"
description = "Unions of nations."
event_types = ["war.arc"]

[unthemed]
event_types = ["army.appeared"]
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "themes.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_committed_file_puts_every_declared_type_in_a_theme_or_the_no_theme_list() -> None:
    themes = load_themes(ROOT / THEMES_PATH)

    assert coverage(themes) == Coverage((), (), ())
    assert coverage(themes).complete


def test_a_type_may_sit_in_several_themes(tmp_path: Path) -> None:
    themes = load_themes(write(tmp_path, VALID))

    assert [theme.name for theme in themes.themes] == ["Wars", "Blocs"]
    assert all("war.arc" in theme.event_types for theme in themes.themes)
    assert themes.unthemed == ("army.appeared",)


def test_the_file_is_read_on_every_load(tmp_path: Path) -> None:
    path = write(tmp_path, VALID)
    load_themes(path)
    path.write_text(VALID.replace('name = "Blocs"', 'name = "Unions"'), encoding="utf-8")

    assert [theme.name for theme in load_themes(path).themes] == ["Wars", "Unions"]


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("not = [toml", id="not TOML"),
        pytest.param(VALID.replace("[unthemed]", "[elsewhere]"), id="no no-theme list"),
        pytest.param(VALID.replace('name = "Blocs"', 'name = "Wars"'), id="repeated name"),
        pytest.param(VALID.replace('description = "Unions of nations."', 'description = ""'), id="empty description"),
        pytest.param(VALID.replace('["war.arc"]', "[]"), id="theme without types"),
        pytest.param(VALID.replace('["war.arc"]', '["war.arc", "war.arc"]'), id="type repeated in a theme"),
        pytest.param(VALID.replace('["army.appeared"]', '["army.appeared", 3]'), id="type not a string"),
        pytest.param(
            VALID.replace('event_types = ["war.arc"]', 'event_types = ["war.arc"]\nweight = 2'), id="unknown key"
        ),
    ],
)
def test_a_malformed_file_is_refused(tmp_path: Path, text: str) -> None:
    with pytest.raises(ThemesError):
        load_themes(write(tmp_path, text))


def test_coverage_names_each_undecided_undeclared_and_doubly_decided_type() -> None:
    themed, undecided, *rest = sorted(KINDS)
    themes = ThemeFile(
        themes=(Theme("Wars", "Wars between nations.", (themed, "nation.no_such_type")),),
        unthemed=(themed, *rest),
    )

    result = coverage(themes)

    assert result == Coverage(undecided=(undecided,), undeclared=("nation.no_such_type",), doubly_decided=(themed,))
    assert not result.complete
