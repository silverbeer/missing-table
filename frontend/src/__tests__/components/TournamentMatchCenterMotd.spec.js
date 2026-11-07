/**
 * TournamentMatchCenter — tournament Match of the Day wiring (SB-1560).
 *
 * The banner shows today's pick only; the picked row carries a chip; a
 * tournament with no picks, or a failed pick fetch, renders the page exactly
 * as it was before picks existed.
 */
import { describe, it, expect, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';

const apiRequest = vi.fn();
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ apiRequest, isAuthenticated: { value: false } }),
}));

import TournamentMatchCenter from '@/components/TournamentMatchCenter.vue';
import { localDateKey } from '@/utils/tournamentStatus';

const TODAY = localDateKey();
const OTHER_DAY = '2020-01-01';

const mkMatch = (id, home, away, date = TODAY) => ({
  id,
  match_date: date,
  scheduled_kickoff: null,
  match_status: 'scheduled',
  home_score: null,
  away_score: null,
  tournament_group: 'A',
  tournament_round: 'group_stage',
  age_group: { id: 2, name: 'U15' },
  home_team: { id: id * 10, name: home },
  away_team: { id: id * 10 + 1, name: away },
});

const MATCHES = [
  mkMatch(501, 'IFA', 'Cedar Stars'),
  mkMatch(502, 'Bolts', 'NEFC'),
];

const TOURNAMENT = {
  id: 12,
  name: 'MLS NEXT Fest',
  start_date: TODAY,
  end_date: TODAY,
  matches: MATCHES,
  age_groups: [{ id: 2, name: 'U15' }],
};

const pickFor = (match, date = TODAY, over = {}) => ({
  tournament_id: 12,
  match_date: date,
  blurb: 'Group A decider',
  reasons: [{ text: 'Both unbeaten' }],
  match,
  ...over,
});

async function mountWith(motdResponse) {
  apiRequest.mockReset();
  apiRequest.mockImplementation(url => {
    if (url.includes('/api/seasons')) return Promise.resolve([]);
    if (url.includes('/motd')) {
      return motdResponse instanceof Error
        ? Promise.reject(motdResponse)
        : Promise.resolve(motdResponse);
    }
    if (/\/api\/tournaments\/\d+/.test(url)) return Promise.resolve(TOURNAMENT);
    if (url.includes('/api/tournaments')) return Promise.resolve([TOURNAMENT]);
    return Promise.resolve(null);
  });
  const wrapper = mount(TournamentMatchCenter, {
    global: { stubs: { MatchDetailView: true } },
  });
  await flushPromises();
  return wrapper;
}

const motdRows = w =>
  w
    .findAll('[data-testid="tournament-match-row"]')
    .filter(r => r.find('[data-variant="motd"]').exists());

describe('TournamentMatchCenter — Match of the Day (SB-1560)', () => {
  it("shows today's pick in the banner and chips its row", async () => {
    const w = await mountWith({ picks: [pickFor(MATCHES[0])] });
    const banner = w.find('[data-testid="motd-banner"]');
    expect(banner.exists()).toBe(true);
    expect(banner.text()).toContain('IFA');
    expect(banner.text()).toContain('Group A decider');
    expect(banner.findAll('[data-testid="motd-reason"]')).toHaveLength(1);
    const rows = motdRows(w);
    expect(rows).toHaveLength(1);
    expect(rows[0].text()).toContain('Cedar Stars');
  });

  it('shows no banner when the only pick is for another day', async () => {
    const w = await mountWith({ picks: [pickFor(MATCHES[1], OTHER_DAY)] });
    expect(w.find('[data-testid="motd-banner"]').exists()).toBe(false);
    // The pick still marks its match in the list.
    expect(motdRows(w)).toHaveLength(1);
  });

  it('renders the page unchanged when there are no picks', async () => {
    const w = await mountWith({ picks: [] });
    expect(w.find('[data-testid="motd-banner"]').exists()).toBe(false);
    expect(motdRows(w)).toHaveLength(0);
    expect(w.findAll('[data-testid="tournament-match-row"]')).toHaveLength(2);
  });

  it('treats a failed pick fetch as no picks, not a page error', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const w = await mountWith(new Error('boom'));
    expect(w.find('[data-testid="motd-banner"]').exists()).toBe(false);
    expect(w.findAll('[data-testid="tournament-match-row"]')).toHaveLength(2);
    expect(w.text()).not.toContain('boom');
    spy.mockRestore();
  });

  it('shows the banner without a Why list when reasons are null', async () => {
    const w = await mountWith({
      picks: [pickFor(MATCHES[0], TODAY, { reasons: null })],
    });
    expect(w.find('[data-testid="motd-banner"]').exists()).toBe(true);
    expect(w.find('[data-testid="motd-reasons"]').exists()).toBe(false);
  });
});
