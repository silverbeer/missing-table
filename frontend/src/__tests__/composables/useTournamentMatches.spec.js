/**
 * useTournamentMatches tests (SB-1749).
 *
 * The scale switch: a small tournament is one detail call; a large one is
 * paged and filtered by the server with an age group always selected. The
 * filters request is decoration — when it fails or cannot count, matches
 * still load and nothing is reported as zero.
 *
 * Fixtures are scraped matches: no scores, no rosters, no user data.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

const apiRequest = vi.fn();
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ apiRequest }),
}));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://test.example',
}));

import {
  GROUP_FILTER_ROUND,
  LARGE_TOURNAMENT_MATCH_THRESHOLD,
  TOURNAMENT_PAGE_SIZE,
  isLargeTournament,
  pickDefaultAgeGroupId,
  useTournamentMatches,
} from '@/composables/useTournamentMatches';
import { localDateKey } from '@/utils/tournamentStatus';

const mkMatch = (id, over = {}) => ({
  id,
  match_date: '2026-12-04',
  scheduled_kickoff: null,
  match_status: 'scheduled',
  home_score: null,
  away_score: null,
  tournament_group: 'HD · A',
  tournament_round: 'group_stage',
  age_group: { id: 5, name: 'U13' },
  home_team: { id: id * 2, name: `Home ${id}` },
  away_team: { id: id * 2 + 1, name: `Away ${id}` },
  ...over,
});

const range = (from, count) =>
  Array.from({ length: count }, (_, i) => mkMatch(from + i));

const SMALL = { id: 3, name: 'NAC', match_count: 186 };
const LARGE = {
  id: 6,
  name: 'MLS NEXT Fest',
  start_date: '2026-12-04',
  match_count: 2400,
  age_groups: [
    { id: 5, name: 'U13' },
    { id: 7, name: 'U15' },
  ],
};

const FILTERS_ALL = {
  facets_available: true,
  age_groups: [
    { id: 5, name: 'U13', matches: 412, matches_on_date: 0 },
    { id: 7, name: 'U15', matches: 380, matches_on_date: 0 },
  ],
  groups: [],
};
const GROUPS_U13 = [
  { key: 'AD · A', division: 'AD', label: 'A', matches: 5 },
  { key: 'HD · A', division: 'HD', label: 'A', matches: 6 },
];

const parse = url => new URL(url);
const calls = pathEnd =>
  apiRequest.mock.calls
    .map(([url]) => parse(url))
    .filter(u => u.pathname.endsWith(pathEnd));
const query = u => Object.fromEntries(u.searchParams.entries());

/**
 * Route requests like the API. `pages` maps "ageId|group" to the full list of
 * matches for that filter; the handler slices it by limit/offset.
 */
function serve({ filters, pages = {}, detail = null } = {}) {
  apiRequest.mockImplementation(url => {
    const u = parse(url);
    if (u.pathname.endsWith('/filters')) {
      const out = typeof filters === 'function' ? filters(query(u)) : filters;
      return out instanceof Error ? Promise.reject(out) : Promise.resolve(out);
    }
    if (u.pathname.endsWith('/matches')) {
      const q = query(u);
      const all = pages[`${q.age_group_id ?? ''}|${q.group ?? ''}`] ?? [];
      const offset = Number(q.offset);
      const limit = Number(q.limit);
      return Promise.resolve({
        matches: all.slice(offset, offset + limit),
        total: all.length,
        limit,
        offset,
      });
    }
    return Promise.resolve(detail);
  });
}

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};
// Let every already-resolved promise run its continuations.
const settle = () => new Promise(resolve => setTimeout(resolve, 0));

const u13Filters = q =>
  q.age_group_id === '5' ? { ...FILTERS_ALL, groups: GROUPS_U13 } : FILTERS_ALL;

beforeEach(() => {
  apiRequest.mockReset();
});

describe('the scale switch', () => {
  it('is one named threshold', () => {
    expect(LARGE_TOURNAMENT_MATCH_THRESHOLD).toBe(300);
    expect(isLargeTournament({ match_count: 300 })).toBe(false);
    expect(isLargeTournament({ match_count: 301 })).toBe(true);
  });

  it('treats a missing match_count as small, not large', () => {
    expect(isLargeTournament({})).toBe(false);
    expect(isLargeTournament(null)).toBe(false);
    expect(isLargeTournament({ match_count: null })).toBe(false);
  });
});

