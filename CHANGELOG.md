# Changelog

All notable user-facing changes. Versions are `MAJOR.MINOR.PATCH` (the `.BUILD`
suffix in the footer is the CI run number). Bumps are driven by the PR label
gate — see [CLAUDE.md → Version Management](CLAUDE.md#version-management).

## [1.4.0] — Follow tournament brackets + score-first notifications

### Added
- **Follow a tournament bracket** — follow a `(tournament, bracket, age group)`
  and get a Web Push at full time for every match in it. Toggle on the
  tournament Bracket and Standings views; manage/unfollow from the profile
  ("Brackets you follow"). Respects existing per-event notification
  preferences. (SB-84)
- **`mt tournament` CLI** — `create` / `list` / `show` / `add-match` /
  `remove-match` / `score` for seeding and scoring tournament brackets.

### Changed
- **Score-first push notifications** — the score is now the notification
  headline (e.g. `🏁 FT · IFA 2-1 NEFC`, `⚽ IFA 2-1 NEFC (34')`), so it's
  visible at a glance and on the lock screen. (SB-86)
- **Tapping a match notification opens that match** (match detail overlay),
  instead of landing on the standings tab. (SB-86)

### Infrastructure
- **Prod test partition** (`is_test`) — the TSC test world (league, clubs,
  teams, tournaments, users) is hidden from real users while visible to test
  users and admins. (SB-85)
- **PR-label version gate** — merging a PR bumps `MAJOR.MINOR.PATCH` from its
  `version:*` label.

## [1.3.1]

- Baseline prior to the changelog. See git history for earlier changes.
