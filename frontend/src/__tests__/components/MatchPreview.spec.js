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

describe('MatchPreview — form rows name their competition (SB-1346)', () => {
  it('labels each form row with its match type', async () => {
    const wrapper = await mountPreview(
      preview({
        home_team_recent: [
          { ...homeLoss, match_type_name: 'League' },
          { ...awayWin, id: 3, match_type_name: 'Flex' },
        ],
      })
    );
    const chips = wrapper.findAll('[data-testid="form-competition"]');
    expect(chips.map(c => c.text())).toEqual(['League', 'Flex']);
  });

  it('omits the label when the match type is unknown', async () => {
    const wrapper = await mountPreview(
      preview({ home_team_recent: [homeLoss] })
    );
    expect(wrapper.find('[data-testid="form-competition"]').exists()).toBe(
      false
    );
  });

  it('sends the previewed match type so the server can scope form', async () => {
    apiRequest.mockResolvedValue(preview());
    mount(MatchPreview, {
      props: { homeTeamId: IFA, awayTeamId: NVA, matchTypeId: 1 },
    });
    await flushPromises();
    expect(apiRequest.mock.calls[0][0]).toContain('match_type_id=1');
  });

  it('sends no match type when none is given', async () => {
    await mountPreview(preview());
    expect(apiRequest.mock.calls[0][0]).not.toContain('match_type_id');
  });
});

// ─── Scouting tab (SB-1782) ─────────────────────────────────────────────────

const MATCH = 620;

const line = over => ({
  kind: 'league',
  competition: 'League',
  division: { id: 201, name: 'Northeast', league: 'Homegrown' },
  league: 'Homegrown',
  position: 4,
  table_size: 12,
  played: 8,
  wins: 5,
  draws: 1,
  losses: 2,
  gf_per_game: 2.25,
  ga_per_game: 1.0,
  low_sample: false,
  no_results: false,
  ...over,
});

const dossier = (teamId, name, over = {}) => ({
  team: {
    id: teamId,
    name,
    club_name: name,
    logo_url: null,
    pro_academy: false,
  },
  age_group: { id: 15, name: 'U15' },
  context: {
    match_id: MATCH,
    bracket_age_group: { id: 15, name: 'U15' },
    season_age_group: { id: 15, name: 'U15' },
    playing_up: false,
    playing_up_inferred: false,
    playing_down: false,
  },
  conferences: [line()],
  totals: { played: 8, wins: 5, draws: 1, losses: 2 },
  key_wins: [],
  form: [],
  flags: [],
  error: null,
  ...over,
});

/** A registered team nobody has tracked: MT's default state. */
const noData = (teamId, name) =>
  dossier(teamId, name, {
    conferences: [
      line({
        position: null,
        played: 0,
        wins: null,
        draws: null,
        losses: null,
        gf_per_game: null,
        ga_per_game: null,
        low_sample: true,
        no_results: true,
      }),
    ],
    totals: null,
    flags: ['no_results'],
  });

const badge = over => ({
  board: 'gf_pg',
  title: 'Goals for per game',
  league_id: 1,
  league: 'Homegrown',
  age_group: 'U15',
  rank: 2,
  of: 134,
  value: 2.25,
  fact_id: `t${IFA}:a15:board:1:gf_pg`,
  text: '…',
  ...over,
});

const matchupOf = (over = {}) => ({
  match: { id: MATCH, date: '2026-11-20', age_group: { id: 15, name: 'U15' } },
  shares_conference: false,
  scouting_relevant: true,
  home: {
    dossier: dossier(IFA, 'IFA'),
    badges: [badge()],
    badges_note: 'A stat board, not a ranking.',
  },
  away: {
    dossier: dossier(NVA, 'Northern Virginia Alliance', {
      conferences: [
        line({ division: { id: 202, name: 'Southeast', league: 'Homegrown' } }),
        line({
          kind: 'flex',
          competition: 'Flex',
          division: { id: 205, name: 'Turnpike', league: 'Flex' },
          league: 'Flex',
        }),
      ],
    }),
    badges: [],
    badges_note: null,
  },
  previous_meetings: [],
  error: null,
  ...over,
});

const httpError = status => Object.assign(new Error('boom'), { status });

/** apiRequest routed by URL: the preview and the matchup are separate reads. */
const routeApi = ({
  previewData = preview(),
  matchupData,
  matchupError,
} = {}) => {
  apiRequest.mockImplementation(async url => {
    if (url.includes('/matchup')) {
      if (matchupError) throw matchupError;
      return matchupData;
    }
    return previewData;
  });
};

const matchupCalls = () =>
  apiRequest.mock.calls.filter(c => c[0].includes('/matchup'));

