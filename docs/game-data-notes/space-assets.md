# Space assets: habs and ships by faction

Evidence base for the space stakes of the entity-scaled significance score
([ADR-0011](../adr/0011-significance-is-judged-once-and-scaled-by-stake.md), roadmap *Entity-scaled significance*). It records how the
habs and ships in a save divide between the alien faction and the human factions, so that a share of "space" can be
defined that behaves from the first save of a campaign to its late game. It follows the rules of the
[notes README](README.md): structure, counts, magnitudes and dates only; faction templates are named, players are not.

Observed on 2026-10-23 in the ten benchmark saves (`benchmarks/samples/`), read from the raw JSON:

| Campaign | Saves | Game dates |
| --- | --- | --- |
| Protectorate | 5 | 2026-02 to 2027-07 |
| Resist | 5 | 2045-08 to 2046-10 |

## How the counts were taken

- A hab is a `TIHabState` entry, owned by its `faction`; its weight is `tier` squared (`tier` ran 1 to 3 on every
  hab).
- A ship is a `TISpaceShipState` entry, owned by the `faction` of the `TISpaceFleetState` its `fleet` references;
  every ship of every save resolved to a faction this way. Its mass is `currentMass_kg`. Whether that figure
  includes the ship's propellant (`propellant_tons`) was not checked (*hypothesis*: it is the current wet mass).
- The alien faction is the one whose `templateName` is `AlienCouncil` (the
  [domain field map](domain-field-map.md)); every other faction is human.

## Alien and human holdings per save

| Save | Alien habs (Σ tier²) | Human habs (Σ tier²) | Human hab tiers 1 / 2 / 3 | Alien share of Σ tier² | Alien ships (mass) | Human ships (mass) | Alien share of ship mass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Protectorate 2026-02-13 | 4 (26) | 2 (2) | 2 / 0 / 0 | 0.93 | 6 (28.9 kt) | 0 | 1.00 |
| Protectorate 2026-04-15 | 5 (27) | 2 (2) | 2 / 0 / 0 | 0.93 | 6 (28.9 kt) | 0 | 1.00 |
| Protectorate 2026-12-16 | 5 (45) | 7 (7) | 7 / 0 / 0 | 0.87 | 7 (42.9 kt) | 0 | 1.00 |
| Protectorate 2027-04-01 | 7 (47) | 8 (8) | 8 / 0 / 0 | 0.85 | 6 (34.8 kt) | 0 | 1.00 |
| Protectorate 2027-07-16 | 13 (59) | 11 (11) | 11 / 0 / 0 | 0.84 | 6 (31.3 kt) | 0 | 1.00 |
| Resist 2045-08-01 | 23 (199) | 245 (1,389) | 67 / 56 / 122 | 0.13 | 217 (2,171 kt) | 328 (3,826 kt) | 0.36 |
| Resist 2045-11-01 | 25 (217) | 246 (1,395) | 68 / 55 / 123 | 0.13 | 220 (2,191 kt) | 327 (3,815 kt) | 0.36 |
| Resist 2045-11-22 | 26 (226) | 246 (1,403) | 67 / 55 / 124 | 0.14 | 223 (2,225 kt) | 327 (3,804 kt) | 0.37 |
| Resist 2046-02-22 | 27 (227) | 246 (1,403) | 67 / 55 / 124 | 0.14 | 224 (2,226 kt) | 351 (4,536 kt) | 0.33 |
| Resist 2046-10-08 | 18 (162) | 251 (1,437) | 64 / 62 / 125 | 0.10 | 215 (2,166 kt) | 373 (5,372 kt) | 0.29 |

Observations:

- **Early game, the aliens hold space.** Over the first eighteen months of Protectorate the alien faction held 84 % to
  93 % of the tier² weight and every ship. The human factions held tier-1 habs only: two at the start (one each for
  two factions), eleven across all seven by 2027-07. No human ship existed in any of these saves.
- **Late game, the humans do.** In Resist the human factions held 245 to 251 habs, half of them tier 3, and 63 % to
  71 % of the ship mass; the alien share of the tier² weight was 10 % to 14 %. In the first and last Resist saves one
  human faction alone held more than half of both (checked in those two only).
- **Consequence for a share of space.** A world total that includes the alien faction gives it nearly all of space
  in the early game, and so nearly half the world in any blend with Earth holdings. A total of human holdings alone
  is 2 tier² and no mass at the start, so one tier-1 station is half of it. Neither total is usable early without a
  floor. The late-game human totals (about 1,400 tier², 4 to 5 Mt) are the scale such a floor is calibrated against.
- Mass per hull class, which a battle stake needs because combat records carry hull counts only, is not recorded
  here yet.
