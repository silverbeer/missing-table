/**
 * TournamentMatchCenter — Match of the Day follows the viewed age group
 * (SB-1750).
 *
 * One pick per (tournament, day, age group). The banner is the pick for the
 * age group on screen; an age group with no pick shows no banner — never
 * another age group's — and its rows render as they always did. All Ages
 * stacks one banner per age group.
 *
 * Every fixture is a scraped match with no user data: no scores, no rosters.
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

const U15 = { id: 2, name: 'U15' };
const U16 = { id: 3, name: 'U16' };
const U17 = { id: 4, name: 'U17' };

const mkMatch = (id, home, away, age, over = {}) => ({
  id,
  match_date: TODAY,
  scheduled_kickoff: null,
  match_status: 'scheduled',
  home_score: null,
  away_score: null,
  tournament_group: 'A',
  tournament_round: 'group_stage',
  age_group: age,
  home_team: { id: id * 10, name: home },
  away_team: { id: id * 10 + 1, name: away },
  ...over,
});

const U15_PICKED = mkMatch(501, 'IFA', 'Cedar Stars', U15);
const U16_PICKED = mkMatch(601, 'Bolts', 'NEFC', U16);
const MATCHES = [
  U15_PICKED,
  mkMatch(502, 'Oakwood', 'Seacoast', U15),
  U16_PICKED,
  mkMatch(602, 'Revolution', 'Valeo', U16),
  mkMatch(701, 'Rush', 'Surf', U17),
  mkMatch(702, 'Ironbound', 'PDA', U17),
];

// As the API embeds it: flat names, not the nested objects of the list.
const embedded = m => ({
  id: m.id,
  match_date: m.match_date,
  home_team_name: m.home_team.name,
  away_team_name: m.away_team.name,
  home_score: null,
  away_score: null,
  age_group_id: m.age_group.id,
  age_group_name: m.age_group.name,
});

const pickFor = (match, blurb, over = {}) => ({
  tournament_id: 12,
  match_date: TODAY,
  age_group_id: match.age_group.id,
  age_group: match.age_group.name,
  blurb,
  reasons: null,
  match: embedded(match),
  ...over,
});

// Ordered by age group, as GET /api/tournaments/{id}/motd returns them.
const PICKS = [
  pickFor(U15_PICKED, 'U15 decider'),
  pickFor(U16_PICKED, 'U16 decider'),
];

const parse = url => new URL(url, 'http://test.example');
const motdRequests = () =>
  apiRequest.mock.calls.filter(([url]) =>
    parse(url).pathname.endsWith('/motd')
  );

async function mountSmall({ matches = MATCHES, picks = PICKS } = {}) {
  const tournament = {
    id: 12,
    name: 'Spring Cup',
    start_date: TODAY,
    end_date: TODAY,
    matches,
    age_groups: [U15, U16, U17],
  };
  apiRequest.mockReset();
  apiRequest.mockImplementation(url => {
    if (url.includes('/api/seasons')) return Promise.resolve([]);
    if (url.includes('/motd')) return Promise.resolve({ picks });
    if (/\/api\/tournaments\/\d+/.test(url)) return Promise.resolve(tournament);
    if (url.includes('/api/tournaments')) return Promise.resolve([tournament]);
    return Promise.resolve(null);
  });
  const wrapper = mount(TournamentMatchCenter, {
    global: { stubs: { MatchDetailView: true } },
  });
  await flushPromises();
  return wrapper;
}

const banners = w => w.findAll('[data-testid="motd-banner"]');
const bannerAges = w =>
  banners(w).map(b => b.find('[data-testid="motd-age"]').text());
const rows = w => w.findAll('[data-testid="tournament-match-row"]');
const motdRows = w =>
  rows(w).filter(r => r.find('[data-variant="motd"]').exists());

const clickButton = async (w, text) => {
  const button = w.findAll('button').find(b => b.text() === text);
  expect(button, `button "${text}"`).toBeTruthy();
  await button.trigger('click');
  await flushPromises();
};

describe('Match of the Day — the viewed age group (SB-1750)', () => {
  it('shows every pick for today under All Ages, ordered by age group', async () => {
    const w = await mountSmall();
    expect(w.vm.viewedAgeGroupId).toBe(null);
    expect(bannerAges(w)).toEqual(['U15', 'U16']);
    expect(banners(w)[0].text()).toContain('U15 decider');
    expect(banners(w)[1].text()).toContain('U16 decider');
  });

  it("shows only the selected age group's banner", async () => {
    const w = await mountSmall();

    await clickButton(w, 'U15');
    expect(w.vm.viewedAgeGroupId).toBe(U15.id);
    expect(bannerAges(w)).toEqual(['U15']);
    expect(banners(w)[0].text()).toContain('IFA');
    expect(banners(w)[0].text()).not.toContain('Bolts');

    await clickButton(w, 'U16');
    expect(bannerAges(w)).toEqual(['U16']);
    expect(banners(w)[0].text()).toContain('Bolts');
    expect(banners(w)[0].text()).not.toContain('IFA');

    await clickButton(w, 'All Ages');
    expect(bannerAges(w)).toEqual(['U15', 'U16']);
  });

  it('shows no banner for an age group with no pick, and still its rows', async () => {
    const w = await mountSmall();
    await clickButton(w, 'U17');

    expect(banners(w)).toHaveLength(0);
    // Nothing stands in for the missing pick.
    expect(w.text()).not.toContain('Match of the Day');
    expect(rows(w)).toHaveLength(2);
    expect(w.text()).toContain('Rush');
    expect(w.text()).toContain('Ironbound');
    expect(motdRows(w)).toHaveLength(0);
  });

  it('badges the picked row in the age group being viewed', async () => {
    const w = await mountSmall();
    expect(motdRows(w)).toHaveLength(2);

    await clickButton(w, 'U15');
    expect(rows(w)).toHaveLength(2);
    expect(motdRows(w)).toHaveLength(1);
    expect(motdRows(w)[0].text()).toContain('Cedar Stars');

    await clickButton(w, 'U16');
    expect(motdRows(w)).toHaveLength(1);
    expect(motdRows(w)[0].text()).toContain('NEFC');
  });

  it("passes the page's live copy of each picked match, per pick", async () => {
    const w = await mountSmall();
    expect(w.vm.todayMotds.map(e => e.liveMatch)).toEqual([
      U15_PICKED,
      U16_PICKED,
    ]);
  });

  it('does not ask for the picks again when the age group changes', async () => {
    const w = await mountSmall();
    const before = motdRequests().length;
    expect(before).toBeGreaterThan(0);

    await clickButton(w, 'U15');
    await clickButton(w, 'U16');
    await clickButton(w, 'U17');
    await clickButton(w, 'All Ages');

    expect(motdRequests()).toHaveLength(before);
  });

  it('follows a legacy pick without age_group_id by its match', async () => {
    const legacy = pickFor(U16_PICKED, 'Legacy pick');
    delete legacy.age_group_id;
    const w = await mountSmall({ picks: [legacy] });

    await clickButton(w, 'U16');
    expect(bannerAges(w)).toEqual(['U16']);
    await clickButton(w, 'U15');
    expect(banners(w)).toHaveLength(0);
  });

  it('follows the standings view own age selection', async () => {
    const w = await mountSmall();
    await clickButton(w, 'Standings');

    // Standings opens on its first age group, whatever the list chip says.
    expect(w.vm.ageGroupFilter).toBe(null);
    expect(w.vm.viewedAgeGroupId).toBe(U15.id);
    expect(bannerAges(w)).toEqual(['U15']);

    await clickButton(w, 'U16');
    expect(bannerAges(w)).toEqual(['U16']);
    await clickButton(w, 'U17');
    expect(banners(w)).toHaveLength(0);

    // Back on the list, the list's own selection (All Ages) applies again.
    await clickButton(w, 'List');
    expect(bannerAges(w)).toEqual(['U15', 'U16']);
  });

  it('follows the bracket view own age selection', async () => {
    const w = await mountSmall({
      matches: [
        ...MATCHES,
        mkMatch(650, 'Bolts', 'Valeo', U16, {
          tournament_round: 'semifinal',
          tournament_group: 'Championship',
        }),
      ],
    });
    await clickButton(w, 'Bracket');

    // U16 is the only age group with a bracket.
    expect(w.vm.viewedAgeGroupId).toBe(U16.id);
    expect(bannerAges(w)).toEqual(['U16']);
  });
});

describe('Match of the Day — a paged tournament (SB-1750)', () => {
  const FEST = {
    id: 12,
    name: 'MLS NEXT Fest',
    start_date: TODAY,
    end_date: TODAY,
    match_count: 2400,
    age_groups: [U15, U16, U17],
  };
  const PAGES = {
    [U15.id]: [mkMatch(502, 'Oakwood', 'Seacoast', U15)],
    [U16.id]: [mkMatch(602, 'Revolution', 'Valeo', U16)],
    [U17.id]: [mkMatch(701, 'Rush', 'Surf', U17)],
  };

  async function mountFest() {
    apiRequest.mockReset();
    apiRequest.mockImplementation(url => {
      const u = parse(url);
      const q = Object.fromEntries(u.searchParams.entries());
      if (u.pathname.endsWith('/api/seasons')) return Promise.resolve([]);
      if (u.pathname.endsWith('/motd')) {
        return Promise.resolve({ picks: PICKS });
      }
      if (u.pathname.endsWith('/filters')) {
        return Promise.resolve({
          facets_available: true,
          age_groups: FEST.age_groups.map(ag => ({
            ...ag,
            matches: 400,
            matches_on_date: 0,
          })),
          groups: [],
        });
      }
      if (u.pathname.endsWith('/matches')) {
        const all = PAGES[q.age_group_id] ?? [];
        return Promise.resolve({
          matches: all,
          total: all.length,
          limit: Number(q.limit),
          offset: Number(q.offset),
        });
      }
      if (u.pathname.endsWith('/api/tournaments')) {
        return Promise.resolve([FEST]);
      }
      return Promise.resolve(null);
    });
    const wrapper = mount(TournamentMatchCenter, {
      global: { stubs: { MatchDetailView: true } },
    });
    await flushPromises();
    return wrapper;
  }

  const selectAge = async (w, age) => {
    await w
      .find('[data-testid="tournament-age-group-select"]')
      .setValue(String(age.id));
    await flushPromises();
  };

  it("shows the viewed age group's pick from the pick itself when its match is not on the page", async () => {
    const w = await mountFest();
    expect(w.vm.isLargeTournament).toBe(true);
    expect(w.vm.viewedAgeGroupId).toBe(U15.id);

    // The picked U15 match (501) is not among the loaded rows.
    expect(rows(w)).toHaveLength(1);
    expect(w.vm.todayMotds.map(e => e.liveMatch)).toEqual([null]);
    expect(bannerAges(w)).toEqual(['U15']);
    expect(banners(w)[0].text()).toContain('IFA');
    expect(banners(w)[0].text()).toContain('Cedar Stars');
    expect(banners(w)[0].text()).toContain('U15 decider');
  });

  it('switches banner with the age group, without another picks request', async () => {
    const w = await mountFest();
    const before = motdRequests().length;

    await selectAge(w, U16);
    expect(w.vm.viewedAgeGroupId).toBe(U16.id);
    expect(bannerAges(w)).toEqual(['U16']);
    expect(banners(w)[0].text()).toContain('Bolts');
    expect(banners(w)[0].text()).not.toContain('IFA');

    await selectAge(w, U17);
    expect(banners(w)).toHaveLength(0);
    expect(rows(w)).toHaveLength(1);
    expect(w.text()).toContain('Rush');

    expect(motdRequests()).toHaveLength(before);
  });
});
