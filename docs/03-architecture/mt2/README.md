# MT 2.0 — Architecture Overview

> **Audience**: Anyone working on MT 2.0, human or agent
> **Prerequisites**: None — start here
> **Status**: Established 2026-09-28 (SB-1141)

MT 2.0 adds native iOS/Android apps and an AI assistant (MT AI) to MissingTable, for
the players, parents and fans who already use the web app. This folder holds the
architecture those efforts build on, and the working rules for building them.

---

## Documents

| Document | What it settles |
|----------|-----------------|
| **[current-state.md](current-state.md)** | What exists today, verified from the repos — read before designing anything |
| **[mobile.md](mobile.md)** | Android assessment; recommendation: one Expo + React Native + TypeScript app, Kotlin scorer retired at parity |
| **[ai.md](ai.md)** | MT AI placement (in the backend process, separable), `/api/ai/*`, tools, ADK + PydanticAI roles, model profiles |
| **[ai-cost.md](ai-cost.md)** | Budget guards, exact and canonical-intent caching with write-driven invalidation, metrics |
| **[ai-quality.md](ai-quality.md)** | Feedback → eval → regression loop; test tiers that keep LLM calls out of normal CI |
| **[a2a.md](a2a.md)** | Why not yet, and the one boundary where A2A could make sense |
| **[content-roadmap.md](content-roadmap.md)** | Blog/social milestones tied to engineering milestones |

### Why this folder, not `docs/architecture/`

The repository already organises docs in numbered sections
([DOCUMENTATION_STANDARDS.md](../../../DOCUMENTATION_STANDARDS.md)), with
architecture in `docs/03-architecture/`. A second, unnumbered `docs/architecture/`
would split one topic across two trees. MT 2.0 docs therefore live here, together,
and later MT 2.0 docs follow the same rule: **extend the numbered section the topic
belongs to** — mobile dev setup under `02-development/`, AI eval how-to under
`04-testing/`, app-store releases under `05-deployment/` — and create each file only
when the work that needs it lands.

---

## Decisions at a glance

1. **Mobile**: Expo + React Native + TypeScript, one app for iOS and Android; the web
   PWA stays; the Kotlin MT Scorer is frozen and retired at scoring parity.
2. **MT AI runs inside the backend process** as `backend/mt_ai/`, behind a feature
   flag, built so that moving it to its own Deployment of the same image is a
   configuration change.
3. **The model never touches the database.** Deterministic, typed tools over the DAO
   layer; resolution, dates and maths are code.
4. **ADK is the runtime**; PydanticAI only for typed specialist functions, and only
   after it beats ADK's own structured output in a measured slice.
5. **Provider independence is configuration**: model profiles resolved to ADK
   `FallbackModel`/`LiteLlm`; no custom router; a model joins a profile only after
   passing the eval suite.
6. **Cost**: budget guards first; exact + canonical-intent caches invalidated by the
   existing DAO write hooks; no semantic cache or vector store until measured.
7. **Quality**: every 👎 becomes an eval case; tiers 0–1 run on every PR without a
   model; live evals are separate and budget-capped.
8. **Absent is not zero** — MT's user-data rules apply to AI answers and are tested.

---

## Development standards for MT 2.0 work

Every change considers the items below; the PR description says which applied.

| Concern | Standard |
|---------|----------|
| Unit tests | Pure logic and tools, default fixture = team with no user data; all three data states |
| Integration tests | DAO queries against local Supabase |
| API tests | New endpoints added to contract tests (`backend/tests/contract/`) |
| AI evals | Any prompt/tool/model change: eval cases added or re-run ([ai-quality.md](ai-quality.md)) |
| Types | New backend code fully typed, Pydantic in and out (`response_model` on new routes); mobile code is TypeScript strict |
| Lint / format | `uv run ruff check .` + `ruff format`; `npm run lint` |
| Errors | Expected conditions are results, not exceptions; absent user data is `200` |
| Observability | structlog with request IDs; a metric for anything with a cost or an SLO |
| Docs | Updated in the same PR (root `CLAUDE.md`: "Documentation First") |
| CI | Green before merge; no test in the default suite may need a paid API key |

---

## Working in small sessions

MT 2.0 is built in **small vertical slices**, one reviewable PR each. A session brief
has these parts, and a session does one of them end to end rather than a whole epic:

1. **Context** — links to the docs here and the Linear ticket
2. **Objective** — one outcome, stated so it can be verified
3. **Constraints** — what not to touch; which dependencies may be added
4. **Implementation**
5. **Tests** — per the standards table
6. **Documentation** — which doc in this folder or the numbered sections changes
7. **Verification** — the exact commands, and their output in the report
8. **Git** — branch from the ticket (`linear.sh branch SB-N`), PR with `Fixes SB-N`
9. **Final report** — what changed, what was verified, what is next

Rules of thumb:

- A slice that needs a new dependency adds **only** that dependency, and says why.
- A slice that needs a refactor does the refactor in its own PR first.
- Architecture drift is fixed in these docs in the same PR that causes it.

### Suggested order

1. MT AI tool foundation (deterministic, no LLM) — see the recommended next session
   in the SB-1141 report
2. Response models for the endpoints tools and mobile both need
3. `/api/ai/chat` walking skeleton: ADK, one tool, budget guard, persistence
4. Feedback endpoint + tier-2 eval runner
5. Expo walking skeleton: login, standings, push registration

---

## 📖 Related Documentation

- **[Architecture hub](../README.md)**
- **[Documentation standards](../../../DOCUMENTATION_STANDARDS.md)**
- **[Linear workflow](../../02-development/linear-workflow.md)**
