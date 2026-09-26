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
