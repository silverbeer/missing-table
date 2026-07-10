/**
 * TournamentMatchCenter.vue Tests (list-view polish — SB-73)
 *
 * Covers the three list-view UX rules:
 *  - chronological sort of group/knockout/untagged sections by
 *    `match_date` then `scheduled_kickoff`
 *  - team-club logos render in each row when `home_team_club.logo_url`
 *    / `away_team_club.logo_url` are present, and silently absent when not
 *  - age-group chip is hidden when the tournament has a single age group
 *    (it duplicates the tournament header), but visible when multiple
 *
 * The component fetches tournaments on mount via `authStore.apiRequest`;
 * we stub the auth store so the mount stays deterministic and offline.
 */

import { describe, it, expect, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';

// Stub the auth store BEFORE importing the component so the import sees the mock.
// isAuthenticated is a ref-like ({ value }) — the bracket-follow composable and
// the component both read `authStore.isAuthenticated.value`. Unauthenticated
// keeps the bracket-follow fetch a no-op and hides the follow toggle.
const apiRequest = vi.fn();
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ apiRequest, isAuthenticated: { value: false } }),
}));

import TournamentMatchCenter from '@/components/TournamentMatchCenter.vue';

const team = (id, name, logoUrl = null) => ({
  id,
  name,
  // The match payload carries the team's club as a flat sibling field, mirroring
  // the shape returned by the tournament endpoint after the SB-73 backend
  // change (and matching /api/matches).
  __club: logoUrl
    ? { id: id * 100, name: `${name} Club`, logo_url: logoUrl }
    : null,
});

// Build one match row with optional kickoff + clubs. The two club refs are
// flattened to home_team_club / away_team_club to match the backend shape.
const mkMatch = (id, home, away, opts = {}) => ({
  id,
  match_date: opts.date || '2026-06-05',
  scheduled_kickoff: opts.kickoff || null,
  match_status: opts.status || 'scheduled',
  home_score: opts.home_score ?? null,
  away_score: opts.away_score ?? null,
  home_penalty_score: null,
  away_penalty_score: null,
  tournament_group: opts.group || 'A',
  tournament_round: opts.round || 'group_stage',
  tournament_round_order: opts.order ?? null,
  age_group: opts.age_group || { id: 2, name: 'U14' },
  home_team: { id: home.id, name: home.name },
  away_team: { id: away.id, name: away.name },
  home_team_club: home.__club,
  away_team_club: away.__club,
});

// Seasons for the season selector. The component fetches these on mount and
// defaults to the newest, so the tournament fetch is season-scoped.
const SEASONS = [
  {
    id: 3,
    name: '2025-2026',
    start_date: '2025-09-01',
    end_date: '2026-06-30',
  },
  {
    id: 4,
    name: '2026-2027',
    start_date: '2026-09-01',
    end_date: '2027-06-30',
  },
];

