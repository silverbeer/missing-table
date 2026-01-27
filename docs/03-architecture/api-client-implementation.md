# API Client Completion - Implementation Tracker

**Branch:** `feature/complete-api-client`
**Created:** 2026-01-27

## Goal

1. Bring `MissingTableClient` to full API coverage (~53 new methods)
2. Refactor `TSCClient` to stop using raw HTTP helpers
3. Create a **Test Inventory file** mapping endpoints -> client methods -> tests
4. Add a **GenAI-powered PR workflow** that detects API changes, flags gaps, and suggests client method code + contract tests
5. Add a deterministic CI test as a hard gate
6. **Rule: Every endpoint must have at least 1 contract test** -- enforced by CI

---

## Progress

| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 1 | Infrastructure (models + multipart) | DONE | `_request_multipart` + model re-exports |
| 2 | Add ~53 client methods | DONE | All domain groups implemented |
| 3 | Refactor TSCClient | DONE | Removed `_get`/`_post`, uses typed methods |
| 4 | Test Inventory file | DONE | `api_inventory.json` + generator script |
| 5 | Deterministic CI gate | DONE | `test_api_client_coverage.py` |
| 6 | GenAI PR workflow | DONE | `api-coverage-review.yml` |
| 7 | Contract tests for all endpoints | DONE | 15 new contract test files |
| 8 | Documentation | DONE | `api-client.md` |

---

## Verification Checklist

- [ ] Run existing TSC tests: `cd backend && uv run pytest tests/tsc/ -v`
- [ ] Run existing contract tests: `cd backend && uv run pytest tests/contract/ -v`
- [ ] Run new coverage guard test: `cd backend && uv run pytest tests/test_api_client_coverage.py -v`
- [ ] Run inventory generator: `cd backend && uv run python scripts/generate_api_inventory.py`
- [ ] Run linter: `cd backend && uv run ruff check api_client/ tests/`

---

## Files Modified/Created

| File | Change |
|------|--------|
| `backend/api_client/client.py` | Add `_request_multipart` + ~53 new methods |
| `backend/api_client/models.py` | Add re-exports from `backend/models/` |
| `backend/api_client/__init__.py` | Update exports |
| `backend/tests/fixtures/tsc/client.py` | Remove `_get`/`_post`, use typed methods |
| `backend/api_inventory.json` | **New**: endpoint -> client -> test mapping |
| `backend/scripts/generate_api_inventory.py` | **New**: inventory generator script |
| `backend/tests/test_api_client_coverage.py` | **New**: deterministic CI gate |
| `.github/workflows/api-coverage-review.yml` | **New**: GenAI PR review workflow |
| `backend/tests/contract/test_*_contract.py` | **New**: ~15 contract test files |
| `docs/03-architecture/api-client.md` | **New**: api client + inventory docs |
