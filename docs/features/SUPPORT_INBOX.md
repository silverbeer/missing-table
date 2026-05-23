# Support Inbox

**Status:** Phase 1 shipped (SB-35) | **Inbound address:** `support@contact.missingtable.com`

An in-app support inbox that receives email replies (and direct sends) from users at `support@contact.missingtable.com`, routes them through Resend Inbound's webhook, threads them by RFC 5322 headers + case number, and persists them to a Supabase-backed schema for the admin UI (Phase 2/3) to read and respond from.

Every conversation gets a sequential **`MT-{n}`** case number — embedded in outbound subjects so threading survives even when RFC 5322 headers get stripped by intermediate mail servers.

## What it does (Phase 1)

1. A user emails `support@contact.missingtable.com` (or replies to any MT-sent transactional email — the Reply-To header routes their reply to the same address).
2. Resend Inbound receives the mail (MX is on `contact.missingtable.com` pointing at Amazon SES inbound), parses it, and POSTs an `email.received` event to our webhook.
3. Our webhook verifies the Svix signature, fetches the full `ReceivedEmail` via the Resend API, runs the 4-tier threading resolver, sanitizes any HTML, drops attachments, and inserts a row into `email_messages` linked to an `email_threads` row.
4. The thread's `status` auto-transitions (`new` → `awaiting_admin` on user reply; `awaiting_user` after admin reply; `spam` and `resolved` are manual).

Phase 2 (admin API) and Phase 3 (admin UI inbox + reply composer) are scheduled but not yet built.

## End-to-end flow

```
                           ┌─────────────┐
   user@gmail.com  ────►   │ contact.... │  MX: inbound-smtp.us-east-1.amazonaws.com
                           │  MX record  │  (Route 53, managed in
                           └──────┬──────┘   missingtable-platform-bootstrap)
                                  │
                                  ▼
                           ┌─────────────┐
                           │   Resend    │  Parses headers/body/attachments.
                           │   Inbound   │  Signs and POSTs an email.received
                           │             │   event (svix-id/timestamp/signature
                           │             │   headers).
                           └──────┬──────┘
                                  │
                                  ▼
            POST https://api.missingtable.com/api/webhooks/email/inbound
                                  │
                                  ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │  backend/api/webhooks_email.py                                   │
   │                                                                  │
   │  1. verify_webhook()          Svix HMAC check                    │
   │  2. event.type == "email.received"  (else 200 ignore)            │
   │  3. _fetch_received_email()   Resend API → full body/headers     │
   │  4. find_by_message_id()      Idempotency check                  │
   │  5. resolve_thread()          4-tier match (see below)           │
   │  6. sanitize_html()           bleach allowlist                   │
   │  7. drop attachments          Set had_attachments flag only      │
   │  8. insert_inbound()          New email_messages row             │
   │  9. transition_on_inbound()   Status / unread_count update       │
   └──────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                       Supabase: email_threads + email_messages
                       (RLS: admin-only; webhook bypasses via
                        service-role connection.)
```

## Threading resolver

`backend/services/email_inbound.py::resolve_thread` tries four lookups in order. The first match wins. Tier 4 creates a new thread.

| Tier | What | Used for |
|---|---|---|
| **1. In-Reply-To** | Look up the inbound's `In-Reply-To` header in `email_messages.message_id`. If found, reuse that message's thread. | The default reply path — every mainstream mail client sets `In-Reply-To` correctly. |
| **2. `[MT-{n}]` in subject** | Parse the bracketed case-number token from the subject and look up `email_threads.case_number`. | Belt-and-suspenders: when an intermediate mail server strips RFC 5322 headers, the subject still carries the case number. |
| **3. Recent participant + normalized subject** | List recent threads from the same sender (30-day window) and match by stripped/lowercased subject. | Tolerates `Re:` / `Fwd:` chains, weird mail clients, and missing headers. |
| **4. New thread** | Insert a fresh `email_threads` row. The case number comes from the `email_thread_case_seq` sequence. | First-time contact. |

