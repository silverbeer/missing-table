# Notification Setup Guide

**Status:** Shipped (SB-810, SB-813) | **Entry points:** install banner, Follow button, Profile → Notifications, first login

Guides a user — especially on iPhone — from "logged in" to "a push actually arrives on my phone".

## Why this exists

A real user tapped the blue "Install Missing Table" banner on their iPhone and nothing happened. Investigating that surfaced a bigger problem: getting a match notification onto an iPhone took **three prerequisites**, each living in a different part of the app, with nothing connecting them and nothing telling the user they existed.

| Wall | What the user did | What the app did |
|------|-------------------|------------------|
| 1 | Tapped **Follow** on a team | Saved a follow record, turned green. No push code runs here at all. |
| 2 | Waited for alerts | Nothing. Push opt-in lives in Profile → Notifications and nothing pointed there. |
| 3 | Found Profile → Notifications | "Install to your home screen first" — pointing back at the banner from Wall 0. |

The banner at the centre of it (`IosInstallTooltip.vue`) had **no click handler**: a filled blue card with `role="dialog"` whose only interactive element was the `×`.

## The constraint that shapes everything

**iOS has no programmatic install API.** `beforeinstallprompt` is Chromium-only; Apple never shipped it. No web page on iOS — in any browser — can open Add to Home Screen. And since iOS 16.4, Web Push works *only* from a home-screen-installed app; a browser tab cannot subscribe.

So on iPhone the app cannot install itself and cannot ask for notifications until the user has installed it by hand. All it can do is **teach the manual steps accurately**. That is what this feature is.

Two consequences worth knowing:

- **Every iOS browser is WebKit**, so Safari, Chrome, Firefox and Edge on iPhone all have the identical install requirement. Only the *location of the Share control* differs. Detection must therefore be `isIos()`, not `isIosSafari()` — the old Safari-only check meant iPhone users on Chrome saw no banner at all.
- **iOS hides `PushManager` outside standalone mode.** A naive support check therefore reports "your browser doesn't support notifications" to an iPhone user who is two taps from working push. The honest answer is "install it first", and the code special-cases this.

## The state machine

`frontend/src/composables/useNotificationSetup.js` is the single answer to "what does this user still have to do".

| Step | Condition | Applies to |
|------|-----------|-----------|
| `install` | `isIosNonStandalone()` | iOS only |
| `blocked` | permission denied | all |
| `enable` | no browser permission / no backend subscription | all |
| `follow` | zero followed teams | all |
| `done` | none of the above | all |
| `unsupported` | no Web Push, and **not** an iOS tab | desktop / old browsers |

State is **derived live on every read, never from a stored "onboarding complete" flag**. A user who revokes permission, deletes the home-screen icon, or signs in on a second device genuinely *is* back at an earlier step, and the guide has to say so.

Two details that are easy to get wrong:

- Follow-count comes from `followedTeamIds` (updated optimistically), not `follows` (waits for the background refetch). Using the slower one makes the guide tell someone to "follow a team" one tick after they did.
- `enable` is considered done only when the **backend** confirms a subscription, not when `Notification.permission` flips to granted. Trusting permission alone caused SB-52 — an "enabled" pill over a backend with no subscription.

## Surfaces

| Component | Role |
|-----------|------|
| `InstallBanner.vue` | Bottom banner on iOS-not-installed. Explicit **"Show me how"** button — replaces the unclickable `IosInstallTooltip`. |
| `NotificationSetupGuide.vue` | The teaching surface. Bottom sheet on mobile, modal on desktop. Shows the whole three-step checklist plus detail for the current step. Mounted globally in `App.vue`. |
| `FollowButton.vue` | Shows an "Alerts aren't on yet — set up" chip while following without live push. Opens the guide on the user's **first ever** follow. |
| `NotificationsCard.vue` | The iOS gate now carries a "Show me how" button instead of dead-ending. |
| `App.vue` | On first authenticated visit on a touch device, offers the guide once. |

## Install instructions

