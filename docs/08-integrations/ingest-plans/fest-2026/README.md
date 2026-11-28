# Fest 2026 Academy teams: plan-20261128T184043-a784296a

Applied to **prod** on 2026-11-28 with `mt ingest apply` (see
[tournament-team-plan.md](../../tournament-team-plan.md)).

| File | |
|---|---|
| `fest-2026-plan.json` | the reviewed plan, with the approvals as applied |
| `fest-2026-plan.applied.json` | what each action created: the only complete record of the rows (needed to undo) |
| `brackets.json` | Academy conference per club and age group, built from the assist feed `mls-next-2-academy-division-26-27` |

The `--teams` input was `match-scraper-agent scrape-event --source assist --event mls-next-fest-allstate-homegrown-division --json` (2,492 messages), not kept here.

## Review decisions

- 70 actions approved as proposed (64 Academy teams created under the club's existing row, 6 aliases).
- 10 clubs whose name ends in "Academy": team named `<Club> AD` rather than `<Club> Academy Academy`.
- 9 clubs MT had never seen created, after checking that none of the near matches is the same club.
- `Seacoast United` (Academy) aliased to Seacoast United Bedford (129): Fest's squads 9609/9611 are Bedford's in the Academy league feed.
- Held: 9 actions on clubs in a known duplicate pair (SB-1861). Not approved: Best of East / Best of West all-star sides.

Result: 83 teams and 9 clubs created, 0 refused, 0 duplicate names.