describe('pickDefaultAgeGroupId', () => {
  it('prefers the first age group playing today', () => {
    expect(
      pickDefaultAgeGroupId([
        { id: 5, matches: 400, matches_on_date: 0 },
        { id: 6, matches: 400, matches_on_date: 12 },
        { id: 7, matches: 400, matches_on_date: 9 },
      ])
    ).toBe(6);
  });

  it('falls back to the first age group with matches', () => {
    expect(
      pickDefaultAgeGroupId([
        { id: 5, matches: 0, matches_on_date: 0 },
        { id: 6, matches: 400, matches_on_date: 0 },
      ])
    ).toBe(6);
  });

  it('does not treat an uncounted age group as empty', () => {
    expect(
      pickDefaultAgeGroupId([
        { id: 5, matches: null, matches_on_date: null },
        { id: 6, matches: null, matches_on_date: null },
      ])
    ).toBe(5);
  });

  it('takes the first listed when none has matches, and null when none exist', () => {
    expect(pickDefaultAgeGroupId([{ id: 5, matches: 0 }])).toBe(5);
    expect(pickDefaultAgeGroupId([])).toBe(null);
    expect(pickDefaultAgeGroupId(null)).toBe(null);
  });
});

describe('small tournament', () => {
  it('makes exactly the one detail call', async () => {
    const detail = { ...SMALL, matches: range(1, 3) };
    serve({ detail });
    const tm = useTournamentMatches();

    await tm.load(SMALL);

    expect(apiRequest).toHaveBeenCalledTimes(1);
    expect(apiRequest.mock.calls[0][0]).toBe(
      'http://test.example/api/tournaments/3'
    );
    expect(tm.isLarge.value).toBe(false);
    expect(tm.tournament.value).toEqual(detail);
    expect(tm.hasMore.value).toBe(false);
  });

  it('refresh refetches the detail', async () => {
    serve({ detail: { ...SMALL, matches: range(1, 3) } });
    const tm = useTournamentMatches();
    await tm.load(SMALL);

    serve({ detail: { ...SMALL, matches: range(1, 4) } });
    await tm.refresh();

    expect(tm.tournament.value.matches).toHaveLength(4);
    expect(calls('/matches')).toHaveLength(0);
  });

  it('a failed load throws and leaves what was there', async () => {
    serve({ detail: { ...SMALL, matches: range(1, 3) } });
    const tm = useTournamentMatches();
    await tm.load(SMALL);

    apiRequest.mockRejectedValue(new Error('offline'));
    await expect(tm.load({ id: 4, match_count: 10 })).rejects.toThrow(
      'offline'
    );
    expect(tm.tournament.value.id).toBe(3);
  });

  it('filter setters do nothing', async () => {
    serve({ detail: { ...SMALL, matches: range(1, 3) } });
    const tm = useTournamentMatches();
    await tm.load(SMALL);
    apiRequest.mockClear();

    await tm.setAgeGroup(5);
    await tm.setGroup('HD · A');
    await tm.loadMore();

    expect(apiRequest).not.toHaveBeenCalled();
  });
});

