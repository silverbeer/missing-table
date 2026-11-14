/**
 * FanProfile "My squads" card (SB-1543, SB-1608).
 *
 * A fan follows any squads (team + age group) in their own club for alerts.
 * Choosing squads writes follows only; the team a manager assigned is shown
 * apart and never changed here. Following nothing is the ordinary state, so
 * the card prompts; a fan with no club gets a sentence, not a broken picker.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import FanProfile from '@/components/profiles/FanProfile.vue';
import { _resetTeamFollowsForTest } from '@/composables/useTeamFollows';

const IFA = { id: 1, name: 'IFA' };
const U14 = { id: 2, name: 'U14' };
const U15 = { id: 3, name: 'U15' };

const opt = (team_id, name, league_name, age_group) => ({
  team_id,
  name,
  club_name: 'IFA',
  league_name,
  age_group,
  registrations: [],
  active: true,
});

const OPTIONS = [
  opt(123, 'IFA Academy', 'Academy', U14),
  opt(19, 'IFA', 'Homegrown', U14),
  opt(19, 'IFA', 'Homegrown', U15),
  opt(183, 'IFA Elite Futsal 2012 Blue', 'Kick Futsal', U14),
  opt(182, 'IFA Elite Futsal 2012 Gold', 'Kick Futsal', U14),
  opt(184, 'IFA Elite Futsal 2012 White', 'Kick Futsal', U14),
];

let teamOptions;
let follows;
const apiRequest = vi.fn();
const fetchProfile = vi.fn();
let mockAuthStore;

vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({ getApiBaseUrl: () => 'http://test' }));

beforeEach(() => {
  teamOptions = {
    status: 'ok',
    club: IFA,
    options: OPTIONS,
    current_team_id: null,
    current_age_group_id: null,
  };
  follows = [];
  _resetTeamFollowsForTest();
  mockAuthStore = {
    isAuthenticated: { value: true },
    state: { profile: { role: 'club-fan', club_id: null } },
    apiRequest,
    fetchProfile,
  };
  fetchProfile.mockReset();
  fetchProfile.mockResolvedValue({});
  apiRequest.mockReset();
  apiRequest.mockImplementation(url => {
    if (url.endsWith('/api/me/team-options')) {
      return Promise.resolve(teamOptions);
    }
    if (url.endsWith('/api/users/me/team-follows')) {
      return Promise.resolve({ follows });
    }
    return Promise.resolve({ success: true });
  });
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve({ ok: true, json: () => [] }))
  );
});

const mountProfile = async () => {
  const wrapper = mount(FanProfile, {
    global: {
      stubs: {
        LiveUpdatesTeaser: true,
        TeamChannelsCard: true,
        NotificationsCard: true,
      },
    },
  });
  await flushPromises();
  return wrapper;
};

const putCalls = () =>
  apiRequest.mock.calls.filter(c => c[1]?.method === 'PUT');

const squadFollow = (team_id, age_group_id) => ({ team_id, age_group_id });
const chipText = li => li.find('span').text();
const chips = wrapper =>
  wrapper.findAll('[data-testid="followed-squads"] li').map(chipText);
const otherChips = wrapper =>
  wrapper.findAll('[data-testid="other-alerts"] li').map(chipText);

describe('FanProfile Match alerts card (SB-1608, SB-1618)', () => {
  it('shows the assigned team apart, as club · league · age', async () => {
    teamOptions.current_team_id = 19;
    teamOptions.current_age_group_id = 3;
    const wrapper = await mountProfile();

    const assigned = wrapper.find('[data-testid="assigned-team"]');
    expect(assigned.text()).toContain('IFA · Homegrown · U15');
    expect(assigned.text()).toContain('set by your team manager');
    // Being assigned a team is not following it.
    expect(wrapper.find('[data-testid="my-team-prompt"]').exists()).toBe(true);
  });

  it('lists followed squads, naming the team when several share a slot', async () => {
    follows = [squadFollow(19, 3), squadFollow(183, 2)];
    const wrapper = await mountProfile();

    expect(chips(wrapper)).toEqual([
      'IFA · Homegrown · U15',
      'IFA · Kick Futsal · U14 · IFA Elite Futsal 2012 Blue',
    ]);
    expect(wrapper.find('[data-testid="following-count"]').text()).toBe('2');
  });

  it('shows an old whole-team follow as one "every age group" chip', async () => {
    follows = [squadFollow(19, null)];
    const wrapper = await mountProfile();

    expect(chips(wrapper)).toEqual(['IFA · Homegrown · every age group']);
    expect(wrapper.find('[data-testid="following-count"]').text()).toBe('1');
  });

  it('pre-ticks every squad of a whole-team follow in the picker', async () => {
    follows = [squadFollow(19, null)];
    const wrapper = await mountProfile();
    await wrapper.find('[data-testid="choose-squads"]').trigger('click');

    expect(wrapper.find('[data-testid="squad-19-2"]').element.checked).toBe(
      true
    );
    expect(wrapper.find('[data-testid="squad-19-3"]').element.checked).toBe(
      true
    );
  });

  it("lists other clubs' squads apart, labelled from the follow", async () => {
    follows = [
      squadFollow(19, 3),
      {
        team_id: 500,
        age_group_id: 6,
        age_group: { id: 6, name: 'U16' },
        team: {
          name: 'New England Revolution',
          division: { leagues: { name: 'Pro Academy' } },
        },
      },
    ];
    const wrapper = await mountProfile();

    expect(chips(wrapper)).toEqual(['IFA · Homegrown · U15']);
    expect(otherChips(wrapper)).toEqual([
      'New England Revolution · Pro Academy · U16',
    ]);
  });

  it('× stops alerts for that squad only', async () => {
    follows = [squadFollow(19, 3)];
    const wrapper = await mountProfile();

    follows = [];
    await wrapper.find('[data-testid="remove-19-3"]').trigger('click');
    await flushPromises();

    const del = apiRequest.mock.calls.find(c => c[1]?.method === 'DELETE');
    expect(del[0]).toBe(
      'http://test/api/users/me/team-follows/19?age_group_id=3'
    );
    expect(chips(wrapper)).toEqual([]);
  });

  it('says when alerts cannot reach this device yet', async () => {
    const wrapper = await mountProfile();
    // jsdom has no PushManager: alerts cannot reach this device.
    expect(wrapper.find('[data-testid="alerts-device-off"]').exists()).toBe(
      true
    );
  });

  it('prompts when nothing is followed, without an error or a zero claim', async () => {
    const wrapper = await mountProfile();

    expect(wrapper.find('[data-testid="my-team-prompt"]').text()).toContain(
      'match alerts'
    );
    expect(wrapper.find('[data-testid="followed-squads"]').exists()).toBe(
      false
    );
    expect(wrapper.find('[data-testid="choose-squads"]').text()).toBe(
      'Choose squads'
    );
    expect(wrapper.find('[data-testid="team-card-error"]').exists()).toBe(
      false
    );
  });

  it('says the account has no club, and offers no picker', async () => {
    teamOptions = {
      status: 'no_club',
      club: null,
      options: [],
      current_team_id: null,
      current_age_group_id: null,
    };
    const wrapper = await mountProfile();

    expect(wrapper.find('[data-testid="my-team-no-club"]').text()).toContain(
      "isn't linked to a club yet"
    );
    expect(wrapper.find('[data-testid="choose-squads"]').exists()).toBe(false);
    // The rest of the profile still renders.
    expect(wrapper.find('.hero-card').exists()).toBe(true);
  });

  it('does not ask for options for a role that cannot pick', async () => {
    mockAuthStore.state.profile.role = 'team-player';
    const wrapper = await mountProfile();

    expect(
      apiRequest.mock.calls.some(c => c[0].includes('/api/me/team-options'))
    ).toBe(false);
    expect(wrapper.find('[data-testid="my-team-card"]').exists()).toBe(false);
  });

  it('groups the club squads by league, with current follows ticked', async () => {
    follows = [squadFollow(19, 3)];
    const wrapper = await mountProfile();
    await wrapper.find('[data-testid="choose-squads"]').trigger('click');

    const legends = wrapper.findAll('.squad-group legend').map(l => l.text());
    expect(legends).toEqual(['Academy', 'Homegrown', 'Kick Futsal']);
    expect(wrapper.find('[data-testid="squad-19-3"]').element.checked).toBe(
      true
    );
    expect(wrapper.find('[data-testid="squad-19-2"]').element.checked).toBe(
      false
    );
  });

  it('saves several squads with one PUT, then refreshes follows', async () => {
    const wrapper = await mountProfile();
    await wrapper.find('[data-testid="choose-squads"]').trigger('click');
    await wrapper.find('[data-testid="squad-19-3"]').setValue(true);
    await wrapper.find('[data-testid="squad-182-2"]').setValue(true);

    follows = [squadFollow(19, 3), squadFollow(182, 2)];
    await wrapper.find('[data-testid="save-squads"]').trigger('click');
    await flushPromises();

    const [put] = putCalls();
    expect(put[0]).toBe('http://test/api/me/squad-follows');
    expect(JSON.parse(put[1].body)).toEqual({
      squads: [
        { team_id: 19, age_group_id: 3 },
        { team_id: 182, age_group_id: 2 },
      ],
    });
    expect(fetchProfile).not.toHaveBeenCalled(); // the profile is not touched
    expect(wrapper.find('[data-testid="squad-picker"]').exists()).toBe(false);
    expect(chips(wrapper)).toHaveLength(2);
  });

  it('unticking everything saves an empty list', async () => {
    follows = [squadFollow(19, 3)];
    const wrapper = await mountProfile();
    await wrapper.find('[data-testid="choose-squads"]').trigger('click');
    await wrapper.find('[data-testid="squad-19-3"]').setValue(false);

    await wrapper.find('[data-testid="save-squads"]').trigger('click');
    await flushPromises();

    expect(JSON.parse(putCalls()[0][1].body)).toEqual({ squads: [] });
  });

  it('shows the API detail on a rejected save and keeps the picker open', async () => {
    const wrapper = await mountProfile();
    await wrapper.find('[data-testid="choose-squads"]').trigger('click');
    await wrapper.find('[data-testid="squad-19-3"]').setValue(true);
    apiRequest.mockImplementationOnce(() =>
      Promise.reject(new Error('Pick only squads in your club'))
    );

    await wrapper.find('[data-testid="save-squads"]').trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-testid="squad-save-error"]').text()).toContain(
      'in your club'
    );
    expect(wrapper.find('[data-testid="squad-picker"]').exists()).toBe(true);
  });
});
