# CrewAI Testing Experiment — Retrospective

**Status**: Retired (July 2026) | **Superseded by**: [qe plugin](https://github.com/silverbeer/qe-plugin)

## What it was

The "MT Testing Crew" (`crew_testing/`, removed) was an autonomous test-generation
experiment built on CrewAI: eight role-specialized LLM agents (Swagger the API
cataloger, Architect the scenario designer, Mocker the test-data craftsman, Forge
the code generator, Flash the executor, plus Inspector/Herald/Sherlock) targeting
the FastAPI backend. Only two of four planned phases shipped: the OpenAPI gap
scanner and the Architect→Mocker→Forge→Flash generation pipeline.

It has been replaced by the much simpler [qe plugin](https://github.com/silverbeer/qe-plugin)
for Claude Code (`/qe`, `/generate-tests`, `@qe-engineer`), configured in
`.claude/qe.yml` with the endpoint test manifest tracked in `.qe/test_manifest.json`.

## What worked (ideas carried into the qe plugin)

- **OpenAPI-driven gap analysis** — parse `/openapi.json`, cross-reference against
  existing tests, and report per-endpoint coverage gaps. The diffing pattern
  outlived the agent framing.
- **Scenario taxonomy** — classifying test cases per endpoint as
  `happy_path / error / edge_case / security / performance` is a useful checklist
  whether tests are written by hand or generated.
- **Schema-aware test data** — inspect FK relationships and required fields
  (teams→divisions→age_groups→seasons) *before* generating fixtures, and produce
  realistic values instead of `test_user_1`.
- **Cost-tiering models by task** — cheap models for procedural cataloging and
  execution, stronger models only for design and codegen.

## What failed (and why we retired it)

- **Reasoning loops.** On a real bug (see
  [club-filtering-type-coercion-bug.md](../bug-fixes/club-filtering-type-coercion-bug.md)),
  the full pipeline hit max iterations without producing any tests; the analysis,
  fix, and tests were all done manually — faster and more thoroughly.
- **Incomplete generation.** In the one successful end-to-end run, Forge emitted a
  valid Python file with six fixtures and *zero test functions*; the monolithic
  "generate a whole test file" step was too big for a single agent task.
- **Overstated status.** Phase docs declared themselves "COMPLETE ✅ /
  production-ready" while core behavior was broken; cost estimates were never
  validated and contradicted each other.

Net lesson: a single capable coding agent with direct repo access beats a
choreographed multi-agent pipeline for test generation at this project's scale.

## Codebase-specific gotcha preserved from the experiment

The teams API `divisions_by_age_group` map has **string keys** (JSON-serialized
integer IDs) while `league_id` values stay **numeric** — any test or fixture
asserting on `/api/teams` filtering must stringify the key and coerce both sides
of an ID comparison. Details in
[club-filtering-type-coercion-bug.md](../bug-fixes/club-filtering-type-coercion-bug.md).
