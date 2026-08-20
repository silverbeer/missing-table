/**
 * AdminUsers — editing a user's role, team and club (SB-803).
 *
 * The Users tab was read-only and showed no affiliation at all, so four real
 * accounts named for a club and attached to nothing looked identical to
 * correct ones. Editing meant shell access to manage_users.py, which is no use
 * at a match.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import AdminUsers from '@/components/admin/AdminUsers.vue';

const USERS = [
  {
    id: 'u-9',
    username: 'tom_ifa_fan',
    display_name: 'Tom_Ifa_Fan',
    role: 'team-fan',
    team_id: null,
    club_id: null,
    team_name: null,
    club_name: null,
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'u-3',
    username: 'tom_ifa',
    display_name: 'Tom (IFA)',
    role: 'team-manager',
    team_id: null,
    club_id: null,
    team_name: null,
    club_name: null,
    created_at: '2026-01-01T00:00:00Z',
  },
];

const TEAMS = [
  { id: 19, name: 'IFA' },
  { id: 30, name: 'New York City FC' },
];
const CLUBS = [{ id: 1, name: 'IFA' }];

const apiRequest = vi.fn();

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ apiRequest }),
}));
vi.mock('@/config/api', () => ({ getApiBaseUrl: () => 'http://test' }));

beforeEach(() => {
  apiRequest.mockReset();
  apiRequest.mockImplementation((url, opts = {}) => {
    if (url.includes('login-events')) return Promise.resolve({ events: [] });
    if (url.includes('/api/admin/users') && (opts.method || 'GET') === 'GET') {
      return Promise.resolve({ users: USERS, total: USERS.length });
    }
    if (url.includes('/api/teams')) return Promise.resolve(TEAMS);
    if (url.includes('/api/clubs')) return Promise.resolve(CLUBS);
    return Promise.resolve({ success: true });
  });
});

const mountUsers = async () => {
  const wrapper = mount(AdminUsers);
  await flushPromises();
  return wrapper;
};

const openEditorFor = async (wrapper, username) => {
  await wrapper.find(`[data-testid="edit-user-${username}"]`).trigger('click');
  await flushPromises();
};

describe('AdminUsers affiliation columns (SB-803)', () => {
  it('shows team and club for every user', async () => {
    const wrapper = await mountUsers();
    const head = wrapper.find('thead').text();

    expect(head).toContain('Team');
    expect(head).toContain('Club');
  });

  it('flags a role that implies an affiliation the account lacks', async () => {
    // tom_ifa is a team-manager with no team — it cannot manage a lineup.
    // That was invisible before; a plain dash reads as "fine".
    const wrapper = await mountUsers();
    const managerRow = wrapper
      .findAll('tbody tr')
      .find(r => r.text().includes('tom_ifa') && !r.text().includes('fan'));

    expect(managerRow.html()).toContain('text-amber-600');
  });

  it('does not flag a team-fan without a team', async () => {
    // A fan with no squad is an ordinary state, not a misconfiguration.
    const wrapper = await mountUsers();
    const fanRow = wrapper
      .findAll('tbody tr')
      .find(r => r.text().includes('tom_ifa_fan'));

    expect(fanRow.html()).not.toContain('text-amber-600');
  });
});

describe('AdminUsers editing (SB-803)', () => {
  it('opens an editor for a user', async () => {
    const wrapper = await mountUsers();
    await openEditorFor(wrapper, 'tom_ifa_fan');

    expect(wrapper.find('[data-testid="user-editor"]').text()).toContain(
      'tom_ifa_fan'
    );
  });

  it('loads teams and clubs for the pickers', async () => {
    const wrapper = await mountUsers();
    await openEditorFor(wrapper, 'tom_ifa_fan');

    expect(wrapper.vm.teams.length).toBe(2);
    expect(wrapper.vm.clubs.length).toBe(1);
  });

  it('filters the team list by search', async () => {
    // 183 teams in a phone-sized list is why this exists.
    const wrapper = await mountUsers();
    await openEditorFor(wrapper, 'tom_ifa_fan');

    wrapper.vm.teamSearch = 'york';
    await flushPromises();

    expect(wrapper.vm.filteredTeams.map(t => t.name)).toEqual([
      'New York City FC',
    ]);
  });

  it('keeps Save disabled until something actually changes', async () => {
    const wrapper = await mountUsers();
    await openEditorFor(wrapper, 'tom_ifa_fan');

    expect(
      wrapper.find('[data-testid="save-user"]').attributes('disabled')
    ).toBeDefined();

    wrapper.vm.form.team_id = 19;
    await flushPromises();

    expect(
      wrapper.find('[data-testid="save-user"]').attributes('disabled')
    ).toBeUndefined();
  });

  it('PATCHes the change and closes the editor', async () => {
    const wrapper = await mountUsers();
    await openEditorFor(wrapper, 'tom_ifa_fan');

    wrapper.vm.form.team_id = 19;
    await flushPromises();
    await wrapper.find('[data-testid="save-user"]').trigger('click');
    await flushPromises();

    const patch = apiRequest.mock.calls.find(c => c[1]?.method === 'PATCH');
    expect(patch[0]).toBe('http://test/api/admin/users/u-9');
    expect(JSON.parse(patch[1].body).team_id).toBe(19);
    expect(wrapper.find('[data-testid="user-editor"]').exists()).toBe(false);
  });

  it('surfaces a guardrail rejection and keeps the editor open', async () => {
    // "Cannot remove the last admin" is the message the admin needs to read,
    // and losing their edit on top of the refusal would be worse.
    const wrapper = await mountUsers();
    await openEditorFor(wrapper, 'tom_ifa_fan');

    wrapper.vm.form.role = 'admin';
    await flushPromises();
    apiRequest.mockImplementationOnce(() =>
      Promise.reject(new Error('Cannot remove the last admin.'))
    );
    await wrapper.find('[data-testid="save-user"]').trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-testid="save-error"]').text()).toContain(
      'last admin'
    );
    expect(wrapper.find('[data-testid="user-editor"]').exists()).toBe(true);
  });

  it('offers roles in the hyphen convention only', async () => {
    // roles.js normalizes spellings; a picker must not add a third form.
    const wrapper = await mountUsers();
    expect(wrapper.vm.ROLE_OPTIONS).toContain('team-manager');
    expect(wrapper.vm.ROLE_OPTIONS).not.toContain('team_manager');
  });
});