## Address choice — why `contact.missingtable.com`

Resend's free plan caps verified domains at 1. The existing slot was already `contact.missingtable.com` (set up for outbound sending). Options considered:

- **`support@missingtable.com` (apex MX)** — clean address, but would require swapping the verified domain (drops outbound during the transition) **and** redoing SPF/DKIM TXT on the apex. Risky for a free-tier project.
- **`support@contact.missingtable.com`** ← **picked**. Enable receiving on the existing verified domain; one new MX record, zero outbound risk, address is slightly less pretty.
- **`support@support.missingtable.com`** — needs a second verified domain (Pro plan).

If MT ever upgrades to Resend Pro or otherwise needs the apex address, the cutover is small: change the `SUPPORT_EMAIL` constants in two places (see Files), update the MX record, update Reply-To. The webhook handler, schema, and admin UI don't care which subdomain receives.

## Schema

Migration: `supabase-local/migrations/20260523000000_add_email_inbox.sql`.

### `email_threads`

| Column | Notes |
|---|---|
| `id` (uuid) | Primary key. |
| `case_number` (int, unique) | From `email_thread_case_seq`. Rendered as `MT-{n}` in the UI and subject lines. |
| `subject` | First inbound's subject. |
| `participant_email` / `participant_name` | External party. |
| `status` | `new` / `awaiting_admin` / `awaiting_user` / `resolved` / `spam`. Check constraint enforces. |
| `last_message_at`, `unread_count` | Hot fields for inbox listing. |
| `created_at`, `updated_at` | `updated_at` maintained by `extensions.moddatetime` trigger. |

### `email_messages`

| Column | Notes |
|---|---|
| `id` (uuid) | Primary key. |
| `thread_id` (uuid) | FK → `email_threads`, `ON DELETE CASCADE`. |
| `direction` | `inbound` / `outbound`. Check constraint enforces. |
| `message_id` (text, **unique**) | RFC 5322 Message-ID with angle brackets stripped. Unique constraint provides webhook idempotency. |
| `in_reply_to`, `references` | For threading. |
| `from_email`, `from_name`, `to_email`, `subject` | Envelope. |
| `body_text`, `body_html` | `body_html` is **always** bleach-sanitized before insert. Never store raw provider HTML. |
| `had_attachments` (bool) | True when the inbound payload included attachments; the attachment bodies themselves are dropped. UI is intended to show "reply via your email client to see attachments". |
| `raw_payload` (jsonb) | Full ReceivedEmail dict from Resend, minus attachments. For debugging; safe to wipe after a retention window. |
| `sent_by_user_id` | FK to `user_profiles`. Null for inbound. Phase 2 admin replies populate this. |
| `read_at`, `created_at` | |

### RLS

Both tables have RLS enabled with one policy each: `*_admin_all` gated by `public.is_admin()`. The webhook uses the service-role Supabase client so its writes bypass RLS — HMAC verification is the actual trust gate.

### Indexes

| Index | Why |
|---|---|
| `idx_email_threads_status_last_message` (status, last_message_at desc) | Default inbox listing query — "needs attention" tab. |
| `idx_email_threads_case_number` | `MT-{n}` lookups from the threading resolver and admin UI deep links. |
| `idx_email_threads_participant_email` | Tier-3 threading fallback ("recent from this sender"). |
| `idx_email_messages_message_id` | Idempotency check on every webhook call. |
| `idx_email_messages_in_reply_to` (partial, `WHERE in_reply_to IS NOT NULL`) | Tier-1 threading fallback. |
| `idx_email_messages_thread_created` | Thread message-list rendering. |

## Files

### Backend

