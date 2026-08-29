/**
 * TournamentMatchCenter — staying current (SB-909).
 *
 * The tab loads its matches once. On 2026-08-29 a U15 match ended, the API
 * returned the final score immediately, and the open tournament page kept
 * showing the pre-match state until a full reload.
 *
 * Two mechanisms now cover that: a realtime subscription per live row, and a
 * refetch when the tab comes back into view.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { ref } from 'vue';

const { subscribeToMatch, handles } = vi.hoisted(() => {
  const made = [];
  return {
    handles: made,
    subscribeToMatch: vi.fn((id, onUpdate) => {
      const handle = { id, onUpdate, unsubscribe: vi.fn() };
      made.push(handle);
      return handle;
    }),
  };
});

vi.mock('@/composables/useMatchRealtime', () => ({ subscribeToMatch }));

const apiRequest = vi.fn();
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    apiRequest,
    isAuthenticated: ref(true),
    isAdmin: ref(false),
    isClubManager: ref(false),
    isTeamManager: ref(false),
    userClubId: ref(null),
    userTeamId: ref(null),
  }),
}));

import TournamentMatchCenter from '@/components/TournamentMatchCenter.vue';

const SEASONS = [
  {
    id: 4,
    name: '2026-2027',
    start_date: '2026-09-01',
    end_date: '2027-06-30',
  },
];

const mkMatch = (over = {}) => ({
  id: 3853,
  match_date: '2026-08-29',
  scheduled_kickoff: '2026-08-29T12:20:00Z',
  match_status: 'live',
  home_score: 0,
  away_score: 0,
  home_penalty_score: null,
  away_penalty_score: null,
  tournament_group: 'MLS Next',
  tournament_round: 'group_stage',
  age_group: { id: 3, name: 'U15' },
  home_team: { id: 19, name: 'IFA' },
  away_team: { id: 601, name: 'Northern Virginia Alliance' },
  home_team_club: { id: 1, name: 'IFA' },
  away_team_club: { id: 267, name: 'NVA' },
  ...over,
});

const TOURNAMENT = matches => ({
  id: 8,
  name: 'Copa Rayados East Coast',
  start_date: '2026-08-29',
  end_date: '2026-08-30',
  matches,
  age_groups: [{ id: 3, name: 'U15' }],
});

// Every mount listens for visibilitychange, so a wrapper left mounted keeps
// answering events raised by later tests.
let wrapper = null;

async function mountWith(matches, laterMatches = null) {
  apiRequest.mockReset();
  let served = 0;
  apiRequest.mockImplementation(url => {
    if (url.includes('/api/seasons')) return Promise.resolve(SEASONS);
    if (/\/api\/tournaments\/\d+/.test(url)) {
      served += 1;
      const body = served > 1 && laterMatches ? laterMatches : matches;
      return Promise.resolve(TOURNAMENT(body));
    }
    if (url.includes('/api/tournaments'))
      return Promise.resolve([TOURNAMENT(matches)]);
    return Promise.resolve(null);
  });
  wrapper = mount(TournamentMatchCenter, {
    global: { stubs: { MatchDetailView: true } },
  });
  await flushPromises();
  return wrapper;
}

const tournamentFetches = () =>
  apiRequest.mock.calls.filter(([url]) => /\/api\/tournaments\/\d+/.test(url))
    .length;

const setHidden = value =>
  Object.defineProperty(document, 'hidden', { value, configurable: true });

beforeEach(() => {
  vi.clearAllMocks();
  handles.length = 0;
  setHidden(false);
});

afterEach(() => {
  wrapper?.unmount();
  wrapper = null;
});

describe('live rows', () => {
  it('subscribes to the live match', async () => {
    await mountWith([mkMatch()]);
    expect(subscribeToMatch).toHaveBeenCalledWith(3853, expect.any(Function));
  });

  it('does not subscribe to a scheduled match', async () => {
    await mountWith([mkMatch({ match_status: 'scheduled' })]);
    expect(subscribeToMatch).not.toHaveBeenCalled();
  });

  it('renders a score that arrives over realtime', async () => {
    const view = await mountWith([mkMatch()]);

    handles[0].onUpdate({
      id: 3853,
      home_score: 2,
      away_score: 3,
      match_status: 'completed',
    });
    await flushPromises();

    const row = view.get('[data-testid="tournament-match-row"]');
    expect(row.text()).toContain('2');
    expect(row.text()).toContain('3');
    // The joined team names survive the merge — the payload has team ids only.
    expect(row.text()).toContain('IFA');
    expect(row.text()).toContain('Northern Virginia Alliance');
  });
});

describe('refresh on return', () => {
  it('refetches the tournament when the tab becomes visible', async () => {
    const view = await mountWith(
      [mkMatch()],
      [mkMatch({ match_status: 'completed', home_score: 2, away_score: 3 })]
    );
    const before = tournamentFetches();

    document.dispatchEvent(new Event('visibilitychange'));
    await flushPromises();

    expect(tournamentFetches()).toBe(before + 1);
    expect(view.get('[data-testid="tournament-match-row"]').text()).toContain(
      '3'
    );
  });

  it('ignores the event when the tab is being hidden', async () => {
    await mountWith([mkMatch()]);
    const before = tournamentFetches();

    setHidden(true);
    document.dispatchEvent(new Event('visibilitychange'));
    await flushPromises();

    expect(tournamentFetches()).toBe(before);
  });

  it('keeps what is on screen when the refresh fails', async () => {
    const view = await mountWith([mkMatch()]);
    apiRequest.mockRejectedValueOnce(new Error('offline'));

    document.dispatchEvent(new Event('visibilitychange'));
    await flushPromises();

    expect(view.find('[data-testid="tournament-match-row"]').exists()).toBe(
      true
    );
  });
});