describe('large tournament — load', () => {
  it('never calls the detail endpoint and never asks for more than a page', async () => {
    serve({ filters: u13Filters, pages: { '5|': range(1, 412) } });
    const tm = useTournamentMatches();

    await tm.load(LARGE);

    const urls = apiRequest.mock.calls.map(([url]) => parse(url).pathname);
    expect(urls).not.toContain('/api/tournaments/6');
    for (const u of calls('/matches')) {
      expect(Number(u.searchParams.get('limit'))).toBe(TOURNAMENT_PAGE_SIZE);
      expect(u.searchParams.get('age_group_id')).toBeTruthy();
    }
    expect(tm.isLarge.value).toBe(true);
    expect(tm.tournament.value.matches).toHaveLength(TOURNAMENT_PAGE_SIZE);
    expect(tm.total.value).toBe(412);
    expect(tm.hasMore.value).toBe(true);
  });

  it('keeps the list row as the header', async () => {
    serve({ filters: u13Filters, pages: { '5|': range(1, 3) } });
    const tm = useTournamentMatches();
    await tm.load(LARGE);
    expect(tm.tournament.value.name).toBe('MLS NEXT Fest');
    expect(tm.tournament.value.match_count).toBe(2400);
  });

  it('asks the filters for today, then for the chosen age group', async () => {
    serve({ filters: u13Filters, pages: { '5|': range(1, 3) } });
    const tm = useTournamentMatches();
    await tm.load(LARGE);

    const filterCalls = calls('/filters').map(query);
    expect(filterCalls).toEqual([
      { on_date: localDateKey() },
      { age_group_id: '5', on_date: localDateKey() },
    ]);
    expect(tm.groups.value).toEqual(GROUPS_U13);
  });

  it('opens on the age group playing today', async () => {
    const filters = {
      ...FILTERS_ALL,
      age_groups: [
        { id: 5, name: 'U13', matches: 412, matches_on_date: 0 },
        { id: 7, name: 'U15', matches: 380, matches_on_date: 40 },
      ],
    };
    serve({ filters, pages: { '7|': range(1, 3) } });
    const tm = useTournamentMatches();
    await tm.load(LARGE);

    expect(tm.selectedAgeGroupId.value).toBe(7);
    expect(calls('/matches').map(query)[0].age_group_id).toBe('7');
  });

  it('a showcase-only age group has an empty group list, not null', async () => {
    serve({ filters: FILTERS_ALL, pages: { '5|': range(1, 3) } });
    const tm = useTournamentMatches();
    await tm.load(LARGE);
    expect(tm.groups.value).toEqual([]);
  });

  it('throws when the first page cannot be loaded', async () => {
    apiRequest.mockImplementation(url =>
      url.includes('/filters')
        ? Promise.resolve(FILTERS_ALL)
        : Promise.reject(new Error('offline'))
    );
    const tm = useTournamentMatches();
    await expect(tm.load(LARGE)).rejects.toThrow('offline');
  });

  it('an age group with no matches loads as a real empty list', async () => {
    serve({ filters: FILTERS_ALL, pages: {} });
    const tm = useTournamentMatches();
    await tm.load(LARGE);

    expect(tm.tournament.value.matches).toEqual([]);
    expect(tm.total.value).toBe(0);
    expect(tm.pageLoading.value).toBe(false);
    expect(tm.hasMore.value).toBe(false);
  });
});

describe('large tournament — filters degrade without touching the list', () => {
  it('a failed filters request still loads matches, from the tournament’s own age groups', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    serve({ filters: new Error('boom'), pages: { '5|': range(1, 3) } });
    const tm = useTournamentMatches();

    await tm.load(LARGE);

    expect(tm.tournament.value.matches).toHaveLength(3);
    expect(tm.selectedAgeGroupId.value).toBe(5);
    // Unknown, not zero and not "no groups".
    expect(tm.groups.value).toBe(null);
    expect(tm.ageGroups.value).toEqual([
      { id: 5, name: 'U13', matches: null, matches_on_date: null },
      { id: 7, name: 'U15', matches: null, matches_on_date: null },
    ]);
    console.error.mockRestore();
  });

  it('facets the server could not count stay null', async () => {
    const unavailable = {
      facets_available: false,
      age_groups: [
        { id: 5, name: 'U13', matches: null, matches_on_date: null },
        { id: 7, name: 'U15', matches: null, matches_on_date: null },
      ],
      groups: null,
    };
    serve({ filters: unavailable, pages: { '5|': range(1, 3) } });
    const tm = useTournamentMatches();
    await tm.load(LARGE);

    expect(tm.groups.value).toBe(null);
    expect(tm.ageGroups.value.every(ag => ag.matches === null)).toBe(true);
    expect(tm.tournament.value.matches).toHaveLength(3);
  });
});

