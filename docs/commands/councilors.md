# `tinarrative councilors`

```
tinarrative councilors <path> [<path>...] [--campaign <selector>] [--player-only] [--output <dir>] [--config <file>]
                       [--send] [--force] [--profile <name>] [--provider anthropic|openai|openrouter|ollama]
                       [--model <id>] [--base-url <url>] [--max-output-tokens <tokens>] [--temperature <t>]
```

Selects the notable councilors of a campaign, builds the dossier a neutral, public-perception
article about each is written from, and builds one model request per councilor. Without `--send`
it is a dry run: it never contacts the network and never calls a model. Stdout gets a one-line
summary per selected councilor, and `--output` writes `dossier.json` and the requests. With
`--send` the requests go to the configured provider and the answers are assembled into
`councilors.md`, with the run record in `manifest.json`.

## Who is selected

From the latest save, a councilor needs at least `councilors.min_tenure_days` of employment
(365 by default) and a human faction. Alien-faction councilors, the unemployed pool and departed
councilors are never selected. Then:

- every councilor of the player's faction is selected;
- of each other human faction, the `councilors.rivals_per_faction` most prominent (2 by default).
  `--player-only` drops them.

Prominence ranks by organization tier squared (summed over the councilor's organizations), then
the skill sum, then XP, then entity ID. The player's faction is the one of the save's single human
player.

## Input

The same inputs as [`events`](events.md): one save, or several saves and directories of one
campaign (`--campaign` and the [campaign picker](events.md#campaign-picker) as there).

- **The portrait** comes from the latest save and may use everything in it, including
  councilors the other factions have not detected. `Loyalty` and `ApparentLoyalty` are never
  written, and neither are traits the public cannot see: cybernetic implants, covert tradecraft and
  pure game mechanics.
- **Visibility** sets how well known the article makes the person: `public` (a world-wide
  celebrity), `private` (high-level but out of the spotlight) or `shadow` (almost a rumor). It
  follows the councilor's espionage, with trait and organization bonuses, and how much the traits
  hide or expose the person; fame traits such as Famous or Megastar push strongly towards
  `public`, Low Profile and Undercover towards `shadow`. A trait the game always reveals rules out
  `shadow`; a low-profile trait rules out `public`.
- **The career** (faction, detention, status and organization changes) comes from the events
  between the saves. One save gives an empty career. Recruitment from the unemployed pool is not a
  career milestone: `recruited` dates it exactly, where the event could only date it to a save.
- **Missions** are listed for the player's councilors only. They come from the game's notification log, which
  keeps only the last two months of resolved missions per save, so with several saves each outcome is
  counted once across all of them; one save gives its own two months. Only the last
  `councilors.missions_window_years` years count; aborted missions do not. The dossier lists the
  `councilors.missions_per_councilor` most frequent mission types with their counts and most frequent regions,
  and says that it is a sample: the period covered and how many outcomes were seen. The mission a
  councilor is on now is listed separately as `active_mission`.

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `PATH...` | | One save, or save files and directories of one campaign. |
| `--campaign SELECTOR` | | The campaign to use when the saves hold several. |
| `--player-only` | off | Select the player's councilors only. |
| `--output DIR` | | Write `dossier.json` and the requests here; without it only the summary is printed. |
| `--config FILE` | `$TINARRATIVE_CONFIG`, else built-in | Settings file: the `[councilors]` selection keys and the `[narrator]` provider and profiles ([configuration](../configuration.md)). |
| `--jobs N` | `processing.jobs`, else bounded by CPUs and memory | With several saves, worker processes for surveying the saves and analyzing the intervals; `1` runs everything in one process. Small inputs run in one process. The output is the same for every value ([configuration](../configuration.md)). |
| `--send` | off | Send the requests to the provider ([Sending](#sending)). Needs `--output`. |
| `--force` | off | With `--send`, send every article again, even one with a matching stored response. |
| `--profile NAME` | | Apply the settings profile `[narrator.profiles.NAME]`. |
| `--provider`, `--model`, `--base-url`, `--max-output-tokens`, `--temperature` | | Override the `narrator` setting of the same name, as [`narrate`](narrate.md#provider-and-budget) does. |

## Requests

Each request holds the dossier header and one councilor's entry, with a request block naming the
councilor, the faction and the length (`about <councilors.article_words> words`). The system
prompt asks for an encyclopedia entry about the person's public standing: a lead, then background,
career and public profile ([narrator](../narrator.md#councilor-articles)). The same dossier always
gives the same request files, so a request can be reviewed, or run by hand against any model.

## Sending

**`--send` hands the dossier to the provider, a third party unless it runs on your machine**
(Ollama, or an OpenAI-compatible server at a local `base_url`). The requests carry no file paths,
but they do carry councilor, faction, nation and organization names.

`--send` needs `--output DIR`, a provider and a model (there is no default model), and, for
`anthropic`, `openrouter`, and for `openai` without a `base_url`, an `api_key_env` setting naming
the environment variable that holds the API key. Anything missing is a usage error and nothing is
contacted.

Articles are sent in dossier order. An article whose stored response was made from the same
request, provider and model is kept, not sent again; `--force` sends every article again. A failed
request, or a completion cut off at the output limit or refused, skips that article only: the run
goes on, the other articles are written, and the command exits 10 at the end. A rerun sends only
the missing articles and reuses the stored responses.

## Output

stdout gets the selection summary (as of the latest save, the player faction and, per councilor,
the faction, player or rival, rank and tenure), then what was written. With `--send` it adds one
line per article (`sent` or `kept`, with token counts) and names the articles file. With
`--output DIR`, the command writes:

```text
DIR/
  dossier.json       # the dossier
  requests/01.json   # one request per councilor, in dossier order
  responses/01.json  # with --send: one per completed article
  councilors.md      # with --send: the articles
  manifest.json      # with --send: the run record, written with councilors.md
```

`dossier.json` has a header (`as_of`, `source` as the file name of the latest save, `player_faction`
and the `selection` settings) and a `councilors` list, the player's councilors first. Each entry
carries identity, the profession in plain words (an intelligence officer, not the game's `Spy`),
gender (`male`, `female` or `null`), traits, the seven skills, the organization skills, age, home
region and nation, recruitment date and tenure, organizations, policy influence, prominence, career
and, for the player's councilors, missions and the active mission.

`skills` are the councilor's own values, implants included. `org_skills` are what their organizations
add on top: per skill, the sum of the organization bonuses, capped so that `skills` plus `org_skills`
never exceed the game's limit of 25. Only nonzero skills are listed in either.

`policy_influence` lists the causes the councilor's organizations push, from their nonzero priority
and space bonuses, strongest first: `economic growth`, `welfare spending`, `education and research`,
`government reform`, `national unity`, `military strength`, `law and order`, `environmental
protection`, `patronage`, `space mining`, `space program development`, `launch capacity` and `mission
control`.

`prominence` is audit data: the organization tier squared and the skill sum the ranking uses, the
capped organization skill sum (`org_skill_sum`, which does not affect the ranking) and the rank in
the faction.

Traits are listed by their in-game names (`Cautious`, not the game's `Averse`), grouped as
`temperament`, `expertise`, `reputation`, `circumstance` and `affiliation`. A trait this version does
not know yet is listed under `other`, its template name split into words.

An organization entry names its nature: `origin` (`generated` or `real`), `category` and the
`basis` of the category. A generated organization takes its category from its template (`template`).
A real-world organization takes it from a hand-assigned catalog of the game's named organizations
(`catalog`); one the catalog does not know yet is categorized by the effects it grants (`stats`). The
categories are `research`, `security_intelligence`, `military`, `militant`, `aerospace`, `government`,
`public_interest`, `commercial`, `engineering_industry`, `technology`, `mining_resources`,
`media_influence`, `ngo`, `criminal`, `vigilante` and `other`. The raw `template` is kept for audit.
`nation` is the name of the nation that holds the organization's home region now; it is `null` for
an organization without a home region, such as a faction's own special organization.

`councilors.md` opens with a header naming the provider, the model as reported, the prompt
version, the dossier date and the player faction, then one `##` section per faction, the player's
first, with one `###` article per councilor. It carries no citations. An article that was not
written is left out of it and listed in `manifest.json`, which records the prompt version, the
dossier hash, the selection and provider settings and, per article, the request hash, whether it
was written, the finish, the reason when it failed, and the token counts. When an article is
missing, stderr gets one summary line.

## Exit codes

| Code | When |
| --- | --- |
| 0 | The summary was printed and, with `--output`, the dossier and requests were written; with `--send`, every article was written. |
| 2 | Usage error: the save input errors of `events` (several campaigns without `--campaign`, fewer than two usable saves among several inputs); `--force` without `--send`; an unknown `--profile` or an invalid override; `--send` without `--output`, provider, model or API key, or over the context window. |
| 4 | A save cannot be read. |
| 5 | A save is not a supported save. |
| 8 | The settings file cannot be read or is not valid settings. |
| 9 | `--output`, or the articles and manifest, cannot be written. |
| 10 | `--send`: an article request failed (authentication, network, HTTP error, invalid response), or its completion hit the output limit or was refused. The other articles are written. |

## Examples

```sh
tinarrative councilors saves/Protectorate00092.json
tinarrative councilors saves/ --campaign protectorate --player-only --output profiles/
tinarrative councilors saves/ --campaign latest --output profiles/ --send --profile local
```
