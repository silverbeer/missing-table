# Live-Match Notifications

Deliver live-match events (kickoff, goal, card, halftime, full-time) to each club's Telegram group and/or Discord channel as matches are scored.

- **Who it's for:** club managers who want their community to follow matches in real time, and admins onboarding new clubs.
- **Per-club, opt-in:** a club receives notifications only if it has a row in `club_notification_channels`. Matches between two clubs with no config produce no external calls.
- **Supported platforms:** Telegram and Discord. A club can enable either or both.
- **Trigger points:** the live-scoring UI and `/api/matches/{match_id}/live/*` endpoints — `kickoff`, `goal`, `yellow_card`, `red_card`, `halftime`, `fulltime`.

---

## 🏗️ Architecture

```
Live-scoring UI  ──► POST /api/matches/{id}/live/{action}
                        │
                        ▼
                  backend/api/matches.py
                        │
                        │ BackgroundTasks.add_task(notify_event_task, ...)
                        ▼
                  backend/notifications/tasks.py::notify_event_task
                        │
                        ▼
                  backend/notifications/dispatcher.py::Notifier.notify
                        │
                        ├─► resolve_destinations()      ── reads club_notification_channels
                        ├─► fetch_club_timezone()       ── reads clubs.timezone
                        ├─► format_event()              ── renders per-platform message
                        │
                        ▼
                  backend/notifications/senders.py::send_to
                        ├─► TelegramClient (bot_token from env) ──► api.telegram.org
                        └─► DiscordWebhookClient (webhook URL)  ──► discord.com
```

Best-effort delivery. The dispatcher catches all exceptions — notifications **never** block the user-facing live-scoring flow. Failures are logged, not retried.

**Execution model:** FastAPI `BackgroundTasks` (in-process, after-response). Not Celery. No retry queue.

---

## 🗄️ Data Model

Migration: `supabase-local/migrations/20260421000000_add_club_notification_channels.sql`

**`club_notification_channels`**

| Column        | Type      | Notes                                                            |
| ------------- | --------- | ---------------------------------------------------------------- |
| `id`          | SERIAL    | Primary key                                                      |
| `club_id`     | INTEGER   | FK → `clubs(id) ON DELETE CASCADE`                               |
| `platform`    | TEXT      | `telegram` or `discord` (CHECK)                                  |
| `destination` | TEXT      | Telegram `chat_id` or Discord webhook URL. Sensitive; not logged |
| `enabled`     | BOOLEAN   | Default `true`                                                   |
| `created_at`  | TIMESTAMP |                                                                  |
| `updated_at`  | TIMESTAMP |                                                                  |

- `UNIQUE (club_id, platform)` — one row per club per platform
- Index: `(club_id, enabled)`

**RLS policies:**
- `club_notification_channels_admin_all` — full CRUD for admins via `is_admin()`.
- `club_notification_channels_club_manager_own_club` — full CRUD for a club manager on rows whose `club_id` matches their `user_profiles.club_id`.
- No anonymous access.

The same migration adds `clubs.timezone TEXT NOT NULL DEFAULT 'America/New_York'` — used to render match kickoff times in notification messages.

---

## 🚀 Onboarding a Club

The flow: create the platform destination (once per club), then paste the identifier into Missing Table.

### Telegram

1. **Create a Telegram group** for your club (or use an existing one).
2. **Add the bot** (`@missingtable_bot`, display name "MTBot") to the group and promote it to admin (sending messages does not require admin, but admin prevents accidental removal).
3. **Get the `chat_id`:**
   - Send any message in the group.
   - From a terminal with the bot token handy, fetch updates:
     ```bash
     curl "https://api.telegram.org/bot<BOT_TOKEN>/getUpdates" | jq '.result[].message.chat'
     ```
   - Look for the group's `id` — it's a negative integer, typically 13 digits (e.g. `-1001234567890`).
4. Copy the `chat_id` — you'll paste it into Missing Table below.