describe('large tournament — changing filters', () => {
  const pages = {
    '5|': range(1, 412),
    '5|HD · A': range(1, 6),
    '5|AD · A': range(500, 5),
    '7|': range(1000, 14),
  };

  async function loaded() {
    serve({ filters: u13Filters, pages });
    const tm = useTournamentMatches();
    await tm.load(LARGE);
    apiRequest.mockClear();
    return tm;
  }

  it('setGroup sends age group, group, the group-stage round, limit and offset 0', async () => {
    const tm = await loaded();

    await tm.setGroup('HD · A');

    // A group is a group-stage pool, and its count is of group-stage
    // matches: the round goes with it so the list is what was counted.
    expect(GROUP_FILTER_ROUND).toBe('group_stage');
    expect(calls('/matches').map(query)).toEqual([
      {
        age_group_id: '5',
        group: 'HD · A',
        round: 'group_stage',
        limit: String(TOURNAMENT_PAGE_SIZE),
        offset: '0',
      },
    ]);
    expect(calls('/filters')).toHaveLength(0);
    expect(tm.total.value).toBe(6);
    expect(tm.tournament.value.matches).toHaveLength(6);
  });

  it('HD · A and AD · A are different requests with different rows', async () => {
    const tm = await loaded();
    await tm.setGroup('HD · A');
    const hd = tm.tournament.value.matches.map(m => m.id);
    await tm.setGroup('AD · A');
    const ad = tm.tournament.value.matches.map(m => m.id);

    expect(calls('/matches').map(u => u.searchParams.get('group'))).toEqual([
      'HD · A',
      'AD · A',
    ]);
    expect(hd.some(id => ad.includes(id))).toBe(false);
  });

  it('clearing the group drops the parameter', async () => {
    const tm = await loaded();
    await tm.setGroup('HD · A');
    apiRequest.mockClear();

    await tm.setGroup(null);

    expect(calls('/matches').map(query)[0]).not.toHaveProperty('group');
    expect(tm.total.value).toBe(412);
  });

  it('clearing the group drops the round with it', async () => {
    const tm = await loaded();
    await tm.setGroup('HD · A');
    apiRequest.mockClear();

    await tm.setGroup(null);

    expect(calls('/matches').map(query)).toEqual([
      { age_group_id: '5', limit: String(TOURNAMENT_PAGE_SIZE), offset: '0' },
    ]);
  });

  it('no request without a group carries a round', async () => {
    const tm = await loaded();
    await tm.loadMore();
    await tm.setAgeGroup(7);
    await tm.refresh();

    for (const u of calls('/matches')) {
      expect(u.searchParams.has('round')).toBe(false);
    }
  });

  it('later pages and refreshes of a group keep the round', async () => {
    serve({
      filters: u13Filters,
      pages: { '5|': range(1, 412), '5|HD · A': range(1, 250) },
    });
    const tm = useTournamentMatches();
    await tm.load(LARGE);
    await tm.setGroup('HD · A');
    apiRequest.mockClear();

    await tm.loadMore();
    await tm.refresh();

    const sent = calls('/matches').map(query);
    expect(sent.map(q => q.offset)).toEqual(['200', '0', '200']);
    for (const q of sent) {
      expect(q.group).toBe('HD · A');
      expect(q.round).toBe('group_stage');
    }
  });

  it('setAgeGroup clears the group and refetches both matches and filters', async () => {
    const tm = await loaded();
    await tm.setGroup('HD · A');
    apiRequest.mockClear();

    await tm.setAgeGroup(7);

    expect(tm.selectedGroup.value).toBe(null);
    expect(calls('/matches').map(query)).toEqual([
      { age_group_id: '7', limit: String(TOURNAMENT_PAGE_SIZE), offset: '0' },
    ]);
    expect(calls('/filters').map(query)).toEqual([
      { age_group_id: '7', on_date: localDateKey() },
    ]);
    expect(tm.tournament.value.matches).toHaveLength(14);
    // U15 is showcase-only here: measured none.
    expect(tm.groups.value).toEqual([]);
  });

  it('selecting the current age group again does nothing', async () => {
    const tm = await loaded();
    await tm.setAgeGroup(5);
    expect(apiRequest).not.toHaveBeenCalled();
  });

  it('a failed page after a filter change reports it and shows no stale rows', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const tm = await loaded();
    apiRequest.mockRejectedValue(new Error('offline'));

    await tm.setGroup('HD · A');

    expect(tm.pageError.value).toBeTruthy();
    expect(tm.tournament.value.matches).toEqual([]);
    expect(tm.total.value).toBe(null);
    expect(tm.pageLoading.value).toBe(false);
    console.error.mockRestore();
  });

  it('drops a slow answer for a filter the visitor has already left', async () => {
    const tm = await loaded();
    let releaseSlow;
    apiRequest.mockImplementation(url => {
      const q = query(parse(url));
      if (q.group === 'HD · A') {
        return new Promise(resolve => {
          releaseSlow = () =>
            resolve({ matches: range(1, 6), total: 6, limit: 200, offset: 0 });
        });
      }
      return Promise.resolve({
        matches: range(500, 5),
        total: 5,
        limit: 200,
        offset: 0,
      });
    });

    const slow = tm.setGroup('HD · A');
    await tm.setGroup('AD · A');
    releaseSlow();
    await slow;

    expect(tm.total.value).toBe(5);
    expect(tm.tournament.value.matches.map(m => m.id)).toEqual(
      range(500, 5).map(m => m.id)
    );
    expect(tm.pageLoading.value).toBe(false);
  });
});

