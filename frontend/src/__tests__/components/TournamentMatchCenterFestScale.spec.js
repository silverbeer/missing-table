/**
 * TournamentMatchCenter.vue at MLS NEXT Fest scale (SB-1749).
 *
 * A tournament past the scale switch is paged and filtered by the server: the
 * page shows Age Group and Group controls, an age group is always selected,
 * the detail endpoint is never called, and there is no bracket or standings
 * tab. Showcase, placement finals and consolation are their own sections.
 *
 * A small tournament is untouched: one detail call, the same list.
 *
 * Every fixture is a scraped match with no user data — no scores, no
 * rosters, no manager. That is the normal state and it must render fully.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';

const apiRequest = vi.fn();
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ apiRequest, isAuthenticated: { value: false } }),
}));

import TournamentMatchCenter from '@/components/TournamentMatchCenter.vue';
import TournamentHeroCard from '@/components/TournamentHeroCard.vue';
import { TOURNAMENT_PAGE_SIZE } from '@/composables/useTournamentMatches';
import { localDateKey } from '@/utils/tournamentStatus';

const SEASONS = [
  {
    id: 4,
    name: '2026-2027',
    start_date: '2026-09-01',
    end_date: '2027-06-30',
  },
];

const U13 = { id: 5, name: 'U13' };
const U15 = { id: 7, name: 'U15' };

let nextId = 1;
const mkMatch = (round, group, age = U13, over = {}) => {
  const id = nextId++;
  return {
    id,
    match_date: '2026-12-04',
    scheduled_kickoff: null,
    match_status: 'scheduled',
    home_score: null,
    away_score: null,
    home_penalty_score: null,
    away_penalty_score: null,
    tournament_group: group,
    tournament_round: round,
    tournament_round_order: null,
    age_group: age,
    home_team: { id: id * 2, name: `Home ${id}` },
    away_team: { id: id * 2 + 1, name: `Away ${id}` },
    home_team_club: null,
    away_team_club: null,
    ...over,
  };
};
const many = (n, ...args) => Array.from({ length: n }, () => mkMatch(...args));

const FEST = {
  id: 6,
  name: 'MLS NEXT Fest',
  start_date: '2026-12-04',
  end_date: '2026-12-08',
  match_count: 2400,
  age_groups: [U13, U15],
};

const AGE_FACETS = [
  { id: 5, name: 'U13', matches: 412, matches_on_date: 0 },
  { id: 7, name: 'U15', matches: 380, matches_on_date: 0 },
];
const U13_GROUPS = [
  { key: 'AD · A', division: 'AD', label: 'A', matches: 5 },
  { key: 'HD · A', division: 'HD', label: 'A', matches: 6 },
];

const parse = url => new URL(url, 'http://test.example');
const query = url => Object.fromEntries(parse(url).searchParams.entries());
const requests = pathEnd =>
  apiRequest.mock.calls
    .map(([url]) => url)
    .filter(url => parse(url).pathname.endsWith(pathEnd));

/**
 * `pages`: "ageId|group" → every match for that filter (sliced by the
 * handler). `filters`: (query) → the filters response, or an Error to fail.
 * `matchesFor`: (query) → every match for that query, in place of `pages`,
 * for a test that needs the server's own filtering.
 */
async function mountFest({
  pages = {},
  matchesFor = null,
  filters,
  tournaments = [FEST],
  motd = { picks: [] },
}) {
  apiRequest.mockReset();
  apiRequest.mockImplementation(url => {
    const u = parse(url);
    if (u.pathname.endsWith('/api/seasons')) return Promise.resolve(SEASONS);
    if (u.pathname.endsWith('/motd')) return Promise.resolve(motd);
    if (u.pathname.endsWith('/filters')) {
      const out = filters(query(url));
      return out instanceof Error ? Promise.reject(out) : Promise.resolve(out);
    }
    if (u.pathname.endsWith('/matches')) {
      const q = query(url);
      const all = matchesFor
        ? matchesFor(q)
        : (pages[`${q.age_group_id ?? ''}|${q.group ?? ''}`] ?? []);
      const offset = Number(q.offset);
      const limit = Number(q.limit);
      return Promise.resolve({
        matches: all.slice(offset, offset + limit),
        total: all.length,
        limit,
        offset,
      });
    }
    if (u.pathname.endsWith('/api/tournaments')) {
      return Promise.resolve(tournaments);
    }
    // The detail endpoint: must never be asked for a large tournament.
    const id = Number(u.pathname.split('/').pop());
    const t = tournaments.find(x => x.id === id);
    return Promise.resolve(t ? { ...t, matches: t.detailMatches ?? [] } : null);
  });
  const wrapper = mount(TournamentMatchCenter, {
    global: { stubs: { MatchDetailView: true } },
  });
  await flushPromises();
  return wrapper;
}