- **`backend/api/webhooks_email.py`** — webhook endpoint at `POST /api/webhooks/email/inbound`. Verifies signature, fetches via `resend.Emails.Receiving.get`, threads, sanitizes, inserts, transitions. Registered in `app.py`.
- **`backend/services/email_inbound.py`** — pure helpers consumed by the handler:
  - `verify_webhook()` — wraps `resend.Webhooks.verify` with env-driven secret + typed `WebhookVerificationError`. **Key gotcha**: Resend's `WebhookHeaders` TypedDict uses short keys `id`/`timestamp`/`signature`, not the prefixed HTTP header names. See "Lessons learned" below.
  - `sanitize_html()` — bleach allowlist. Conservative tag set; protocols limited to `http`/`https`/`mailto`.
  - `parse_case_number_from_subject()` — `[MT-{n}]` regex, case-insensitive on `MT`.
  - `normalize_subject()` — strips chained `Re:`/`Fwd:` and case-number tokens for tier-3 fallback comparison.
  - `resolve_thread()` — 4-tier resolver (see Threading resolver section above).
- **`backend/dao/email_threads_dao.py`** — `EmailThreadsDAO` with `get_thread_by_id`, `get_by_case_number`, `find_recent_by_participant`, `create_for_inbound`, `transition_on_inbound`. The `transition_on_inbound` method encodes the spam-is-sticky and resolved-reopens-on-reply rules.
- **`backend/dao/email_messages_dao.py`** — `EmailMessagesDAO` with `find_by_message_id` (idempotency), `find_thread_id_by_in_reply_to` (tier 1), `insert_inbound`.
- **`backend/services/email_service.py`** — outbound sender (pre-existing). Defines `SUPPORT_EMAIL = "support@contact.missingtable.com"` and the support-line helpers used in invite email templates. **Side effect**: `EmailService.__init__` sets `resend.api_key` as a module global. The inbound webhook calls `_ensure_resend_api_key()` to avoid depending on that side effect (see Lessons learned).

### Frontend

- **`frontend/src/components/SupportEmailLink.vue`** — single source of truth for the support address on the UI. Builds the `mailto:` href at runtime from JS constants (`SUPPORT_USER = "support"`, `SUPPORT_DOMAIN = "contact.missingtable.com"`) so the literal address never appears in template source. Accepts optional `subject` / `body` props for pre-filled mail clients.
- **`frontend/src/components/LoginForm.vue`** — uses `<SupportEmailLink />` in the invite-signup flow (footer + error states) with subject/body pre-filled from invite code + email.
- **`frontend/src/components/AuthNav.vue`** — uses `<SupportEmailLink />` in the user dropdown ("Contact support") with subject pre-filled as `[Account: {email}] Help request`.
- **Invite email templates** in `backend/services/email_service.py` (`send_invitation`, `send_invite_request_approval`) include a "Need help? Contact support@…" line via `_support_html_block()` / `_support_text_block()` helpers.

### Schema

- **`supabase-local/migrations/20260523000000_add_email_inbox.sql`** — full schema (sequence, both tables, indexes, RLS policies, updated_at trigger).

### Infrastructure

- **`helm/missing-table/templates/backend.yaml`** — wires two env vars from the K8s Secret `missing-table-secrets`:
  - `EMAIL_INBOUND_WEBHOOK_SECRET` ← `email-inbound-webhook-secret` (optional)
  - `RESEND_API_KEY` ← `resend-api-key` (optional). Pre-existing reference, but the K8s Secret key was only added during the SB-35 rollout — see Lessons learned.
