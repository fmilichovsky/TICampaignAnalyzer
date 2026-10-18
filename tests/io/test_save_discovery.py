"""Expanding command-line paths into candidate save files."""

from pathlib import Path

from tinarrative.io.save_discovery import expand_inputs


def test_expand_inputs_is_sorted_and_one_level_deep(tmp_path: Path) -> None:
    saves = tmp_path / "saves"
    (saves / "nested").mkdir(parents=True)
    for name in ("b.json", "a.json", "nested/ignored.json"):
        (saves / name).write_text("{}", encoding="utf-8")
    empty = tmp_path / "empty"
    empty.mkdir()

    inputs = expand_inputs([saves, tmp_path / "missing.json", empty])

    assert [(item.path.name, item.explicit, item.empty_directory, item.directory) for item in inputs] == [
        ("a.json", False, False, saves),
        ("b.json", False, False, saves),
        ("missing.json", True, False, None),
        ("empty", True, True, None),
    ]