const sectionTitles = w =>
  w.findAll('[data-testid="tournament-section"]').map(s => s.find('h3').text());
const buttonTexts = w => w.findAll('button').map(b => b.text());
const groupSelect = w => w.find('[data-testid="tournament-group-select"]');
const ageSelect = w => w.find('[data-testid="tournament-age-group-select"]');
const detailCalls = () =>
  apiRequest.mock.calls.filter(([url]) =>
    /\/api\/tournaments\/\d+$/.test(parse(url).pathname)
  );

beforeEach(() => {
  nextId = 1;
  vi.spyOn(console, 'error').mockImplementation(() => {});
});
afterEach(() => {
  console.error.mockRestore();
});

describe('Fest scale — a showcase-only age group (U15)', () => {
  const mountShowcase = () =>
    mountFest({
      // U15 plays today, so the page opens on it.
      filters: () => ({
        facets_available: true,
        age_groups: [
          AGE_FACETS[0],
          { id: 7, name: 'U15', matches: 380, matches_on_date: 40 },
        ],
        groups: [],
      }),
      pages: {
        '7|': [
          ...many(3, 'showcase', 'HD · Showcase', U15),
          ...many(2, 'showcase', 'AD · Showcase', U15),
          ...many(2, 'quarterfinal', 'GA Cup Qualifier', U15),
          ...many(1, 'consolation', 'GA Cup Qualifier', U15),
        ],
      },
    });

  it('opens on the age group playing today', async () => {
    const w = await mountShowcase();
    expect(ageSelect(w).element.value).toBe('7');
    expect(w.vm.viewedAgeGroupId).toBe(7);
  });

  it('has no Group control', async () => {
    const w = await mountShowcase();
    expect(ageSelect(w).exists()).toBe(true);
    expect(groupSelect(w).exists()).toBe(false);
  });

  it('renders Showcase as its own sections, titled by stage label', async () => {
    const w = await mountShowcase();
    expect(sectionTitles(w)).toEqual([
      'AD · Showcase',
      'HD · Showcase',
      'Knockout Rounds',
      'Consolation — GA Cup Qualifier',
    ]);
    // Nothing falls into the catch-all bucket.
    expect(sectionTitles(w)).not.toContain('Matches');
  });

  it('renders every scraped match with no roster or user data', async () => {
    const w = await mountShowcase();
    const rows = w.findAllComponents({ name: 'TournamentMatchRow' });
    expect(rows).toHaveLength(8);
    expect(w.text()).toContain('Home 1');
    expect(w.text()).toContain('Away 8');
    // Unplayed fixtures show no score — absent is not 0-0.
    expect(w.text()).not.toMatch(/\b0\s*[-–]\s*0\b/);
  });
});