`getInstallSteps()` in `frontend/src/utils/pwa.js` returns per-browser steps. The middle step is flagged `emphasis: true` and rendered with an amber rail, because it is where users give up:

> **"Add to Home Screen" is below the fold.** In Safari's share sheet you must scroll past the row of apps and past Copy and Add Bookmark. It looks like the option doesn't exist.

Safari points at the **bottom toolbar** (with a note to tap the bottom edge if it's hidden after scrolling); Chrome/Edge/Firefox point at their own `⋯` menu.

## Anti-nag rules

Being wrong here means pestering someone on every visit, which is worse than them never finding the guide.

- The banner and the guide **share one dismissal record** (`mt.notificationSetup.promptDismissedAt`, 30 days). One "not now" silences both.
- The unprompted first-login offer waits for the follows list to load — an unloaded list looks identical to an empty one, and would prompt a user who is already set up.
- The follow-triggered modal fires only on the **first ever** follow. Later follows get the persistent chip instead.
- Closing the guide *after* completing setup records no dismissal — there is no future nag to mute.
- The legacy `mt.iosInstallTooltip.dismissedAt` key is deliberately ignored: dismissing a dead-end banner says nothing about whether a working one is wanted.

## Testing

| File | Covers |
|------|--------|
| `__tests__/utils/pwa.spec.js` | iOS detection across browsers, per-browser install steps, the emphasised step |
| `__tests__/composables/useNotificationSetup.spec.js` | every state, the iOS-tab-is-not-unsupported regression, permission revoke, anti-nag gating |
| `__tests__/components/InstallBanner.spec.js` | shows on all iOS browsers, real action button, shared dismissal |
| `__tests__/components/NotificationSetupGuide.spec.js` | correct step detail, per-browser copy, backend re-read after enable |
| `__tests__/components/FollowButton.alerts.spec.js` | the honesty chip, first-follow-only prompt, no prompt on unfollow or failure |
| `__tests__/composables/useInstallPrompt.spec.js` | event capture, infobar suppression, single-use enforcement, `appinstalled` |
| `__tests__/components/InstallBanner.android.spec.js` | native vs instructional mode, no false "install required" claim, desktop exclusion |

## Android and desktop (SB-813)

The mirror image of the iOS problem. There, no install API exists and we hand-write instructions. Here, Chromium fires `beforeinstallprompt` and hands us a working one — MT just never used it, so Android users got no install offer at all.

`frontend/src/composables/useInstallPrompt.js` captures the event, suppresses Chrome's own mini-infobar, and stashes it for replay on a user gesture. Two constraints from the API shape the code:

- **`prompt()` requires a user gesture**, so the event is stored rather than fired on arrival.
- **Each event is single-use.** It's discarded *before* awaiting `userChoice`, so a double-tap can't replay a spent event.

Listeners attach at module load and `main.js` imports the module directly, because the event fires early in page life and is offered once — a listener registered after mount can miss it.

### Install is optional here, and the UI has to say so

Push works in a normal Chrome tab on Android. Presenting install as a prerequisite would invent a barrier Google doesn't impose and make setup look longer than it is.

So outside iOS the install step is marked `required: false`, labelled "(optional)", and **never folded into `currentStep` or `isComplete`** — a user with notifications on and a team followed is "all set" whether or not they installed. The guide's install offer says outright that notifications work either way.

The pitch differs accordingly:

| | iPhone | Android |
|---|---|---|
| Banner headline | "Want live match alerts?" | "Add Missing Table to your phone" |
| Why install | It's the only way to get notifications | The home-screen icon itself |
| Button | "Show me how" → instructions | "Install" → native prompt |
| Checklist | 3 steps, install required | 2 steps + optional install |

The banner's native path is gated to touch devices. Chromium offers the event on desktop too, but a fixed bottom banner on a laptop is noise — the guide still carries the offer there.

### Push payloads are identical

`backend/notifications/web_push_sender.py` has no platform branching. Same VAPID Web Push, same payload, every device. Only the *setup instructions* differ.
