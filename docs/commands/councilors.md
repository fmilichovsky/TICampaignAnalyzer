# `tinarrative councilors`

<!-- generated: synopsis councilors -->
```
tinarrative councilors [--campaign SELECTOR] [--player-only] [--output DIR] [--send] [--force]
                       [--profile NAME] [--provider {anthropic,openai,openrouter,ollama}]
                       [--model MODEL] [--base-url URL] [--max-output-tokens TOKENS]
                       [--temperature TEMPERATURE] [--config FILE] [--jobs N]
                       PATH [PATH ...]
```
<!-- end generated -->

Writes a short encyclopedia article about each notable councilor of a campaign, as the public sees them, with an LLM.
It selects the councilors, builds a dossier and one model request per councilor. Without `--send` it contacts nothing:
review the requests, or run them by hand against any model. With `--send` it sends them and collects the articles in
`councilors.md`. Read [sending to a model](README.md#sending-to-a-model) before the first `--send`.

## Examples

```sh
# Who would get an article? Prints the selection only.
tinarrative councilors saves/Protectorate00092.json

# Write the dossier and requests for the player's councilors.
tinarrative councilors saves/ --campaign protectorate --player-only --output profiles/

# Write the articles with the "local" settings profile.
tinarrative councilors saves/ --campaign latest --output profiles/ --send --profile local
```

Saves are chosen as described in [saves and campaigns](README.md#saves-and-campaigns). One save is enough, but **pass
every save of the campaign** for a fuller record: careers come from the changes between saves, and each save
remembers only about two months of missions.

## Who is selected

Every councilor of the player's faction, plus the two most prominent of each other human faction, once employed for a
year. `--player-only` drops the rivals; `councilors.rivals_per_faction` and `councilors.min_tenure_days` in the
[settings](../configuration.md) change the numbers.

Articles are written from the latest save as a whole, so they can mention councilors that other factions have not
detected. Keep that in mind before sharing them during a campaign.

## Options

<!-- generated: options councilors -->
| Option | Meaning |
| --- | --- |
| `PATH...` | One save, or saves and directories of one campaign; a directory is read one level deep. |
| `--campaign SELECTOR` | The campaign to use when the saves hold several: a key, a unique key prefix, a listing number or 'latest'. |
| `--player-only` | Select only the player's councilors. |
| `--output DIR` | Write dossier.json and one request per councilor here. |
| `--send` | Send the requests to the provider and write councilors.md; needs --output. Hands the dossier to a third party unless the provider runs locally. |
| `--force` | With --send, send every article again, even one with a matching stored response. |
| `--profile NAME` | Apply the settings profile llm.profiles.NAME. |
| `--provider anthropic\|openai\|openrouter\|ollama` | Override llm.provider. |
| `--model MODEL` | Override llm.model; there is no default model. |
| `--base-url URL` | Override llm.base_url. |
| `--max-output-tokens TOKENS` | Override llm.max_output_tokens. |
| `--temperature TEMPERATURE` | Override llm.temperature. |
| `--config FILE` | TOML settings file (default: $TINARRATIVE_CONFIG, else the built-in settings). |
| `--jobs N` | Worker processes; 1 runs everything in one process; the output is the same (default: processing.jobs). |
<!-- end generated -->

## Output

stdout gets the selection: per councilor the faction, player or rival, rank and tenure. With `--send` it adds one line
per article, `sent` or `kept`. With `--output DIR`, the command writes:

```text
DIR/
  dossier.json       # the dossier
  requests/01.json   # one request per councilor
  responses/01.json  # with --send: one per completed article
  councilors.md      # with --send: the articles
  manifest.json      # with --send: the run record
```

`councilors.md` has one section per faction, the player's first. A failed article is left out and listed in
`manifest.json`; the others are still written, the run exits 10, and a rerun sends only the missing ones.

## Exit codes

<!-- generated: exit-codes councilors -->
| Code | When |
| --- | --- |
| 0 | The summary was printed; with --send, every article was written. |
| 2 | Usage error, no campaign chosen, or --send without --output, a provider, a model or an API key. |
| 4 | A save cannot be read. |
| 5 | A save is not a supported save. |
| 8 | The settings file cannot be read or is not valid settings. |
| 9 | --output cannot be written. |
| 10 | An article request failed, or its completion was cut off, refused or empty; the other articles are written. |
<!-- end generated -->