> Don't have the bot token? An admin does. Rotation steps are in [Operations](#-operations).

### Discord

1. **Open the Discord channel** where notifications should post.
2. **Edit channel → Integrations → Webhooks → New Webhook.**
3. Name it (e.g. `Missing Table`), pick the channel, copy the **Webhook URL**.
4. The URL looks like `https://discord.com/api/webhooks/<id>/<token>`. Treat it like a password — anyone with this URL can post to your channel.

### Configure in Missing Table

Two paths — both write to the same table, governed by RLS.

**Club manager (self-serve):**
1. Sign in → **Profile** tab.
2. Scroll to the **Notifications** card.
3. For each platform, paste the `chat_id` / webhook URL, toggle **Enabled**, click **Save**.
4. Click **Send test** to verify delivery.

**Admin (on behalf of any club):**
1. Sign in → **Admin** tab → **Club Notifications** section.
2. Pick the club from the dropdown.
3. Same Save / Send test flow as above.

Component: `frontend/src/components/notifications/ClubNotificationChannels.vue` (reused in both contexts).

API endpoints (defined in `backend/api/club_notifications.py`):

| Action       | Method | Path                                                  |
| ------------ | ------ | ----------------------------------------------------- |
| List         | GET    | `/api/clubs/{club_id}/notifications`                  |
| Upsert       | PUT    | `/api/clubs/{club_id}/notifications/{platform}`       |
| Delete       | DELETE | `/api/clubs/{club_id}/notifications/{platform}`       |
| Send test    | POST   | `/api/clubs/{club_id}/notifications/{platform}/test`  |

---

## 🛠️ Operations

### Global kill switch

Environment variable `NOTIFICATIONS_ENABLED` (default `true`).

- Values treated as disabled: `0`, `false`, `no`, `off` (case-insensitive).
- Checked in `backend/notifications/dispatcher.py::is_notifications_enabled` and `backend/api/club_notifications.py`.
- When **disabled**:
  - Dispatcher short-circuits and logs `notifications.skipped reason=disabled`.
  - Test-send endpoint returns **HTTP 503**.
  - No external calls to Telegram or Discord.

In production it's wired from `helm/missing-table/values.yaml`:

```yaml
notifications:
  enabled: true
```

To flip it off without a rollout, `kubectl set env` on the backend Deployment:

```bash
kubectl -n missing-table set env deploy/missing-table-backend NOTIFICATIONS_ENABLED=false
```

(this will trigger a rolling restart, but is faster than a values.yaml → ArgoCD round-trip.)

### Rate limits

- **Test-send only:** 5 sends/min/club, fixed-window in Redis (`ratelimit:notify-test:{club_id}`).
- Fail-open: if Redis is down, requests are allowed.
- Returns **HTTP 429** when exceeded. The UI surfaces a toast.
- **No rate limit on live-event dispatch** — expected volume is bounded by match activity.

### Rotating the Telegram bot token

Secret path in AWS Secrets Manager: `missing-table-app-secrets` → key `telegram_bot_token`.

