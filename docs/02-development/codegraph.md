# CodeGraph (agent code index) — under evaluation

[CodeGraph](https://github.com/colbymchenry/codegraph) indexes the repo into a symbol and call graph so an
AI agent can find code without grepping and reading whole files. **It is on trial** (SB-1067, and SB-1066
in `trd`): it stays only if it measurably cuts exploration and context tokens.

## What is wired up

| Piece | File | Committed |
|-------|------|-----------|
| Index (SQLite, ~640 files) | `.codegraph/` | no — per machine, gitignored |
| MCP server (`codegraph_explore`, `codegraph_node`, ...) | `.mcp.json` | yes |
| Auto-allow for its tools | `.claude/settings.json` | yes |
| Nudge to use it before grep/read | `.claude/CLAUDE.md` | yes |
| Prompt hook that injects related code into each prompt | `.claude/hooks/codegraph-hook.sh` | yes |
| Measurement | `scripts/codegraph-eval.py` | yes |

Everything is project-local. Do **not** run `codegraph install -t claude` — it writes the server into the
global `~/.claude.json`, which turns it on for every repo.

## Setup on a new machine

Install `codegraph` per the [upstream README](https://github.com/colbymchenry/codegraph). It lands as a
self-contained versioned binary under `~/.codegraph/versions/`, linked from `~/.local/bin/codegraph`;
`codegraph upgrade` updates it. Then:

```bash
codegraph init .    # builds .codegraph/ in a few seconds
```

Without `.codegraph/` the hook injects nothing and the nudge tells the agent to skip CodeGraph, so a
machine that never runs `init` is unaffected. The MCP server keeps the index in sync while a session runs;
`codegraph sync` catches up by hand.

## The A/B

The prompt hook is the part with a cost: it adds 1–16 KB of source to a prompt, and that text stays in
context for the rest of the session. Alternate sessions between the two arms:

```bash
claude                    # arm "on"  — hook injects CodeGraph context
CODEGRAPH_OFF=1 claude    # arm "off" — hook injects nothing
```

Each prompt appends `<session_id> <arm>` to `.codegraph/ab-arms.log`, so an "off" session can be told apart
from an "on" session whose prompts never matched. The MCP tools and the nudge stay available in both arms.

## Reading the result

```bash
scripts/codegraph-eval.py                     # every session
scripts/codegraph-eval.py --since 2026-09-13  # only the trial
```

| Column | Meaning |
|--------|---------|
| `lookups/p` | code reads + searches per prompt (Read/Grep/Glob, and cat/sed/grep/rg in Bash) |
| `reread` | reads of a file the hook had already put in context |
| `inj KB` | context injected by the hook |
| `ctx M/p` | context tokens sent per prompt, millions |
| `cg` | direct CodeGraph calls (MCP or CLI) |

**Keep** the hook if the `on` arm shows lower `lookups/p` **and** lower `ctx M/p` than `off` after roughly two
weeks of comparable work. **Otherwise remove CodeGraph**: delete the `codegraph` entry from `.mcp.json`, the
hook from `.claude/settings.json`, `.claude/CLAUDE.md`, the hook script and the eval script, then
`codegraph uninit`.

Sessions before 2026-09-13 show as `unlogged` or `on?`; they had no arm log and are not a fair comparison.
In `trd` those earlier sessions showed no saving — lookups per prompt went up with the hook on, and the agent
re-read files the hook had already injected — which is why this is an A/B rather than a rollout.
