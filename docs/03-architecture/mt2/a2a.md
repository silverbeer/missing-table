# MT 2.0 — A2A Assessment

> **Audience**: Anyone tempted to split MT AI into cooperating agents
> **Prerequisites**: [MT AI architecture](ai.md)
> **Status**: Future assessment (2026-09-28, SB-1141). No A2A work is planned.

A2A (agent-to-agent protocol) is a learning objective, not a requirement. This is a
short record of where it could fit MT and where a function call or an HTTP API is the
better tool.

---

## The test

Use A2A only when **both** sides are genuinely independent agents: separately
deployed, separately owned or versioned, and each needing to negotiate a task in
natural language rather than exchange a typed request. If one side is deterministic,
or both live in the same process, A2A adds a network hop, a protocol and a failure
mode for no gain.

## Candidate boundaries

| Boundary | Verdict | Why |
|----------|---------|-----|
| MT assistant → **Data agent** | **No — tools** | Data access must be deterministic, typed and testable ([ai.md](ai.md#tools)). An agent in front of the data re-introduces the guesswork tools remove |
| MT assistant → **Match intelligence** (form, trends) | **No — in-process** | A typed specialist (`analyze_team_form` → `MatchAnalysis`) called as a tool, or an ADK sub-agent/`AgentTool` if it grows. Same process, same deploy |
| MT assistant → **Content agent** (IG captions, recaps) | **Maybe, later** | Different cadence (batch, not chat), different reviewers (human approval before posting), could run as its own service. Even then, an ADK agent behind a job queue is simpler until a second consumer exists |
| MT → **match-scraper-agent** | **No — API/queue** | It is a deterministic rules engine now; it talks to MT over RabbitMQ and `/api/agent/*`. Nothing to negotiate |
| **External agents → MT** (a parent's personal assistant, a club's agent, the "Claw" chat agent that already drives the `mt` CLI) | **Most plausible** | MT as an A2A *server*: a published agent card exposing "ask about a team's schedule/results". Genuinely independent parties is exactly A2A's case. Needs auth for third-party agents and fits only once MT AI is stable and MT's invite-only posture allows outside callers. **mt-mcp ([mcp.md](mcp.md)) now covers most of this need first**: a typed tool surface, per-user auth, no agent card to negotiate |

## What would have to be true first

1. MT AI's single-agent design is in production with evals and cost metrics.
2. A concrete external consumer exists (not a hypothetical one).
3. An auth model for agents acting on behalf of MT users — today the only non-human
   identity is the service-account JWT, which is far too broad to hand to a third party.

Until then, the learning goal is better served by ADK's in-process composition
(sub-agents, `AgentTool`), which teaches the same decomposition questions without
the protocol.

---

## 📖 Related Documentation

- **[MT AI architecture](ai.md)** · **[MT 2.0 overview](README.md)**
