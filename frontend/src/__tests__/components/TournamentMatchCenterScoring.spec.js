/**
 * TournamentMatchCenter — inline scoring (SB-906).
 *
 * Scores arrive round by round during a tournament weekend. Before this, the
 * only way to enter one was the Admin panel or the CLI: the tournament list
 * itself was read-only, and the match-detail modal behind it only offers the
 * post-match editor, which is gated on the match already being completed.
 *
 * These cases cover the write path the row now hands to this component: who
 * gets the affordance, what the PATCH body says, and what a failure leaves on
 * screen. Auth is stubbed per-describe because the answer depends on the role.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { ref } from 'vue';

const apiRequest = vi.fn();
// Real refs, not `{ value }` literals: the store exposes computed refs and the
// component reads them through `unref`, which leaves a plain object alone —
// a hand-rolled stub would read as permanently truthy and every role would
// look like an admin.
const authState = {
  isAuthenticated: ref(true),
  isAdmin: ref(false),
  isClubManager: ref(false),
  isTeamManager: ref(false),
  userClubId: ref(null),
  userTeamId: ref(null),
};

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ apiRequest, ...authState }),
}));

import TournamentMatchCenter from '@/components/TournamentMatchCenter.vue';

const IFA = { id: 19, name: 'IFA' };
const NVA = { id: 601, name: 'Northern Virginia Alliance' };

const SEASONS = [
  {
    id: 4,
    name: '2026-2027',
    start_date: '2026-09-01',
    end_date: '2027-06-30',
  },
];

const mkMatch = (over = {}) => ({
  id: 5995,
  match_date: '2026-08-29',
  scheduled_kickoff: '2026-08-29T12:20:00Z',
  match_status: 'scheduled',
  home_score: null,
  away_score: null,
  home_penalty_score: null,
  away_penalty_score: null,
  tournament_group: 'MLS Next',
  tournament_round: 'group_stage',
  age_group: { id: 5, name: 'U17' },
  home_team: IFA,
  away_team: NVA,
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
  age_groups: [{ id: 5, name: 'U17' }],
});

// Route the component's three GETs; anything else (the PATCH) falls through to
// whatever the test staged with mockImplementationOnce.
async function mountWith(matches = [mkMatch()], onPatch = null) {
  apiRequest.mockReset();
  const tournament = TOURNAMENT(matches);
  apiRequest.mockImplementation((url, options) => {
    if (url.includes('/api/seasons')) return Promise.resolve(SEASONS);
    if (/\/api\/tournaments\/\d+/.test(url)) return Promise.resolve(tournament);
    if (url.includes('/api/tournaments')) return Promise.resolve([tournament]);
    if (/\/api\/matches\/\d+/.test(url) && onPatch)
      return onPatch(url, options);
    return Promise.resolve(null);
  });
  const wrapper = mount(TournamentMatchCenter, {
    global: { stubs: { MatchDetailView: true } },
  });
  await flushPromises();
  return wrapper;
}

const setRole = (role = {}) => {
  authState.isAdmin.value = !!role.isAdmin;
  authState.isClubManager.value = !!role.isClubManager;
  authState.isTeamManager.value = !!role.isTeamManager;
  authState.userClubId.value = role.clubId ?? null;
  authState.userTeamId.value = role.teamId ?? null;
};

const patchCalls = () =>
  apiRequest.mock.calls.filter(([url]) => /\/api\/matches\/\d+/.test(url));

beforeEach(() => setRole({}));

describe('who sees the edit affordance', () => {
  it('nobody, for a signed-in viewer with no management role', async () => {
    const wrapper = await mountWith();
    expect(wrapper.find('[data-testid="edit-score-button"]').exists()).toBe(
      false
    );
  });

  it('an admin, on every match', async () => {
    setRole({ isAdmin: true });
    const wrapper = await mountWith([mkMatch(), mkMatch({ id: 5996 })]);
    expect(wrapper.findAll('[data-testid="edit-score-button"]')).toHaveLength(
      2
    );
  });

  it('a team manager, only on their own team’s match', async () => {
    setRole({ isTeamManager: true, teamId: 19 });
    const wrapper = await mountWith([
      mkMatch(),
      mkMatch({
        id: 5996,
        home_team: { id: 570, name: 'Alexandria SA' },
        away_team: { id: 573, name: 'Baltimore Armour' },
        home_team_club: { id: 236 },
        away_team_club: { id: 239 },
      }),
    ]);
    expect(wrapper.findAll('[data-testid="edit-score-button"]')).toHaveLength(
      1
    );
  });

  it('a club manager, on any match involving their club', async () => {
    setRole({ isClubManager: true, clubId: 267 });
    const wrapper = await mountWith();
    expect(wrapper.findAll('[data-testid="edit-score-button"]')).toHaveLength(
      1
    );
  });
});

describe('saving a score', () => {
  it('PATCHes the score and completes a scheduled match', async () => {
    setRole({ isAdmin: true });
    const wrapper = await mountWith([mkMatch()], () =>
      Promise.resolve({
        id: 5995,
        home_score: 2,
        away_score: 1,
        match_status: 'completed',
      })
    );

    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    await wrapper.find('[data-testid="edit-home-score"]').setValue('2');
    await wrapper.find('[data-testid="edit-away-score"]').setValue('1');
    await wrapper.find('[data-testid="save-score-button"]').trigger('click');
    await flushPromises();

    const [url, options] = patchCalls()[0];
    expect(url).toContain('/api/matches/5995');
    expect(options.method).toBe('PATCH');
    expect(JSON.parse(options.body)).toEqual({
      home_score: 2,
      away_score: 1,
      match_status: 'completed',
    });
  });

  it('renders the new score on the row without a refetch', async () => {
    setRole({ isAdmin: true });
    const wrapper = await mountWith([mkMatch()], () =>
      Promise.resolve({
        id: 5995,
        home_score: 3,
        away_score: 0,
        match_status: 'completed',
      })
    );

    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    await wrapper.find('[data-testid="edit-home-score"]').setValue('3');
    await wrapper.find('[data-testid="edit-away-score"]').setValue('0');
    await wrapper.find('[data-testid="save-score-button"]').trigger('click');
    await flushPromises();

    expect(
      wrapper.find('[data-testid="tournament-score-editor"]').exists()
    ).toBe(false);
    expect(wrapper.text()).toContain('3');
    expect(wrapper.text()).toContain('0');
    // Only the one PATCH — the row updates in place.
    expect(patchCalls()).toHaveLength(1);
  });

  it('leaves a live match’s status alone', async () => {
    setRole({ isAdmin: true });
    const wrapper = await mountWith(
      [mkMatch({ match_status: 'live', home_score: 1, away_score: 0 })],
      () => Promise.resolve({ id: 5995, home_score: 2, away_score: 0 })
    );

    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    await wrapper.find('[data-testid="edit-home-score"]').setValue('2');
    await wrapper.find('[data-testid="save-score-button"]').trigger('click');
    await flushPromises();

    expect(JSON.parse(patchCalls()[0][1].body)).toEqual({
      home_score: 2,
      away_score: 0,
    });
  });

  it('sends the shootout on a level bracket score', async () => {
    setRole({ isAdmin: true });
    const wrapper = await mountWith(
      [
        mkMatch({
          tournament_round: 'final',
          tournament_group: 'Championship',
        }),
      ],
      () => Promise.resolve({ id: 5995, home_score: 1, away_score: 1 })
    );

    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    await wrapper.find('[data-testid="edit-home-score"]').setValue('1');
    await wrapper.find('[data-testid="edit-away-score"]').setValue('1');
    await wrapper.find('[data-testid="edit-home-penalty"]').setValue('5');
    await wrapper.find('[data-testid="edit-away-penalty"]').setValue('4');
    await wrapper.find('[data-testid="save-score-button"]').trigger('click');
    await flushPromises();

    expect(JSON.parse(patchCalls()[0][1].body)).toMatchObject({
      home_penalty_score: 5,
      away_penalty_score: 4,
    });
  });

  it('keeps the editor open with the typed score when the write fails', async () => {
    setRole({ isAdmin: true });
    const wrapper = await mountWith([mkMatch()], () =>
      Promise.reject(new Error('Match is locked'))
    );

    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    await wrapper.find('[data-testid="edit-home-score"]').setValue('4');
    await wrapper.find('[data-testid="edit-away-score"]').setValue('2');
    await wrapper.find('[data-testid="save-score-button"]').trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-testid="edit-home-score"]').element.value).toBe(
      '4'
    );
    expect(wrapper.find('[data-testid="save-score-error"]').text()).toContain(
      'Match is locked'
    );
  });
});
