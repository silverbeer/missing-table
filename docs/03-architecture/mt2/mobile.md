# MT 2.0 — Mobile Architecture

> **Audience**: Anyone deciding or building MT's iOS/Android apps
> **Prerequisites**: [Current state](current-state.md)
> **Status**: Recommendation (2026-09-28, SB-1141). Nothing here is built yet.

What mobile code exists today, the three ways forward we considered, and which one we
recommend — with the evidence from the repositories that decided it.

---

## Current state

### There are two mobile surfaces, not one

| Surface | Where | Audience | Distribution |
|---------|-------|----------|--------------|
| **Web PWA** | `frontend/` (this repo) | fans, players, parents, admins | missingtable.com, installable to home screen |
| **MT Scorer (Android)** | `silverbeer/missing-table-android` (separate repo) | team managers scoring matches | signed APK, sideloaded from a private R2 bucket |

There is **no iOS code** in either repository, and no Capacitor, Expo or React Native
anywhere.

### Web PWA

- `vite-plugin-pwa` in `injectManifest` mode with a hand-written `frontend/src/sw.js`:
  app-shell precache, read-API caching (`utils/swRoutes.js`), offline fallback, and Web
  Push `push`/`notificationclick` handlers.
- Web Push works on Android Chrome and on iOS Safari as an installed PWA (verified
  2026-05-27 for SB-44). This is the only push channel MT has.
- Install prompts: `useInstallPrompt`, `InstallBanner.vue`. iOS install instructions live
  in [NOTIFICATION_SETUP.md](../../features/NOTIFICATION_SETUP.md).

### MT Scorer — the Android app

| Aspect | Finding |
|--------|---------|
| Language / UI | Kotlin 2.1.21, Jetpack Compose (BOM 2025.06.01), Material 3 |
| SDK / build | minSdk 29, target/compile 36; AGP 8.10.1, Gradle 8.14.2, Kotlin DSL + version catalog; one `:app` module |
| App id | `com.missingtable.scorer`; flavors `local` (`http://10.0.2.2:8000`) and `prod` (`https://api.missingtable.com`) |
| Architecture | Package layers `data/{api,auth,db,sync,repo}`, `domain/`, `ui/`. Hand-rolled DI (`AppContainer` in `MtApp.kt`). **No ViewModels** — screens call the container directly |
| Networking | Retrofit 2.11 + OkHttp 4.12, kotlinx.serialization |
| Storage | DataStore (tokens, session — **unencrypted**); Room `pending_actions` offline queue |
| Offline scoring | `data/sync/SyncEngine.kt`: strict-FIFO queue keyed by `client_event_id`, backoff 2s→60s on 5xx/offline, a 4xx pauses the queue; kicked on connectivity/foreground, WorkManager fallback. Contract: [live-scoring-offline-sync.md](../live-scoring-offline-sync.md) |
| Screens | Login, Matches, Lineup, Live scoring (optimistic UI, read-only mode for fans), Post-match editor, Table, Cups (tournaments), Leaderboard, Profile, force-update |
| Auth | `/api/auth/login` username/password → backend JWTs; `AuthInterceptor` + `TokenAuthenticator` (refresh with rotation, retry once) |
| Push | **None** (no FCM) |
| Tests | 45 JUnit4 unit tests in 8 files (LiveClock, SyncEngine via Robolectric+Room, TokenAuthenticator via MockWebServer, domain logic). No instrumented tests. 3 Maestro flows |
| CI/CD | `android-pr.yml` (build + unit tests), `android-e2e.yml` (weekly Maestro on an API 34 emulator), `android-release.yml` (on `v*` tag: signed `assembleProdRelease` → Maestro smoke → R2 `latest/missingtable.apk`) |
| Store | **Not on Google Play.** No AAB, no fastlane. Force-upgrade via `min_version_code` from `/api/android/apk-url` |
| Size / age | ~5.4K lines main + ~0.8K test across 39 `.kt` files; 50 commits, all 2026-07-19 → 07-26; untouched since |

### Health

The codebase is small, recent and clean (no TODO/FIXME), and its hardest part — the
offline queue — is well tested. Its debt is ordinary for a one-week build:

- no ViewModels, so screen state is not testable apart from the UI;
- tokens stored in plain DataStore rather than Keystore-backed storage;
- no push, which is the capability the engagement strategy depends on;
- dependencies pinned at mid-2025 versions; deprecated `kotlinOptions { jvmTarget }`;
- `docs/RELEASE_SETUP.md` still describes a public r2.dev URL; the bucket is now private.

**Is it worth modernizing?** As a scorer, yes — it works. As *the* MT mobile app, no: it
was built for a different audience (managers, not fans), it has no push, and keeping it
as the Android half of a two-platform strategy means writing iOS a second time in Swift.

---

## Options considered

### Option A — Modernize the Kotlin app, add a native Swift iOS app

| For | Against |
|-----|---------|
| Best native fidelity and performance | **Two native codebases** for one developer, plus the Vue web app — three clients |
| Keeps the existing, tested offline queue | iOS starts from zero in a third language |
| No new JS runtime on device | Every feature ships three times |

### Option B — New shared Expo + React Native + TypeScript app