describe('large tournament — paging', () => {
  async function loaded() {
    serve({ filters: u13Filters, pages: { '5|': range(1, 412) } });
    const tm = useTournamentMatches();
    await tm.load(LARGE);
    apiRequest.mockClear();
    return tm;
  }

  it('loadMore asks for the next offset and appends', async () => {
    const tm = await loaded();

    await tm.loadMore();

    expect(calls('/matches').map(query)).toEqual([
      { age_group_id: '5', limit: '200', offset: '200' },
    ]);
    expect(tm.tournament.value.matches).toHaveLength(400);
    expect(tm.hasMore.value).toBe(true);

    await tm.loadMore();
    expect(tm.tournament.value.matches).toHaveLength(412);
    expect(tm.hasMore.value).toBe(false);
    const ids = tm.tournament.value.matches.map(m => m.id);
    expect(new Set(ids).size).toBe(412);
  });

  it('loadMore past the end does nothing', async () => {
    const tm = await loaded();
    await tm.loadMore();
    await tm.loadMore();
    apiRequest.mockClear();
    await tm.loadMore();
    expect(apiRequest).not.toHaveBeenCalled();
  });

  it('a failed loadMore keeps the rows already loaded', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const tm = await loaded();
    apiRequest.mockRejectedValue(new Error('offline'));

    await tm.loadMore();

    expect(tm.tournament.value.matches).toHaveLength(200);
    expect(tm.pageError.value).toBeTruthy();
    expect(tm.loadingMore.value).toBe(false);
    console.error.mockRestore();
  });

  it('refresh refetches the pages already loaded, a page at a time', async () => {
    const tm = await loaded();
    await tm.loadMore();
    apiRequest.mockClear();

    await tm.refresh();

    expect(calls('/matches').map(u => u.searchParams.get('offset'))).toEqual([
      '0',
      '200',
    ]);
    expect(tm.tournament.value.matches).toHaveLength(400);
    expect(
      apiRequest.mock.calls.some(([url]) => /\/tournaments\/6$/.test(url))
    ).toBe(false);
  });
});

describe('large tournament — a filter change while "Load more" is in flight', () => {
  it('does not append the old filter’s rows', async () => {
    serve({
      filters: u13Filters,
      pages: { '5|': range(1, 412), '5|HD · A': range(1000, 6) },
    });
    const tm = useTournamentMatches();
    await tm.load(LARGE);

    // The next page of the unfiltered list hangs…
    const slowPage = deferred();
    apiRequest.mockImplementation(url => {
      const q = query(parse(url));
      if (q.offset === '200') return slowPage.promise;
      return Promise.resolve({
        matches: range(1000, 6),
        total: 6,
        limit: 200,
        offset: 0,
      });
    });
    const more = tm.loadMore();
    expect(tm.loadingMore.value).toBe(true);

    // …the visitor picks a group, and only then does it arrive.
    await tm.setGroup('HD · A');
    slowPage.resolve({
      matches: range(201, 200),
      total: 412,
      limit: 200,
      offset: 200,
    });
    await more;

    expect(tm.tournament.value.matches.map(m => m.id)).toEqual(
      range(1000, 6).map(m => m.id)
    );
    expect(tm.total.value).toBe(6);
    expect(tm.hasMore.value).toBe(false);
    expect(tm.loadingMore.value).toBe(false);
    expect(tm.pageError.value).toBe(null);
  });

  it('does not report the old filter’s failure either', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    serve({ filters: u13Filters, pages: { '5|': range(1, 412) } });
    const tm = useTournamentMatches();
    await tm.load(LARGE);

    const slowPage = deferred();
    apiRequest.mockImplementation(url =>
      query(parse(url)).offset === '200'
        ? slowPage.promise
        : Promise.resolve({
            matches: range(1000, 6),
            total: 6,
            limit: 200,
            offset: 0,
          })
    );
    const more = tm.loadMore();
    await tm.setGroup('HD · A');
    slowPage.reject(new Error('offline'));
    await more;

    expect(tm.pageError.value).toBe(null);
    expect(tm.tournament.value.matches).toHaveLength(6);
    console.error.mockRestore();
  });
});