describe('Fest scale — a groups-plus-finals age group (U13)', () => {
  const pages = {
    '5|': [
      ...many(6, 'group_stage', 'HD · A'),
      ...many(5, 'group_stage', 'AD · A'),
      ...many(3, 'placement_final', 'HD · Group Play'),
      ...many(2, 'consolation', 'HD · Group Play'),
    ],
    '5|HD · A': many(6, 'group_stage', 'HD · A'),
    '5|AD · A': many(5, 'group_stage', 'AD · A'),
    '7|': many(4, 'showcase', 'HD · Showcase', U15),
  };
  const filters = q => ({
    facets_available: true,
    age_groups: AGE_FACETS,
    groups: q.age_group_id === '5' ? U13_GROUPS : [],
  });
  const mountGroups = () => mountFest({ pages, filters });

  it('lists both HD · A and AD · A in the Group control', async () => {
    const w = await mountGroups();
    const options = groupSelect(w)
      .findAll('option')
      .map(o => o.element.value);
    expect(options).toEqual(['', 'AD · A', 'HD · A']);
    expect(groupSelect(w).text()).toContain('HD · A (6)');
    expect(groupSelect(w).text()).toContain('AD · A (5)');
  });

  it('renders group stage, placement finals and consolation sections', async () => {
    const w = await mountGroups();
    expect(sectionTitles(w)).toEqual([
      'Group Stage',
      'Placement Finals — HD · Group Play',
      'Consolation — HD · Group Play',
    ]);
  });

  it('has no Bracket or Standings tab, though it has group-stage matches', async () => {
    const w = await mountGroups();
    expect(buttonTexts(w)).not.toContain('Bracket');
    expect(buttonTexts(w)).not.toContain('Standings');
    expect(buttonTexts(w)).not.toContain('List');
    expect(w.vm.viewMode).toBe('list');
  });

  it('has no "All Ages" chip and no team filter', async () => {
    const w = await mountGroups();
    expect(buttonTexts(w)).not.toContain('All Ages');
    expect(w.find('input[placeholder="Filter by team…"]').exists()).toBe(false);
  });

  it('never calls the detail endpoint and always sends an age group', async () => {
    const w = await mountGroups();
    await groupSelect(w).setValue('HD · A');
    await flushPromises();
    await ageSelect(w).setValue('7');
    await flushPromises();

    expect(detailCalls()).toHaveLength(0);
    for (const url of requests('/matches')) {
      const q = query(url);
      expect(q.age_group_id).toBeTruthy();
      expect(Number(q.limit)).toBe(TOURNAMENT_PAGE_SIZE);
    }
  });

  it('sends the group when one is chosen, and narrows the list', async () => {
    const w = await mountGroups();
    apiRequest.mockClear();

    await groupSelect(w).setValue('HD · A');
    await flushPromises();

    // The group goes with the group-stage round: a group is a pool.
    expect(requests('/matches').map(query)).toEqual([
      {
        age_group_id: '5',
        group: 'HD · A',
        round: 'group_stage',
        limit: '200',
        offset: '0',
      },
    ]);
    expect(sectionTitles(w)).toEqual(['Group Stage']);
    expect(w.findAllComponents({ name: 'TournamentMatchRow' })).toHaveLength(6);
    expect(w.find('[data-testid="tournament-shown"]').text()).toBe(
      'Showing 6 of 6 matches'
    );
  });

  it('changing the age group resets the group and asks for the new age', async () => {
    const w = await mountGroups();
    await groupSelect(w).setValue('AD · A');
    await flushPromises();
    apiRequest.mockClear();

    await ageSelect(w).setValue('7');
    await flushPromises();

    expect(requests('/matches').map(query)).toEqual([
      { age_group_id: '7', limit: '200', offset: '0' },
    ]);
    expect(requests('/filters').map(u => query(u).age_group_id)).toEqual(['7']);
    expect(w.vm.viewedAgeGroupId).toBe(7);
    // U15 has no groups: the control goes away.
    expect(groupSelect(w).exists()).toBe(false);
    expect(sectionTitles(w)).toEqual(['HD · Showcase']);
  });

  it('shows the tournament’s exact size in the header, not the page size', async () => {
    const w = await mountGroups();
    expect(w.text()).toContain('2400 matches');
  });
});

describe('Fest scale — a group’s count and its list agree', () => {
  // HD · A is a pool of 16 group-stage matches, and one placement final
  // carries the same tournament_group. The facet counts the pool.
  const all = [
    ...many(16, 'group_stage', 'HD · A'),
    ...many(1, 'placement_final', 'HD · A'),
    ...many(5, 'group_stage', 'AD · A'),
  ];
  // Filters like the API: `group` and `round` are independent.
  const matchesFor = q =>
    all.filter(
      m =>
        String(m.age_group.id) === q.age_group_id &&
        (q.group == null || m.tournament_group === q.group) &&
        (q.round == null || m.tournament_round === q.round)
    );
  const filters = () => ({
    facets_available: true,
    age_groups: [{ id: 5, name: 'U13', matches: 22, matches_on_date: 0 }],
    groups: [
      { key: 'AD · A', division: 'AD', label: 'A', matches: 5 },
      { key: 'HD · A', division: 'HD', label: 'A', matches: 16 },
    ],
  });

  it('the option says 16 and the list shows 16', async () => {
    const w = await mountFest({ matchesFor, filters });
    expect(groupSelect(w).text()).toContain('HD · A (16)');

    await groupSelect(w).setValue('HD · A');
    await flushPromises();

    expect(w.findAllComponents({ name: 'TournamentMatchRow' })).toHaveLength(
      16
    );
    expect(w.find('[data-testid="tournament-shown"]').text()).toBe(
      'Showing 16 of 16 matches'
    );
    expect(sectionTitles(w)).toEqual(['Group Stage']);
  });

  it('clearing the group brings the other rounds back', async () => {
    const w = await mountFest({ matchesFor, filters });
    await groupSelect(w).setValue('HD · A');
    await flushPromises();
    apiRequest.mockClear();

    await groupSelect(w).setValue('');
    await flushPromises();

    expect(requests('/matches').map(query)).toEqual([
      { age_group_id: '5', limit: '200', offset: '0' },
    ]);
    expect(w.find('[data-testid="tournament-shown"]').text()).toBe(
      'Showing 22 of 22 matches'
    );
  });
});