- **`helm/missing-table/templates/secrets.yaml`** — local-dev path; values come from `values.secrets.emailInboundWebhookSecret` / `.resendApiKey`.
- **`helm/missing-table/values-prod.yaml`** — sets `RESEND_REPLY_TO: "support@contact.missingtable.com"` so user replies to MT-sent transactional emails route through the same inbound webhook.
- **`missingtable-platform-bootstrap/clouds/aws/global/certificate-management/main.tf`** — Route 53 record `aws_route53_record.resend_inbound_mx` on `contact.missingtable.com` pointing at `inbound-smtp.us-east-1.amazonaws.com`. **Do NOT confuse** with the pre-existing `resend_mx` resource on `send.contact.missingtable.com` — that's the outbound bounce-return MX and must stay as-is.
- **`missingtable-platform-bootstrap/clouds/linode/environments/dev/main.tf`** — the `missing-table-app-external-secret` ExternalSecret projects two additional properties from AWS Secrets Manager `missing-table-app-secrets`:
  - `email_inbound_webhook_secret` → K8s Secret key `email-inbound-webhook-secret`
  - `resend_api_key` → K8s Secret key `resend-api-key`

### Resend dashboard

Not in source control, but the configured state matters:

- **Domains** → `contact.missingtable.com` → Receiving toggled **on**.
- **Webhooks** → endpoint `https://api.missingtable.com/api/webhooks/email/inbound`, subscribed only to `email.received`, signing secret stored in AWS Secrets Manager (`resend_api_key` property).

## Operations

### Smoke test the inbound path

```bash
# 1. Send an email to the address from any external account.
# 2. Watch the Resend webhook dashboard:
#    Webhooks → your webhook → Recent Events → expect HTTP 200.
# 3. Tail backend logs:
kubectl -n missing-table logs deploy/missing-table-backend --tail=50 \
  | grep -E "email_webhook_ingested|email_thread_resolved"
# 4. Inspect the DB (Supabase Studio SQL editor):
SELECT t.case_number, t.status, t.unread_count, count(m.id) AS message_count
FROM public.email_threads t
LEFT JOIN public.email_messages m ON m.thread_id = t.id
GROUP BY t.case_number, t.status, t.unread_count
ORDER BY t.case_number DESC LIMIT 5;
```

### Debugging matrix

| Symptom | Likely cause | Where to look |
|---|---|---|
| `401 {"detail":"invalid webhook signature"}` | `EMAIL_INBOUND_WEBHOOK_SECRET` env var unset, wrong value, or Svix header names not remapped | `kubectl exec deploy/missing-table-backend -- printenv EMAIL_INBOUND_WEBHOOK_SECRET \| head -c 12`; compare with `whsec_` in Resend dashboard. |
| `502 {"detail":"failed to fetch email <id>"}` with `ValidationError: API key is invalid` in logs | `RESEND_API_KEY` env var unset (or `resend.api_key` global not initialized) | `kubectl exec deploy/missing-table-backend -- printenv RESEND_API_KEY \| head -c 8`. Must be `re_...`. |
| `500` with `relation "public.email_threads" does not exist` | Migration not applied to prod Supabase | Apply via Studio SQL editor; see SB-35 ticket for the SQL. |
| Webhook never arrives at the pod | DNS / MX issue or Resend not configured | `dig MX contact.missingtable.com` → expect `10 inbound-smtp.us-east-1.amazonaws.com.`; Resend dashboard → Domains → Receiving status. |
| Receives but thread number jumps unexpectedly | Tier-4 fallback firing when tier-1/2/3 should have matched | Check the `via:` field in the `email_thread_resolved` log line. |

### Sending a test from CLI

To probe the endpoint without a real email:

```bash
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST https://api.missingtable.com/api/webhooks/email/inbound \
  -H 'Content-Type: application/json' -d '{}'
# Expect: HTTP 401 (no svix headers).
```

### Resend dashboard event replay

If a delivery fails (your endpoint was down, secret rotation, etc.), Resend retries on a backoff schedule (~5s, 5m, 30m, 2h, 5h, 10h, 14h) for ~3 days. You can also manually replay from **Webhooks → your webhook → Recent Events → Replay** without composing another email — handy while iterating on the handler.

### Quota note

Inbound emails count against the same shared quota as sent (100/day, 3,000/month on Resend free tier). Each inbound also costs **one** API call (the `Emails.Receiving.get` for the body), but that doesn't count separately. Monitor in Resend dashboard.

