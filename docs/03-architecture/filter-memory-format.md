# Filter-memory format v1 (web, Android, iOS)

**Tickets:** SB-1722 (this spec + server merge) · SB-1716 (web) · SB-1717 (Android) · SB-1718 (iOS)
**Builds on:** SB-1715 — `user_profiles.filter_memory`, `PUT /api/auth/filter-memory/{view}`

A signed-in viewer's Table and Matches filters are stored on their account, so
they follow the viewer to another device **and to another platform**. That only
works if every client means the same thing by the same field. This page is
that agreement.

## Envelope

`GET /api/auth/me` returns, under `user.profile.filter_memory`:

```json
{
  "matches": {
    "filters": { "v": 1, "savedAt": 1763160000000, "ageGroupId": 3, "competition": "qualifying", "conferenceIds": [1, 7] },
    "panel_open": false,
    "saved_at": 1763160000000
  },
  "table": { "filters": { "v": 1, "savedAt": 1763150000000, "ageGroupId": 3, "leagueId": 1, "divisionId": 1 } }
}
```

| Field | Meaning |
|-------|---------|
| `filters` | The fields below. `null` = cleared on purpose (e.g. a default age group was saved in Profile); forget the local copy if this is newer. |
| `filters.v` | Format version, `1`. Absent = written by web before this spec (see *Legacy*). |
| `filters.savedAt` | Client clock, ms, of the **last write by any client**. Restore rule: the copy with the later `savedAt` wins; a local copy wins ties. |
| `panel_open` | Filter panel open/closed. Used only when this device has no choice of its own yet. |
| `saved_at` | Time of the last write of any kind to this view (filters or panel). Not used to choose filters. |

## Fields

**Absent ≠ `null`.** Absent means *no client has set this* — use your own
default. `null` means *the viewer chose "all"*. Never write a field you do not
have a filter for, and never collapse "never chose" into "chose All".

### `matches`

| Field | Type | `null` / empty means | Web | Android | iOS |
|-------|------|----------------------|:---:|:---:|:---:|
| `ageGroupId` | int \| null | every age group | ✓ | ✓ | ✓ |
| `seasonId` | int | — | ✓ | | ✓ |
| `programLeagueId` | int \| null | every program (Homegrown + Academy) | | ✓ | |
| `competition` | string | — | ✓ | ✓ | |
| `conferenceIds` | int[] | `[]` = every conference | ✓ | ✓ | ✓ |
| `viewTab` | `"all"` \| `"myclub"` | — | ✓ | | |
| `clubId` | int \| null | no club picked | ✓ | | |
| `teamId` | int \| null | no team picked | ✓ | | |

### `table`

| Field | Type | Web | Android | iOS |
|-------|------|:---:|:---:|:---:|
| `ageGroupId` | int | ✓ | | ✓ |
| `seasonId` | int | ✓ | | ✓ |
| `leagueId` | int — top-level division (Homegrown, Academy) | ✓ | | ✓ |
| `divisionId` | int — conference | ✓ | | ✓ |
| `competition` | string | ✓ | | |

### `competition`

One of:

- `"all"` — every competition (the viewer chose All)
- `"qualifying"` — every match type flagged `counts_for_qualification` ("League + Flex")
- `"<matchTypeId>"` — one match type, its id **as a string** (`"1"`), never its name

Ids, not names: names are display text and are renamed; the combined label
("League + Flex") is built from the API and is not a key.

## Rules for every client

1. **Send only your own fields.** The server merges `filters` key by key
   (`set_filter_memory`), so a PUT with `{ ageGroupId, conferenceIds }` leaves
   `seasonId` and `programLeagueId` as another client set them. Do **not** copy
   fields you loaded from `/me` into your PUT: that copy may be stale, and would
   overwrite a newer value set on another device.
2. **Always send `v: 1` and `savedAt`** inside `filters`, plus top-level
   `saved_at` (the endpoint requires it).
3. **Check every id before applying it** against the lists you fetched
   (SB-1112). A stored id is a claim about data that may have moved; one that no
   longer exists falls back to your default, never to an empty screen.
4. **Ignore fields you don't know.** Future fields are added, never renamed; a
   breaking change bumps `v`.
5. **Debounce writes** (~1.5 s) and ignore failures — the device's own copy
   already has the change.
6. **Re-read `/me` when the app returns to the foreground** (mobile), or a
   change made on the laptop is not seen until the next cold start.
7. **Clearing:** `PUT { "filters": null, "saved_at": … }` forgets every field
   for that view, for every client.

## Legacy (web before SB-1716)

Web entries written before this spec have no `v` and use web-only names. After
the server merge they can sit in the same object as v1 fields:

| Legacy web key | v1 field |
|----------------|----------|
| `divisionIds` (matches) | `conferenceIds` |
| `matchTypeId` (matches): id, `"qualifying"` or `null` | `competition`: `"<id>"`, `"qualifying"` or `"all"` |
| `matchType` (table): match-type **name**, `"qualifying"` or `"all"` | `competition` |

Readers use the v1 field when present and may fall back to the legacy key.
Writers write only v1 fields. Shared names (`ageGroupId`, `seasonId`,
`leagueId`, `divisionId`, `viewTab`, `clubId`, `teamId`) already mean the same.

## Server

- `set_filter_memory(user_id, view, patch)`: one `UPDATE`. The view's entry is
  merged with the patch; when the patch's `filters` is an object it is merged
  **into** the stored `filters` object, key by key. `filters: null` replaces it.
- Validation (`backend/filter_memory.py`): ≤16 keys; values are scalars or
  ≤50-item scalar lists; strings ≤64 chars. The backend does not interpret the
  fields.
- Only that viewer's cached profile (`mt:dao:players:profile:<id>`) is cleared.
