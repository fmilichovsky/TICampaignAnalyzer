# Resist must-tell list: rough first take (PROTOTYPE, throwaway)

Draft for [Resist must-tell list: a rough first take](https://github.com/fmilichovsky/TICampaignAnalyzer/issues/532).
Untracked for now, like the transcript it is drawn from; both are to be committed. A thing to react to, not the list.

**Sources.** The 14 player turns of the transcript, split into 52 recalled episodes (2026 to 2043). The narrator
package of `real_saves/resist-2026-2046` (63 saves, 2026-08-01 to 2046-10-08, default settings): 1841 narrative
events, 54 campaign-defining, 1133 major, 633 minor. Four Sonnet subagents mapped the episodes onto a one-line digest
of the package; I re-checked every "not found" I rely on below and corrected three.

**Level** is the highest level at which the package states the episode. **Buried** means the fact is only evidence
under an event that says something else.

## The list

| # | Must-tell episode | Recalled | Data window | Level in package | How it is recognised today |
|---|---|---|---|---|---|
| 1 | Resistance milks the USA, then strips its nuclear arsenal before leaving | 2026-27 | 2026-08 to 2027-05 | defining (nukes 28 -> 0); inequality minor; democracy absent | `nation.nuclear_disarmament`; the Resistance holding the USA is only implied by "from the Resistance" |
| 2 | USA falls to Humanity First, turns to Russia | 2027-28 | 2027-02 to 2027-12 | major | `faction.takeover` + `nation.diplomatic_realignment` (allies +1/-42); the Initiative share is absent |
| 3 | Resistance moves into China | 2027 | 2026-08 to 2027-05 | defining | `faction.takeover_wave` (6 nations) + `faction.takeover` |
| 4 | Russia arms and swallows Ukraine | late 2027 | by 2029-08 | major, annexation **buried** | `war.arc` "4 regions changed hands"; Kyiv, Kharkiv, Donetsk, Odesa only as evidence; armies 2 -> 4 as `nation.military_buildup`; no navy or modernisation |
| 5 | China becomes a space power | 2027-29 | 2027-05 to 2030-08 | **minor 37** | `nation.space_program_growth` (mission control 4 -> 52) |
| 6 | First Moon base | early 2028 | 2027-02 to 2027-05 | defining | `campaign.first_milestone`; "mining" not stated |
| 7 | First Mars colonies | 2029-30 | 2028-02 to 2029-08 | defining | `campaign.first_milestone` + `faction.colonisation_wave` (Mars, Deimos, 4 habs) |
| 8 | Resistance takes the rump EU and the UK | early 2029 | 2028-02 to 2029-08 | major | `faction.takeover` x2 + `federation.lifecycle` (21 member changes); Germany comes a year later; no France event |
| 9 | The bloc reunifies Europe by force | 2030-33 | 2029-08 to 2035-05 | defining, **15 times** | 15 `war.arc` lines (14 defining), each "16 regions changed hands"; about 7 `nation.merger`; one `nation.expansion` (major) holds the whole result |
| 10 | Türkiye is annexed into Europe | 2033 | 2033-08 to 2033-11 | **buried** | Ankara, Istanbul, Diyarbakir change hands as evidence of the "United Kingdom-Denmark War" arc; no line names Türkiye's fall |
| 11 | Resistance takes Japan, the bloc's military arm | 2032 | 2031-02 to 2031-08 | takeover major; military rise absent | `faction.takeover`; Japan only shows as a war participant from 2031-12; "top 10 by strength" in 2044 |
| 12 | India's long war with Egypt and its collapse | 2030-32 | 2028-03 to 2031-09 | major | `war.arc` India-Egypt; armies 3 -> 5; no unrest, coup or regime event; control passes Protectorate -> Academy (2033) |
| 13 | Akhand Bharat forms | 2032-33 | 2033-08 to 2034-11 | major, says nothing | `federation.lifecycle` "no net change"; formation and end are not events |
| 14 | Singapore and Brunei join for launch sites; India attacks Brunei | 2033 | 2033-01 to 2036-12 | takeovers major/minor; war defining | `faction.takeover`, `war.arc` India-Brunei (EU, Japan on Brunei's side; China absent) |
| 15 | China and Taiwan unify under Taipei | late 2033 | 2033-11 to 2034-01 | major | `nation.merger` "Republic of China absorbed China"; democracy not stated |
| 16 | The Caliphate is born, takes Saudi Arabia, claims the Muslim world | 2034 | 2033-06 to 2034-11 | major | `nation.release`, `nation.merger`, `nation.claims_declared` (claims dated 2033 and 2036) |
| 17 | Indonesia changes hands | spring 2034 | 2034-01 to 2034-07 | major | `faction.takeover` from Exodus; no war, so "military operation" is unsupported |
| 18 | Resistance coup in India | Aug 2034 | 2034-01 to 2034-11 | major | `faction.takeover` "holds every control point"; demobilisation 4 -> 2 dated 2036; unrest and regime absent |
| 19 | Caliphate wars in Arabia: Yemen, UAE, Oman | early 2035 | 2034-11 to 2043-03 | defining x3 | three `war.arc` lines, all closing at the 2043 save |
| 20 | Caliphate across North Africa; Pakistan and Iran merge in | 2035-37 | 2037-05 to 2039-09 | major | `nation.merger` (Egypt 2037, Iran 2038-39, Morocco 2039), `nation.expansion` to 2043 |
| 21 | India absorbs Bangladesh, Nepal, Bhutan | 2035-37 | 2037-09 to 2039-02 | major | `war.arc` x2 + `nation.merger`; no Nepal war |
| 22 | Southeast Asia federates, becomes the Pan-Asian Combine, then one nation | 2037-40 | 2037-05 to 2044-02 | defining x4, about 25 lines | `federation.lifecycle` x3, `nation.expansion`, `nation.claims_declared`, `nation.merger` x5; the rename and China joining are not events |
| 23 | China takes Myanmar, Laos, Cambodia | 2037-39 | 2038-10 to 2044-02 | defining x3 | three `war.arc` lines "5 regions changed hands" |
| 24 | Russia attacks the Philippines; the Resistance seizes Russia | late 2039 | 2039-03 to 2039-10 | major | `war.arc` Eurasian Union-Philippines (May to Sep) + `faction.takeover`; Thailand, Bangkok and the peace absent |
| 25 | Russia stands down | early 2040 | 2036-07 to 2040-10 | major / minor | `nation.demobilization` 5 -> 2; mission control 26 -> 38 minor; rivalry end absent |
| 26 | The grand federation: Caliphate and Russia with the EU, Russia dissolves | 2042 | 2041-05 to 2044-06 | defining | `federation.lifecycle` (20 member changes; adds Australia, Canada, PAC, African Union, Japan; Russia never a member); Kazakhstan -> Caliphate found; EU absorbs Russia 2044; Siberia, Tajikistan, Kyrgyzstan not found |
| 27 | The African Union | 2042 | 2041-10 to 2046-10 | major, about 20 lines | `faction.takeover` (from the Initiative, Kenya from HF), `nation.claims_declared`, `nation.expansion` |
| 28 | England restored and claims the Commonwealth | 2043 | 2041-10 to 2043-03 | major | `nation.release` + `nation.claims_declared`. **After the cut-off:** England and the Southern Cross join the EU federation (2043-03 to 2044-02), Canada becomes a rival of England and Japan (same window), and all 9 Canadian regions plus Australia pass to the United Kingdom between 2044-06-16 and 2044-11-22. No war, no army event: the month-long operation fell inside one save gap |
| 29 | California and Texas break away | 2043 | 2044-06 to 2044-11 | major, **after the cut-off** | `nation.breakaway` x2; off the list |
| 30 | Mars fully settled by the Resistance | by 2034 | none | not found | no Resistance Mars wave after the first 4 habs; the space economy (research share, net income) is accepted as not captured |
| 31 | Orbital war: raids on Earth-orbit stations, Mars sites lost and rebuilt | 2032-34 | 2031-09 to 2034-01 | major 62, flat | `faction.space_campaign`: "habs lost at Earth, Mars", sides ambiguous, nothing about docking or rebuilding |
| 32 | First offensive against the aliens at 391 Ingeborg | Feb 2040 | 2040-02-09 to 2040-02-14 | **buried**, exact | atomic `faction.hab_destruction_recorded`: alien base destroyed 2040-02-09, station 2040-02-14, a battle logged 2040-02-09; the first alien hab the Resistance ever destroyed. Lost in one open `faction.space_campaign` line covering 2030 to 2046 |
| 33 | Clean energy turn in the EU, PAC, India | 2040 | none | no event kind | only the global `ClimateChangeMitigation` tech; a project to keep in the allowlist revision (#296) |
| 34 | Nuclear proliferation among the middle powers | not recalled | 2032 to 2043 | major | `nation.nuclear_armament` / `nuclear_buildup`: South Korea, Taiwan, Iran, Israel, Egypt, Brazil |
| 35 | Fusion, then antimatter | not recalled | 2034-07 to 2037-10 | defining x2 | `technology.milestone` |
| 36 | The rest of the world was not idle | not recalled | whole sample | defining and major | rival `faction.takeover_wave` lines (Humanity First 12 nations, Protectorate 12 and 13, Initiative 9), their wars (India, Russia, Egypt, Brazil) |
| 37 | The aliens keep spreading | not recalled | whole sample | defining and major, as stand-out events | `faction.colonisation_wave`; wanted as one constant background thread, not single events |

## Where memory and data part

**Dates.** Early game is recalled about a year late (Moon base, Mars, Japan); from 2035 on it is recalled one to two
years early (Iran, India's neighbours, Russia into the EU, California and Texas). Save gaps of up to 18 months widen
every window, so only the Moon base, Japan and the breakaways are clear misses.

**What the recollection leans on that the data cannot carry.**
- Motives and method: the coup, the opinion campaign, "peaceful" against "forced", why Japan stayed outside.
- Who backed whom. Alliances and blocs exist only as participant lists of war arcs.
- Things that did not happen: China's neutrality, Japan and Singapore staying out.
- Regime and society: democracy level, inequality, emissions. The USA's inequality is minor; no democracy shift fires
  for the USA, India or unified China.
- Space as an economy and as single battles.

**What the recollection leaves out and the package ranks high.**
- Other factions: Humanity First's 12-nation wave (defining), the Initiative's and Protectorate's waves, the Servants'
  and the Protectorate's endgame projects (both defining).
- The aliens: their spread over Saturn's moons (defining), then Jupiter's.
- Technology: fusion and antimatter (both defining), 132 major milestones.
- Space firsts after Mercury: first victory over the aliens 2031, Kuiper belt 2036, Jupiter 2041-42, Uranus 2044.
- Nuclear proliferation: South Korea, Taiwan, Iran, Israel, Egypt, Brazil.
- The bloc's side wars: Yemen 2032, Laos 2033, Kosovo, Sudan, Timor-Leste, Mongolia, and a dozen Caliphate wars in
  West Africa.
- Resistance takeovers it never names: Israel, North Korea, Pakistan, South Korea, Saudi Arabia.
- The EU disbanding its armies (4 -> 0, major 73).
- Everything after early 2043: the Nigeria and Congo wars, Russia absorbed, the USA retaken.

## What this says about the package

1. **One episode, many top-level events.** 30 of the 54 defining events are war arcs. Europe's reunification is 15 of
   them with the same "16 regions changed hands". The recollection has about 3 episodes a year; the package has about
   58 events a year at major or above.
2. **The outcome is buried under the wrong name.** A war arc carries the name of the first war declared, so Türkiye
   falls inside the "United Kingdom-Denmark War" and Ukraine inside "4 regions changed hands".
3. **Takeovers are flat.** 265 major takeovers; the USA, China, Japan, India and Russia sit at the level of Senegal.
4. **The player's own policy is under-ranked.** China's space programme is minor 37; Japan's military rise does not
   exist.
5. **Federation events can be empty.** "No net change" at major or defining for Akhand Bharat and the early PAC.
6. **Space combat has no shape.** Flat 62, one 16-year line, sides ambiguous.
7. **Names drift.** Russia / Eurasian Union, China / Republic of China / Pan-Asian Combine, England / United Kingdom.

## Settled with the dev (2026-11-17)

- **An entry is an arc.** Europe's reunification was one manoeuvre of many annexations and should read as one.
  Whether that connection can be inferred deterministically stays open.
- **Cut-off: the 2043-03-16 save.** Rows 29 and the Canada and merger half of row 28 fall after it.
- **Space economy:** not captured, accepted. Too many income sources to reconstruct from saves.
- **Ingeborg:** on the list. The data confirms the recollection to the week.
- **Clean energy:** on the list as a project worth tracking, through the allowlist revision (#296).
- **Faction special projects** (the rival endgames included) are expected to drop out in #296: they read as public
  statements and the narrator fixates on them. Fusion and antimatter stay.
- **Other factions' geopolitics** belongs on the list when notable: a blind spot of the player's own view.
- **Alien colonisation** is a constant serious background thread, not stand-out events. Alien operations on Earth
  are a different matter and a massive deal (#304, #221).
- **Proliferation:** on the list.
