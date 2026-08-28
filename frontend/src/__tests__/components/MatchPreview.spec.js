/**
 * MatchPreview.vue tests (SB-892).
 *
 * The bug these guard: the W/L letter on a recent-form row swapped on
 * `isHome`, but the score beside it printed raw `home_score–away_score` with
 * no swap — while the opponent-name span deliberately hides who was home.
 *
 * So IFA's form rendered "W 1–3 FC Delco": a win whose first number is lower,
 * with nothing on the row to say which number was IFA's. Same failure family
 * as the 0-0 fixed in SB-886 — data presented so a reader draws a confident,
 * wrong conclusion.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';

const apiRequest = vi.fn();
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ apiRequest, isAuthenticated: { value: false } }),
}));

import MatchPreview from '@/components/MatchPreview.vue';

const IFA = 19;
const NVA = 40;

/** IFA won 3-1 away at FC Delco: stored home 3, away 1, IFA is the away side. */
const awayWin = {
  id: 1,
  home_team_id: 99,
  away_team_id: IFA,
  home_team_name: 'FC Delco',
  away_team_name: 'IFA',
  home_score: 3,
  away_score: 1,
  match_date: '2026-08-16',
};

/** IFA lost 1-3 at home to New York City FC. */
const homeLoss = {
  id: 2,
  home_team_id: IFA,
  away_team_id: 98,
  home_team_name: 'IFA',
  away_team_name: 'New York City FC',
  home_score: 1,
  away_score: 3,
  match_date: '2026-08-23',
};

const preview = (over = {}) => ({
  home_team_recent: [],
  away_team_recent: [],
  common_opponents: [],
  head_to_head: [],
  ...over,
});

const mountPreview = async previewData => {
  apiRequest.mockResolvedValue(previewData);
  const wrapper = mount(MatchPreview, {
    props: {
      homeTeamId: IFA,
      homeTeamName: 'IFA',
      awayTeamId: NVA,
      awayTeamName: 'Northern Virginia Alliance',
    },
  });
  await flushPromises();
  return wrapper;
};

const rowText = row => row.text().replace(/\s+/g, ' ').trim();

beforeEach(() => {
  apiRequest.mockReset();
});

describe('MatchPreview — form scorelines are oriented to their team', () => {
  it('leads with the subject team goals when it played away', async () => {
    // Stored as 3-1 to the home side, and IFA were away — so IFA scored 1 and
    // lost. The row must not print "3-1" beside the L, which invites the
    // reader to think IFA scored three.
    const wrapper = await mountPreview(
      preview({ home_team_recent: [awayWin] })
    );
    const row = wrapper.find('[data-testid="home-recent-match"]');

    expect(rowText(row)).toContain('1–3');
    expect(rowText(row)).not.toContain('3–1');
  });

  it('leads with the subject team goals when it played at home', async () => {
    const wrapper = await mountPreview(
      preview({ home_team_recent: [homeLoss] })
    );
    const row = wrapper.find('[data-testid="home-recent-match"]');

    expect(rowText(row)).toContain('1–3');
  });

  it('marks whether the subject team was home or away', async () => {
    // Without this, "3-1" is unreadable: you cannot tell whose goals came
    // first, because the opponent-name span hides who was home.
    const away = await mountPreview(preview({ home_team_recent: [awayWin] }));
    expect(away.find('[data-testid="form-venue"]').text()).toBe('A');

    const home = await mountPreview(preview({ home_team_recent: [homeLoss] }));
    expect(home.find('[data-testid="form-venue"]').text()).toBe('H');
  });

  it('agrees with the W/L letter it sits beside', async () => {
    // The regression in one assertion: the letter and the score must tell the
    // same story. A W whose first number is lower is the bug.
    const wrapper = await mountPreview(
      preview({
        home_team_recent: [
          { ...awayWin, home_score: 1, away_score: 3 }, // IFA away, scored 3 → W
        ],
      })
    );
    const text = rowText(wrapper.find('[data-testid="home-recent-match"]'));

    expect(text).toContain('W');
    expect(text).toContain('3–1');
  });

  it('orients the away column to the away team', async () => {
    const wrapper = await mountPreview(
      preview({
        away_team_recent: [
          {
            ...awayWin,
            id: 5,
            away_team_id: NVA,
            away_team_name: 'Northern Virginia Alliance',
          },
        ],
      })
    );
    const row = wrapper.find('[data-testid="away-recent-match"]');

    // NVA were away with 1 goal against FC Delco's 3.
    expect(rowText(row)).toContain('1–3');
  });

  it('renders an em dash rather than a bare separator for a missing score', async () => {
    // A "Not reported" match (SB-889) reaches here with null scores.
    const wrapper = await mountPreview(
      preview({
        home_team_recent: [{ ...homeLoss, home_score: null, away_score: null }],
      })
    );

    expect(
      rowText(wrapper.find('[data-testid="home-recent-match"]'))
    ).toContain('—');
  });
});

describe('MatchPreview — tabs only exist when they hold something', () => {
  it('hides Common Opponents and Head-to-Head when both are empty', async () => {
    // They used to render a literal 0 badge, so two of three tabs advertised
    // their own emptiness and invited a click that led nowhere.
    const wrapper = await mountPreview(preview());

    expect(wrapper.find('[data-testid="tab-form"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="tab-common"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="tab-h2h"]').exists()).toBe(false);
  });

  it('shows a tab once it has rows, with its count', async () => {
    const wrapper = await mountPreview(
      preview({ head_to_head: [homeLoss, awayWin] })
    );
    const tab = wrapper.find('[data-testid="tab-h2h"]');

    expect(tab.exists()).toBe(true);
    expect(tab.text()).toContain('2');
  });
});

describe('MatchPreview — a club with no tracked results', () => {
  it('states the reason rather than leaving a void', async () => {
    // Most clubs have no user data; this is the default state, not an error.
    // One column populated, one not — the asymmetric case from the screenshot,
    // where "No recent matches" sat alone above ~200px of dead space.
    const wrapper = await mountPreview(
      preview({ home_team_recent: [homeLoss], away_team_recent: [] })
    );
    const empty = wrapper.find('[data-testid="away-form-empty"]');

    expect(empty.exists()).toBe(true);
    expect(empty.text()).toContain('No matches on record');
  });
});