describe('Fest scale — a refresh whose filters request fails', () => {
  it('keeps the Group control on screen while a group is applied', async () => {
    let filtersFail = false;
    const w = await mountFest({
      pages: {
        '5|': many(11, 'group_stage', 'HD · A'),
        '5|HD · A': many(6, 'group_stage', 'HD · A'),
      },
      filters: () =>
        filtersFail
          ? new Error('boom')
          : {
              facets_available: true,
              age_groups: AGE_FACETS,
              groups: U13_GROUPS,
            },
    });
    await groupSelect(w).setValue('HD · A');
    await flushPromises();

    // The tab comes back and the background refresh's filters request fails.
    filtersFail = true;
    apiRequest.mockClear();
    document.dispatchEvent(new Event('visibilitychange'));
    await flushPromises();

    expect(requests('/filters').length).toBeGreaterThan(0);
    // Still narrowed to the group — and the control to clear it is still there.
    expect(w.findAllComponents({ name: 'TournamentMatchRow' })).toHaveLength(6);
    expect(groupSelect(w).exists()).toBe(true);
    expect(groupSelect(w).element.value).toBe('HD · A');

    await groupSelect(w).setValue('');
    await flushPromises();
    expect(w.findAllComponents({ name: 'TournamentMatchRow' })).toHaveLength(
      11
    );
    w.unmount();
  });
});

describe('Fest scale — the hero card does not describe one page', () => {
  const filters = () => ({
    facets_available: true,
    age_groups: AGE_FACETS,
    groups: [],
  });

  it('passes the page with the exact total, and renders nothing read off the page', async () => {
    // A live match and a kickoff still to come, both on the loaded U13 page.
    const soon = new Date(Date.now() + 3 * 3600 * 1000).toISOString();
    const w = await mountFest({
      filters,
      pages: {
        '5|': [
          mkMatch('group_stage', 'HD · A', U13, { match_status: 'live' }),
          mkMatch('group_stage', 'HD · A', U13, { scheduled_kickoff: soon }),
        ],
      },
    });

    const hero = w.findComponent(TournamentHeroCard);
    expect(hero.props('totalMatches')).toBe(2400);
    expect(hero.text()).not.toContain('Live now');
    expect(hero.text().toLowerCase()).not.toContain('group stage');
    expect(hero.find('[data-testid="tournament-countdown"]').exists()).toBe(
      false
    );
    expect(hero.find('[data-testid="tournament-next-match"]').exists()).toBe(
      false
    );
    // The exact total stays, alone.
    const stats = hero.findAll('[data-testid="tournament-stat"]');
    expect(stats.map(s => s.text())).toEqual(['2400Matches']);
  });

  describe('the card itself, given part of a tournament', () => {
    // Sat 5 Dec 2026, local noon: the second day of the event.
    const NOW = new Date(2026, 11, 5, 12, 0, 0);
    const page = [
      mkMatch('group_stage', 'HD · A', U13, {
        match_status: 'live',
        home_team_club: { id: 1, name: 'IFA' },
      }),
      mkMatch('group_stage', 'HD · A', U13, {
        match_date: '2026-12-05',
        scheduled_kickoff: new Date(2026, 11, 5, 15, 0, 0).toISOString(),
        home_team_club: { id: 1, name: 'IFA' },
      }),
    ];
    const mountCard = props => {
      vi.useFakeTimers();
      vi.setSystemTime(NOW);
      return mount(TournamentHeroCard, {
        props: {
          tournament: FEST,
          matches: page,
          myClubId: 1,
          stageLabel: 'Group stage',
          ...props,
        },
      });
    };
    afterEach(() => {
      vi.useRealTimers();
    });

    it('large: the ribbon comes from the tournament’s dates, with no countdown, stage or next match', () => {
      const card = mountCard({ totalMatches: 2400 });

      const ribbon = card.find('[data-testid="tournament-status-ribbon"]');
      // True from start_date/end_date alone — not "Live now", which would be
      // a claim about one age group's page.
      expect(ribbon.text()).toBe('Happening today');
      expect(card.find('[data-testid="tournament-countdown"]').exists()).toBe(
        false
      );
      expect(card.find('[data-testid="tournament-next-match"]').exists()).toBe(
        false
      );
      expect(
        card.findAll('[data-testid="tournament-stat"]').map(s => s.text())
      ).toEqual(['2400Matches']);
    });

    it('large: an empty page changes nothing about the ribbon', () => {
      const withRows = mountCard({ totalMatches: 2400 });
      const empty = mountCard({ totalMatches: 2400, matches: [] });
      expect(
        empty.find('[data-testid="tournament-status-ribbon"]').text()
      ).toBe(withRows.find('[data-testid="tournament-status-ribbon"]').text());
    });

    it('large: a tournament with no dates has no ribbon at all', () => {
      const card = mountCard({
        totalMatches: 2400,
        tournament: { ...FEST, start_date: null, end_date: null },
      });
      expect(
        card.find('[data-testid="tournament-status-ribbon"]').exists()
      ).toBe(false);
    });

    it('small: the same rows still give Live now, the stage, a countdown and the next match', () => {
      const card = mountCard();

      const ribbon = card.find('[data-testid="tournament-status-ribbon"]');
      expect(ribbon.text()).toContain('Live now');
      expect(ribbon.text()).toContain('Group stage');
      expect(
        card.find('[data-testid="tournament-countdown"]').text()
      ).toContain('3h');
      expect(card.find('[data-testid="tournament-next-match"]').exists()).toBe(
        true
      );
    });
  });
});