// Mount with a pre-staged tournament + matches. Resolve apiRequest by URL
// (order-independent): `/api/seasons`, the `/api/tournaments` list, and the
// `/api/tournaments/{id}` detail — so the component renders against real data,
// not loading state.
async function mountWith(tournament) {
  apiRequest.mockReset();
  apiRequest.mockImplementation(url => {
    if (url.includes('/api/seasons')) return Promise.resolve(SEASONS);
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

const IFA = team(19, 'IFA');
const BWG = team(13, 'Blau Weiss Gottschee');
const OAK = team(24, 'Oakwood SC', 'https://cdn.example/oakwood.png');
const BOLTS = team(17, 'Boston Bolts', 'https://cdn.example/bolts.png');

describe('TournamentMatchCenter — list polish (SB-73)', () => {
  it('sorts group-stage matches by date then kickoff', async () => {
    // Deliberately out of order in the input.
    const matches = [
      mkMatch(102, IFA, BWG, {
        date: '2026-06-06',
        kickoff: '2026-06-06T12:00:00Z',
      }),
      mkMatch(100, OAK, BOLTS, {
        date: '2026-06-05',
        kickoff: '2026-06-05T19:00:00Z',
      }),
      mkMatch(101, IFA, OAK, {
        date: '2026-06-05',
        kickoff: '2026-06-05T14:30:00Z',
      }),
    ];
    const tournament = {
      id: 6,
      name: 'NAC',
      start_date: '2026-06-05',
      end_date: '2026-06-07',
      matches,
      age_groups: [{ id: 2, name: 'U14' }],
    };
    const wrapper = await mountWith(tournament);

    // Pull the rendered text of each group-stage row in order; the earliest
    // kickoff should come first (IFA vs Oakwood at 14:30 on 06-05).
    const rows = wrapper.findAll(
      '[data-testid="group-stage-match"], .cursor-pointer'
    );
    const text = rows.map(r => r.text()).join('\n');
    const ifaOakIdx = text.indexOf('Oakwood');
    const ifaBwgIdx = text.indexOf('Blau Weiss Gottschee');
    const oakBoltsIdx = text.indexOf('Boston Bolts');
    // 06-05 14:30 (IFA vs Oakwood) renders before 06-05 19:00 (Oakwood vs Bolts)
    // which renders before 06-06 12:00 (IFA vs BWG).
    expect(ifaOakIdx).toBeGreaterThan(-1);
    expect(oakBoltsIdx).toBeGreaterThan(ifaOakIdx);
    expect(ifaBwgIdx).toBeGreaterThan(oakBoltsIdx);
  });

  it('renders team-club logos when logo_url is present', async () => {
    const tournament = {
      id: 6,
      name: 'NAC',
      start_date: '2026-06-05',
      matches: [mkMatch(1, OAK, BOLTS, { kickoff: '2026-06-05T14:30:00Z' })],
      age_groups: [{ id: 2, name: 'U14' }],
    };
    const wrapper = await mountWith(tournament);

    const imgs = wrapper.findAll('img');
    const srcs = imgs.map(i => i.attributes('src'));
    expect(srcs).toContain('https://cdn.example/oakwood.png');
    expect(srcs).toContain('https://cdn.example/bolts.png');
  });

  it('omits the logo img when a team has no club logo_url', async () => {
    const tournament = {
      id: 6,
      name: 'NAC',
      start_date: '2026-06-05',
      // Both teams have null clubs — no team logos in this row.
      matches: [mkMatch(1, IFA, BWG)],
      age_groups: [{ id: 2, name: 'U14' }],
    };
    const wrapper = await mountWith(tournament);

    const srcs = wrapper.findAll('img').map(i => i.attributes('src'));
    // No team-club URLs (only tournament-header logo, if any, would appear).
    expect(srcs.every(s => !s?.includes('cdn.example'))).toBe(true);
  });

  it('hides the age-group chip when the tournament has only one age group', async () => {
    const tournament = {
      id: 6,
      name: 'NAC',
      start_date: '2026-06-05',
      matches: [mkMatch(1, IFA, BWG, { age_group: { id: 2, name: 'U14' } })],
      age_groups: [{ id: 2, name: 'U14' }],
    };
    const wrapper = await mountWith(tournament);

    // The U14 chip would appear twice per row (mobile + desktop) if rendered.
    // The tournament header still renders the U14 badge, so we look for the
    // chip styled with bg-indigo-100 (the per-row variant).
    const chips = wrapper.findAll('.bg-indigo-100');
    expect(chips.length).toBe(0);
  });

  it('shows the age-group chip when matches span multiple age groups', async () => {
    const tournament = {
      id: 4,
      name: 'MLS NEXT Cup',
      start_date: '2026-05-23',
      matches: [
        mkMatch(1, IFA, BWG, { age_group: { id: 1, name: 'U13' } }),
        mkMatch(2, OAK, BOLTS, { age_group: { id: 2, name: 'U14' } }),
      ],
      age_groups: [
        { id: 1, name: 'U13' },
        { id: 2, name: 'U14' },
      ],
    };
    const wrapper = await mountWith(tournament);

    // At least one bg-indigo-100 chip should render now that there are 2 ages.
    expect(wrapper.findAll('.bg-indigo-100').length).toBeGreaterThan(0);
  });
});
