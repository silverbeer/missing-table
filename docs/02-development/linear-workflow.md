# 🧭 Linear Issue Tracking Workflow

> **Audience**: Developers (currently solo: @silverbeer)
> **Status**: Active — Linear is the source of truth for issues across all silverbeer projects
> **Replaces**: GitHub Issues on `silverbeer/missing-table` (and other silverbeer repos as they migrate)

Linear is the canonical issue tracker. GitHub Issues are read-only / archived; new work originates in Linear. PRs continue to live on GitHub and auto-sync state back to Linear via the GitHub integration.

---

## 🔑 Why Linear

- **First-class GitHub integration** — branch ↔ issue ↔ PR linking, auto-status on merge
- **Keyboard-driven UX** — faster triage than GH Issues
- **Cycles, projects, sub-issues** — structure beyond flat labels
- **MCP-ready** — Claude Code can read/write issues directly once MCP server is wired up

---

## 🗂️ Workspace Structure

Linear Free plan caps at **2 teams** and **250 issues** workspace-wide. With 3 personal projects (missing-table, qualityplaybook, myrunstreak) the team allowance does not fit cleanly, so all projects share **one Linear team**. Project boundary is encoded via a **label group**, not the team prefix.

### Team

| Property | Value |
|----------|-------|
| Team name | **silverbeer** |
| Team prefix (issue ID) | **SB** (e.g., `SB-12`, `SB-247`) |
| Workspace | personal (silverbeer) |

All issues — regardless of repo — get `SB-N` IDs. Repo is identified by the `repo` label group below.

### Label Groups

Linear supports **label groups** where members are mutually exclusive (pick one). Use them for fields that should not double up.

> Note: Linear reserves the name `project` for its built-in Projects feature, so the repo grouping label is named **`repo`**.

**`repo`** (group, pick one — required):
- `MT` — missingtable.com
- `QB` — qualityplaybook.dev
- `STK` — myrunstreak.run
- `MS` — match-scraper
- `MSA` — match-scraper-agent

**`type`** (group, pick one):
- `bug` — defect / regression
- `feature` — new capability
- `chore` — maintenance, deps, refactor with no behavior change
- `docs` — documentation only
- `infra` — CI/CD, k8s, helm, terraform, deploy plumbing
- `security` — vulnerability or hardening work

### Flat Labels (multi-select)

**Area** (one or more — repo-specific, prefix to disambiguate):

`backend`, `frontend`, `db`, `auth`, `qop`, `scraper-integration` — applies to MT
`engine`, `ui` — applies to QB (future)
`ios`, `widget`, `sync` — applies to STK (future)

Use the `repo` label to scope what "frontend" or "ui" means.

### Priority

Use Linear's built-in priority field (`Urgent / High / Medium / Low / No priority`). Do not duplicate priority as a label.

### Workflow States

Default Linear states are fine:

```
Backlog → Todo → In Progress → In Review → Done
                                          ↘ Canceled
```

---

## 🌿 Branch & PR Conventions

### Branch Naming

Use the branch name Linear suggests on each issue (`Copy git branch name` button). Format:

```
silverbeer/sb-123-short-slug
```

Same convention across all three repos — issue ID is what links the branch to Linear, repo isolation is implicit (different git remote).

If you don't use Linear's suggested name, include the issue ID anywhere in the branch (e.g., `feat/sb-123-add-foo`) and it still auto-links.

### PR Title

Include the issue ID in title or body:

```
feat(qop): add QoP rank column to LeagueTable (SB-301)
```

### Auto-close Keywords

Use in PR description to move the issue to Done on merge:

- `Fixes SB-123`
- `Closes SB-123`
- `Resolves SB-123`

Use `Ref SB-123` for related-but-not-closing PRs.

### Multi-issue PRs

```
Fixes SB-300, SB-301, SB-302
```

---

## 🔁 Daily Flow

```
1. Pick / create issue in Linear     →  status: Todo
   - Apply repo:MT|QB|STK|MS|MSA label
   - Apply type label
   - Set priority
2. Hit "Copy git branch name"        →  silverbeer/sb-N-slug
3. cd into the right repo            →  ~/gitrepos/missing-table | qualityplaybook | myrunstreak
4. git checkout -b <branch>          →  Linear auto-moves issue to In Progress
5. Code + commit + push
6. Open PR with "Fixes SB-N"         →  Linear auto-moves to In Review
7. Merge PR                          →  Linear auto-moves to Done
```

No manual status changes needed for the happy path.

---

## 🚚 Migrating GitHub Issues to Linear

Open GH issues are migrated 1:1 into Linear `silverbeer` team. Each migrated issue:

1. Created in Linear with original title + body + appropriate `repo` + `type` + area labels
2. Original GH issue closed with comment linking to the new Linear issue
3. GH issue labeled `migrated-to-linear`