const scoutingProps = (over = {}) => ({
  homeTeamId: IFA,
  homeTeamName: 'IFA',
  awayTeamId: NVA,
  awayTeamName: 'Northern Virginia Alliance',
  matchId: MATCH,
  tournamentId: 3,
  ...over,
});

const mountScouting = async (opts = {}, props = {}) => {
  routeApi(opts);
  const wrapper = mount(MatchPreview, { props: scoutingProps(props) });
  await flushPromises();
  return wrapper;
};

const text = w => w.text().replace(/\s+/g, ' ').trim();

describe('MatchPreview — Scouting tab (SB-1782)', () => {
  it('leads, and is the default, for a tournament match', async () => {
    const wrapper = await mountScouting({ matchupData: matchupOf() });

    const tabs = wrapper
      .findAll('nav button')
      .map(b => b.attributes('data-testid'));
    expect(tabs[0]).toBe('tab-scouting');
    expect(wrapper.find('[data-testid="tab-panel-scouting"]').exists()).toBe(
      true
    );
    expect(matchupCalls()[0][0]).toContain(`/api/matches/${MATCH}/matchup`);
  });

  it('a league match keeps the old tabs and never reads the matchup', async () => {
    const wrapper = await mountScouting(
      {
        previewData: preview({ home_team_recent: [homeLoss] }),
        matchupData: matchupOf(), // even one the API calls scouting_relevant
      },
      { tournamentId: null }
    );

    expect(wrapper.find('[data-testid="tab-scouting"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="tab-panel-form"]').exists()).toBe(true);
    expect(matchupCalls()).toHaveLength(0);
  });

  it('shows both dossiers: standing, record, per-game rates and badges', async () => {
    const wrapper = await mountScouting({ matchupData: matchupOf() });
    const home = wrapper.find('[data-testid="scouting-home"]');

    expect(text(home)).toContain('4th of 12');
    expect(text(home)).toContain('5-1-2');
    expect(text(home)).toContain('GF 2.3 · GA 1.0 per game');
    expect(text(home.find('[data-testid="scouting-badge"]'))).toBe(
      '2nd in U15 Homegrown goals for per game, of 134 teams'
    );
    expect(home.find('[data-testid="scouting-badges-note"]').text()).toContain(
      'not a ranking'
    );
    // The away side has a Flex line too; the home side is Homegrown only.
    const away = wrapper.find('[data-testid="scouting-away"]');
    expect(away.find('[data-testid="scouting-conference-flex"]').exists()).toBe(
      true
    );
    expect(home.find('[data-testid="scouting-conference-flex"]').exists()).toBe(
      false
    );
  });

  it('keeps a badge title in its own case but for the first letter', async () => {
    const data = matchupOf();
    data.home.badges = [
      badge({
        board: 'pts',
        title: 'Points (W=3, D=1; shootouts count as draws)',
        rank: 1,
        fact_id: `t${IFA}:a15:board:1:pts`,
      }),
    ];
    const wrapper = await mountScouting({ matchupData: data });
    expect(text(wrapper.find('[data-testid="scouting-badge"]'))).toBe(
      '1st in U15 Homegrown points (W=3, D=1; shootouts count as draws), of 134 teams'
    );
  });

  it('a side with no data says so, and never renders 0', async () => {
    const data = matchupOf();
    data.away = {
      dossier: noData(NVA, 'Northern Virginia Alliance'),
      badges: [],
      badges_note: null,
    };
    const wrapper = await mountScouting({ matchupData: data });
    const away = wrapper.find('[data-testid="scouting-away"]');

    expect(away.find('[data-testid="scouting-side-empty"]').text()).toContain(
      'No results tracked this season'
    );
    expect(away.find('[data-testid="scouting-line-empty"]').exists()).toBe(
      true
    );
    expect(away.text()).not.toMatch(/\b0\b/);
    // The other side is untouched.
    expect(text(wrapper.find('[data-testid="scouting-home"]'))).toContain(
      '4th of 12'
    );
  });

  it('both sides with no data is one honest empty state', async () => {
    const data = matchupOf();
    data.home = { dossier: noData(IFA, 'IFA'), badges: [], badges_note: null };
    data.away = { dossier: noData(NVA, 'NVA'), badges: [], badges_note: null };
    const wrapper = await mountScouting({ matchupData: data });

    expect(wrapper.find('[data-testid="scouting-empty"]').text()).toContain(
      'No results tracked for either team this season'
    );
  });

  it('labels a playing-up team and a small sample', async () => {
    const data = matchupOf();
    data.home.dossier = dossier(IFA, 'IFA', {
      age_group: { id: 14, name: 'U14' },
      context: {
        match_id: MATCH,
        bracket_age_group: { id: 15, name: 'U15' },
        season_age_group: { id: 14, name: 'U14' },
        playing_up: true,
        playing_up_inferred: true,
        playing_down: false,
      },
      flags: ['low_sample', 'playing_up', 'playing_up_inferred'],
    });
    const wrapper = await mountScouting({ matchupData: data });
    const labels = wrapper
      .find('[data-testid="scouting-home"]')
      .findAll('[data-testid="scouting-label"]')
      .map(l => l.text());

    expect(labels).toContain('Playing up from U14 (inferred)');
    expect(labels).toContain('Small sample');
  });

  it('marks a pro academy upset', async () => {
    const data = matchupOf();
    data.home.dossier.key_wins = [
      {
        match_id: 9,
        score: '3-2',
        opponent: { id: 10, name: 'Pro FC' },
        opponent_position: null,
        kind: 'pro_academy_upset',
      },
    ];
    const wrapper = await mountScouting({ matchupData: data });
    expect(wrapper.find('[data-testid="scouting-upset"]').exists()).toBe(true);
  });

  it('a failed matchup (5xx) shows a retry, and the other tabs still work', async () => {
    const wrapper = await mountScouting({
      previewData: preview({
        home_team_recent: [homeLoss],
        head_to_head: [homeLoss],
      }),
      matchupError: httpError(503),
    });

    expect(wrapper.find('[data-testid="scouting-error"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="scouting-retry"]').exists()).toBe(true);

    await wrapper.find('[data-testid="tab-form"]').trigger('click');
    expect(wrapper.findAll('[data-testid="home-recent-match"]')).toHaveLength(
      1
    );
    await wrapper.find('[data-testid="tab-h2h"]').trigger('click');
    expect(wrapper.findAll('[data-testid="h2h-match"]')).toHaveLength(1);
  });

  it('a network failure (no status) offers a retry', async () => {
    const wrapper = await mountScouting({
      matchupError: new Error('Network error'),
    });
    expect(wrapper.find('[data-testid="scouting-retry"]').exists()).toBe(true);
  });

  it('a refused matchup (4xx) drops Scouting, with no retry, and picks the usual tab', async () => {
    const wrapper = await mountScouting({
      previewData: preview({ head_to_head: [homeLoss] }),
      matchupError: httpError(400),
    });

    expect(wrapper.find('[data-testid="tab-scouting"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="scouting-retry"]').exists()).toBe(false);
    // No form, no common opponents: the usual choice lands on Head-to-Head.
    expect(wrapper.find('[data-testid="tab-panel-h2h"]').exists()).toBe(true);
  });

  it('drops a late answer for the previous match', async () => {
    const pending = {};
    apiRequest.mockImplementation(
      url =>
        new Promise(resolve => {
          pending[url] = resolve;
        })
    );
    const wrapper = mount(MatchPreview, { props: scoutingProps() });
    const first = Object.keys(pending).find(u =>
      u.includes(`/${MATCH}/matchup`)
    );
    await wrapper.setProps({ matchId: 621 });
    const second = Object.keys(pending).find(u => u.includes('/621/matchup'));

    const fresh = matchupOf();
    fresh.home.dossier.team.name = 'Match B home';
    pending[second](fresh);
    await flushPromises();
    const stale = matchupOf();
    stale.home.dossier.team.name = 'Match A home';
    pending[first](stale);
    await flushPromises();

    expect(
      wrapper
        .find(
          '[data-testid="scouting-home"] [data-testid="scouting-team-name"]'
        )
        .text()
    ).toBe('Match B home');
  });

  it("never shows the previous match's preview while the next one loads", async () => {
    const wrapper = await mountScouting({
      previewData: preview({ home_team_recent: [homeLoss] }),
      matchupData: matchupOf(),
    });
    await wrapper.find('[data-testid="tab-form"]').trigger('click');
    expect(wrapper.findAll('[data-testid="home-recent-match"]')).toHaveLength(
      1
    );

    apiRequest.mockImplementation(() => new Promise(() => {})); // match B never answers
    await wrapper.setProps({ matchId: 621, homeTeamId: 77 });
    await wrapper.find('[data-testid="tab-form"]').trigger('click');

    expect(wrapper.findAll('[data-testid="home-recent-match"]')).toHaveLength(
      0
    );
    expect(wrapper.find('[data-testid="preview-loading"]').exists()).toBe(true);
  });

  it('keeps Common Opponents and Head-to-Head empty states unchanged', async () => {
    const wrapper = await mountScouting({ matchupData: matchupOf() });
    expect(wrapper.find('[data-testid="tab-common"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="tab-h2h"]').exists()).toBe(false);
    await wrapper.find('[data-testid="tab-form"]').trigger('click');
    expect(wrapper.find('[data-testid="form-empty"]').exists()).toBe(true);
  });

  it('does not read the matchup without a match id', async () => {
    await mountPreview(preview());
    expect(matchupCalls()).toHaveLength(0);
  });
});
