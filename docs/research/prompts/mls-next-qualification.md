# MLS NEXT Competition & Qualification Research

## Objective

Research and document the official MLS NEXT competition structure and qualification process for the 2026–27 season.

The primary focus is the U15 Allstate Homegrown Division, particularly the Northeast Conference.

We want to understand exactly how clubs qualify for:

1. MLS NEXT Fest
2. MLS NEXT Flex
3. MLS NEXT Cup
4. Any additional qualification competitions or pathways

This research will eventually inform features in MissingTable.com, including standings, qualification tracking, tournament schedules, and team qualification projections.

**Important: This is initially a research and analysis task. Do not modify application code or database schemas until the research and proposed data model have been reviewed.**

## 1. Official Sources

Prioritize official MLS NEXT sources:

- https://www.mlssoccer.com/mlsnext/
- https://www.mlssoccer.com/news/
- Official MLS NEXT competition announcements.
- Official MLS NEXT competition rules and regulations.
- Official MLS NEXT standings and schedules.

Use secondary sources only when official information is unavailable.

For every important rule, capture:
- Source URL.
- Publication or update date.
- Applicable season.
- Applicable age group.
- Applicable division.
- Exact rule or a concise summary.
- Whether the information is confirmed or inferred.

Do not carry forward rules from previous seasons without confirming they remain applicable to 2026–27.

## 2. MLS NEXT Competition Structure

Document the complete competition structure for the 2026–27 season.

Investigate:

- Age groups U13 through U19.
- Allstate Homegrown Division.
- Academy Division.
- Conference structure.
- Regional structure.
- Regular-season competition.
- Flex Conference.
- MLS NEXT Fest.
- MLS NEXT Cup.
- Generation adidas Cup.
- Regional Cup Qualifiers.
- Pro Player Pathway.

Explain how these competitions relate to each other.

Create a competition flow diagram showing the progression from regular-season competition through qualification and ultimately MLS NEXT Cup.

## 3. MLS NEXT Fest

Research the 2026 MLS NEXT Fest.

Answer:

- Which age groups participate?
- Which divisions participate?
- How are teams selected or invited?
- Is attendance automatic or qualification-based?
- How many games does each team play?
- Is there a guaranteed minimum number of games?
- Are games competitive, showcase-only, or qualification-based?
- Does the new Academy Division Play-In apply to all age groups?
- How does the Play-In affect MLS NEXT Cup qualification?
- Are there standings or elimination rounds?
- What are the rules for tied games?
- Are penalty kicks used?

Distinguish between the general showcase format and the specific qualification competitions held during Fest.

## 4. MLS NEXT Flex

Research the 2027 MLS NEXT Flex competition.

Answer:

- What teams qualify for Flex?
- How are teams seeded?
- Is seeding based on regular-season standings?
- How are conferences represented?
- How many teams participate?
- How many groups are created?
- How many teams are in each group?
- How many games does each team play?
- Is it round-robin?
- How are group standings calculated?
- What happens when teams finish tied on points?
- Are head-to-head results used?
- Are goal differential and goals scored used?
- Are penalty kicks used for tied matches?
- Does every group winner qualify automatically for MLS NEXT Cup?
- Are there additional qualification pathways?

Provide an example of a four-team Flex group and explain exactly how the group winner is determined.

Do not assume that a tied group-stage game goes to penalty kicks. Verify the actual competition regulations.

## 5. MLS NEXT Cup Qualification

This is the most important section.

Document the complete qualification process for each age group and division.

For U15–U19 Allstate Homegrown:

- How many teams qualify per age group?
- How many qualify through regular-season competition?
- How many qualify through Flex?
- What is the Pro Player Pathway?
- Are there conference-specific qualification slots?
- Are Flex group winners guaranteed qualification?
- Are there wild-card or at-large selections?
- What happens when a qualified team declines its spot?

For Academy Division:

- How many teams qualify?
- How many qualify through regular-season league play?
- How many qualify through the Fest Play-In?
- How many qualify through regional Cup Qualifiers?
- How are those regional competitions structured?

