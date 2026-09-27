/**
 * AdminUsers — the Email column (SB-1125).
 *
 * The address was in `/api/admin/users` all along and never rendered, so an
 * admin had no way to see that most accounts cannot receive mail at all. In
 * production 24 of 34 have no real address, which means a password reset or
 * an invite for those people has nowhere to go.
 *
 * The case that matters most is the synthetic one: MT gives every account a
 * `username@missingtable.local` address so Supabase Auth has a key. It is a
 * login identity, not a mailbox, and showing it under a heading that says
 * Email would assert the opposite of the truth.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import AdminUsers from '@/components/admin/AdminUsers.vue';

const USERS = [
  {
    id: 'u-1',
    username: 'check',
    display_name: 'Check',
    role: 'club_manager',
    email: 'silverbeer@zohomail.com',
    team_id: null,
    club_id: 1,
    team_name: null,
    club_name: 'IFA',
    created_at: '2026-09-26T00:00:00Z',
  },
  {
    id: 'u-2',
    username: 'anngoutis',
    display_name: 'Ann',
    role: 'club-fan',
    email: null,
    team_id: null,
    club_id: 1,
    team_name: null,
    club_name: 'IFA',
    created_at: '2026-05-02T00:00:00Z',
  },
  {
    id: 'u-3',
    username: 'gabe35',
    display_name: 'Gabe 35',
    role: 'team-player',
    email: 'gabe35@missingtable.local',
    team_id: 19,
    club_id: 1,
    team_name: 'IFA',
    club_name: 'IFA',
    created_at: '2025-12-01T00:00:00Z',
  },
];

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
    if (url.includes('delete-preflight')) {
      return Promise.resolve({
        username: 'anngoutis',
        refusal: null,
        destroys: [{ what: 'roster history entries', count: 3 }],
        orphans: [{ what: 'match events they recorded', count: 5 }],
        blockers: [],
      });
    }
    if (url.includes('/api/teams')) return Promise.resolve([]);
    if (url.includes('/api/clubs')) return Promise.resolve([]);
    return Promise.resolve({ success: true });
  });
});

const mountUsers = async () => {
  const wrapper = mount(AdminUsers);
  await flushPromises();
  return wrapper;
};

describe('AdminUsers — Email column', () => {
  it('has an Email heading', async () => {
    const wrapper = await mountUsers();
    expect(wrapper.find('thead').text()).toContain('Email');
  });

  it('shows a real address', async () => {
    const wrapper = await mountUsers();
    expect(wrapper.text()).toContain('silverbeer@zohomail.com');
  });

  it('says an account with no address is unreachable, not blank', async () => {
    const wrapper = await mountUsers();
    const missing = wrapper.findAll('[data-testid="user-email-missing"]');
    expect(missing.length).toBeGreaterThan(0);
    expect(missing[0].text()).toBe('No email');
  });

  it('never shows the synthetic login address as an email', async () => {
    const wrapper = await mountUsers();
    // gabe35 has @missingtable.local, which nothing can be delivered to.
    expect(wrapper.text()).not.toContain('@missingtable.local');
  });

  it('counts a synthetic address as unreachable, same as none at all', async () => {
    const wrapper = await mountUsers();
    // Ann (null) and gabe35 (synthetic) both qualify; check does not.
    expect(wrapper.findAll('[data-testid="user-email-missing"]')).toHaveLength(
      2
    );
    expect(wrapper.findAll('[data-testid="user-email"]')).toHaveLength(1);
  });
});

describe('AdminUsers — contactEmail', () => {
  const contactEmail = user => {
    const email = user?.email;
    if (!email) return null;
    return email.endsWith('@missingtable.local') ? null : email;
  };

  it('matches the component on all three states', async () => {
    const wrapper = await mountUsers();
    const fn = wrapper.vm.contactEmail;

    for (const user of USERS) {
      expect(fn(user)).toBe(contactEmail(user));
    }
    expect(fn({ email: 'a@b.com' })).toBe('a@b.com');
    expect(fn({ email: null })).toBeNull();
    expect(fn({ email: 'x@missingtable.local' })).toBeNull();
    expect(fn({})).toBeNull();
    expect(fn(null)).toBeNull();
  });
});

describe('AdminUsers — an admin setting an email (SB-1128)', () => {
  const openEditor = async (wrapper, username) => {
    await wrapper
      .find(`[data-testid="edit-user-${username}"]`)
      .trigger('click');
    await flushPromises();
  };

  it('offers an Email field in the editor', async () => {
    const wrapper = await mountUsers();
    await openEditor(wrapper, 'check');
    expect(wrapper.find('[data-testid="edit-email"]').exists()).toBe(true);
  });

  it('opens with the existing address', async () => {
    const wrapper = await mountUsers();
    await openEditor(wrapper, 'check');
    expect(wrapper.find('[data-testid="edit-email"]').element.value).toBe(
      'silverbeer@zohomail.com'
    );
  });

  it('opens empty for an account with none', async () => {
    const wrapper = await mountUsers();
    await openEditor(wrapper, 'anngoutis');
    expect(wrapper.find('[data-testid="edit-email"]').element.value).toBe('');
  });

  it('opens empty rather than pre-filling a synthetic sign-in identity', async () => {
    const wrapper = await mountUsers();
    await openEditor(wrapper, 'gabe35');
    expect(wrapper.find('[data-testid="edit-email"]').element.value).toBe('');
  });

  it('sends the address on save', async () => {
    const wrapper = await mountUsers();
    await openEditor(wrapper, 'anngoutis');
    await wrapper
      .find('[data-testid="edit-email"]')
      .setValue('ann@example.com');
    await wrapper.find('[data-testid="save-user"]').trigger('click');
    await flushPromises();

    const patch = apiRequest.mock.calls.find(
      ([, opts]) => opts?.method === 'PATCH'
    );
    expect(JSON.parse(patch[1].body).email).toBe('ann@example.com');
  });

  it('sends an empty string to clear one, which the API reads as "remove"', async () => {
    const wrapper = await mountUsers();
    await openEditor(wrapper, 'check');
    await wrapper.find('[data-testid="edit-email"]').setValue('');
    await wrapper.find('[data-testid="save-user"]').trigger('click');
    await flushPromises();

    const patch = apiRequest.mock.calls.find(
      ([, opts]) => opts?.method === 'PATCH'
    );
    expect(JSON.parse(patch[1].body).email).toBe('');
  });
});

describe('AdminUsers — deleting an account (SB-1132)', () => {
  const openEditor = async (wrapper, username) => {
    await wrapper
      .find(`[data-testid="edit-user-${username}"]`)
      .trigger('click');
    await flushPromises();
  };

  const openDelete = async (wrapper, username = 'anngoutis') => {
    await openEditor(wrapper, username);
    await wrapper.find('[data-testid="delete-user"]').trigger('click');
    await flushPromises();
    return wrapper;
  };

  it('offers deletion from the editor', async () => {
    const wrapper = await mountUsers();
    await openEditor(wrapper, 'anngoutis');
    expect(wrapper.find('[data-testid="delete-user"]').exists()).toBe(true);
  });

  it('says what else will be destroyed, with counts', async () => {
    const wrapper = await openDelete(await mountUsers());
    const destroys = wrapper.find('[data-testid="delete-destroys"]');
    expect(destroys.exists()).toBe(true);
    // Roster history cannot be reconstructed; the number is the point.
    expect(destroys.text()).toContain('3');
    expect(destroys.text()).toContain('roster history entries');
  });

  it('separates what is kept but unattributed', async () => {
    const wrapper = await openDelete(await mountUsers());
    expect(wrapper.find('[data-testid="delete-orphans"]').text()).toContain(
      'match events they recorded'
    );
  });

  it('will not delete until the username is typed', async () => {
    const wrapper = await openDelete(await mountUsers());
    const confirm = wrapper.find('[data-testid="delete-confirm"]');
    expect(confirm.attributes('disabled')).toBeDefined();

    await wrapper
      .find('[data-testid="delete-confirm-input"]')
      .setValue('wrong');
    expect(
      wrapper.find('[data-testid="delete-confirm"]').attributes('disabled')
    ).toBeDefined();

    await wrapper
      .find('[data-testid="delete-confirm-input"]')
      .setValue('anngoutis');
    expect(
      wrapper.find('[data-testid="delete-confirm"]').attributes('disabled')
    ).toBeUndefined();
  });

  it('sends the delete once confirmed', async () => {
    const wrapper = await openDelete(await mountUsers());
    await wrapper
      .find('[data-testid="delete-confirm-input"]')
      .setValue('anngoutis');
    await wrapper.find('[data-testid="delete-confirm"]').trigger('click');
    await flushPromises();

    const call = apiRequest.mock.calls.find(
      ([, opts]) => opts?.method === 'DELETE'
    );
    expect(call).toBeTruthy();
    expect(call[0]).toContain('/api/auth/users/u-2');
  });

  it('refuses when the API says the account cannot be deleted', async () => {
    apiRequest.mockImplementation((url, opts = {}) => {
      if (url.includes('delete-preflight')) {
        return Promise.resolve({
          username: 'anngoutis',
          refusal: 'Cannot delete the last admin.',
          destroys: [],
          orphans: [],
          blockers: [],
        });
      }
      if (url.includes('login-events')) return Promise.resolve({ events: [] });
      if (
        url.includes('/api/admin/users') &&
        (opts.method || 'GET') === 'GET'
      ) {
        return Promise.resolve({ users: USERS, total: USERS.length });
      }
      return Promise.resolve([]);
    });

    const wrapper = await openDelete(await mountUsers());
    expect(wrapper.find('[data-testid="delete-refusal"]').text()).toContain(
      'last admin'
    );
    expect(
      wrapper.find('[data-testid="delete-confirm"]').attributes('disabled')
    ).toBeDefined();
  });

  it('does not offer deletion when the preflight cannot be read', async () => {
    apiRequest.mockImplementation((url, opts = {}) => {
      if (url.includes('delete-preflight'))
        return Promise.reject(new Error('boom'));
      if (url.includes('login-events')) return Promise.resolve({ events: [] });
      if (
        url.includes('/api/admin/users') &&
        (opts.method || 'GET') === 'GET'
      ) {
        return Promise.resolve({ users: USERS, total: USERS.length });
      }
      return Promise.resolve([]);
    });

    const wrapper = await openDelete(await mountUsers());
    // Agreeing to an unknown is worse than not offering the button.
    expect(
      wrapper.find('[data-testid="delete-confirm"]').attributes('disabled')
    ).toBeDefined();
  });
});
