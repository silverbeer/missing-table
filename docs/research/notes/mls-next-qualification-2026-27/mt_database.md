# MissingTable production database — measured, 2026-11-05

Source: read-only SQL against the MissingTable prod database (scraped from MLS NEXT), season `2026-2027`, age groups U15/U16/U17/U19. This is first-party measured data, not an official MLS rule source; it is reliable for *which tables exist and who plays in them*, not for qualification rules.

## Finding 1: Flex conferences are a separate league, not Homegrown divisions

MT stores Flex matches under a league named `Flex`, with match type `Flex`. Its divisions are the **Flex conferences**. Homegrown league divisions carry only `League` matches. No Homegrown division is named Empire, New England or Turnpike.

Flex conferences present in MT, identical set at U15, U16, U17 and U19 — **13 per age group**:
Empire, Florida, Frontier, Mid-America (East), Mid-America (West), Mid-Atlantic (North), Mid-Atlantic (South), New England, Northwest, Southeast, Southwest (North), Southwest (South), Turnpike.

The official 2026–27 release refers to **14** "regular-season Flex Conference winners". MT sees 13 at every age group. Unresolved: a 14th conference MT's scraper does not see, or a different meaning of "Flex Conference". (Independent unofficial site also showed 13 at U15.)

Flex match counts (scheduled / played) in the three Northeast-area Flex conferences:

| Conference | U15 | U16 | U17 | U19 |
|---|---|---|---|---|
| Empire | 16 / 3 | 20 / 6 | 22 / 8 | 21 / 9 |
| New England | 21 / 12 | 32 / 17 | 33 / 18 | 32 / 17 |
| Turnpike | 31 / 14 | 45 / 21 | 42 / 18 | 44 / 20 |

## Finding 2: Homegrown League divisions (regular-season conferences)

Homegrown `League` divisions with matches in 2026–27:
- All four age groups: Florida, Frontier, Mid-America, Mid-Atlantic, Northeast, Northwest, Southeast, Southwest.
- **Pro Player Pathway divisions exist only at U16, U17, U19** (not U15): Central (PPP), Northeast (PPP), Southeast (PPP), West (PPP) — 7–8 teams each. Consistent with the PPP play-up rule (MLS academy U15 plays in U16).

Northeast (League):

| Age | Teams | Matches scheduled | Played |
|---|---|---|---|
| U15 | 20 | 190 | 51 |
| U16 | 19 | 171 | 46 |
| U17 | 19 | 171 | 46 |
| U19 | 19 | 171 | 46 |

190 = C(20,2) and 171 = C(19,2): a **single round-robin**, each team plays every other team once (U15: 19 games per team; U16–U19: 18). Measured, not an official figure.

Northeast (PPP): 7 teams, 42 matches = 7×6 → double round-robin (12 games per team) at U16/U17/U19.

## Implication

A Northeast Homegrown team appears in **two tables at once**: its Northeast (League) conference table and one Flex conference table (Empire, New England or Turnpike). Flex results are a separate table. Per the official release, the Flex Conference winners are tied to MLS NEXT Cup (bye race), so the Flex conference table is where a Cup route is visible in MT data.