After cutover, **do not file new GitHub Issues** in migrated repos.

### Cutover Checklist

- [x] Create Linear team "silverbeer" with prefix `SB`
- [x] Create label group `repo` with values `MT`, `QB`, `STK`, `MS`, `MSA`
- [x] Create label group `type` with values `bug`, `feature`, `chore`, `docs`, `infra`, `security`
- [x] Create area labels (above)
- [x] Install Linear GitHub app on each repo (already done for `silverbeer/missing-table`)
- [x] Bulk-migrate open GH issues for `missing-table` (see [Migration mapping](#migration-mapping---missing-table))
- [ ] Pin a GH notice issue in each repo pointing to Linear
- [ ] Update each repo README with Linear link
- [ ] Migrate `qualityplaybook` and `myrunstreak` GH issues when ready

### Migration Mapping — `missing-table`

Migrated 2026-05-13 (10 issues). Regenerate snapshot for future migrations with `gh issue list --repo silverbeer/missing-table --state open --limit 100 --json number,title,labels`.

| GH # | Linear | Title | Repo | Type | Area | Priority |
|------|--------|-------|------|------|------|----------|
| #270 | [SB-5](https://linear.app/silverbeer/issue/SB-5) | Remove guest/tournament teams incorrectly associated with U14 HG Northeast division | `MT` | `bug` | `db` | High |
| #283 | [SB-6](https://linear.app/silverbeer/issue/SB-6) | feat: add admin note field to channel access request invites | `MT` | `feature` | `backend` | Low |
| #284 | [SB-7](https://linear.app/silverbeer/issue/SB-7) | fix: improve Admin panel tab bar UX — too many tabs overflowing | `MT` | `bug` | `frontend` | Medium |
| #298 | [SB-8](https://linear.app/silverbeer/issue/SB-8) | feat: Add QoP rankings API endpoints (ingest + query) | `MT` | `feature` | `backend`, `qop` | High |
| #300 | [SB-9](https://linear.app/silverbeer/issue/SB-9) | feat: Extend /api/matches/preview to include QoP ranks | `MT` | `feature` | `backend`, `qop` | Medium |
| #301 | [SB-10](https://linear.app/silverbeer/issue/SB-10) | feat: Add QoP rank column to LeagueTable.vue | `MT` | `feature` | `frontend`, `qop` | Medium |
| #302 | [SB-11](https://linear.app/silverbeer/issue/SB-11) | feat: Show QoP rank in MatchPreview.vue | `MT` | `feature` | `frontend`, `qop` | Medium |
| #308 | [SB-12](https://linear.app/silverbeer/issue/SB-12) | feat: add Redis caching for QoP rankings endpoint | `MT` | `feature` | `backend`, `qop` | Low |
| #315 | [SB-13](https://linear.app/silverbeer/issue/SB-13) | Feature: Live match notifications (Telegram + Discord) (epic) | `MT` | `feature` | `backend` | Medium |
| #322 | [SB-14](https://linear.app/silverbeer/issue/SB-14) | [Phase 7] Smoke test + docs | `MT` | `docs` | `backend` | Low |

`SB-13` is the epic, `SB-14` is its sub-issue (Linear native parent/child).

### Migration Mapping — `qualityplaybook` / `myrunstreak`

Run `gh issue list --repo silverbeer/<repo> --state open --limit 100 --json number,title,labels` when migrating each.

---

## 💰 Free Plan Constraints

| Limit | Value | Impact |
|-------|-------|--------|
| Teams | 2 | Drove the single-team design above |
| Issues | 250 active | Archive Done issues older than ~90 days |
| Members | Unlimited | Fine |
| File upload | 10 MB | Avoid attaching large logs/screenshots; link instead |

If we hit the 250-issue cap, archive Done issues in bulk (Linear has a built-in archive action). Archived issues don't count against the cap.

Upgrade to Standard (~$8/mo) buys: unlimited teams, unlimited issues, cycles, custom views, SLAs.

---

## 🤖 Future: Linear MCP Server

Not wired up yet. When added, Claude Code can:

- Create issues from conversation (`"file this as SB issue, project MT"`)
- Update status / assignee
- Query "what's in progress" without leaving the editor

Tracking issue: TBD (file as `SB-N` once the team exists).

---

## 📖 Related Documentation

- **[Daily Workflow](daily-workflow.md)** — broader dev commands
- **[CLAUDE.md](../../CLAUDE.md)** — project root instructions (branch protection, PR workflow)
- **Linear docs**: <https://linear.app/docs>
- **Linear GitHub integration**: <https://linear.app/docs/github>
- **Linear label groups**: <https://linear.app/docs/labels#label-groups>

---

<div align="center">

[⬆ Back to Development Guide](README.md)

</div>
