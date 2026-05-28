/**
 * NotificationsCard.vue — focused tests for the SB-57 preferences section.
 *
 * The rest of the card (enable/disable, devices, follows) is exercised
 * via manual + smoke tests; here we only validate the new "What to notify
 * me about" toggles wire through to useNotificationPreferences correctly.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { ref, computed } from 'vue';

// Stub usePushNotifications so the component can mount without browser APIs.
vi.mock('@/composables/usePushNotifications', () => ({
  usePushNotifications: () => ({
    isSupported: ref(true),
    isEnabled: ref(true),
    isBlocked: ref(false),
    isIosBlocked: ref(false),
    loading: ref(false),
    lastError: ref(null),
    enable: vi.fn(),
    disable: vi.fn(),
    listSubscriptions: vi.fn().mockResolvedValue([]),
    sendTest: vi.fn(),
  }),
}));

// Stub useTeamFollows — not under test here.
vi.mock('@/composables/useTeamFollows', () => ({
  useTeamFollows: () => ({
    follows: computed(() => []),
    refresh: vi.fn().mockResolvedValue(),
  }),
}));

// Stub useNotificationPreferences with a controllable mock.
let mockPrefs;
let setPreferenceMock;
let setCardsMock;
let ensureLoadedMock;

vi.mock('@/composables/useNotificationPreferences', () => ({
  useNotificationPreferences: () => ({
    preferences: computed(() => mockPrefs.value),
    cardsEnabled: computed(
      () => mockPrefs.value.yellow_card || mockPrefs.value.red_card
    ),
    loaded: ref(true),
    loading: ref(false),
    error: ref(null),
    ensureLoaded: ensureLoadedMock,
    setPreference: setPreferenceMock,
    setCards: setCardsMock,
  }),
}));

import NotificationsCard from '@/components/notifications/NotificationsCard.vue';

beforeEach(() => {
  mockPrefs = ref({
    kickoff: true,
    goal: true,
    halftime: true,
    fulltime: true,
    yellow_card: false,
    red_card: false,
  });
  setPreferenceMock = vi.fn().mockResolvedValue({ success: true });
  setCardsMock = vi.fn().mockResolvedValue({ success: true });
  ensureLoadedMock = vi.fn().mockResolvedValue();
});

describe('NotificationsCard preferences section (SB-57)', () => {
  it('renders all five toggles when push is supported', async () => {
    const wrapper = mount(NotificationsCard);
    await flushPromises();

    expect(wrapper.find('[data-testid="pref-toggle-kickoff"]').exists()).toBe(
      true
    );
    expect(wrapper.find('[data-testid="pref-toggle-goal"]').exists()).toBe(
      true
    );
    expect(wrapper.find('[data-testid="pref-toggle-halftime"]').exists()).toBe(
      true
    );
    expect(wrapper.find('[data-testid="pref-toggle-fulltime"]').exists()).toBe(
      true
    );
    expect(wrapper.find('[data-testid="pref-toggle-cards"]').exists()).toBe(
      true
    );
  });

  it('reflects current preferences as checkbox state', async () => {
    mockPrefs.value = {
      kickoff: true,
      goal: false,
      halftime: true,
      fulltime: true,
      yellow_card: true,
      red_card: false,
    };
    const wrapper = mount(NotificationsCard);
    await flushPromises();

    expect(
      wrapper.find('[data-testid="pref-toggle-goal"]').element.checked
    ).toBe(false);
    expect(
      wrapper.find('[data-testid="pref-toggle-kickoff"]').element.checked
    ).toBe(true);
    // Cards toggle is true because yellow_card is true.
    expect(
      wrapper.find('[data-testid="pref-toggle-cards"]').element.checked
    ).toBe(true);
  });

  it('toggling an individual event calls setPreference', async () => {
    const wrapper = mount(NotificationsCard);
    await flushPromises();

    const goalToggle = wrapper.find('[data-testid="pref-toggle-goal"]');
    await goalToggle.setValue(false);
    await flushPromises();

    expect(setPreferenceMock).toHaveBeenCalledWith('goal', false);
  });

  it('toggling cards calls setCards once for both event types', async () => {
    const wrapper = mount(NotificationsCard);
    await flushPromises();

    const cardsToggle = wrapper.find('[data-testid="pref-toggle-cards"]');
    await cardsToggle.setValue(true);
    await flushPromises();

    expect(setCardsMock).toHaveBeenCalledWith(true);
    // Each event isn't separately toggled — that's the whole point of the
    // combined UI control.
    expect(setPreferenceMock).not.toHaveBeenCalled();
  });

  it('calls ensureLoaded on mount so the section hydrates', async () => {
    mount(NotificationsCard);
    await flushPromises();

    expect(ensureLoadedMock).toHaveBeenCalled();
  });
});
