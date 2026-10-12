/**
 * LiveMatchView — chat safety wiring (SB-1324): reporting hides the author's
 * chat at once (their goal stays), the chat rules prompt comes before the
 * first post, and refused posts say why.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref, computed } from 'vue';
import { mount, flushPromises } from '@vue/test-utils';

const ME = 'me-id';
const AUTHOR = 'author-id';

const events = ref([]);
const postMessage = vi.fn();
const apiRequest = vi.fn();

vi.mock('@/composables/useLiveMatch', () => ({
  useLiveMatch: () => ({
    matchState: ref({ home_team_id: 1, away_team_id: 2 }),
    events,
    isLoading: ref(false),
    error: ref(null),
    isConnected: ref(true),
    clockDisplayFormatted: computed(() => '10:00'),
    isInStoppage: computed(() => false),
    matchPeriod: computed(() => '1st Half'),
    canManage: computed(() => false),
    postMessage,
    deleteEvent: vi.fn(),
    loadMoreEvents: vi.fn(),
    fetchMatchState: vi.fn(),
    fetchTeamRosters: vi.fn(),
    homeLineup: ref(null),
    awayLineup: ref(null),
    fetchLineups: vi.fn(),
    saveLineup: vi.fn(),
  }),
}));

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ state: { user: { id: ME } }, apiRequest }),
}));
vi.mock('@/config/api', () => ({ getApiBaseUrl: () => 'http://api' }));

import LiveMatchView from '@/components/live/LiveMatchView.vue';
import { useBlockedUsers } from '@/composables/useBlockedUsers';
import { chatRulesKey } from '@/utils/chatSafety';

const mountView = () =>
  mount(LiveMatchView, {
    props: { matchId: 5 },
    global: {
      stubs: { LiveScoreboard: true, LiveAdminControls: true },
    },
  });

beforeEach(() => {
  useBlockedUsers().clear();
  localStorage.clear();
  apiRequest.mockReset();
  postMessage.mockReset();
  events.value = [
    {
      id: 11,
      event_type: 'message',
      created_by: AUTHOR,
      created_by_username: 'rude',
      message: 'nasty words',
    },
    {
      id: 12,
      event_type: 'goal',
      created_by: AUTHOR,
      team_id: 1,
      player_name: 'Scorer Sam',
    },
  ];
});

describe('reporting', () => {
  it("hides the author's chat at once and keeps their goal", async () => {
    apiRequest.mockResolvedValueOnce({
      reported: true,
      blocked_user_id: AUTHOR,
    });
    const wrapper = mountView();

    await wrapper.find('[data-testid="report-message"]').trigger('click');
    await wrapper.find('[data-testid="report-reason-spam"]').trigger('click');
    await flushPromises();

    expect(wrapper.text()).not.toContain('nasty words');
    expect(wrapper.text()).toContain('Scorer Sam');
    expect(wrapper.text()).toContain('Report Sent');
    // The report blocked the author server-side: no separate block call.
    expect(apiRequest).toHaveBeenCalledTimes(1);
  });

  it('hides chat from a blocked author that arrives later (realtime)', async () => {
    useBlockedUsers().noteBlocked(AUTHOR);
    const wrapper = mountView();
    events.value = [
      { id: 13, event_type: 'message', created_by: AUTHOR, message: 'again' },
      ...events.value,
    ];
    await flushPromises();
    expect(wrapper.text()).not.toContain('again');
    expect(wrapper.text()).toContain('Scorer Sam');
  });
});

describe('posting', () => {
  async function send(wrapper, text = 'hello') {
    await wrapper.find('.message-input').setValue(text);
    await wrapper.find('.send-button').trigger('click');
    await flushPromises();
  }

  it('asks for the chat rules before the first post, then sends', async () => {
    postMessage.mockResolvedValue({ success: true });
    const wrapper = mountView();

    await send(wrapper);
    expect(postMessage).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain('Chat Rules');

    await wrapper.find('[data-testid="agree-chat-rules"]').trigger('click');
    await flushPromises();
    expect(postMessage).toHaveBeenCalledWith('hello');
    expect(localStorage.getItem(chatRulesKey(ME))).toBe('1');
  });

  it('does not ask again once agreed', async () => {
    localStorage.setItem(chatRulesKey(ME), '1');
    postMessage.mockResolvedValue({ success: true });
    const wrapper = mountView();
    await send(wrapper);
    expect(postMessage).toHaveBeenCalledWith('hello');
    expect(wrapper.find('.message-input').element.value).toBe('');
  });

  it.each([
    [422, "That message contains language that isn't allowed."],
    [403, 'You can no longer post in chat.'],
    [429, "You're sending messages too fast."],
  ])('a %i keeps the draft and says why', async (status, copy) => {
    localStorage.setItem(chatRulesKey(ME), '1');
    postMessage.mockResolvedValue({ success: false, status, error: 'raw' });
    const wrapper = mountView();
    await send(wrapper);
    expect(wrapper.find('[data-testid="chat-send-error"]').text()).toBe(copy);
    expect(wrapper.find('.message-input').element.value).toBe('hello');
  });
});
