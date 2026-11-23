"""Coverage for the repository skill discovery layout."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _repo_skill_paths() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", ".agents/skills", ".claude/skills"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return set(result.stdout.splitlines())


def test_repo_skills_have_canonical_copies_and_claude_symlinks() -> None:
    tracked = _repo_skill_paths()
    canonical_skills = {
        path.split("/")[2] for path in tracked if path.startswith(".agents/skills/") and path.endswith("/SKILL.md")
    }
    claude_skills = {path.removeprefix(".claude/skills/") for path in tracked if path.startswith(".claude/skills/")}

    assert canonical_skills, "no canonical repo skills are tracked"
    assert claude_skills == canonical_skills

    for name in canonical_skills:
        skill_file = ROOT / ".agents" / "skills" / name / "SKILL.md"
        front_matter = skill_file.read_text(encoding="utf-8").split("---", 2)
        assert len(front_matter) == 3
        match = re.search(r"(?m)^name: ([\w-]+)$", front_matter[1])
        assert match is not None and match.group(1) == name

        link = ROOT / ".claude" / "skills" / name
        assert link.is_symlink()
        assert link.readlink() == Path("..") / ".." / ".agents" / "skills" / name
