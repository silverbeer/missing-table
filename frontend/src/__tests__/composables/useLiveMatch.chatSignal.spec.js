/**
 * useLiveMatch — chat arrives through the live_chat_signals doorbell
 * (SB-1329), not raw match_events rows, which clients can no longer read.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { flushPromises } from '@vue/test-utils';

// channel name → { table: handler }
const channels = {};

vi.mock('@/config/supabase', () => ({
  supabase: {
    channel: vi.fn(name => {
      const handlers = {};
      channels[name] = handlers;
      const ch = {
        on: vi.fn((_type, opts, handler) => {
          handlers[`${opts.table}:${opts.event}`] = handler;
          return ch;
        }),
        subscribe: vi.fn(() => ch),
      };
      return ch;
    }),
    removeChannel: vi.fn(),
  },
}));

const apiRequest = vi.fn();
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAuthenticated: { value: true },
    isAdmin: { value: false },
    isClubManager: { value: false },
    isTeamManager: { value: false },
    userTeamId: { value: null },
    apiRequest,
  }),
}));

vi.mock('@/config/api', () => ({ getApiBaseUrl: () => 'http://api' }));

vi.mock('@/composables/useMatchLineup', () => ({
  useMatchLineup: () => ({
    homeLineup: { value: null },
    awayLineup: { value: null },
    lineupLoading: { value: false },
    fetchLineup: vi.fn(),
    fetchLineups: vi.fn(),
    saveLineup: vi.fn(),
    fetchTeamRosters: vi.fn(),
  }),
}));

import { useLiveMatch } from '@/composables/useLiveMatch';

const goal = { id: 1, event_type: 'goal' };
const chat = { id: 2, event_type: 'message', message: 'hi' };

beforeEach(() => {
  apiRequest.mockReset();
  for (const k of Object.keys(channels)) delete channels[k];
});

async function startLive() {
  apiRequest.mockResolvedValueOnce({ id: 9, recent_events: [goal] });
  const live = useLiveMatch(9);
  await flushPromises();
  return live;
}

const ring = () => channels['live_chat_signals:9']['live_chat_signals:*']();
const eventsCalls = () =>
  apiRequest.mock.calls.filter(([url]) => url.includes('/live/events'));

describe('useLiveMatch chat doorbell', () => {
  it('subscribes to the match’s chat signal', async () => {
    await startLive();
    expect(channels['live_chat_signals:9']).toBeDefined();
  });

  it('re-reads chat through the API when it rings', async () => {
    const live = await startLive();
    apiRequest.mockResolvedValueOnce([chat, goal]);

    ring();
    await flushPromises();

    expect(eventsCalls()[0][0]).toBe(
      'http://api/api/matches/9/live/events?limit=50'
    );
    expect(live.events.value.map(e => e.id)).toEqual([2, 1]);
  });

  it('coalesces rings that arrive during a fetch into one more read', async () => {
    await startLive();
    let release;
    apiRequest.mockImplementationOnce(
      () => new Promise(resolve => (release = () => resolve([goal])))
    );
    apiRequest.mockResolvedValue([chat, goal]);

    ring();
    ring();
    ring();
    release();
    await flushPromises();

    expect(eventsCalls()).toHaveLength(2);
  });

  it('a failed re-read leaves the stream as it was', async () => {
    const live = await startLive();
    apiRequest.mockRejectedValueOnce(new Error('down'));
    ring();
    await flushPromises();
    expect(live.events.value).toEqual([goal]);
  });
});

describe('useLiveMatch club rooms (SB-1330)', () => {
  it('reads and posts without a room for a member', async () => {
    const live = await startLive();
    apiRequest.mockResolvedValueOnce({ id: 5 });
    await live.postMessage('hi');
    const [url, opts] = apiRequest.mock.calls.at(-1);
    expect(url).toBe('http://api/api/matches/9/live/message');
    expect(JSON.parse(opts.body)).toEqual({ message: 'hi' });
  });

  it('an admin’s chosen room is read, re-read and posted to', async () => {
    const live = await startLive();
    apiRequest.mockResolvedValueOnce({
      id: 9,
      chat: { available: true, club_id: 20, rooms: [], closed: false },
      recent_events: [chat],
    });
    await live.setChatRoom(20);
    expect(apiRequest.mock.calls.at(-1)[0]).toBe(
      'http://api/api/matches/9/live?chat_club_id=20'
    );
    expect(live.events.value).toEqual([chat]);
    expect(live.chat.value.club_id).toBe(20);

    apiRequest.mockResolvedValueOnce([chat]);
    ring();
    await flushPromises();
    expect(eventsCalls().at(-1)[0]).toBe(
      'http://api/api/matches/9/live/events?limit=50&chat_club_id=20'
    );

    apiRequest.mockResolvedValueOnce({ id: 6 });
    await live.postMessage('be nice');
    expect(JSON.parse(apiRequest.mock.calls.at(-1)[1].body)).toEqual({
      message: 'be nice',
      club_id: 20,
    });
  });

  it('chat defaults to unavailable until the API says otherwise', async () => {
    const live = await startLive();
    expect(live.chat.value.available).toBe(false);
  });
});
