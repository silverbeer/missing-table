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

// Stub useTeamFollows. SB-65 tests below populate `mockFollows` to verify
// the new label rendering.
let mockFollows;
vi.mock('@/composables/useTeamFollows', () => ({
  useTeamFollows: () => ({
    follows: computed(() => mockFollows.value),
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
  mockFollows = ref([]);
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

describe('NotificationsCard "Teams you follow" labels (SB-65)', () => {
  it('renders "team · league · division" when all fields are present', async () => {
    mockFollows.value = [
      {
        team_id: 19,
        team: {
          id: 19,
          name: 'IFA',
          club: { id: 1, name: 'IFA' },
          division: {
            id: 1,
            name: 'Northeast',
            leagues: { id: 1, name: 'Homegrown' },
          },
        },
      },
    ];

    const wrapper = mount(NotificationsCard);
    await flushPromises();

    const primary = wrapper.find('[data-testid="follow-label-primary"]');
    expect(primary.text()).toBe('IFA · Homegrown · Northeast');
  });

  it('shows the "Showing all age groups" subtitle on every follow row', async () => {
    mockFollows.value = [
      {
        team_id: 19,
        team: {
          id: 19,
          name: 'IFA',
          club: { id: 1, name: 'IFA' },
          division: {
            id: 1,
            name: 'Northeast',
            leagues: { id: 1, name: 'Homegrown' },
          },
        },
      },
    ];

    const wrapper = mount(NotificationsCard);
    await flushPromises();

    expect(wrapper.find('[data-testid="follow-label-sub"]').text()).toBe(
      'Showing all age groups'
    );
  });

  it('falls back gracefully when league + division join data is missing', async () => {
    mockFollows.value = [
      {
        team_id: 99,
        team: {
          id: 99,
          name: 'Mystery Team',
          club: { id: 99, name: 'Mystery Team' },
          // No division field — backend was unable to join it.
        },
      },
    ];

    const wrapper = mount(NotificationsCard);
    await flushPromises();

    const primary = wrapper.find('[data-testid="follow-label-primary"]');
    expect(primary.text()).toBe('Mystery Team');
    // No "undefined" leaks.
    expect(primary.text()).not.toMatch(/undefined/);
  });

  it('suppresses the redundant club name on the right when it duplicates the team name', async () => {
    mockFollows.value = [
      {
        team_id: 19,
        team: {
          id: 19,
          name: 'IFA',
          club: { id: 1, name: 'IFA' },
          division: {
            id: 1,
            name: 'Northeast',
            leagues: { id: 1, name: 'Homegrown' },
          },
        },
      },
    ];

    const wrapper = mount(NotificationsCard);
    await flushPromises();

    // IFA / IFA looked duplicative before SB-65. Now the club tag is hidden
    // when it would be redundant.
    const item = wrapper.find('[data-testid="follow-item-19"]');
    expect(item.findAll('.follow-club').length).toBe(0);
  });

  it('keeps the club name on the right when it differs from the team name', async () => {
    mockFollows.value = [
      {
        team_id: 7,
        team: {
          id: 7,
          name: 'Bayside U14',
          club: { id: 5, name: 'Bayside FC' },
          division: {
            id: 1,
            name: 'Northeast',
            leagues: { id: 1, name: 'Homegrown' },
          },
        },
      },
    ];

    const wrapper = mount(NotificationsCard);
    await flushPromises();

    const item = wrapper.find('[data-testid="follow-item-7"]');
    expect(item.find('.follow-club').text()).toBe('Bayside FC');
  });
});
