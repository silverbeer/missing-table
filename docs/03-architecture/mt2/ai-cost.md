# MT 2.0 — MT AI Cost Architecture

> **Audience**: Anyone building or operating MT AI
> **Prerequisites**: [MT AI architecture](ai.md), [caching.md](../caching.md)
> **Status**: Target design (2026-09-28, SB-1141). Nothing here is built yet.

Cost is a design constraint, not a later optimisation. This document sets the caching
layers, how each stays correct as MT data changes, the guards that cap spend, and the
numbers recorded so every choice here can be revisited with data.

---

## Order of defences

Cheapest first. Each layer only sees what the one before it could not answer.

| # | Layer | Saves | Built |
|---|-------|-------|-------|
| 1 | **Budget guards** | runaway spend | first AI slice |
| 2 | **Exact answer cache** | the whole turn (model + tools) | after metrics show repeats |
| 3 | **Canonical-intent cache** | the whole turn for paraphrases | after (2), if measured hit rate justifies |
| 4 | **Tool/data cache** | DB round-trips | **already exists** (Redis DAO cache) |
| 5 | **Provider context caching** | input tokens on long prompts | free where the provider does it implicitly |
| — | Semantic (embedding) cache | paraphrases | **deferred** — see below |

---

## 1. Budget guards

- **Per user**: requests per minute (slowapi already exists in `rate_limiter.py`) and a
  daily turn cap. Exceeding either returns `429 {reason: "budget"}`.
- **Global**: a daily estimated-cost ceiling. When reached, `/api/ai/chat` returns `503
  {reason: "unavailable"}` until midnight UTC — MT AI switches off rather than
  overspending.
- **Per turn**: max tool calls (start at 6), max output tokens, model call timeout.
- Counters live in the existing Redis (`mt:ai:budget:*`), which already runs in prod.

## 2. Exact answer cache

An identical question with identical relevant context reuses the stored answer.

**Key** — a hash of:

| Part | Why |
|------|-----|
| normalised question (case, whitespace, punctuation) | identical questions |
| `context.team_id` and resolved conversation state | "their next game" differs per team |
| viewer scope (`is_test` visibility) | never serve partition data across the line |
| today's date in the club's timezone | "next game" changes at midnight |
| `agent_version`, `prompt_version`, model profile | a new prompt must not serve old answers |

**Only first turns are cached.** Follow-ups depend on conversation history, and keying
on history hashes gives near-zero hits at a real cost in complexity.

### Invalidation: reuse the DAO cache's write hooks

MT already knows when data changes: every write goes through `@invalidates_cache(pattern)`
(`dao/base_dao.py`). The answer cache piggybacks on it:

1. `invalidates_cache` additionally increments a **data epoch** per resource family:
   `mt:ai:epoch:matches`, `…:teams`, `…:standings`, … (one `INCR` per write).
2. When an answer is stored, it records **which resource families its tools read** and
   the epoch of each at that moment.
3. On lookup, the entry is valid only if every recorded epoch is unchanged.
4. A TTL cap (start at 6 h) bounds anything the epochs miss.

This gives write-driven invalidation without re-deriving invalidation rules — the same
reasoning that made the service worker bust its whole cache on any write.

**Known gap**: direct SQL in Supabase Studio bypasses `@invalidates_cache` today, and
so will bypass the epochs. The existing rule applies: pair a Studio fix with an API
write or a `redis-cli DEL` (here, of `mt:ai:*`). The ArgoCD PostSync hook that flushes
`mt:dao:*` should flush `mt:ai:*` too.

## 3. Canonical-intent cache (instead of a semantic cache, first)

"Who does Boston United play next?" and "What's Boston United's next game?" differ as
text but resolve to the same **(intent, entities, date)**:

```text
intent=next_match  team_id=123  age_group_id=7  date=2026-09-28
```

