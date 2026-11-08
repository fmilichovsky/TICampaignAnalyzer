# Configuration

Settings come from `--config`, then `TINARRATIVE_CONFIG`, then built-in defaults. The example file is the only
place that describes each key. Copy it and remove keys you do not change; a test keeps it equal to the defaults.

## File format and validation

Settings use UTF-8 TOML. The accepted tables are `[events]`, `[llm]`, `[llm.profiles.NAME]`, `[councilors]` and
`[processing]`. Unknown tables and keys, wrong types, invalid choices and values below their minimum fail with
exit code 8 and name the setting.

Each `[llm.profiles.NAME]` table accepts the same keys as `[llm]`. Profile values override `[llm]` values,
and command flags override both. API keys are read from the environment variable named by `llm.api_key_env`; the key itself is
never stored or reported. `--period` selects quarter, half-year or year chapters.

## Reproducibility

`events --format json --narrative` records its effective `[events]` settings. Markdown reports identify
non-default event settings. `plan.json` records the LLM budget values used to make the chapter plan; existing
run directories remain assemblable.

## Adding a setting

A setting earns a place only when a player would change it for a different story, budget or connection. Other
values are named constants next to the rule that uses them. Document a setting only in
`configuration.example.toml`, with a short comment that says how raising or lowering it changes the result.