describe('refresh never puts the previous tournament back', () => {
  const SMALL_B = { id: 4, name: 'Copa', match_count: 40 };
  const detailA = { ...SMALL, matches: range(1, 3) };
  const detailB = { ...SMALL_B, matches: range(100, 2) };
  const detailId = url => {
    const m = /\/api\/tournaments\/(\d+)$/.exec(parse(url).pathname);
    return m ? Number(m[1]) : null;
  };

  it('small → small: a refresh during the load of B does not bring A back', async () => {
    serve({ detail: detailA });
    const tm = useTournamentMatches();
    await tm.load(SMALL);

    // The visitor taps B; while it loads, the tab is hidden and shown.
    const loadB = deferred();
    const refreshA = deferred();
    apiRequest.mockReset();
    apiRequest.mockImplementation(url =>
      detailId(url) === 4 ? loadB.promise : refreshA.promise
    );
    const load = tm.load(SMALL_B);
    const refresh = tm.refresh();

    loadB.resolve(detailB);
    await load;
    // A's answer arrives last.
    refreshA.resolve({ ...SMALL, matches: range(1, 9) });
    await refresh;
    await settle();

    expect(tm.tournament.value).toEqual(detailB);
    // It was never asked for: A is not the selected tournament any more.
    expect(apiRequest.mock.calls.map(([url]) => detailId(url))).toEqual([4]);

    // And what is refreshed from here on is B, not A.
    apiRequest.mockReset();
    apiRequest.mockResolvedValue({ ...SMALL_B, matches: range(100, 5) });
    await tm.refresh();
    expect(apiRequest.mock.calls.map(([url]) => detailId(url))).toEqual([4]);
    expect(tm.tournament.value.id).toBe(4);
    expect(tm.tournament.value.matches).toHaveLength(5);
  });

  it('small → small: a refresh already in flight when B is tapped is dropped', async () => {
    serve({ detail: detailA });
    const tm = useTournamentMatches();
    await tm.load(SMALL);

    const loadB = deferred();
    const refreshA = deferred();
    apiRequest.mockImplementation(url =>
      detailId(url) === 4 ? loadB.promise : refreshA.promise
    );
    const refresh = tm.refresh();
    const load = tm.load(SMALL_B);
    loadB.resolve(detailB);
    await load;
    refreshA.resolve({ ...SMALL, matches: range(1, 9) });
    await refresh;

    expect(tm.tournament.value).toEqual(detailB);
  });

  it('large → small: a refresh during the load of B does not write A’s page into B', async () => {
    serve({ filters: u13Filters, pages: { '5|': range(1, 412) } });
    const tm = useTournamentMatches();
    await tm.load(LARGE);

    const loadB = deferred();
    const pageA = deferred();
    apiRequest.mockReset();
    apiRequest.mockImplementation(url => {
      if (detailId(url) === 4) return loadB.promise;
      if (parse(url).pathname.endsWith('/matches')) return pageA.promise;
      return Promise.resolve(FILTERS_ALL);
    });
    const load = tm.load(SMALL_B);
    const refresh = tm.refresh();

    loadB.resolve(detailB);
    await load;
    pageA.resolve({
      matches: range(1, 200),
      total: 412,
      limit: 200,
      offset: 0,
    });
    await refresh;
    await settle();

    expect(tm.tournament.value).toEqual(detailB);
    expect(tm.isLarge.value).toBe(false);
    expect(tm.total.value).toBe(null);
    expect(calls('/matches')).toHaveLength(0);
    expect(calls('/filters')).toHaveLength(0);
  });

  it('large → small: a page refresh already in flight when B is tapped is dropped', async () => {
    serve({ filters: u13Filters, pages: { '5|': range(1, 412) } });
    const tm = useTournamentMatches();
    await tm.load(LARGE);

    const loadB = deferred();
    const pageA = deferred();
    apiRequest.mockReset();
    apiRequest.mockImplementation(url => {
      if (detailId(url) === 4) return loadB.promise;
      if (parse(url).pathname.endsWith('/matches')) return pageA.promise;
      return Promise.resolve(FILTERS_ALL);
    });
    const refresh = tm.refresh();
    const load = tm.load(SMALL_B);
    loadB.resolve(detailB);
    await load;
    pageA.resolve({
      matches: range(1, 200),
      total: 412,
      limit: 200,
      offset: 0,
    });
    await refresh;
    await settle();

    expect(tm.tournament.value).toEqual(detailB);
    expect(tm.total.value).toBe(null);
    // The dropped refresh did not go on to refetch A's filters.
    expect(calls('/filters')).toHaveLength(0);
  });

  it('does nothing when the tournament asked for last never loaded', async () => {
    serve({ detail: detailA });
    const tm = useTournamentMatches();
    await tm.load(SMALL);

    apiRequest.mockReset();
    apiRequest.mockRejectedValue(new Error('offline'));
    await expect(tm.load(SMALL_B)).rejects.toThrow('offline');
    apiRequest.mockReset();
    apiRequest.mockResolvedValue({ ...SMALL, matches: range(1, 9) });

    await tm.refresh();

    // A is still what is on screen, but it is not what was selected.
    expect(apiRequest).not.toHaveBeenCalled();
    expect(tm.tournament.value).toEqual(detailA);
  });
});