| For | Against |
|-----|---------|
| One codebase for iOS and Android; EAS builds and signs both in the cloud | New UI stack: web is Vue, so no component reuse with `frontend/` |
| Native push (APNs/FCM) and store distribution for both platforms | Introduces TypeScript to a JS-only frontend team |
| The existing native investment is small (~5.4K LOC, one week) | The offline queue must be re-built and re-proven |
| Kotlin `domain/` logic is pure and tested — its tests become the port spec | Three clients during the transition (Vue, Kotlin, RN) |

Expo SDK 56 (released 2026-05-21) ships React Native 0.85 and React 19.2 with the New
Architecture on by default since SDK 53 ([Expo changelog](https://expo.dev/changelog/sdk-56.md)).

### Option C — Wrap the existing Vue PWA (Capacitor)

This was the plan of record for SB-44 ("PWA Phase 1 → Capacitor Phase 2"), so it gets
a fair hearing.

| For | Against |
|-----|---------|
| Reuses 106 Vue components and the whole PWA — fastest route to both stores | The Vue app has no router (tab state in `App.vue`) and an ~1,100-line auth store; a WebView inherits both |
| One UI codebase across web and mobile | Offline scoring in a WebView needs an IndexedDB queue the web app does not have — the Kotlin app exists precisely because that reliability mattered |
| Web Push work partly reusable | Push still needs native plugins (APNs/FCM), so web push is not reused as-is |
| | Store review of thin web wrappers is a known risk and must be checked against current App Store guidance before committing |

---

## Recommendation

**Option B — Expo + React Native + TypeScript, for one app on both platforms. Keep the
Kotlin scorer in maintenance mode until the Expo app reaches scoring parity, then retire
it.** Keep the Vue web app as the desktop/admin surface and the no-install fan surface.

Why the repository points here rather than confirming the prior assumption blindly:

1. **The sunk cost is small.** The only native code is a week old and 5.4K lines. Option
   A's main advantage — keeping it — is worth little against writing iOS twice.
2. **The audience moved.** MT 2.0 targets fans, players and parents. The Android app
   targets managers. Rebuilding for the new audience is needed under every option.
3. **Push is the product bet**, and native push on both platforms is table stakes for
   Options A and B and extra native work for C.
4. **The hard logic is portable.** `LiveClock`, `MinutesPlayed`, `Positions`,
   `Formations`, `Seasons`, `TournamentStandings` and the `SyncEngine` rules are pure
   functions with tests. Porting them to TypeScript with the same test vectors is
   bounded work.
5. **Option C's saving is smaller than it looks.** The web app's routing and state
   shape would be carried into the WebView, and offline scoring would still have to be
   built.

**Reverse this if**: the first Expo slice (below) shows the offline queue cannot be made
as reliable as `SyncEngine`, or a TypeScript/React toolchain proves to be a larger tax
than expected. Option C remains the fallback for a fast store presence.

---

## Migration implications

- **New repository** (`missing-table-mobile`), following the Android precedent of
  one repo per client. Monorepo is not justified: no code is shared with `frontend/`.
- **API contract.** The backend declares no `response_model` on any route in `app.py`, so
  `openapi.json` describes inputs but not responses. Generated TypeScript types will be
  weak until response models exist for the endpoints the app uses. Adding them is a
  backend task that also benefits MT AI tools.
- **Auth.** Reuse `/api/auth/login` + `/api/auth/refresh`; store tokens in
  `expo-secure-store` (fixes the Android plaintext-token debt rather than porting it).
- **Push.** Needs a native push path in the backend (`api/push.py` is Web Push/VAPID
  only today): device-token registration plus an APNs/FCM sender alongside `pywebpush`.
- **Distribution.** Apple Developer Program and a Play Console account; move Android from
  sideloaded APK to Play (internal testing track first). The invite-only posture carries
  over: TestFlight and Play internal testing are both invitation-based.
- **Retirement of MT Scorer.** Freeze features now; security/bug fixes only. Retire once
  the Expo app passes the same Maestro flows plus the offline scoring scenarios.

## Testing implications

- Unit: Jest for ported domain logic, reusing the Kotlin test vectors verbatim.
- Component: React Native Testing Library.
- E2E: **Maestro** — already in use for the Android app, supports both platforms, so the
  existing flows are the starting suite.
- Contract: the backend's contract tests already pin the API; add the mobile-used
  endpoints to them rather than mocking the API in the app.

## CI/CD implications

- PR: typecheck (`tsc --noEmit`), lint, Jest — GitHub Actions, no device.
- Build/sign: EAS Build for iOS and Android (no local Xcode dependency for CI).
- Release: EAS Submit to TestFlight / Play internal track; EAS Update for JS-only fixes,
  with the backend's `min_version_code` force-upgrade pattern kept for native changes.
- Weekly Maestro run carries over from `android-e2e.yml`.

---

## 📖 Related Documentation

- **[Current state](current-state.md)** — the whole system as it is today
- **[Live scoring offline sync](../live-scoring-offline-sync.md)** — the contract the Android queue implements
- **[Notification setup](../../features/NOTIFICATION_SETUP.md)** — Web Push and PWA install
- **[MT 2.0 overview](README.md)**