## Lessons learned

These were the six layers we peeled back during the SB-35 prod cutover. All locked in by regression tests now. Worth understanding before touching this code:

### 1. Svix `WebhookHeaders` uses short keys, not HTTP header names

Resend's `WebhookHeaders` TypedDict expects keys `id` / `timestamp` / `signature` — **not** the HTTP header names `svix-id` / `svix-timestamp` / `svix-signature`. The field docstrings call them "the svix-id header value" etc. but the field names drop the prefix. Pass the full HTTP names through and the SDK fails with `Signature verification failed: svix-id header is required`. `verify_webhook` does the remap; test `test_passes_short_keys_to_svix_verify` locks it in.

### 2. `resend.api_key` is a module global with a hidden initializer

`EmailService.__init__` sets `resend.api_key` as a side effect on construction. But `EmailService` is instantiated lazily inside request handlers, so on a fresh pod with no outbound email having gone out yet, the inbound webhook calls `resend.Emails.Receiving.get` against `api_key=None` and gets `ValidationError: API key is invalid`. `_ensure_resend_api_key()` sets it on demand from the env var. Test `test_ensures_resend_api_key_before_fetch` covers this.

### 3. `RESEND_API_KEY` was never wired through ESO (latent bug, pre-SB-35)

The Helm chart has referenced `RESEND_API_KEY` from K8s Secret key `resend-api-key` for a long time, but the ESO `ExternalSecret` never mapped that property out of AWS Secrets Manager. Result: env var has been unset on every backend pod since the LKE migration in Feb 2026 — **outbound transactional emails (password resets, invites, request-approval notices) were silently broken**, and the SB-35 inbound bumped into it too. Fix: add the mapping in `clouds/linode/environments/dev/main.tf` and populate the AWS secret property.

### 4. `RESEND_REPLY_TO` initially pointed at an unreachable address

`values-prod.yaml` had `RESEND_REPLY_TO: "support@missingtable.com"` — the apex domain has no MX record, so user replies to MT-sent transactional emails were silently bouncing. Now set to `support@contact.missingtable.com`.

### 5. Migration tracking drift in prod Supabase

`scripts/db_tools.sh migrate prod` (which wraps `supabase db push --linked`) failed with "Remote migration versions not found in local migrations directory" for 11 pre-existing migrations, even though the files were all present locally. Workaround for SB-35: apply the migration directly via Supabase Studio SQL editor. Long-term fix is tracked in [SB-?? — fix migration tracking drift] (separate ticket). To record a manually-applied migration so future `db push` doesn't re-attempt:

```bash
cd supabase-local
npx supabase migration repair --status applied 20260523000000 --linked
```

### 6. Image-tag vs commit-SHA confusion in ArgoCD GitOps

After merging a PR with application code changes, the deployed image tag is the **code commit SHA** (e.g. `10f1709`), not the auto-created `chore: Update image tags to ...` commit SHA (e.g. `e6fa46e`). Polling for the wrong SHA looks like a hung deploy when really the new pod is up. Always compare the running image tag against the **PR merge commit**, not the latest commit on main.

## Out of scope (Phase 2/3)

- **Phase 2 — admin API**: `GET /api/admin/emails/threads`, `GET /api/admin/emails/threads/{id_or_case_number}`, `POST .../reply`, `PATCH .../status`, `PATCH .../read`, `GET .../unread-count`. Outbound replies set proper `In-Reply-To` / `References` headers so user mail clients keep the thread.
- **Phase 3 — admin UI**: new section in `AdminPanel.vue`. Inbox list with status tabs and case-number column, thread view with chat-style rendering, reply composer. Nav badge for "needs attention" count.

When these ship, this doc should be updated rather than forked.

---

**Last updated:** 2026-05-23 (Phase 1 cutover)
