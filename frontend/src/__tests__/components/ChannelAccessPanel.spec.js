/**
 * ChannelAccessPanel (SB-1671): a manager's requests, members and invites.
 *
 * Every decision ends with what to do on the platform, because Missing Table
 * only controls who sees the invite link.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import ChannelAccessPanel from '@/components/notifications/ChannelAccessPanel.vue';

const apiRequest = vi.fn();

vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ apiRequest }) }));
vi.mock('@/config/api', () => ({ getApiBaseUrl: () => 'http://test' }));

const REQUEST = {
  channel_id: 5,
  user_id: 'u-1',
  display_name: 'Pat',
  requested_at: '2026-11-10T12:00:00Z',
  platform: 'slack',
  audience: 'fans',
  age_group_name: 'U15',
};
const MEMBER = {
  channel_id: 5,
  user_id: 'u-2',
  display_name: 'Sam',
  since: '2026-11-09T12:00:00Z',
  source: 'invite',
  platform: 'discord',
  audience: 'fans',
  age_group_name: 'U15',
};
const FAN_CHANNEL = {
  id: 5,
  platform: 'slack',
  platform_label: 'Slack',
  audience: 'fans',
  age_group_name: 'U15',
};

const routes = ({ requests = [], members = [], candidates = [] } = {}) =>
  apiRequest.mockImplementation((url, opts) => {
    if (opts?.method === 'PUT') return Promise.resolve({ status: 'active' });
    if (url.includes('/channels/requests')) return Promise.resolve(requests);
    if (url.includes('/channels/members')) return Promise.resolve(members);
    if (url.includes('/candidates')) return Promise.resolve(candidates);
    return Promise.reject(new Error('unexpected'));
  });

const mountPanel = async (data, fanChannels = [FAN_CHANNEL]) => {
  routes(data);
  const w = mount(ChannelAccessPanel, { props: { teamId: 10, fanChannels } });
  await flushPromises();
  return w;
};

beforeEach(() => {
  apiRequest.mockReset();
});

describe('empty', () => {
  it('says nobody is waiting and nobody has a link', async () => {
    const w = await mountPanel();
    expect(w.find('[data-testid="no-requests"]').exists()).toBe(true);
    expect(w.find('[data-testid="no-members"]').exists()).toBe(true);
  });

  it('offers no invite without a squad fan channel', async () => {
    const w = await mountPanel({}, []);
    expect(w.find('[data-testid="invite-block"]').exists()).toBe(false);
  });

  it('says so when requests cannot be loaded', async () => {
    apiRequest.mockRejectedValue(new Error('down'));
    const w = mount(ChannelAccessPanel, { props: { teamId: 10 } });
    await flushPromises();
    expect(w.find('[data-testid="access-error"]').exists()).toBe(true);
  });
});

describe('requests', () => {
  it('approves, then says what to do in Slack', async () => {
    const w = await mountPanel({ requests: [REQUEST] });
    await w.find('[data-testid="approve-btn"]').trigger('click');
    await flushPromises();
    expect(apiRequest).toHaveBeenCalledWith(
      'http://test/api/channels/5/members/u-1',
      { method: 'PUT', body: JSON.stringify({ status: 'active' }) }
    );
    expect(w.find('[data-testid="platform-notice"]').text()).toContain(
      'add Pat to the private Slack channel'
    );
    expect(w.emitted('changed')).toBeTruthy();
  });

  it('denies', async () => {
    const w = await mountPanel({ requests: [REQUEST] });
    await w.find('[data-testid="deny-btn"]').trigger('click');
    await flushPromises();
    expect(apiRequest).toHaveBeenCalledWith(
      'http://test/api/channels/5/members/u-1',
      { method: 'PUT', body: JSON.stringify({ status: 'denied' }) }
    );
  });
});

describe('members', () => {
  it('revokes and reminds the manager to remove them on the platform', async () => {
    const w = await mountPanel({ members: [MEMBER] });
    expect(w.find('[data-testid="member-u-2"]').text()).toContain('invited');
    await w.find('[data-testid="revoke-btn"]').trigger('click');
    await flushPromises();
    expect(w.find('[data-testid="platform-notice"]').text()).toContain(
      'remove them in Discord'
    );
  });
});

describe('invite', () => {
  it('invites a chosen fan to the squad channel', async () => {
    const w = await mountPanel({
      candidates: [{ user_id: 'u-3', display_name: 'Lee' }],
    });
    await w.find('[data-testid="invite-person"]').setValue('u-3');
    await w.find('[data-testid="invite-btn"]').trigger('click');
    await flushPromises();
    expect(apiRequest).toHaveBeenCalledWith(
      'http://test/api/channels/5/members/u-3',
      { method: 'PUT', body: JSON.stringify({ status: 'active' }) }
    );
  });

  it('says when there is nobody to invite', async () => {
    const w = await mountPanel();
    expect(w.find('[data-testid="invite-person"]').text()).toContain(
      'No fans to invite'
    );
    expect(
      w.find('[data-testid="invite-btn"]').attributes('disabled')
    ).toBeDefined();
  });
});