describe('Fest scale — paging', () => {
  it('loads one page, says how many are shown, and loads the next on request', async () => {
    const w = await mountFest({
      filters: () => ({
        facets_available: true,
        age_groups: AGE_FACETS,
        groups: [],
      }),
      pages: { '5|': many(250, 'showcase', 'HD · Showcase') },
    });

    expect(w.findAllComponents({ name: 'TournamentMatchRow' })).toHaveLength(
      TOURNAMENT_PAGE_SIZE
    );
    expect(w.find('[data-testid="tournament-shown"]').text()).toBe(
      'Showing 200 of 250 matches'
    );

    await w.find('[data-testid="tournament-load-more"]').trigger('click');
    await flushPromises();

    expect(requests('/matches').map(u => query(u).offset)).toEqual([
      '0',
      '200',
    ]);
    expect(w.findAllComponents({ name: 'TournamentMatchRow' })).toHaveLength(
      250
    );
    expect(w.find('[data-testid="tournament-load-more"]').exists()).toBe(false);
  });
});

describe('Fest scale — an age group with no matches', () => {
  it('says so in words instead of spinning', async () => {
    const w = await mountFest({
      filters: () => ({
        facets_available: true,
        age_groups: [{ id: 5, name: 'U13', matches: 0, matches_on_date: 0 }],
        groups: [],
      }),
      pages: {},
    });

    expect(w.find('[data-testid="tournament-page-empty"]').text()).toBe(
      'No U13 matches entered yet.'
    );
    expect(w.find('.animate-spin').exists()).toBe(false);
    expect(w.find('[data-testid="tournament-page-footer"]').exists()).toBe(
      false
    );
  });
});

describe('Fest scale — the filters request degrades on its own', () => {
  const pages = {
    '5|': [
      ...many(4, 'group_stage', 'HD · A'),
      ...many(2, 'placement_final', 'HD · Group Play'),
    ],
  };

  it('a failed filters request leaves the list rendered and shows no counts', async () => {
    const w = await mountFest({ pages, filters: () => new Error('boom') });

    expect(w.findAllComponents({ name: 'TournamentMatchRow' })).toHaveLength(6);
    expect(sectionTitles(w)).toEqual([
      'Group Stage',
      'Placement Finals — HD · Group Play',
    ]);
    // Age Group still works, built from the tournament's own age groups…
    expect(
      ageSelect(w)
        .findAll('option')
        .map(o => o.text())
    ).toEqual(['U13', 'U15']);
    // …with no "(0)" anywhere, and no Group control claiming anything.
    expect(w.find('[data-testid="tournament-filters"]').text()).toBe(
      'Age GroupU13U15'
    );
    expect(groupSelect(w).exists()).toBe(false);
    expect(w.find('.bg-red-50').exists()).toBe(false);
  });

  it('null groups and null counts hide the control and render no zeros', async () => {
    const w = await mountFest({
      pages,
      filters: () => ({
        facets_available: false,
        age_groups: [
          { id: 5, name: 'U13', matches: null, matches_on_date: null },
          { id: 7, name: 'U15', matches: null, matches_on_date: null },
        ],
        groups: null,
      }),
    });

    expect(w.findAllComponents({ name: 'TournamentMatchRow' })).toHaveLength(6);
    expect(groupSelect(w).exists()).toBe(false);
    const filtersText = w.find('[data-testid="tournament-filters"]').text();
    expect(filtersText).toBe('Age GroupU13U15');
    expect(filtersText.toLowerCase()).not.toContain('no groups');
    expect(w.find('[data-testid="tournament-shown"]').text()).toBe(
      'Showing 6 of 6 matches'
    );
  });
});

