---
name: mt-admin
description: Missing Table admin work through mt-mcp — today, triaging ingest failures (team, division and league names the match scraper could not resolve) and closing the ones fixed at the sender. Use when the user asks what the scraper dropped, why matches are missing after a load, to triage or clean up ingest failures, or to close/resolve one. Requires the mt-mcp server (tools list_ingest_failures, resolve_ingest_failure).
allowed-tools: Bash, Read
---

# MT admin (via mt-mcp)

Admin operations on Missing Table go through **mt-mcp**, MT's MCP server
(`docs/03-architecture/mt2/mcp.md`). The tools run as *you* — the token comes from
your `mt login` session — and every call is recorded with your user id. Never reach
for the database or the Supabase SQL tool for anything these tools cover.

## Connecting

`.mcp.json` declares the `mt-mcp` server. Claude Code gets its auth headers from
`mt mcp headers`, which uses the `mt login` session for the targeted environment and
refreshes it near expiry.

| Target | How |
|--------|-----|
| local (default) | backend running with `MT_MCP_ENABLED=true`; `mt login` |
| prod | start Claude Code with `APP_ENV=prod MT_MCP_URL=https://api.missingtable.com/mcp/`, after `mt --env prod login`. Prod must have `MT_MCP_ENABLED` on |

If the `mt-mcp` tools are missing: the project's trust dialog was not accepted (the
headers helper does not run until it is), the backend is not running with
`MT_MCP_ENABLED=true`, or the session expired — run `mt login` and reconnect with
`/mcp`. A non-admin login sees no admin tools at all; that is the tier gate, not a bug.

## Ingest failure triage

An ingest failure is one **name** the scraper sent that MT could not resolve, with the
number of matches it cost. One row per name, not per match.

1. **List** — `list_ingest_failures` (optionally `since` = the run's start time, ISO
   8601). Report it as a table: name, kind, league, matches dropped, last seen, stale.
   Lead with total matches dropped. `failures: []` means nothing is open;
   `failures: null` with an `error` means the list could not be read — say that, never
   "all clear".
2. **Diagnose each name** — the usual causes, and the fix for each:

   | Cause | Fix | Close the row? |
   |-------|-----|----------------|
   | A real MT team under a different spelling | add an alias: `mt team alias add "<MT team>" --alias "<raw name>"` | No — the next ingest resolves it and closes the row itself |
   | A team MT does not have yet | create it (`mt team create`), map it (`mt team mapping add`) | No — same |
   | Fixed at the sender (scraper stopped sending it) | nothing to change in MT | **Yes** — note "fixed at the sender" |
   | Not a real team (junk, placeholder, test data) | nothing | **Yes** — note "not a real team" |

   Check MT before deciding: `mt team matches`, `mt team mapping list` and the read
   tools (`search_teams`) answer "does MT know this team?".
3. **`stale: true`** means unseen for a while. It is a hint to de-emphasise, **never**
   proof the problem is fixed. Do not close a row because it is stale.

## Closing a row

`resolve_ingest_failure` is a write. The flow is always:

1. Call it with `failure_id` and a `note`, **no `dry_run`** (the default is a dry run).
   It returns `would_resolve` with the row, or `already_resolved` / `not_found`.
2. Show the user the row and the note, and ask for a yes.
3. Only then call it again with `dry_run: false`. Expect `resolved`.

One row at a time, one confirmation each, unless the user explicitly approves a named
batch. The note must say *why* — "fixed at the sender" and "not a real team" are
different outcomes, and the history is the point of keeping the row.

## Rules

- Never print or log a token. `mt mcp headers` writes one to stdout for Claude Code; do
  not run it in a visible shell command.
- Prod writes are real: say "→ prod" before any prod `resolve_ingest_failure`.
- An `error` in a result is a tool result, not a crash: report it in one sentence and
  stop; do not retry writes in a loop.