describe('large tournament — a refresh whose filters request fails', () => {
  const pages = { '5|': range(1, 412), '5|HD · A': range(1, 6) };

  async function onGroup() {
    serve({ filters: u13Filters, pages });
    const tm = useTournamentMatches();
    await tm.load(LARGE);
    await tm.setGroup('HD · A');
    return tm;
  }

  it('keeps the Group control while a group is still applied', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const tm = await onGroup();

    serve({ filters: new Error('boom'), pages });
    await tm.refresh();
    await settle();

    // Still narrowed to the group, and the control that clears it is still
    // there with the groups it had.
    expect(tm.selectedGroup.value).toBe('HD · A');
    expect(tm.tournament.value.matches).toHaveLength(6);
    expect(tm.groups.value).toEqual(GROUPS_U13);
    expect(tm.ageGroups.value).toEqual(FILTERS_ALL.age_groups);
    console.error.mockRestore();
  });

  it('keeps it when the server answers but could not count', async () => {
    const tm = await onGroup();

    serve({
      filters: {
        facets_available: false,
        age_groups: [
          { id: 5, name: 'U13', matches: null, matches_on_date: null },
          { id: 7, name: 'U15', matches: null, matches_on_date: null },
        ],
        groups: null,
      },
      pages,
    });
    await tm.refresh();
    await settle();

    expect(tm.selectedGroup.value).toBe('HD · A');
    expect(tm.groups.value).toEqual(GROUPS_U13);
  });

  it('a refresh that does answer replaces the groups', async () => {
    const tm = await onGroup();
    const fresh = [{ key: 'HD · A', division: 'HD', label: 'A', matches: 7 }];

    serve({ filters: { ...FILTERS_ALL, groups: fresh }, pages });
    await tm.refresh();
    await settle();

    expect(tm.groups.value).toEqual(fresh);
  });

  it('an age-group change still clears the group, and failed filters leave none', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const tm = await onGroup();

    serve({ filters: new Error('boom'), pages: { '7|': range(1000, 14) } });
    await tm.setAgeGroup(7);

    // The old age's groups are not carried over: unknown, and nothing is
    // selected, so nothing is stranded.
    expect(tm.selectedGroup.value).toBe(null);
    expect(tm.groups.value).toBe(null);
    expect(tm.tournament.value.matches).toHaveLength(14);
    console.error.mockRestore();
  });

  it('unknown groups on first load leave no group selected', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    serve({ filters: new Error('boom'), pages });
    const tm = useTournamentMatches();
    await tm.load(LARGE);

    expect(tm.groups.value).toBe(null);
    expect(tm.selectedGroup.value).toBe(null);
    console.error.mockRestore();
  });
});
