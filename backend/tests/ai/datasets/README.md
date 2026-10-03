# MT AI eval datasets

Eval cases for MT AI, in the format defined in
[ai-quality.md](../../../../docs/03-architecture/mt2/ai-quality.md#dataset-layout).

**Status (SB-1191, 2026-10-02):** seed cases only, taken from the first live
eval (SB-1144, `docs/03-architecture/mt2/ai.md`). There is no pytest runner
here yet. The cases are run against a live `/api/ai/chat` by the mt-dt
desktop app's **MT AI evals** screen (admin only), which reads this directory.

## What a live run can and can't check

These seeds run against **live prod data**, not the frozen fixtures
ai-quality.md asks for, so:

- `fixture` is `null` and `today` records when the case was written. It can't
  be pinned through the API.
- Answer checks (`answer_contains`, `answer_excludes`) are case-insensitive
  substring checks. Keep them to strings that stay true as data moves.
- `expect.tools` and `expect.args` (trajectory) document intent. The API
  doesn't return tool calls yet (SB-1197), so a live runner can't check them.
- `viewer` says who the question is asked as. A runner that can only ask as
  one user skips cases whose viewer sees different data (test-content
  visibility: admins and `is_test` users see test teams).

## Known failures

Tagged with the ticket that fixes them, so a run shows expected red:

| Case | Fails until |
|---|---|
| `team-age-mismatch-ifa-u12` | SB-1155 |
| `next-match-ifa-u15` | SB-1152 |
| `club-weekend-ifa` | SB-1207 |
