"""Coverage for the generated regions of the command pages: they are current and the generator is strict."""

from __future__ import annotations

from pathlib import Path

import pytest

from tinarrative import cli
from tinarrative.reference_docs import DocsError, config_example, generate

COMMANDS = Path(__file__).resolve().parents[1] / "docs" / "commands"


def test_command_pages_are_current() -> None:
    stale = [page.name for page, text in generate(COMMANDS).items() if page.read_text(encoding="utf-8") != text]
    assert not stale, f"stale command pages {stale}; run make docs"


def _pages(tmp_path: Path, extra: str) -> Path:
    for page in COMMANDS.glob("*.md"):
        (tmp_path / page.name).write_text(page.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "extra.md").write_text(extra, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ("<!-- generated: options nosuch -->\n<!-- end generated -->\n", "unknown command"),
        ("<!-- generated: summary events -->\n<!-- end generated -->\n", "unknown region kind"),
        ("<!-- generated: options events -->\n<!-- end generated -->\n", "already generated"),
        ("<!-- generated: options save -->\n<!-- end generated -->\n", "command group"),
        ("<!-- generated: options events -->\n", "malformed or unclosed"),
    ],
)
def test_broken_regions_fail(tmp_path: Path, extra: str, message: str) -> None:
    with pytest.raises(DocsError, match=message):
        generate(_pages(tmp_path, extra))


def test_a_missing_region_fails(tmp_path: Path) -> None:
    (tmp_path / "empty.md").write_text("# Nothing generated\n", encoding="utf-8")
    with pytest.raises(DocsError, match="no page generates"):
        generate(tmp_path)


def test_a_restated_static_default_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    build = cli.build_parser

    def restating() -> object:
        parser = build()
        parser.add_argument("--extra", default="x", help="An extra option (default x).")
        return parser

    monkeypatch.setattr("tinarrative.reference_docs.build_parser", restating)
    with pytest.raises(DocsError, match="%\\(default\\)s"):
        generate(_pages(tmp_path, ""))


def test_every_leaf_command_has_exit_codes() -> None:
    assert generate(COMMANDS)
    assert all(codes[0][0] == cli.EXIT_SUCCESS for codes in cli.EXIT_CODES.values())


EXAMPLE = COMMANDS.parent / "configuration.example.toml"


def test_the_settings_example_is_current() -> None:
    text = EXAMPLE.read_text(encoding="utf-8")
    assert config_example(text) == text, "the settings example is stale; run make docs"


def test_a_changed_default_rewrites_only_its_value() -> None:
    text = EXAMPLE.read_text(encoding="utf-8")
    stale = text.replace("rivals_per_faction = 2", "rivals_per_faction = 7")
    assert stale != text
    assert config_example(stale) == text


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("rivals_per_faction = 2\n", ""), "add councilors.rivals_per_faction by hand"),
        (("article_words = 300\n", "article_words = 300\n# A retired key.\nretired = 1\n"), "not a setting"),
        (("# More rivals adds more councilors from other factions.\n", ""), "needs a comment line"),
        (("rivals_per_faction = 2", "# rivals_per_faction = 2"), "set it instead"),
        (("# jobs = 4", "jobs = 4"), "comment it out"),
        (("[councilors]", "[councillors]"), "unknown table"),
    ],
)
def test_a_broken_settings_example_fails(change: tuple[str, str], message: str) -> None:
    text = EXAMPLE.read_text(encoding="utf-8")
    assert change[0] in text
    with pytest.raises(DocsError, match=message):
        config_example(text.replace(change[0], change[1], 1))
