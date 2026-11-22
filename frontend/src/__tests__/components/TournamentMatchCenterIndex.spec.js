/**
 * TournamentMatchCenter.vue — the season index and the URL per tournament
 * (SB-1767).
 *
 * The tab opens on an index of the season's tournaments; a card opens one at
 * `/tournaments/<id>`; that URL opens it directly, from any season; back
 * returns to the index. A season with one tournament opens it.
 *
 * window.location is a plain object in this suite (see setup.js), so history
 * is faked: push / replace / back update `window.location.pathname` the way a
 * browser would, and back dispatches `popstate`.
 *
 * Fixtures are scraped tournaments with no user data.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';

const apiRequest = vi.fn();
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ apiRequest, isAuthenticated: { value: false } }),
}));

import TournamentMatchCenter from '@/components/TournamentMatchCenter.vue';
import { localDateKey } from '@/utils/tournamentStatus';

const day = offset => {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return localDateKey(d);
};

const SEASONS = [
  {
    id: 4,
    name: '2026-2027',
    start_date: '2026-08-01',
    end_date: '2027-07-31',
    is_current: true,
  },
  {
    id: 3,
    name: '2025-2026',
    start_date: '2025-08-01',
    end_date: '2026-07-31',
  },
  {
    id: 2,
    name: '2024-2025',
    start_date: '2024-08-01',
    end_date: '2025-07-31',
  },
];

const U13 = { id: 5, name: 'U13' };

const DONE = {
  id: 13,
  season_id: 4,
  name: 'Fall Festival',
  start_date: day(-30),
  end_date: day(-28),
  location: 'Richmond, VA',
  logo_url: null,
  match_count: 12,
  age_groups: [U13],
};
const LIVE = {
  id: 11,
  season_id: 4,
  name: 'Thanksgiving Cup',
  start_date: day(-1),
  end_date: day(1),
  location: 'Bradenton, FL',
  logo_url: 'https://example.test/cup.png',
  match_count: 40,
  age_groups: [U13],
};
const LATER = {
  id: 12,
  season_id: 4,
  name: 'Winter Showcase',
  start_date: day(20),
  end_date: day(21),
  location: null,
  logo_url: null,
  match_count: null,
  age_groups: [U13],
};
// Last season, and large: past the scale switch, so it is paged.
const FEST = {
  id: 21,
  season_id: 3,
  name: 'MLS NEXT Fest',
  start_date: '2025-12-04',
  end_date: '2025-12-08',
  location: 'Sarasota, FL',
  logo_url: null,
  match_count: 2400,
  age_groups: [U13],
};
const SOLO = {
  id: 31,
  season_id: 2,
  name: 'Only Cup',
  start_date: '2024-10-04',
  end_date: '2024-10-06',
  location: null,
  logo_url: null,
  match_count: 3,
  age_groups: [U13],
};

const ALL = [DONE, LIVE, LATER, FEST, SOLO];

const mkMatch = id => ({
  id,
  match_date: '2025-12-04',
  scheduled_kickoff: null,
  match_status: 'scheduled',
  home_score: null,
  away_score: null,
  tournament_group: null,
  tournament_round: null,
  age_group: U13,
  home_team: { id: id * 2, name: `Home ${id}` },
  away_team: { id: id * 2 + 1, name: `Away ${id}` },
  home_team_club: null,
  away_team_club: null,
});

const parse = url => new URL(url, 'http://test.example');

function mockApi(tournaments = ALL) {
  apiRequest.mockReset();
  apiRequest.mockImplementation(url => {
    const u = parse(url);
    const path = u.pathname;
    if (path.endsWith('/api/seasons')) return Promise.resolve(SEASONS);
    if (path.endsWith('/motd')) return Promise.resolve({ picks: [] });
    if (path.endsWith('/filters')) {
      return Promise.resolve({
        facets_available: true,
        age_groups: [{ id: 5, name: 'U13', matches: 2400, matches_on_date: 0 }],
        groups: [],
      });
    }
    if (path.endsWith('/matches')) {
      return Promise.resolve({
        matches: [mkMatch(1), mkMatch(2)],
        total: 2400,
        limit: 200,
        offset: 0,
      });
    }
    if (path.endsWith('/api/tournaments')) {
      const season = u.searchParams.get('season_id');
      return Promise.resolve(
        season == null
          ? tournaments
          : tournaments.filter(t => String(t.season_id) === season)
      );
    }
    const id = Number(path.split('/').pop());
    const t = tournaments.find(x => x.id === id);
    return t
      ? Promise.resolve({ ...t, matches: [mkMatch(id * 10)] })
      : Promise.reject(Object.assign(new Error('Not found'), { status: 404 }));
  });
}

// A browser's session history, enough of it for push / replace / back.
function fakeHistory(start) {
  const entries = [start];
  let index = 0;
  const sync = () => {
    window.location.pathname = entries[index];
  };
  sync();
  const push = vi
    .spyOn(window.history, 'pushState')
    .mockImplementation((_s, _t, url) => {
      entries.splice(index + 1);
      entries.push(url);
      index += 1;
      sync();
    });
  const replace = vi
    .spyOn(window.history, 'replaceState')
    .mockImplementation((_s, _t, url) => {
      entries[index] = url;
      sync();
    });
  const go = delta => {
    index = Math.max(0, Math.min(entries.length - 1, index + delta));
    sync();
    window.dispatchEvent(new PopStateEvent('popstate', { state: null }));
  };
  const back = vi
    .spyOn(window.history, 'back')
    .mockImplementation(() => go(-1));
  return {
    push,
    replace,
    back,
    forward: () => go(1),
    entries: () => entries.slice(),
    path: () => entries[index],
  };
}

let wrapper = null;
let history = null;

async function mountAt(path, tournaments = ALL) {
  mockApi(tournaments);
  history = fakeHistory(path);
  wrapper = mount(TournamentMatchCenter, {
    global: { stubs: { MatchDetailView: true } },
  });
  await flushPromises();
  return wrapper;
}

const cardIds = w =>
  w
    .findAll('[data-testid="tournament-card"]')
    .map(c => Number(c.attributes('data-id')));
const heroName = w => w.find('[data-testid="tournament-hero"] h2');
const listCalls = () =>
  apiRequest.mock.calls
    .map(([url]) => parse(url))
    .filter(u => u.pathname.endsWith('/api/tournaments'));
const detailCalls = id =>
  apiRequest.mock.calls.filter(
    ([url]) => parse(url).pathname === `/api/tournaments/${id}`
  );
const tournamentRequests = () =>
  apiRequest.mock.calls.filter(([url]) => url.includes('/api/tournaments'));

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  if (wrapper) wrapper.unmount();
  wrapper = null;
  vi.restoreAllMocks();
  delete window.location.pathname;
  window.history.replaceState(null, '', '/');
});

describe('the season index', () => {
  it('opens on one card per tournament, in status order, with no detail call', async () => {
    const w = await mountAt('/');

    expect(cardIds(w)).toEqual([11, 12, 13]);
    expect(w.find('[data-testid="tournament-hero"]').exists()).toBe(false);
    expect(
      tournamentRequests().filter(
        ([url]) => parse(url).pathname !== '/api/tournaments'
      )
    ).toHaveLength(0);
    // Entered from the tab bar: the address bar says where we are.
    expect(history.path()).toBe('/tournaments');
    expect(history.push).not.toHaveBeenCalled();
  });

  it('keeps the season selector', async () => {
    const w = await mountAt('/tournaments');
    expect(w.find('[data-testid="tournament-season-select"]').exists()).toBe(
      true
    );
    expect(w.vm.selectedSeasonId).toBe(4);
  });

  it('fetches the list once on mount', async () => {
    await mountAt('/tournaments');
    expect(listCalls()).toHaveLength(1);
    expect(listCalls()[0].searchParams.get('season_id')).toBe('4');
  });

  it('a card pushes /tournaments/<id> and opens that tournament', async () => {
    const w = await mountAt('/tournaments');

    await w
      .find('[data-testid="tournament-card"][data-id="12"]')
      .trigger('click');
    await flushPromises();

    expect(history.push).toHaveBeenCalledWith(null, '', '/tournaments/12');
    expect(history.path()).toBe('/tournaments/12');
    expect(heroName(w).text()).toBe('Winter Showcase');
    expect(detailCalls(12)).toHaveLength(1);
    expect(w.find('[data-testid="tournament-index"]').exists()).toBe(false);
  });

  it('the switcher moves between the season’s tournaments', async () => {
    const w = await mountAt('/tournaments/11');

    const switcher = w.find('[data-testid="tournament-switcher"]');
    expect(switcher.exists()).toBe(true);
    const chip = switcher
      .findAll('button')
      .find(b => b.text() === 'Fall Festival');
    await chip.trigger('click');
    await flushPromises();

    expect(history.path()).toBe('/tournaments/13');
    expect(heroName(w).text()).toBe('Fall Festival');
  });

  it('shows the existing empty state for a season with no tournaments', async () => {
    const w = await mountAt('/tournaments', [FEST]);
    // Season 4 has nothing in this world.
    expect(w.text()).toContain('No tournaments this season');
    expect(cardIds(w)).toEqual([]);
    expect(w.find('[data-testid="tournament-season-select"]').exists()).toBe(
      true
    );
  });

  it('changing the season resets the URL and applies the one-tournament rule', async () => {
    const w = await mountAt('/tournaments/11');
    expect(heroName(w).text()).toBe('Thanksgiving Cup');

    await w.find('[data-testid="tournament-season-select"]').setValue('3');
    await flushPromises();

    expect(history.path()).toBe('/tournaments/21');
    expect(heroName(w).text()).toBe('MLS NEXT Fest');
  });
});

describe('a link to one tournament', () => {
  it('opens it directly, without pushing history', async () => {
    const w = await mountAt('/tournaments/13');

    expect(heroName(w).text()).toBe('Fall Festival');
    expect(history.entries()).toEqual(['/tournaments/13']);
    expect(history.push).not.toHaveBeenCalled();
    expect(w.find('[data-testid="tournament-back-to-index"]').exists()).toBe(
      true
    );
  });

  it('opens a tournament from another season, and switches the season', async () => {
    const w = await mountAt('/tournaments/21');

    expect(w.vm.selectedSeasonId).toBe(3);
    expect(
      w.find('[data-testid="tournament-season-select"]').element.value
    ).toBe('3');
    expect(heroName(w).text()).toBe('MLS NEXT Fest');
    // The row came from the list, so the large tournament still pages: no
    // detail call, the paged endpoint instead.
    expect(w.vm.isLargeTournament).toBe(true);
    expect(detailCalls(21)).toHaveLength(0);
    expect(
      apiRequest.mock.calls.some(([url]) =>
        parse(url).pathname.endsWith('/api/tournaments/21/matches')
      )
    ).toBe(true);
    // One season-scoped list, one unfiltered lookup — the season change did
    // not fetch a third time.
    expect(listCalls().map(u => u.searchParams.get('season_id'))).toEqual([
      '4',
      null,
    ]);
    expect(history.path()).toBe('/tournaments/21');
  });

  it('shows the index and a notice for an unknown id, at /tournaments', async () => {
    const w = await mountAt('/tournaments/999');

    expect(cardIds(w)).toEqual([11, 12, 13]);
    expect(w.find('[data-testid="tournament-index-notice"]').text()).toBe(
      "That tournament isn't available."
    );
    expect(history.path()).toBe('/tournaments');
    // Never the detail endpoint for an id the lists do not have.
    expect(detailCalls(999)).toHaveLength(0);
  });

  it('the notice also shows in an empty season', async () => {
    const w = await mountAt('/tournaments/999', [FEST]);
    expect(w.text()).toContain('No tournaments this season');
    expect(w.find('[data-testid="tournament-index-notice"]').text()).toBe(
      "That tournament isn't available."
    );
  });

  it('never touches the page title', async () => {
    document.title = 'Missing Table';
    const w = await mountAt('/tournaments/11');
    expect(heroName(w).text()).toBe('Thanksgiving Cup');
    await w
      .find('[data-testid="tournament-switcher"] button:last-child')
      .trigger('click');
    await flushPromises();
    expect(document.title).toBe('Missing Table');
  });
});

describe('back to the index', () => {
  it('"All tournaments" after a card is history.back(), and forward reopens it', async () => {
    const w = await mountAt('/tournaments');
    await w
      .find('[data-testid="tournament-card"][data-id="13"]')
      .trigger('click');
    await flushPromises();

    await w.find('[data-testid="tournament-back-to-index"]').trigger('click');
    await flushPromises();

    expect(history.back).toHaveBeenCalledTimes(1);
    expect(history.path()).toBe('/tournaments');
    expect(cardIds(w)).toEqual([11, 12, 13]);

    history.forward();
    await flushPromises();
    expect(heroName(w).text()).toBe('Fall Festival');
  });

  it('"All tournaments" after a direct link pushes /tournaments', async () => {
    const w = await mountAt('/tournaments/11');

    await w.find('[data-testid="tournament-back-to-index"]').trigger('click');
    await flushPromises();

    expect(history.back).not.toHaveBeenCalled();
    expect(history.entries()).toEqual(['/tournaments/11', '/tournaments']);
    expect(cardIds(w)).toEqual([11, 12, 13]);
  });

  it('a popstate to /tournaments shows the index', async () => {
    const w = await mountAt('/tournaments/12');
    expect(heroName(w).text()).toBe('Winter Showcase');

    window.location.pathname = '/tournaments';
    window.dispatchEvent(new PopStateEvent('popstate', { state: null }));
    await flushPromises();

    expect(cardIds(w)).toEqual([11, 12, 13]);
    expect(w.vm.selectedId).toBe(null);
    expect(w.vm.viewMode).toBe('list');
  });

  it('a popstate outside the tab is left to App', async () => {
    const w = await mountAt('/tournaments/12');
    window.location.pathname = '/';
    window.dispatchEvent(new PopStateEvent('popstate', { state: null }));
    await flushPromises();
    expect(heroName(w).text()).toBe('Winter Showcase');
  });
});

describe('a season with one tournament', () => {
  it('opens it directly, replacing the URL', async () => {
    const w = await mountAt('/tournaments', [SOLO]);
    // Season 4 is empty here; pick the one-tournament season.
    await w.find('[data-testid="tournament-season-select"]').setValue('2');
    await flushPromises();

    expect(heroName(w).text()).toBe('Only Cup');
    expect(history.path()).toBe('/tournaments/31');
    expect(history.push).not.toHaveBeenCalled();
    // One tournament: no switcher, but still a way to the index.
    expect(w.find('[data-testid="tournament-switcher"]').exists()).toBe(false);
    expect(w.find('[data-testid="tournament-back-to-index"]').exists()).toBe(
      true
    );
  });

  it('"All tournaments" shows its one card and does not reopen it', async () => {
    const one = [{ ...LIVE }];
    const w = await mountAt('/tournaments', one);
    expect(heroName(w).text()).toBe('Thanksgiving Cup');
    expect(history.path()).toBe('/tournaments/11');

    await w.find('[data-testid="tournament-back-to-index"]').trigger('click');
    await flushPromises();

    expect(cardIds(w)).toEqual([11]);
    expect(history.path()).toBe('/tournaments');
    expect(w.find('[data-testid="tournament-hero"]').exists()).toBe(false);
  });
});

describe('leaving the tab', () => {
  it('resets the URL so a reload elsewhere does not reopen a tournament', async () => {
    await mountAt('/tournaments/11');
    wrapper.unmount();
    wrapper = null;
    expect(history.path()).toBe('/');
  });

  it('leaves a path outside the tab alone', async () => {
    await mountAt('/tournaments/11');
    window.location.pathname = '/chat';
    wrapper.unmount();
    wrapper = null;
    expect(window.location.pathname).toBe('/chat');
  });
});

// ── Late answers (review of SB-1767) ──
// Work that resolves after the visitor has moved on — another tab, signed
// out, a different history entry — must not write the address bar, fetch, or
// change what is on screen.

// Every list request waits until released; everything else answers from ALL.
function deferLists() {
  const pending = [];
  apiRequest.mockReset();
  apiRequest.mockImplementation(url => {
    const u = parse(url);
    const path = u.pathname;
    if (path.endsWith('/api/seasons')) return Promise.resolve(SEASONS);
    if (path.endsWith('/motd')) return Promise.resolve({ picks: [] });
    if (path.endsWith('/api/tournaments')) {
      return new Promise(resolve => {
        pending.push({ season: u.searchParams.get('season_id'), resolve });
      });
    }
    const id = Number(path.split('/').pop());
    const t = ALL.find(x => x.id === id);
    return Promise.resolve({ ...t, matches: [] });
  });
  // Answer the oldest waiting list request for `season` (null = unfiltered).
  const release = (season, rows) => {
    const i = pending.findIndex(p => p.season === season);
    pending.splice(i, 1)[0].resolve(rows);
  };
  return { release, waiting: () => pending.map(p => p.season) };
}

const mountDeferred = async path => {
  const lists = deferLists();
  history = fakeHistory(path);
  wrapper = mount(TournamentMatchCenter, {
    global: { stubs: { MatchDetailView: true } },
  });
  await flushPromises();
  return lists;
};

const callsSince = n => apiRequest.mock.calls.slice(n).map(([url]) => url);

describe('late answers', () => {
  it('a list that arrives after the tab is left writes nothing and fetches nothing', async () => {
    const lists = await mountDeferred('/');
    expect(history.path()).toBe('/tournaments');
    expect(lists.waiting()).toEqual(['4']);

    // Tournaments, then Table, before the list arrives.
    wrapper.unmount();
    wrapper = null;
    expect(history.path()).toBe('/');
    const before = apiRequest.mock.calls.length;

    // A one-tournament season: the live code path would open it.
    lists.release('4', [LIVE]);
    await flushPromises();

    expect(history.path()).toBe('/');
    expect(history.replace).not.toHaveBeenCalledWith(
      null,
      '',
      '/tournaments/11'
    );
    expect(callsSince(before)).toEqual([]);
  });

  it('signing out mid-load sends no request once the session is gone', async () => {
    // Session gone = the tab content unmounts (App hides it behind the
    // session). A link into another season is the longest chain of awaits.
    const lists = await mountDeferred('/tournaments/21');
    lists.release('4', [LIVE, LATER]);
    await flushPromises();
    expect(lists.waiting()).toEqual([null]);

    wrapper.unmount();
    wrapper = null;
    const before = apiRequest.mock.calls.length;

    lists.release(null, ALL);
    await flushPromises();

    expect(callsSince(before)).toEqual([]);
    expect(history.path()).toBe('/');
  });

  it('back to the index while a link lookup is in flight keeps the index', async () => {
    const lists = await mountDeferred('/tournaments');
    lists.release('4', [LIVE, LATER, DONE]);
    await flushPromises();
    expect(cardIds(wrapper)).toEqual([11, 12, 13]);

    // Forward to another season's tournament: the unfiltered lookup starts.
    window.history.pushState(null, '', '/tournaments/21');
    window.dispatchEvent(new PopStateEvent('popstate', { state: null }));
    await flushPromises();
    expect(lists.waiting()).toEqual(['4']);
    lists.release('4', [LIVE, LATER, DONE]);
    await flushPromises();
    expect(lists.waiting()).toEqual([null]);

    // Back to the index before it answers.
    history.back();
    await flushPromises();
    expect(history.path()).toBe('/tournaments');

    lists.release(null, ALL);
    await flushPromises();

    expect(history.path()).toBe('/tournaments');
    expect(wrapper.vm.selectedId).toBe(null);
    expect(wrapper.vm.selectedSeasonId).toBe(4);
    expect(cardIds(wrapper)).toEqual([11, 12, 13]);
    expect(detailCalls(21)).toHaveLength(0);
  });
});

describe('a season change into a one-tournament season', () => {
  it('"All tournaments" then pushes /tournaments rather than going back', async () => {
    const w = await mountAt('/tournaments', [LIVE, LATER, SOLO]);
    await w
      .find('[data-testid="tournament-card"][data-id="12"]')
      .trigger('click');
    await flushPromises();

    await w.find('[data-testid="tournament-season-select"]').setValue('2');
    await flushPromises();
    expect(heroName(w).text()).toBe('Only Cup');
    expect(history.path()).toBe('/tournaments/31');

    await w.find('[data-testid="tournament-back-to-index"]').trigger('click');
    await flushPromises();

    expect(history.back).not.toHaveBeenCalled();
    expect(history.path()).toBe('/tournaments');
    expect(cardIds(w)).toEqual([31]);
  });
});
