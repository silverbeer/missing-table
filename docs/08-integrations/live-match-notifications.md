# Live-Match Notifications

Deliver live-match events (kickoff, goal, card, halftime, full-time) to each club's Telegram group, Discord channel and/or Slack channel as matches are scored.

- **Who it's for:** club managers who want their community to follow matches in real time, and admins onboarding new clubs.
- **Per-club, opt-in:** a club receives notifications only if it has a row in `club_notification_channels`. Matches between two clubs with no config produce no external calls.
- **Supported platforms:** Telegram, Discord and Slack. A club can enable any combination.
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
                        ├─► format_event()              ── renders one plain-text message
                        │
                        ▼
                  backend/notifications/senders.py::send_to
                        │
                        ▼
                  backend/notifications/registry.py::get_adapter
                        ├─► adapters/telegram.py (bot_token from env) ──► api.telegram.org
                        ├─► adapters/discord.py  (webhook URL)        ──► discord.com
                        └─► adapters/slack.py    (webhook URL)        ──► hooks.slack.com
```

Best-effort delivery. The dispatcher catches all exceptions — notifications **never** block the user-facing live-scoring flow. Failures are logged, not retried.

**Execution model:** FastAPI `BackgroundTasks` (in-process, after-response). Not Celery. No retry queue.

### Adding a platform

Platforms are adapters. Everything specific to one platform (destination format, escaping, config check, send) lives in one module:

1. Subclass `ChannelAdapter` in `backend/notifications/adapters/<platform>.py`.
2. Add `register(YourAdapter())` in `backend/notifications/registry.py`.

No migration, API change or frontend change. `GET /api/notifications/platforms` serves the label, hint and validation pattern to the setup UI, and `tests/unit/test_notification_adapters.py` applies the contract to every registered adapter.

`destination_pattern` is checked by both Python and the browser, so keep it to syntax both read the same way. For webhook platforms it is also the SSRF guard: the backend POSTs to whatever passes it. Implement `_deliver`, which returns a `DeliveryResult` with the provider's message id when there is one, and declare optional features in `capabilities`. The public `send` converts provider failures to `DeliveryError`, because `httpx` errors include the URL, which holds the Telegram bot token or a webhook's secret path.

---

## 🗄️ Data Model

Migration: `supabase/migrations/20261109130000_notification_channels.sql`

**`notification_channels`** says where match updates are posted.

| Column         | Type      | Notes                                                                        |
| -------------- | --------- | ---------------------------------------------------------------------------- |
| `id`           | SERIAL    | Primary key                                                                  |
| `scope_type`   | TEXT      | `club`, `team` or `global`                                                   |
| `club_id`      | INTEGER   | Set for `club` scope only                                                    |
| `team_id`      | INTEGER   | Set for `team` scope only                                                    |
| `age_group_id` | INTEGER   | Required with `team_id`: a team row is a club in one league, the age group makes it a squad |
| `audience`     | TEXT      | `fans` or `players`; `global` is fans only                                   |
| `platform`     | TEXT      | A registered adapter id; validated by the API, not the database              |
| `destination`  | TEXT      | Chat id or webhook URL. Sensitive; never logged or returned in full          |
| `event_types`  | TEXT[]    | `NULL` = every event, `{}` = none; never collapse the two                    |
| `enabled`      | BOOLEAN   | Default `true`                                                               |
| `created_by`   | UUID      | Who set it up; `NULL` for rows migrated from the old table                   |

A match reaches both clubs' channels, both squads' channels at the match's age group, and every global channel, de-duplicated by destination. Test matches reach none.

**Player channels** exist from U14 and only on platforms that allow it: each adapter sets `min_player_age` from the platform's terms (Discord 14, Slack 17, Telegram none, so fans only). A club player channel spans every age from U14, so only a platform that allows U14 can host it. An age group MT can't read as `U<number>` never qualifies. U13 matches skip player channels entirely.

`club_notification_channels` is the previous table: no longer read, kept until this has been verified in production.

**RLS policies:** admins have full access; club managers manage their club's channels and its teams'; team managers manage their own team's. No access for anyone else, including fans and players.

`20260421000000_add_club_notification_channels.sql` also added `clubs.timezone TEXT NOT NULL DEFAULT 'America/New_York'` — used to render match kickoff times in notification messages.

---

## 🚀 Onboarding a Club

The flow: create the platform destination (once per club), then paste the identifier into Missing Table.

**Rooms are community-run (SB-1612).** Missing Table is independent community software, not affiliated with any club or league. MT posts match updates to a room; it does not run or moderate it. The manager who sets the room up owns it and moderates it.
- The UI says so on the members' card, titled "Community channels for <club>", and on the setup screen.
- The UI never calls a room private or verified, because invite links can be passed on.
- Each platform's minimum age (`age_note` on the adapter, e.g. Discord 13+ and older in some countries) is shown wherever a channel on it is offered.

### Telegram

1. **Create a Telegram group** for your club (or use an existing one).
2. **Add the bot** (`@missingtable_bot`, display name "MTBot") to the group and promote it to admin (sending messages does not require admin, but admin prevents accidental removal).
3. **Get the `chat_id`:** open the group at [web.telegram.org](https://web.telegram.org) and copy the number after `#` in the address bar (e.g. `-1001234567890`). A public group or channel can use its `@username` instead.
   - If **Send test** fails and the number does not start with `-100`, add `-100` in front: supergroups and channels need it, and Telegram Web does not always show it.
   - Admins can also read it from the bot directly:
     ```bash
     curl "https://api.telegram.org/bot<BOT_TOKEN>/getUpdates" | jq '.result[].message.chat'
     ```
