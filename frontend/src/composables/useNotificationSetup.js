/**
 * Notification setup state machine (SB-810).
 *
 * Getting a live match notification on a phone takes three things, and before
 * this composable existed each lived in a different place with nothing linking
 * them — so a user could tap Follow, see it go green, and never learn that two
 * more steps stood between them and an alert:
 *
 *   1. install  — iOS only: Web Push requires a home-screen app (iOS 16.4+)
 *   2. enable   — browser permission + a registered push subscription
 *   3. follow   — you only get alerts for teams you follow
 *
 * State is derived from live sources every time, never from a stored
 * "onboarding complete" flag. A user who revokes permission, deletes the
 * home-screen icon, or signs in on a second device is genuinely back at an
 * earlier step, and the guide has to say so.
 *
 * Singleton, mirroring useAuthStore / useTeamFollows: module-level reactive
 * state so the banner, the Follow button, the profile card and the modal are
 * all looking at the same thing.
 */

import { ref, computed } from 'vue';
import { usePushNotifications } from './usePushNotifications';
import { useTeamFollows } from './useTeamFollows';
import { isIosNonStandalone, isIos, isStandalone } from '../utils/pwa';

// Bumped whenever the guide's content changes enough that a previously
// dismissed user deserves to see it again.
const PROMPT_KEY = 'mt.notificationSetup.promptDismissedAt';
const RESHOW_DAYS = 30;

const guideOpen = ref(false);
// Why the guide was opened — lets the modal lead with the right sentence
// ("You're following X" vs "Get match alerts").
const guideReason = ref('manual');

// Mirrors the localStorage value as reactive state so a dismissal in one
// surface immediately retires the other. Without this, dismissing the guide
// leaves the install banner sitting there underneath it — still nagging about
// a thing the user just said no to.
const dismissedAt = ref(null);

function readStoredDismissedAt() {
  try {
    const raw = localStorage.getItem(PROMPT_KEY);
    if (!raw) return null;
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
  } catch {
    return null;
  }
}

/**
 * Has the user waved the setup prompt away recently?
 *
 * Shared by the guide and the install banner deliberately: they are two faces
 * of the same nag, and one "not now" should silence both. (The legacy
 * `mt.iosInstallTooltip.dismissedAt` key is intentionally ignored — that
 * banner was a dead end, so a dismissal of it says nothing about whether this
 * one is wanted.)
 */
export function wasPromptDismissed() {
  // The ref wins once something has been dismissed in this session (it's what
  // makes the banner retire the moment the guide is dismissed). Until then,
  // fall through to storage — the value can predate this module's load, or
  // have been written by another tab.
  const at = dismissedAt.value ?? readStoredDismissedAt();
  if (at === null) return false;
  const ageDays = (Date.now() - at) / (1000 * 60 * 60 * 24);
  return ageDays < RESHOW_DAYS;
}

export function openSetupGuide(reason = 'manual') {
  guideReason.value = reason;
  guideOpen.value = true;
}

export function closeSetupGuide() {
  guideOpen.value = false;
}

export function useNotificationSetup() {
  const { isEnabled, isBlocked, isSupported } = usePushNotifications();
  // followedTeamIds rather than follows: it updates optimistically on follow,
  // while `follows` waits for the background refetch. Using the slower one
  // makes the guide claim "follow a team" to someone who just did.
  const {
    followedTeamIds,
    loaded: followsLoaded,
    ensureLoaded,
  } = useTeamFollows();

  const followCount = computed(() => followedTeamIds.value.size);

  // iOS is the only platform where install is a hard prerequisite. Elsewhere
  // push works fine in a normal tab, so we never make install a blocker.
  const needsInstall = computed(() => isIosNonStandalone());

  const needsEnable = computed(() => !needsInstall.value && !isEnabled.value);

  const needsFollow = computed(
    () => followsLoaded.value && followCount.value === 0
  );

  /**
   * Push is genuinely impossible here — an old browser, or a desktop that
   * doesn't do Web Push. Note this deliberately does NOT fire for an iOS tab:
   * iOS hides PushManager outside standalone mode, which looks like
   * "unsupported" but really means "install it first".
   */
  const isUnsupported = computed(
    () => !needsInstall.value && !isSupported.value
  );

  const currentStep = computed(() => {
    if (isUnsupported.value) return 'unsupported';
    if (needsInstall.value) return 'install';
    if (isBlocked.value) return 'blocked';
    if (needsEnable.value) return 'enable';
    if (needsFollow.value) return 'follow';
    return 'done';
  });

  const isComplete = computed(() => currentStep.value === 'done');

  /** Ordered checklist the modal renders. */
  const steps = computed(() => {
    const list = [];
    if (isIos()) {
      list.push({
        key: 'install',
        label: 'Add Missing Table to your home screen',
        done: isStandalone(),
        // Only iOS forces this, and only because Apple gives web pages no
        // install API — so the guide has to teach it by hand.
        required: true,
      });
    }
    list.push({
      key: 'enable',
      label: 'Turn on notifications',
      done: isEnabled.value,
      blocked: isBlocked.value,
      required: true,
    });
    list.push({
      key: 'follow',
      label: 'Follow a team',
      done: followsLoaded.value && followCount.value > 0,
      required: true,
    });
    return list;
  });

  /**
   * Should we volunteer the guide unprompted (first login on a phone)?
   *
   * Only when there is something real to fix, and not if the user already
   * waved it away recently. Being wrong here means nagging someone on every
   * visit, which is worse than them never finding the guide.
   */
  const shouldPromptUnprompted = computed(() => {
    if (isComplete.value) return false;
    if (isUnsupported.value) return false;
    // Wait for the follows fetch before judging — an unloaded list looks
    // identical to an empty one and would prompt someone already set up.
    if (!followsLoaded.value) return false;
    return !wasPromptDismissed();
  });

  function dismissPrompt() {
    const now = Date.now();
    // Reactive first so the banner retires even if persistence fails.
    dismissedAt.value = now;
    try {
      localStorage.setItem(PROMPT_KEY, String(now));
    } catch {
      // localStorage unavailable (private mode) — fine, just don't persist.
    }
    closeSetupGuide();
  }

  return {
    // modal plumbing
    guideOpen: computed(() => guideOpen.value),
    guideReason: computed(() => guideReason.value),
    open: openSetupGuide,
    close: closeSetupGuide,
    dismissPrompt,
    // state machine
    currentStep,
    steps,
    isComplete,
    needsInstall,
    needsEnable,
    needsFollow,
    isUnsupported,
    shouldPromptUnprompted,
    promptDismissed: computed(() => wasPromptDismissed()),
    ensureFollowsLoaded: ensureLoaded,
  };
}

// Test-only: reset module-level singleton between tests.
export function _resetNotificationSetupForTest() {
  guideOpen.value = false;
  guideReason.value = 'manual';
  dismissedAt.value = null;
}
