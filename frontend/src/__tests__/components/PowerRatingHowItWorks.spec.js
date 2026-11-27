/**
 * How the Power Rating works (SB-1811).
 *
 * What these guard: the screen opens from the panel header and closes from
 * ✕, the backdrop and Escape; the safeguarding line about the margin cap is
 * there; the worked example's +13 and −21 are what the formula gives, not
 * typed-in numbers; and the copy says matches, never games, and never
 * presents itself as an official MLS NEXT ranking.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import {
  HOME_EDGE,
  K,
  expectedScore,
  marginFactor,
  ratingChange,
} from '@/utils/powerRatingModel';

const apiRequest = vi.fn();
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    apiRequest,
    isAuthenticated: { value: false },
    state: {},
  }),
}));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

import PowerRatingHowItWorks from '@/components/ranking/PowerRatingHowItWorks.vue';
import PowerRatingPanel from '@/components/ranking/PowerRatingPanel.vue';

const RANKINGS = {
  league: 'Homegrown',
  age_group: 'U17',
  season: '2026-2027',
  view: 'conference',
  conferences: ['Northeast'],
  run: { id: 1, computed_at: '2026-12-15T10:00:04Z' },
  movement_since: null,
  publication: { national: false, reason: 'not connected' },
  coverage: { teams_in_pool: 147, min_matches: 6, note: 'MT Power Rating' },
  tiers: [],
  teams: [
    {
      rank: null,
      team_id: 21,
      team: 'IFA U17',
      rating: 1600,
      mp: 10,
      w: 6,
      d: 2,
      l: 2,
      conference: 'Northeast',
      conference_rank: 1,
      badges: [],
    },
  ],
  unranked: [],
};

const stubs = { global: { stubs: { Teleport: true } } };
const mountScreen = (props = {}) =>
  mount(PowerRatingHowItWorks, { props, ...stubs });

describe('Power Rating model (SB-1811)', () => {
  it('gives the worked example from the formula: +13 for 2–0, −21 for 0–1', () => {
    const e = expectedScore(1600, 1500, HOME_EDGE);
    expect(e).toBeCloseTo(0.7034, 3);
    const win = ratingChange({
      rating: 1600,
      opponent: 1500,
      home: HOME_EDGE,
      goalsFor: 2,
      goalsAgainst: 0,
    });
    const loss = ratingChange({
      rating: 1600,
      opponent: 1500,
      home: HOME_EDGE,
      goalsFor: 0,
      goalsAgainst: 1,
    });
    expect(win).toBeCloseTo(K * 1.5 * (1 - e), 10);
    expect(Math.round(win)).toBe(13);
    expect(Math.round(loss)).toBe(-21);
  });

  it('caps the margin factor at 3 goals', () => {
    expect(marginFactor(0)).toBe(1);
    expect(marginFactor(1)).toBe(1);
    expect(marginFactor(-2)).toBe(1.5);
    expect(marginFactor(3)).toBe(1.75);
    expect(marginFactor(7)).toBe(1.75);
  });

  it('is equal and opposite at equal K, and a draw between equals moves nothing', () => {
    const a = ratingChange({
      rating: 1550,
      opponent: 1480,
      goalsFor: 1,
      goalsAgainst: 1,
    });
    const b = ratingChange({
      rating: 1480,
      opponent: 1550,
      goalsFor: 1,
      goalsAgainst: 1,
    });
    expect(a + b).toBeCloseTo(0, 10);
    expect(
      ratingChange({
        rating: 1500,
        opponent: 1500,
        goalsFor: 2,
        goalsAgainst: 2,
      })
    ).toBe(0);
  });
});

describe('PowerRatingHowItWorks (SB-1811)', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('shows the worked example computed from the formula', () => {
    const w = mountScreen();
    const text = w.get('[data-testid="pr-how-example"]').text();
    expect(text).toContain('1,600 home team');
    expect(text).toContain('1,500 visitor');
    expect(text).toContain('70% of the points');
    expect(w.get('[data-testid="pr-how-example-win"]').text()).toMatch(
      /30 × 1\.5 × 0\.30 =\s*\+13/
    );
    expect(w.get('[data-testid="pr-how-example-loss"]').text()).toMatch(
      /30 × 0\.70 =\s*−21/
    );
  });

  it('states the formula, K and G', () => {
    const w = mountScreen();
    const formula = w.get('[data-testid="pr-how-formula"]').text();
    expect(formula).toContain('E = 1 / (1 + 10^(−(R_team − R_opp + H)/400))');
    expect(formula).toContain('new R = R + K × G × (S − E)');
    const table = w.get('[data-testid="pr-how-table"]').text();
    expect(table).toContain('30 in every competition');
    expect(table).toContain('60 during');
    expect(table).toContain('first 8 rated matches');
    expect(table).toMatch(/1\.5 for 2 goals.*1\.75 for\s+3 goals or more/s);
  });

  it('carries the safeguarding line', () => {
    expect(
      mountScreen().get('[data-testid="pr-how-safeguard"]').text()
    ).toContain('Winning by more than 3 goals earns nothing extra.');
  });

  it('covers what counts, badges, tiers, the national rule and cadence', () => {
    const text = mountScreen().text();
    expect(text).toContain('counts as a draw');
    expect(text).toContain('Forfeits are not rated');
    expect(text).toContain('Provisional');
    expect(text).toContain('Low cross-conference data');
    expect(text).toContain('Pro academy');
    expect(text).toMatch(/Elite\s+1,700\+/);
    expect(text).toMatch(/Contender\s+1,600\+/);
    expect(text).toMatch(/Above average\s+1,500\+/);
    expect(text).toContain('at least 90% of the teams');
    expect(text).toContain('at least 5 matches against other');
    expect(text).toContain('MLS NEXT Fest');
    expect(text).toContain('updated nightly');
  });

  it('names its source as MT, with the pool size when known', () => {
    expect(
      mountScreen({ teamsInPool: 147, ageGroup: 'U17' })
        .get('[data-testid="pr-how-source"]')
        .text()
    ).toBe('MT Power Rating, from 147 U17 teams in MT.');
    expect(mountScreen().get('[data-testid="pr-how-source"]').text()).toBe(
      'MT Power Rating, from the teams in MT.'
    );
  });

  it('says matches, never games, and claims no official ranking', () => {
    const text = mountScreen({ teamsInPool: 147, ageGroup: 'U17' }).text();
    expect(text).not.toMatch(/\bgames?\b/i);
    expect(text).not.toMatch(/official/i);
    expect(text).not.toMatch(/MLS NEXT rank/i);
  });

  it('closes from the ✕, the backdrop and Escape', async () => {
    const w = mountScreen();
    await w.get('[data-testid="pr-how-close"]').trigger('click');
    await w.get('[data-testid="pr-how-overlay"]').trigger('click');
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(w.emitted('close')).toHaveLength(3);
    w.unmount();
  });

  it('a click inside the card does not close it', async () => {
    const w = mountScreen();
    await w.get('[data-testid="pr-how-table"]').trigger('click');
    expect(w.emitted('close')).toBeUndefined();
    w.unmount();
  });

  it('stops listening for Escape once closed', () => {
    const w = mountScreen();
    w.unmount();
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(w.emitted('close')).toBeUndefined();
  });
});

describe('PowerRatingPanel → How it works (SB-1811)', () => {
  beforeEach(() => {
    apiRequest.mockReset();
    apiRequest.mockImplementation(url =>
      Promise.resolve(url.includes('/api/rankings') ? RANKINGS : [])
    );
  });

  it('opens from the header link and closes again', async () => {
    const w = mount(PowerRatingPanel, { ...stubs, attachTo: document.body });
    await flushPromises();
    expect(w.find('[data-testid="pr-how-overlay"]').exists()).toBe(false);

    await w.get('[data-testid="pr-how-link"]').trigger('click');
    expect(w.find('[data-testid="pr-how-overlay"]').exists()).toBe(true);
    expect(w.get('[data-testid="pr-how-source"]').text()).toContain(
      '147 U17 teams'
    );

    await w.get('[data-testid="pr-how-close"]').trigger('click');
    await flushPromises();
    expect(w.find('[data-testid="pr-how-overlay"]').exists()).toBe(false);
    expect(document.activeElement).toBe(
      w.get('[data-testid="pr-how-link"]').element
    );

    await w.get('[data-testid="pr-how-link"]').trigger('click');
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    await flushPromises();
    expect(w.find('[data-testid="pr-how-overlay"]').exists()).toBe(false);
    w.unmount();
  });
});