For U13–U14:

- Explain the Quality of Play ranking system.
- Explain TAKA and how it is used.
- Determine whether wins and losses directly determine qualification.

Create a qualification matrix for every age group and division.

## 6. U15 Allstate Homegrown: Northeast Conference

Investigate the specific qualification pathway for U15 Allstate Homegrown Northeast Conference clubs.

Determine:

- How many clubs participate?
- What are the regular-season standings?
- How many regular-season matches are scheduled?
- Are there separate Flex Conference standings?
- How are teams seeded into Flex?
- How many Northeast teams qualify for MLS NEXT Cup through regular-season performance?
- How many qualification opportunities exist through Flex?
- Are there conference-specific qualification allocations?
- What are the tiebreaking rules?
- How do results against other conferences affect qualification?

If official qualification allocations are not published, explicitly identify this as an unresolved question.

Do not invent qualification slots or assume the conference standings directly translate into MLS NEXT Cup qualification.

## 7. Data Model Recommendations for MissingTable

After completing the research, propose a data model that could support this competition structure.

Consider these entities:

- Competition
- CompetitionSeason
- Division
- AgeGroup
- Conference
- Club
- Team
- Match
- Standings
- Tournament
- TournamentGroup
- QualificationRule
- QualificationPathway
- QualificationSlot
- TeamQualificationStatus

The model should support:

- Different qualification rules by season.
- Different qualification rules by age group.
- Different rules by division.
- Conference-specific qualification.
- Multiple qualification pathways.
- Tournament group standings.
- Tiebreaking rules.
- Qualification status and projections.
- Historical qualification records.

Avoid hardcoding qualification logic into individual age-group implementations.

Qualification rules should be configurable and versioned by season.

## 8. Potential MissingTable Features

Recommend how MissingTable could expose this information to users.

Potential features:

### Competition Overview
Show the structure of MLS NEXT competitions and qualification pathways.

### Qualification Tracker
For each team, show:
- Current league position.
- Qualification status.
- Qualification pathway.
- Remaining matches.
- Points required or projected.
- Distance from qualification.
- Flex seeding position.
- Probability or confidence of qualifying, if sufficient data exists.

### Flex Simulator
Allow users to simulate:
- Match results.
- Group standings.
- Tiebreakers.
- Qualification outcomes.

### MLS NEXT Cup Tracker
Show qualified teams, remaining qualification slots, and qualification routes.

## 9. Required Deliverables

Produce the following documents:

1. **Official Rules Summary:** A detailed explanation of the 2026–27 MLS NEXT competition and qualification rules.
2. **Qualification Matrix:** Age group, division, qualification pathway, number of teams, and relevant deadlines.
3. **U15 Homegrown Northeast Analysis:** A detailed breakdown of the pathway for Northeast clubs.
4. **Competition Flow Diagram:** Visual representation of the entire competition structure.
5. **MissingTable Data Model:** Recommended entities, relationships, and configuration strategy.
6. **Feature Recommendations:** Prioritized MissingTable product enhancements.
7. **Open Questions:** Any rules that could not be verified from official sources.

## 10. Accuracy Requirements

- Use 2026–27 rules only unless explicitly comparing historical seasons.
- Cite official sources for every qualification rule.
- Distinguish official rules from assumptions.
- Do not infer qualification slots from the total number of Cup participants.
- Do not assume all divisions use the same format.
- Do not assume Fest participation means Cup qualification.
- Verify whether tied Flex matches go to penalties.
- Identify any inconsistencies between official announcements and competition regulations.
- Clearly flag information that cannot be confirmed.

## Final Question

At the end of this research, answer:

**For a U15 Allstate Homegrown team competing in the Northeast Conference, what exactly must the team accomplish during the regular season and Flex to qualify for the 2027 MLS NEXT Cup?**

Provide a concrete example using a hypothetical team and explain the possible qualification scenarios.
