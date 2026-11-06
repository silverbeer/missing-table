# MLS NEXT qualification — MissingTable data model & features

Proposal from the 2026–27 qualification research (SB-1544). Facts it relies on: [mls-next-qualification-facts.md](mls-next-qualification-facts.md); full analysis: [mls-next-qualification-2026-27.md](mls-next-qualification-2026-27.md). Not yet built — see SB-1549 for the first slice (rules YAML).

## Proposed model: sourced, versioned rules where nulls stay null

MissingTable already has `leagues → divisions`, Flex stored as its own league whose divisions are the Flex conferences, and a `match_types.counts_for_qualification` flag set for League and Flex. That structure matches how MLS actually runs the season. The **flag is too coarse**, though. It says that a match matters but not *which pathway* it feeds or *how it is scored*, and League and Flex differ on both. The proposal below keeps the existing tables as the physical layer and adds a rules layer on top. Every rule row carries a `source_url`, a `confidence` (CONFIRMED/INFERRED/UNKNOWN) and a `season`. This fits MT's provenance rule and its rule against treating absent values as zero: a slot count of `null` means "MLS has not said".

| Entity | Maps to / new | Key fields | Purpose |
|---|---|---|---|
| Competition | new (wraps `leagues`) | name, organiser, kind (`league`, `flex_conference_play`, `tournament`, `qualifier`, `showcase`) | MLS NEXT League, Flex conference play, Flex event, Fest, Cup, Regional Qualifier, Play-In |
| CompetitionSeason | new | competition_id, season_id, start/end, `rules_version` | Versioning anchor; 2025–26 and 2026–27 rules coexist |
| Division (tier) | new or reuse | name (`Homegrown`, `Academy`) | Tier, distinct from MT's current "division = conference" usage |
| AgeGroup | `age_groups` | label, birth-year rule per season | Already present |
| Conference | `divisions` (existing) | competition_season_id, tier, age_group, name, `kind` (`league`, `flex`, `ppp`) | Northeast vs Turnpike vs Northeast (PPP) |
| Club / Team | `teams`, `team_mappings` | club_id, age_group, conference memberships (many) | A team belongs to one league conference and one Flex conference |
| Match | `matches` | + `decided_by` (`regulation`, `shootout`, `forfeit`), `pk_home`, `pk_away`, competition_season_id, group_id | Shootouts change points; they must be stored, not reconstructed |
| StandingsRule | new | competition_season × conference kind: points scheme (W/SOW/SOL/D/L), ranking metric (`points`, `ppg`), ordered tiebreaker list, `confidence`, source_url | 3-1-0 League vs 3-2-1-0 Flex; tiebreakers left `UNKNOWN` until published |
| Standings | computed view | rank, pts, ppg, gd, `tiebreak_applied`, `as_of` | Shows *which* tiebreaker resolved a tie |
| Tournament / TournamentGroup | new (Fest, Flex event, Play-In, Qualifiers, Cup) | stage, group label, seeds, advancement rule | Atlanta groups of four, Cup bracket with byes |
| QualificationPathway | new | target (Cup 2027), tier, age_group set, name, source competition, `confidence`, source_url | "Flex Conference winner", "Flex group winner", "League play", "PPP", "QoP", "Play-In", "Regional Qualifier" |
| QualificationRule | new | pathway_id, selector (`rank<=N in each conference of kind X`, `winner of each group`, `winner of event`), pass-down rule, `confidence` | Declarative, so no per-age-group code |
| QualificationSlot | new | pathway_id, age_group, `count` (**nullable**), `count_confidence`, deadline | Academy 20/2/10 CONFIRMED; Homegrown splits `null` |
| TeamQualificationStatus | new | team, pathway, status (`clinched`, `in_position`, `alive`, `eliminated`, `unknown`), as_of, provenance (`official`, `computed`, `manual`) | History by season; computed and official kept apart |

Two design choices matter most. First, **pathways select from a conference *kind*, never a named conference**. "Rank 1 in every Flex conference" then survives realignment, and the 13-versus-14 question becomes a data fix, not a code change. Second, **status must allow `unknown`.** Under today's published rules MT can say "Harbor leads Turnpike, and Flex Conference winners enter the Cup". It cannot say "Harbor is in the top 20 of league play, therefore qualified". A computed status should never be written over an official announcement; the two are stored side by side.

## Feature priorities follow data certainty

| Priority | Feature | Why now | Blocker |
|---|---|---|---|
| P0 | **Correct Flex conference standings with shootout scoring**, labelled "This table decides a Cup route" | It is the clearest documented U15 Cup route, and a 1-1 draw scoring would mis-rank it | Confirm MT stores PK outcomes; verify 3-2-1-0 on an official table |
| P0 | **Two-table team page**: league conference and Flex conference side by side | Every Homegrown team lives in both; users conflate them | None |
| P1 | **Competition overview** (the flow above, per season, each edge tagged CONFIRMED/INFERRED with link) | Cheapest high-trust page; recruits managers by explaining stakes | None |
| P1 | **Qualification tracker** (position, games left, PPG, pathway status, "unknown" shown honestly) | The core adoption hook | League-play cutoff unpublished, so show it as unknown |
| P2 | **Cup tracker** (clinched teams by route, open slots where counts are known) | Academy counts are confirmed; Homegrown counts are not | Homegrown split |
| P2 | **Flex group simulator** | Useful in April | Official tiebreaker chain; ship with a "provisional rules" banner |
| P3 | **Probability projections** | Needs confirmed rules and complete fixtures | Most of the open questions below |
