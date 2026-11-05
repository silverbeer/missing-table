/**
 * FanProfile "My team" card (SB-1543).
 *
 * A fan's team is club + league + age group. Not having picked one is the
 * ordinary state, so the card prompts; a fan with no club gets a sentence,
 * not a broken picker.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import FanProfile from '@/components/profiles/FanProfile.vue';

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
  mockAuthStore = {
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
      stubs: { LiveUpdatesTeaser: true, LiveUpdatesSection: true },
    },
  });
  await flushPromises();
  return wrapper;
};

const putCalls = () =>
  apiRequest.mock.calls.filter(c => c[1]?.method === 'PUT');

describe('FanProfile My team card (SB-1543)', () => {
  it('shows the current pick as club · league · age', async () => {
    teamOptions.current_team_id = 19;
    teamOptions.current_age_group_id = 3;
    const wrapper = await mountProfile();

    expect(wrapper.find('[data-testid="my-team-label"]').text()).toBe(
      'IFA · Homegrown · U15'
    );
  });

  it('names the squad when several share the league and age', async () => {
    teamOptions.current_team_id = 183;
    teamOptions.current_age_group_id = 2;
    const wrapper = await mountProfile();

    expect(wrapper.find('[data-testid="my-team-label"]').text()).toBe(
      'IFA · Kick Futsal · U14 · IFA Elite Futsal 2012 Blue'
    );
  });

  it('prompts to pick when nothing is picked, without an error', async () => {
    const wrapper = await mountProfile();

    expect(wrapper.find('[data-testid="my-team-prompt"]').text()).toContain(
      'MT AI'
    );
    expect(wrapper.find('[data-testid="my-team-label"]').exists()).toBe(false);
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
    expect(wrapper.find('[data-testid="pick-team"]').exists()).toBe(false);
    // The rest of the profile still renders.
    expect(wrapper.find('.quick-access-section').exists()).toBe(true);
  });

  it('does not ask for options for a role that cannot pick', async () => {
    mockAuthStore.state.profile.role = 'team-player';
    const wrapper = await mountProfile();

    expect(
      apiRequest.mock.calls.some(c => c[0].includes('/api/me/team-options'))
    ).toBe(false);
    expect(wrapper.find('[data-testid="my-team-card"]').exists()).toBe(false);
  });

  it('auto-selects the only squad at a league and age', async () => {
    const wrapper = await mountProfile();
    await wrapper.find('[data-testid="pick-team"]').trigger('click');

    await wrapper.find('[data-testid="pick-league"]').setValue('Homegrown');
    await wrapper.find('[data-testid="pick-age-group"]').setValue('3');

    expect(wrapper.find('[data-testid="pick-squad"]').exists()).toBe(false);
    expect(
      wrapper.find('[data-testid="save-team"]').attributes('disabled')
    ).toBeUndefined();
  });

  it('asks for the squad when several share the league and age', async () => {
    const wrapper = await mountProfile();
    await wrapper.find('[data-testid="pick-team"]').trigger('click');

    await wrapper.find('[data-testid="pick-league"]').setValue('Kick Futsal');
    await wrapper.find('[data-testid="pick-age-group"]').setValue('2');

    const squad = wrapper.find('[data-testid="pick-squad"]');
    expect(squad.exists()).toBe(true);
    expect(squad.findAll('option').map(o => o.text())).toContain(
      'IFA Elite Futsal 2012 Gold'
    );
    expect(
      wrapper.find('[data-testid="save-team"]').attributes('disabled')
    ).toBeDefined();

    await squad.setValue('182');
    expect(
      wrapper.find('[data-testid="save-team"]').attributes('disabled')
    ).toBeUndefined();
  });

  it('saves with PUT team_id and age_group_id, then refreshes', async () => {
    const wrapper = await mountProfile();
    await wrapper.find('[data-testid="pick-team"]').trigger('click');
    await wrapper.find('[data-testid="pick-league"]').setValue('Homegrown');
    await wrapper.find('[data-testid="pick-age-group"]').setValue('3');

    await wrapper.find('[data-testid="save-team"]').trigger('click');
    await flushPromises();

    const [put] = putCalls();
    expect(put[0]).toBe('http://test/api/me/team');
    expect(JSON.parse(put[1].body)).toEqual({ team_id: 19, age_group_id: 3 });
    expect(fetchProfile).toHaveBeenCalled();
    expect(wrapper.find('[data-testid="team-picker"]').exists()).toBe(false);
  });

  it('clears with PUT {}', async () => {
    teamOptions.current_team_id = 19;
    teamOptions.current_age_group_id = 3;
    const wrapper = await mountProfile();

    await wrapper.find('[data-testid="clear-team"]').trigger('click');
    await flushPromises();

    const [put] = putCalls();
    expect(put[0]).toBe('http://test/api/me/team');
    expect(JSON.parse(put[1].body)).toEqual({});
  });

  it('shows the API detail on a rejected save and keeps the picker open', async () => {
    const wrapper = await mountProfile();
    await wrapper.find('[data-testid="pick-team"]').trigger('click');
    await wrapper.find('[data-testid="pick-league"]').setValue('Homegrown');
    await wrapper.find('[data-testid="pick-age-group"]').setValue('3');
    apiRequest.mockImplementationOnce(() =>
      Promise.reject(new Error("That team and age group aren't in your club"))
    );

    await wrapper.find('[data-testid="save-team"]').trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-testid="team-save-error"]').text()).toContain(
      "aren't in your club"
    );
    expect(wrapper.find('[data-testid="team-picker"]').exists()).toBe(true);
  });
});