MT's questions are narrow — next match, last result, standings position, top scorer —
so a small deterministic classification (resolved entities + an intent label the agent
already produced on the first answer) yields a canonical key with the same epoch-based
invalidation as layer 2. Correctness is inspectable: a wrong hit can be traced to a
wrong key, which a vector distance cannot offer.

## Semantic cache — deferred

Embedding-similarity caching is **not** planned for MT 2.0's first phase:

- **Volume**: MT is invite-only. Few repeated paraphrases exist to hit.
- **Correctness**: "Boston United U15" and "Boston United U16" are near-identical
  embeddings with different answers. Every wrong hit is a confidently wrong answer.
- **Infrastructure**: needs an embedding call per question and a vector index — a
  datastore MT does not run today.

**Revisit when** layers 2–3 are live and metrics show a meaningful share of misses are
paraphrases of cached questions. Postgres `pgvector` in Supabase would then be the
first option, before any new datastore.

## 4. Tool/data caching — already there

Tools read through DAOs, and the hot DAO reads (`get_standings`, team lists, club
lists, leaderboards) are already `@dao_cache`d in Redis with write invalidation and a
24 h TTL. MT AI adds only a **per-turn memo** so the same tool with the same args is not
executed twice inside one answer.

## 5. Provider context caching

- Gemini applies **implicit caching** automatically on 2.5-and-newer models, with a
  minimum prompt size of 2,048–4,096 tokens depending on the model
  ([Gemini caching docs, June 2026 snapshot](https://techdevnotes.com/releases/gemini-docs/20260626-140339Z-75a2454c2e49/content/pages/caching.txt)).
  MT AI's system prompt plus tool schemas will likely sit near that threshold at first.
- What MT does: keep the **static prefix stable and first** — instructions, then tool
  definitions, then conversation. Never interpolate the date or user name into the top
  of the system prompt; pass them as a later message so the prefix stays cacheable.
- Explicit context caches (paid storage) are not worth it until conversations are long.
- **Verify on the bill, not from the docs.** A June 2026 report describes implicit
  cache discounts silently stopping for one Gemini model on some projects
  ([Google AI forum](https://discuss.ai.google.dev/t/gemini-3-1-flash-lite-implicit-cache-stopped-applying-cost-savings-june-30-2026/173779)).
  The `cached_input_tokens` metric below exists to catch exactly that.

---

## Metrics

Recorded per turn in `ai_messages` (queryable history) and as Prometheus metrics on
the existing `/metrics` endpoint (dashboards/alerts in Grafana Cloud).

| Field | `ai_messages` column | Prometheus |
|-------|---------------------|------------|
| model, provider | `model`, `provider` | label |
| input / output / cached input tokens | `input_tokens`, `output_tokens`, `cached_input_tokens` | `mt_ai_tokens_total{direction}` |
| latency | `latency_ms` | `mt_ai_turn_duration_seconds` |
| exact cache hit | `cache_hit` | `mt_ai_turns_total{cache="exact"}` |
| canonical/semantic hit | `semantic_cache_hit` (true for the canonical layer too) | `mt_ai_turns_total{cache="canonical"}` |
| tool calls | `tool_calls` (count; detail in `ai_tool_calls`) | `mt_ai_tool_calls_total{tool,outcome}` |
| estimated cost | `estimated_cost_usd` | `mt_ai_estimated_cost_usd_total` |
| budget refusals | — | `mt_ai_refusals_total{reason}` |

- **Estimated cost** comes from a versioned price table in configuration, keyed by
  provider + model. Prices are never hardcoded in agent code; `price_table_version`
  is stored with each row so historic estimates can be recomputed.
- Labels stay low-cardinality: no user IDs or conversation IDs in Prometheus.
- One alert from day one: estimated daily cost above a threshold (Grafana Cloud alert
  as code, next to `backend-500-errors.yaml` in platform-bootstrap).

---

## 📖 Related Documentation

- **[MT AI architecture](ai.md)** · **[AI quality](ai-quality.md)**
- **[Caching](../caching.md)** — the DAO and service-worker caches this builds on