describe('Fest scale — Match of the Day', () => {
  it('shows a pick whose match is not on the loaded page, from the pick itself', async () => {
    const today = localDateKey();
    const picked = mkMatch('showcase', 'HD · Showcase', U13, {
      id: 9001,
      match_date: today,
      home_team: { id: 1, name: 'IFA' },
      away_team: { id: 2, name: 'Cedar Stars' },
    });
    const w = await mountFest({
      filters: () => ({
        facets_available: true,
        age_groups: AGE_FACETS,
        groups: [],
      }),
      // The page on screen is U13; the pick is a U13 match that is not on it.
      pages: { '5|': many(3, 'group_stage', 'HD · A') },
      motd: {
        picks: [
          {
            tournament_id: 6,
            match_date: today,
            blurb: 'Showcase opener',
            reasons: null,
            match: picked,
          },
        ],
      },
    });

    expect(w.vm.viewedAgeGroupId).toBe(5);
    expect(w.vm.todayMotds[0].liveMatch).toBe(null);
    const banner = w.find('[data-testid="motd-banner"]');
    expect(banner.exists()).toBe(true);
    expect(banner.text()).toContain('IFA');
    expect(banner.text()).toContain('Cedar Stars');
    expect(banner.text()).toContain('Showcase opener');
    // The list underneath is untouched by it.
    expect(w.findAllComponents({ name: 'TournamentMatchRow' })).toHaveLength(3);
  });
});

describe('Small tournament — unchanged', () => {
  const SMALL = {
    id: 3,
    name: 'NAC',
    start_date: '2026-06-05',
    end_date: '2026-06-07',
    match_count: 186,
    age_groups: [U13],
    detailMatches: [
      ...many(2, 'group_stage', 'Bracket A'),
      ...many(1, 'semifinal', 'Championship'),
    ],
  };

  it('makes exactly the one detail call and none of the paged ones', async () => {
    const w = await mountFest({
      tournaments: [SMALL],
      pages: {},
      filters: () => new Error('must not be called'),
    });
    // Mounting selects the tournament once per list fetch; count one
    // selection on its own.
    apiRequest.mockClear();
    await w.vm.selectTournament(3);
    await flushPromises();

    expect(detailCalls()).toHaveLength(1);
    expect(
      apiRequest.mock.calls.filter(([url]) => !url.includes('/motd'))
    ).toHaveLength(1);
    expect(requests('/matches')).toHaveLength(0);
    expect(requests('/filters')).toHaveLength(0);
    expect(w.vm.isLargeTournament).toBe(false);
  });

  it('keeps the list, the bracket and standings tabs, and no filter controls', async () => {
    const w = await mountFest({
      tournaments: [SMALL],
      pages: {},
      filters: () => new Error('must not be called'),
    });

    expect(sectionTitles(w)).toEqual(['Group Stage', 'Knockout Rounds']);
    expect(buttonTexts(w)).toEqual(
      expect.arrayContaining(['List', 'Bracket', 'Standings'])
    );
    expect(w.find('[data-testid="tournament-filters"]').exists()).toBe(false);
    expect(w.find('[data-testid="tournament-page-footer"]').exists()).toBe(
      false
    );
    expect(w.text()).toContain('3 matches');
    // Small mode: the viewed age group is the chip, and none is chosen.
    expect(w.vm.viewedAgeGroupId).toBe(null);
  });

  it('a tournament at the threshold is still small', async () => {
    const w = await mountFest({
      tournaments: [{ ...SMALL, match_count: 300 }],
      pages: {},
      filters: () => new Error('must not be called'),
    });
    expect(w.vm.isLargeTournament).toBe(false);
    expect(detailCalls().length).toBeGreaterThan(0);
    expect(requests('/matches')).toHaveLength(0);
  });
});
