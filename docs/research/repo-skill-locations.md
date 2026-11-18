# Repo skills: where agents discover them

Research for [#575](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/575). Sources read on 2026-11-18.
Every fact cites the page or source file it came from; anything not confirmed by a primary source is marked
**Unconfirmed**.

## Answer

- **Claude Code** finds project skills only under `.claude/skills/<name>/SKILL.md` (and nested
  `<subdir>/.claude/skills/`). It does not read `.agents/skills/`.
- **OpenAI Codex** finds repo skills under `.agents/skills/<name>/SKILL.md`, in every directory from the working
  directory up to the repository root.
- There is no single directory both read natively. One copy can serve both by keeping the skill in one location and
  symlinking it from the other: both agents follow symlinked skill folders.
- The repo's current `skills/narrator-contract-iteration/` is read by neither agent. `skills/<name>/` is the layout of
  a Claude Code *plugin*, not a project.
- Front matter: `name` and `description` are what an agent sees before loading; `description` alone decides automatic
  loading. The existing skill's front matter already satisfies the shared standard.

## Claude Code

### Locations

Source: [Extend Claude with skills](https://code.claude.com/docs/en/skills).

| Scope | Path |
| --- | --- |
| Enterprise | `.claude/skills/<skill-name>/SKILL.md` in the managed settings directory |
| Personal | `~/.claude/skills/<skill-name>/SKILL.md` |
| Project | `.claude/skills/<skill-name>/SKILL.md` |
| Nested | `<subdir>/.claude/skills/<skill-name>/SKILL.md`, for sessions started in or below `<subdir>` |
| Added directory | `.claude/skills/` inside a directory passed with `--add-dir` or `/add-dir` |
| Plugin | `<plugin>/skills/<skill-name>/SKILL.md`, invoked as `/plugin-name:skill-name` |

- Project skills load from the start directory and every parent up to the repository root; nested skills load the
  first time Claude reads or edits a file in that subdirectory ([skills](https://code.claude.com/docs/en/skills)).
- Sharing a project skill means committing `.claude/skills/` ([skills, "Share
  skills"](https://code.claude.com/docs/en/skills)).
- Skill directories are watched; adding or editing a skill takes effect without a restart. A top-level skills
  directory created after startup needs `/reload-skills` ([skills](https://code.claude.com/docs/en/skills)).
- Legacy `.claude/commands/*.md` files still load as skills ([skills](https://code.claude.com/docs/en/skills)).

### `.agents/skills`

- The skills page lists no `.agents` location ([skills](https://code.claude.com/docs/en/skills)).
- Anthropic's own tracker has the request open:
  [anthropics/claude-code#31005](https://github.com/anthropics/claude-code/issues/31005) ("Support for AGENTS.md and
  .agents/skills/", open, reopened). A narrower user-level request,
  [#66352](https://github.com/anthropics/claude-code/issues/66352), was closed as not planned on 2026-07-16.
- Commenters on #31005 report that `.agents/skills/` is not discovered and that per-skill symlinks from
  `.claude/skills/` work. **Unconfirmed** by Anthropic; community reports only.

### Symlinks

"A `<skill-name>` entry in the enterprise, personal, or project location can be a symlink to a directory elsewhere on
disk. Claude Code reads `SKILL.md` from the target and loads the skill once even if several locations point at the
same target." ([skills](https://code.claude.com/docs/en/skills)). Plugin skills handle symlinks differently (same
page).

## OpenAI Codex

### Locations

Source: [Build skills](https://learn.chatgpt.com/docs/build-skills) (the target of the permanent redirect from
`https://developers.openai.com/codex/skills`).

| Scope | Path |
| --- | --- |
| Repo | `$CWD/.agents/skills`, `$CWD/../.agents/skills`, …, `$REPO_ROOT/.agents/skills` |
| User | `$HOME/.agents/skills` |
| Admin | `/etc/codex/skills` |
| System | bundled with Codex (`skill-creator`, `skill-installer`) |

- Codex checks `.agents/skills` in every directory from the working directory up to the repository root; skills with
  the same `name` are not merged ([build skills](https://learn.chatgpt.com/docs/build-skills)).
- Symlinked skill folders are followed ([build skills](https://learn.chatgpt.com/docs/build-skills)). The source
  agrees: user, repo and admin roots use `DirectorySymlinkPolicy::Follow`
  ([`codex-rs/ext/skills/src/loader/host.rs`](https://github.com/openai/codex/blob/main/codex-rs/ext/skills/src/loader/host.rs)).
- The source also adds a `skills/` folder next to each config layer: for a project config layer that is
  `.codex/skills` (scope Repo), and `$CODEX_HOME/skills` is kept as a "deprecated user skills location"
  ([`codex-rs/ext/skills/src/host_roots.rs`](https://github.com/openai/codex/blob/0b21a5b5264301bdb2e083c68c5ebd1d5cea0af9/codex-rs/ext/skills/src/host_roots.rs),
  `roots_from_layer_stack`). **Unconfirmed** as supported behaviour: the docs do not list `.codex/skills`, and a project
  config layer exists only for trusted projects, so do not rely on it.
- Restart Codex after changing skill configuration ([build skills](https://learn.chatgpt.com/docs/build-skills)).
- Codex does not read `.claude/skills/`. **Unconfirmed** as a stated rule; neither the docs page nor the
  `host_roots.rs` source lists it.

### Enabling and disabling

- `[[skills.config]]` entries in `~/.codex/config.toml` take a `path` or a `name` and `enabled = false`
  ([build skills](https://learn.chatgpt.com/docs/build-skills)).
- `[skills.bundled] enabled = false` in a trusted project's `.codex/config.toml` turns off the bundled system skills
  (same page).

## Shared convention

- Both vendors say their skills follow the [Agent Skills](https://agentskills.io) open standard
  ([Claude Code skills](https://code.claude.com/docs/en/skills); [build skills](https://learn.chatgpt.com/docs/build-skills)).
- The [specification](https://agentskills.io/specification) defines the skill directory and `SKILL.md` format only. It
  names no discovery directory, so `.agents/skills` is Codex's choice, not part of the standard.

## One directory for several agents

No native shared path exists for the two agents. Options, from the sources above:

1. **Skill in `.agents/skills/<name>/`, symlink at `.claude/skills/<name>`.** Codex reads it natively; Claude Code
   follows the project-level symlink.
2. **Skill in `.claude/skills/<name>/`, symlink at `.agents/skills/<name>`.** Equivalent; Codex follows the symlink.
3. **Copies in both.** No symlink, but two files to keep in step.

Git stores symlinks as links; a checkout on Windows without symlink support gets a plain text file instead.
**Unconfirmed** here (general Git behaviour, not from the agents' docs); it matters only if Windows contributors use
the skill.

## Front matter and loading

### Shared standard ([specification](https://agentskills.io/specification))

| Field | Required | Constraint |
| --- | --- | --- |
| `name` | yes | 1–64 chars, lowercase `a-z0-9` and hyphens, no leading, trailing or double hyphen, must match the parent directory name |
| `description` | yes | 1–1024 chars; what the skill does and when to use it |
| `license`, `compatibility`, `metadata`, `allowed-tools` | no | `compatibility` ≤ 500 chars; `allowed-tools` experimental |

Progressive disclosure: name and description load at startup; the body loads on activation; bundled files load as
needed (same page).

### Claude Code ([skills](https://code.claude.com/docs/en/skills))

- All fields are optional; `name` defaults to the directory name and `description` falls back to the first body
  line. The frontmatter `name` and the directory name both invoke the skill.
- Only descriptions sit in context; Claude uses `description` (plus optional `when_to_use`) to decide when to load.
  Their combined text is cut at 1,536 characters, and the whole listing is held to about 1% of the context window,
  dropping descriptions of the least-used skills first.
- `disable-model-invocation: true` keeps the skill out of automatic loading and out of context; `user-invocable:
  false` hides it from the `/` menu; `paths` limits automatic activation to matching files.
- Other Claude Code fields: `argument-hint`, `arguments`, `allowed-tools`, `disallowed-tools`, `model`, `effort`,
  `context`, `agent`, `background`, `hooks`, `shell`. Unknown fields are ignored; malformed YAML loads the body with
  empty metadata, so the skill is never matched automatically.

### Codex ([build skills](https://learn.chatgpt.com/docs/build-skills))

- `name` and `description` are required.
- Codex starts with each skill's name, description and path, and loads `SKILL.md` when selected. It picks a skill
  implicitly when the task matches the `description`, or explicitly through `/skills` or `$name`.
- The initial listing is held to 2% of the context window (8,000 characters if unknown); descriptions are shortened
  first and skills may be omitted. `skills.max_context_tokens` raises it up to 10,000 tokens.
- Codex-only metadata goes in an optional `agents/openai.yaml` inside the skill directory; its
  `policy.allow_implicit_invocation: false` blocks implicit selection, the Codex counterpart of Claude Code's
  `disable-model-invocation`.

### The existing skill

`skills/narrator-contract-iteration/SKILL.md` has `name: narrator-contract-iteration`, matching its directory, and a
description of about 300 characters that states use and non-use. It meets the standard and both agents' limits; only
its location keeps it from being discovered.
