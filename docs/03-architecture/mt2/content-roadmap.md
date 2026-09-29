# MT 2.0 — Content Roadmap

> **Audience**: Whoever writes MT's technical blog and Instagram posts
> **Prerequisites**: [MT 2.0 overview](README.md)
> **Status**: Plan only (2026-09-28, SB-1141). Nothing written or published.

Each post is tied to an engineering milestone, so it is written from something that
shipped and was measured — not from a plan. Nothing here is published before the
milestone it depends on is merged.

---

| # | Piece | Unlocked by | Angle worth telling |
|---|-------|-------------|---------------------|
| 1 | **MT 2.0 announcement** | this architecture set | What MT is for (players, parents, fans), and what 2.0 adds |
| 2 | **Why our first two AI agents were retired** | already true | PydanticAI scrape planner → rules engine; CrewAI test crew → one coding agent. "Deterministic first" as the lesson that shaped MT AI |
| 3 | **Building MT AI** | `/api/ai/chat` walking skeleton | Tools over DAOs; multi-age team resolution as the real problem |
| 4 | **An AI agent with Google ADK** | skeleton + callbacks | Runner, sessions rebuilt from our own tables, callbacks as the cost/audit seam |
| 5 | **Making MT AI model-independent** | second model profile passes evals | Model profiles, `FallbackModel`, and letting evals pick the model |
| 6 | **AI caching and cost control** | answer cache + metrics live | Invalidating AI answers with the DAO cache's write hooks; real hit rates and cost per answer |
| 7 | **AI evaluation and feedback** | feedback + eval runner | "Absent is not zero" as an eval category; 👎 → regression test |
| 8 | **ADK vs PydanticAI** | `MatchAnalysis` spike | Measured comparison on one typed specialist |
| 9 | **Building MT mobile with Expo** | Expo walking skeleton | Porting a tested Kotlin offline queue to TypeScript by reusing its test vectors |
| 10 | **Experimenting with A2A** | only if [a2a.md](a2a.md)'s preconditions hold | Possibly "why we didn't", which is also a post |
| 11 | **Launching the MT mobile app** | TestFlight + Play internal track | Invite-only distribution on both stores |

**Instagram**: short visual companions to 1, 3, 6 and 11 — a screen recording of MT AI
answering "who do we play next?", a before/after cost chart, the app on a phone at a
match. Match-share cards (`docs/features/IG_SHARE_CARD.md`) already establish the look.

**Privacy**: no screenshot shows a real player's name or a minor's stats without
consent; use the `is_test` partition or a claimed team whose manager agreed.

---

## 📖 Related Documentation

- **[MT 2.0 overview](README.md)**