1. **Generate the new token** with [@BotFather](https://t.me/BotFather): `/revoke` then `/newtoken` (or `/token` to view the current one first).
2. **Update AWS Secrets Manager:**
   ```bash
   aws secretsmanager update-secret \
     --secret-id missing-table-app-secrets \
     --secret-string "$(aws secretsmanager get-secret-value \
       --secret-id missing-table-app-secrets --query SecretString --output text \
       | jq --arg t 'NEW_TOKEN' '.telegram_bot_token = $t')"
   ```
3. **Force ESO to pull the new value:**
   ```bash
   kubectl -n missing-table annotate externalsecret missing-table-app-secrets \
     force-sync=$(date +%s) --overwrite
   ```
4. **Roll the backend so the new pod picks up the env var:**
   ```bash
   kubectl -n missing-table rollout restart deploy/missing-table-backend
   ```
5. **Verify:**
   ```bash
   kubectl -n missing-table exec deploy/missing-table-backend -- sh -c 'echo -n $TELEGRAM_BOT_TOKEN | wc -c'
   ```
   Expect the length of the new token. Then send a test message from the admin UI.

Discord webhook URLs live per-club in Postgres — no global rotation; the club edits their own row to swap.

### Debugging with logs

All notification logs use `structlog` and share the `notifications.` prefix. To tail a running pod:

```bash
kubectl -n missing-table logs -f deploy/missing-table-backend | grep 'notifications\.'
```

Fields to grep for:

| Log event                                  | Level   | When it fires                                       |
| ------------------------------------------ | ------- | --------------------------------------------------- |
| `notifications.skipped reason=disabled`    | info    | `NOTIFICATIONS_ENABLED=false`                       |
| `notifications.skipped reason=match_not_found` | warn | Match ID not in DB                                  |
| `notifications.skipped reason=no_channels` | info    | Neither home nor away club has channel config       |
| `notifications.skipped reason=unknown_event_type` | warn | Formatter doesn't recognize `event_type`        |
| `notifications.send_failed`                | warn    | Single destination errored (includes `platform`, `error_type`, `error`) |
| `notifications.dispatched`                 | info    | Summary: `sent` and `failed` counts per event       |
| `notifications.task_failed`                | warn    | Exception in the BackgroundTask wrapper itself      |

All carry `match_id` and `event_type` as keys. `notifications.send_failed` also carries `platform` so you can pivot by Telegram vs. Discord.

**Triage pattern for "why didn't a club get a message?":**
1. Grep for the `match_id`. If you see `notifications.skipped reason=no_channels`, neither club is onboarded.
2. If you see `notifications.dispatched sent=N failed=M`, at least one destination was attempted. Non-zero `failed` → check for `notifications.send_failed` with the same `match_id`.
3. If you see nothing at all, the backend didn't reach the dispatcher — check that the live-scoring endpoint was actually called and that BackgroundTasks fired.

---

## 🔒 Security Model

- **Webhook URLs and Telegram `chat_id`s live in Postgres** (`club_notification_channels.destination`). They're protected by RLS — only admins and the club's own manager can read or write them.
- **Bot token** lives only in env var (via k8s Secret, via AWS Secrets Manager). Never in the DB, never in git, never in logs.
- **The `destination` column is never logged.** Only `platform`, `match_id`, `event_type`, and error metadata appear in structured logs.
- **No cross-club leakage:** a club manager cannot read, edit, or send tests for another club — enforced in Postgres by the `club_manager_own_club` RLS policy, not just by UI.
- **Test-send rate limit** (5/min/club) protects both platforms from a runaway loop via the admin UI.
- **`optional: true`** on the `TELEGRAM_BOT_TOKEN` secret reference means the backend boots even if the token is missing. The dispatcher raises `NotificationConfigError` on the first Telegram send; the error is caught and logged as `notifications.send_failed` — the live-scoring flow keeps working.

---

## Related Files

- Dispatcher: `backend/notifications/dispatcher.py`
- BackgroundTask wrapper: `backend/notifications/tasks.py`
- Channel resolver: `backend/notifications/channel_resolver.py`
- Formatters: `backend/notifications/formatters.py`
- Platform senders: `backend/notifications/senders.py`
- API: `backend/api/club_notifications.py`
- DAO: `backend/dao/club_notifications_dao.py`
- Admin UI: `frontend/src/components/notifications/ClubNotificationChannels.vue`, `frontend/src/components/admin/AdminClubNotifications.vue`
- Club-manager UI: `frontend/src/components/profiles/ClubManagerProfile.vue`
- Helm: `helm/missing-table/templates/backend.yaml`, `helm/missing-table/values.yaml`
- Migration: `supabase-local/migrations/20260421000000_add_club_notification_channels.sql`
- Epic: [#315](https://github.com/silverbeer/missing-table/issues/315)