4. Paste the `chat_id` into Missing Table below.

> Don't have the bot token? An admin does. Rotation steps are in [Operations](#-operations).

### Discord

1. **Open the Discord channel** where notifications should post.
2. **Edit channel → Integrations → Webhooks → New Webhook.**
3. Name it (e.g. `Missing Table`), pick the channel, copy the **Webhook URL**.
4. The URL looks like `https://discord.com/api/webhooks/<id>/<token>`. Treat it like a password — anyone with this URL can post to your channel.

Full guide, including the forum layout for match threads and read-only player rooms: [discord-setup.md](discord-setup.md).

### Slack

1. In your workspace, [create a Slack app](https://api.slack.com/apps) and turn on **Incoming Webhooks**.
2. Click **Add New Webhook to Workspace** and pick the channel. Each webhook posts to one channel.
3. Copy the URL, which starts `https://hooks.slack.com/services/`. Treat it like a password.

Slack's terms require users to be over 16, so don't use it for youth player rooms.

### Configure in Missing Table

One setup screen, `ChannelManager.vue` (with `ChannelForm.vue`), handles one scope at a time and holds several channels. Each channel has a platform, an audience (fans or players), an optional **name**, its destination, an optional **invite link**, and which events it posts. It shows when it last posted.

| Scope | Where | Who |
|-------|-------|-----|
| Squad (team + age group) | Team page → **Team chat channels** card → **Manage chat channels** | anyone who can manage the team (the card asks the server: `can_manage`) |
| Club | **Profile** (club manager), or **Admin → Access → Live Match Notifications → One club** | that club's manager, admins |
| Every match | **Admin → Access → Live Match Notifications → Every match** | admins |

On each channel:
- **Name** (`label`, up to 80 characters): the manager's own name for it, e.g. `#u15-live`. A destination is write-only and a Slack webhook URL doesn't carry the channel's name, so this is how managers tell channels apart. Blank is stored as `NULL`.
- **Events**: "Every match event" saves `event_types = NULL`; "Only these" saves the chosen list, and an empty list means nothing posts. The UI never collapses the two.
- **Enabled** pauses or resumes (`PATCH` with `enabled`) and keeps everything else; **Remove** deletes the channel and its grants.
- **Send test** posts a test message (`POST /{id}/test`, 5 a minute per channel). It is not recorded in the delivery ledger.
- **Last post** comes from the newest `notification_deliveries` row: posted, failed (with the sanitized error), or sending. "Nothing posted yet" and "Delivery history unavailable" (ledger unreadable) are different states.

Platform names, setup steps, destination labels and the destination and invite-link patterns all come from `GET /api/notifications/platforms`; event names come from `GET /api/notification-channels/event-types`. Nothing in the UI lists them.

API endpoints (defined in `backend/api/club_notifications.py`):

| Action       | Method | Path                                                  |
| ------------ | ------ | ----------------------------------------------------- |
| List         | GET    | `/api/clubs/{club_id}/notifications`                  |
| Upsert       | PUT    | `/api/clubs/{club_id}/notifications/{platform}`       |
| Pause/resume | PATCH  | `/api/clubs/{club_id}/notifications/{platform}`       |
| Delete       | DELETE | `/api/clubs/{club_id}/notifications/{platform}`       |
| Send test    | POST   | `/api/clubs/{club_id}/notifications/{platform}/test`  |
| Platforms    | GET    | `/api/notifications/platforms`                        |

Those endpoints manage each club's oldest fan channel per platform; the UI no longer uses them. Scoped channels (squads, club players, global, several per platform) use `/api/notification-channels`: `GET` with `scope_type` plus its ids (each row carries `label`, `last_delivery` and `last_delivery_known`), `GET /event-types`, `POST`, `PATCH /{id}`, `DELETE /{id}`, `POST /{id}/test`. Global needs an admin, a club needs that club's manager, and a squad needs anyone who can manage the team.

---

## 🛠️ Operations

### Global kill switch

Environment variable `NOTIFICATIONS_ENABLED` (default `true`).

- Values treated as disabled: `0`, `false`, `no`, `off` (case-insensitive).
- Checked in `backend/notifications/dispatcher.py::is_notifications_enabled` and `backend/api/club_notifications.py`.
- When **disabled**:
  - Dispatcher short-circuits and logs `notifications.skipped reason=disabled`.
  - Test-send endpoint returns **HTTP 503**.
  - No external calls to any chat platform.

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
- Platform adapters: `backend/notifications/adapters/`, registered in `backend/notifications/registry.py`
- Send entry point: `backend/notifications/senders.py`
- API: `backend/api/club_notifications.py`
- DAO: `backend/dao/notification_channels_dao.py`, `backend/dao/club_notifications_dao.py`
- Scoped API and audience rules: `backend/api/notification_channels.py`, `backend/notifications/audience.py`
- Setup UI: `frontend/src/components/notifications/ChannelManager.vue`, `ChannelForm.vue`, mounted in `admin/AdminClubNotifications.vue`, `profiles/ClubManagerProfile.vue` and `TeamChannelsCard.vue`
- Club-manager UI: `frontend/src/components/profiles/ClubManagerProfile.vue`
- Helm: `helm/missing-table/templates/backend.yaml`, `helm/missing-table/values.yaml`
- Migrations: `supabase/migrations/20260421000000_add_club_notification_channels.sql`, `20261109120000_drop_notification_platform_check.sql`
- Epic: [#315](https://github.com/silverbeer/missing-table/issues/315)

## Delivery ledger

Every chat post is recorded in `notification_deliveries`, one row per channel and event. The dispatcher inserts the row before it posts, and `UNIQUE (channel_id, event_key)` makes a second attempt for the same event skip the post.

| Event | `event_key` | Effect |
|-------|-------------|--------|
| Goal, card | `match:<id>:event:<match_events.id>` | Each recorded event posts once |
| Kickoff, halftime | `match:<id>:<event>` | Once per match |
| Full time | `match:<id>:fulltime:<home>-<away>` | Same result posts once; a corrected score posts again |

- A row stuck in `pending` means the process stopped mid-send: the message was missed, not doubled.
- A `failed` row also blocks a repeat. Retrying is a separate change (SB-1604).
- If the ledger is unreachable the post goes out unrecorded, because losing an update is worse than the small chance of repeating one.
- The ledger holds no destination, and `error` is sanitized. Web Push, APNs and FCM keep using `push_send_log`.

## Channel access (SB-1607)

MT does not add people to chat rooms. It decides who may see a channel's **invite link** (`notification_channels.invite_url`) and records each grant in `channel_members`. The link must be the platform's private join link (`t.me/+…`, `discord.gg/…`, `join.slack.com/t/…/shared_invite/…`); a public link would make the grant meaningless. Unlike `destination`, the link is shown, but only to an active member who is still eligible.

| Channel | Who sees it | How they get in |
|---------|-------------|-----------------|
| Squad fans | fans of the club; the squad's managers | fan requests, a manager approves; or a manager invites |
| Squad players (U14+) | players currently on the squad; its managers | join directly |
| Club fans | fans and team managers whose My Club is the club; club managers | join directly |
| Club players (U14+) | the club's players on a U14+ squad; club managers | join directly |
| Global | nobody through this API | admin only |

- Rules are pure functions in `notifications/membership.py`; the viewer's standing (role, club, current squads) comes from `channel_viewer` in `mt_tools/my_team.py`.
- Players never see fan or club fan channels, and fans never see player channels. A hidden channel answers 404, so its existence does not leak.
- Eligibility is re-checked on every read. A player who leaves a squad stops seeing its link without anyone revoking it. Removing them from the chat itself is still a manual step on the platform.
- A manager can only grant access to someone the rules already allow to ask or join.
- No handle is collected: the member uses the link themselves, so nothing about a minor's chat account is stored.
- A fan cannot change their own club; only an admin or an invite sets `club_id`.

| Endpoint | Who |
|----------|-----|
| `GET /api/teams/{id}/channels/available` | any signed-in user; always 200 |
| `GET /api/me/channels[?team_id=]` | any signed-in user: the profile card's view, with `has_team`, `managed` (claimed) and `can_manage` |
| `POST /api/channels/{id}/join`, `POST`/`DELETE /api/channels/{id}/request` | the user |
| `GET /api/channels/requests?team_id=` | admin, club manager, the team's manager |
| `PUT /api/channels/{id}/members/{user_id}` (`active`, `denied`, `revoked`) | same |

### Team chat channels card (SB-1609)

`components/notifications/TeamChannelsCard.vue` sits on every profile page (the viewer's own team and club) and on the My Club page (that team, via `team_id`). It renders only what `/api/me/channels` returns, so platform names and audience rules live on the server.

| State | Shown |
|-------|-------|
| No club or team | "Channels show up here once you belong to a club or team" |
| Unclaimed team (`managed: false`) | claim prompt |
| No channels, viewer manages | channels appear once they have an invite link |
| No channels, viewer is a member | ask your team manager |
| `can_request` / `requested` | Request invite / Request pending, with Withdraw |
| `can_join` | Join |
| `member` | Open in <platform> |
| `denied` / `revoked` | ask a manager |

It never says "Joined": MT gives out a link and cannot tell whether it was used.

Managers add invite links on the setup screen (SB-1605); the form checks each one against the platform's private-link pattern. The old `channel_access_requests` table and `/api/channel-requests` (admin review screen) stay until that screen moves over.

## Personal alerts: team and squad follows (SB-1608)

Chat channels post to a group. A **follow** sends match alerts to one user's own devices (web push, iOS via APNs, Android via FCM). Following is for alerts only; it never grants access to a chat channel.

A team row spans several age groups, so a follow names the squad:

| `user_team_follows.age_group_id` | Alerts for |
|---|---|
| `NULL` | every age group of the team. Every follow made before SB-1608 is one of these and keeps exactly the alerts it had. The mobile apps still create these. |
| `N` | matches of that team in age group `N` only |

- The dispatcher passes the match's age group to the follower lookup, and `follows_match` in `dao/team_follow_dao.py` decides each row. All three device fan-outs share that lookup.
- A match with no age group reaches whole-team followers only, because MT cannot tell which squad played.
- Rows are unique on `(user_id, team_id, age_group_id)`, with `NULL` counted as a value.
- Per-event preferences (kickoff, goals, cards…) remain per user. There is no per-squad override yet.

**Following a squad of any club (SB-1618).** The **Follow** button on the Matches tab and on a team page follows the squad being viewed, e.g. New England Revolution Pro Academy U16. It sends `age_group_id`, which must be an age group the team plays; otherwise the request is a 400. A whole-team follow already covers every squad, so following a squad of a team that is already followed whole adds nothing. Unfollowing a squad that is covered by a whole-team follow removes the whole-team follow.

**Profile card: Match alerts.** The fan profile lists every follow as one chip. Own-club follows are under **Your club**; follows of other clubs' teams are under **Other teams**. A whole-team follow shows as one "… · every age group" chip. Each chip has × to stop those alerts. A line appears when alerts cannot reach this device yet, linking to the setup guide. The hero stat **Alerts** counts the chips. The notifications settings list the same follows as **Your match alerts**.

**Choosing squads.** On the fan profile, **Choose squads** opens a picker of every squad in the fan's own club, grouped by league. Saving sends `PUT /api/me/squad-follows` with `{squads: [{team_id, age_group_id}, …]}`, which replaces the fan's follows of their club's teams:

- A whole-team follow of a club team is replaced by the squads ticked for it. The picker shows an existing whole-team follow with all of that team's squads ticked, so saving without changes keeps every alert.
- Follows of other clubs' teams are untouched.
- New rows are written before old ones are removed, so a failed save can leave extra alerts but never removes any.
- Only `team-fan` and `club-fan` accounts can use it, and only for squads in their own club; anything else is a 400.

**Assignment is separate.** A fan's `team_id` and `assigned_age_group_id` are their assigned team. Only a team-fan invite or an admin sets them, and the profile shows that team as "set by your team manager". Before SB-1608 a fan's own pick (`PUT /api/me/team`) wrote the same fields, so a self-pick could not be told apart from a manager's assignment. That endpoint is gone, and choosing squads never touches the profile. MT AI's "my team" reads the assignment only.

| Endpoint | What |
|---|---|
| `GET /api/me/team-options` | the fan's club squads, plus the assigned team as `current_team_id` / `current_age_group_id` |
| `PUT /api/me/squad-follows` | replace the fan's own-club squad follows |
| `POST /api/users/me/team-follows` `{team_id, age_group_id?}` | follow a whole team, or with `age_group_id` one squad (any club) |
| `GET /api/users/me/team-follows` | every follow, with `age_group_id` and `age_group {id, name}` |
| `DELETE /api/users/me/team-follows/{team_id}[?age_group_id=N]` | without `age_group_id`, removes every follow of the team (what the apps send); with it, removes only that squad |


## Scraped scores (SB-1619)

The match scraper's Celery worker writes scores straight to `matches`, so the API's own write-path alert (`_maybe_notify_final_score`) never runs for them. The worker also has none of the push credentials. Instead, after a write that `is_new_final_score` says set a new final score, the worker calls:

`POST /api/matches/{id}/final-score-alert`. Only admins, or a service account with `manage_matches`, may call it.

The API re-reads the match and sends the `fulltime` alert (followers' devices and chat channels) only when `final_alert_blocker` finds nothing:

| Reason | Meaning |
|---|---|
| `no_score` / `not_completed` | not a final score |
| `too_old` | dated more than 3 days ago, or in the future. A backfill or a season load must not alert anyone. |
| `already_sent` | this match and score were already alerted. A Redis claim on `alert:sent:<event key>` lasts 5 days; with Redis down it fails open. |

- The response is always 200 for a known match, with `queued` and `reason`.
- The event key is the score, so a corrected score alerts again.
- A live-scored match the scraper later confirms with the same score does not, because the worker sees no change.

**Worker side.** `celery_tasks/final_score_alert.py` signs a 5-minute service token with `SERVICE_ACCOUNT_SECRET`, which must match the backend's, and posts to `MT_API_URL`. It is best-effort: a failure is logged (`final_score_alert_failed` / `_rejected`) and never fails or retries the ingest. Without `MT_API_URL` it logs `final_score_alert_dormant` and does nothing.

**Deploying it.** The worker runs on rancher-desktop, outside GitOps. After merge:
1. Tag the running image as a rollback: `docker tag missing-table-worker:latest missing-table-worker:pre-sb1619`.
2. Add `MT_API_URL: "https://api.missingtable.com"` to the `missing-table-worker-prod-config` configmap.
3. Run `k3s/worker/rebuild-and-deploy.sh`.
4. Check the worker log for `final_score_alert_requested` after the next scored match. `final_score_alert_rejected` with `http_status=401` means the two `SERVICE_ACCOUNT_SECRET`s differ.

## Player-only events (SB-1610)

Some posts are content for a squad's players, not its fans. They are listed in `PLAYER_EVENT_TYPES` (`notifications/preferences.py`). `CHANNEL_EVENT_TYPES` is the full list a channel can choose from. `GET /api/notification-channels/event-types` marks them `player_only: true`.

| Event | Fires when | Post |
|---|---|---|
| `lineup` ("Lineup posted") | a manager saves a lineup with at least one player, for a scheduled, TBD or live match | "📋 LINEUP — Home vs Away", the squad tag, "<team> lineup is up in Missing Table: 11 players, 4-3-3", kickoff time |

**Rules:**
- **Audience:** a player-only event reaches only the player channel of the squad it is about. That means scope `team`, audience `players`, and the event's `team_id`.
  - Never a fan channel or a club channel, even one set to "every event".
  - Never the other team's squad, and never a global channel.
  - Never anyone's personal push: followers are fans.
  - Enforced in `select_destinations` and in `Notifier.notify`.
- **Setup:** the API refuses a player-only event on any other channel (422). The setup form offers it only on a squad player channel, and drops it from the selection if the audience is switched to fans.
- **Once:** the event key is `match:<id>:lineup:<team_id>`, so editing a saved lineup does not post again. An empty lineup, or one saved for a match already played, sends nothing. Teams that never enter lineups get no posts.
- **Names stay in MT:** the post gives the formation and the number of players, not who. Squads are minors, and the room's invite link can be forwarded.

**Kickoff reminders: decided, not built.** A reminder is a post at a set time (e.g. two hours before kickoff), not a reaction to a write. The API has no scheduler, and the Celery worker runs outside GitOps. Reminders will therefore run on the delivery worker from SB-1604, as ledger rows with a `not_before` time. When that ships, `kickoff_reminder` joins `PLAYER_EVENT_TYPES`.

## Retrying chat posts (SB-1604)

The live path posts each message once. A post is no longer lost when the provider rate-limits it, has a server error, the network fails, or the pod restarts mid-send.

- **Ledger:** each `notification_deliveries` row keeps the rendered `content` (match text only, never a destination), plus `match_id`, `event_type` and `next_attempt_at`.
- **Which failures retry:** `classify_failure` in `notifications/adapters/base.py` decides.
  - **Retried:** 429 (honouring `Retry-After` or the provider's `retry_after`), 5xx, and timeouts or other transport errors. The row stays `pending` with a `next_attempt_at`.
  - **Final:** anything else, e.g. a deleted webhook (404) or a bad chat ID (400). The row becomes `failed` immediately.
- **Backoff:** `notifications/retry_policy.py`. 30 s, 60 s, 120 s, 240 s, capped at 15 minutes, with up to 10% jitter. A provider's own wait is never shortened. After 5 attempts the row is `failed` for good, and the channel's **Last post** shows that to its managers and admins.
- **Worker:** `notifications/retry_worker.py` runs in a background thread of the backend process, never on a request. Every 15 s it calls `claim_due_notification_deliveries`:
  - The claim is atomic (`FOR UPDATE SKIP LOCKED`), counts the attempt, and leases the row for 120 s, so two pods never send the same post.
  - It also picks up a first send that never finished: a `pending` row more than 120 s old with no `next_attempt_at`.
  - Sends run on up to 8 threads, and each records its own outcome, so one slow destination does not hold up the others.
  - A channel removed or paused since the first try is not posted to.
  - The global kill switch (`NOTIFICATIONS_ENABLED`) pauses it.
- **Switch:** `NOTIFICATION_RETRY_WORKER` (`notifications.retryWorker` in Helm). Off by default, so tests and local runs never start it; `"on"` in `values-prod.yaml`.
- **Duplicates:** a post that succeeded at the provider but whose result was lost (e.g. a timeout after delivery) can be posted twice. That is preferred to losing a goal update; the ledger's unique `(channel_id, event_key)` still stops a resent event from creating a second row.
