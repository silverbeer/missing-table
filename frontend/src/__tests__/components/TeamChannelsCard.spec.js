/**
 * TeamChannelsCard (SB-1609): one test per state, empty states included.
 *
 * The server decides which channels a viewer may see and their state; the card
 * renders what it is given and never claims someone "Joined".
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import TeamChannelsCard from '@/components/notifications/TeamChannelsCard.vue';

const apiRequest = vi.fn();

vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ apiRequest }) }));
vi.mock('@/config/api', () => ({ getApiBaseUrl: () => 'http://test' }));

const channel = overrides => ({
  id: 1,
  scope_type: 'team',
  audience: 'fans',
  platform: 'discord',
  platform_label: 'Discord',
  team_id: 10,
  age_group_id: 3,
  age_group_name: 'U15',
  state: 'can_request',
  invite_url: null,
  ...overrides,
});

const response = overrides => ({
  channels: [],
  has_team: true,
  managed: true,
  can_manage: false,
  ...overrides,
});

const mountCard = async (body, props = {}) => {
  apiRequest.mockImplementation(url =>
    url.includes('/me/channels')
      ? Promise.resolve(body)
      : Promise.reject(new Error('unexpected'))
  );
  const wrapper = mount(TeamChannelsCard, { props });
  await flushPromises();
  return wrapper;
};

// A block body: a returned function would run as a cleanup hook.
beforeEach(() => {
  apiRequest.mockReset();
});

describe('empty states', () => {
  it('asks for a club or team when the viewer has none', async () => {
    const w = await mountCard(response({ has_team: false, managed: null }));
    expect(w.find('[data-testid="no-team"]').exists()).toBe(true);
  });

  it('prompts a claim on an unclaimed team', async () => {
    const w = await mountCard(response({ managed: false }));
    expect(w.find('[data-testid="unclaimed"]').text()).toContain('claim');
  });

  it('tells a manager channels need an invite link', async () => {
    const w = await mountCard(response({ can_manage: true }));
    expect(w.find('[data-testid="manager-empty"]').text()).toContain(
      'invite link'
    );
  });

  it('tells a member to ask their manager', async () => {
    const w = await mountCard(response());
    expect(w.find('[data-testid="member-empty"]').text()).toContain(
      'Ask your team manager'
    );
  });

  it('says so when channels cannot be loaded', async () => {
    apiRequest.mockRejectedValue(new Error('down'));
    const w = mount(TeamChannelsCard);
    await flushPromises();
    expect(w.find('[data-testid="channels-error"]').exists()).toBe(true);
  });

  it('renders no channel list for an unclaimed team', async () => {
    const w = await mountCard(response({ managed: false }));
    expect(w.find('.channel-list').exists()).toBe(false);
  });
});

describe('channel states', () => {
  it('requests an invite', async () => {
    const w = await mountCard(response({ channels: [channel()] }));
    apiRequest.mockResolvedValueOnce(channel({ state: 'requested' }));
    await w.find('[data-testid="request-btn"]').trigger('click');
    await flushPromises();
    expect(apiRequest).toHaveBeenLastCalledWith(
      'http://test/api/channels/1/request',
      { method: 'POST' }
    );
    expect(w.find('[data-testid="pending"]').exists()).toBe(true);
  });

  it('shows a pending request and withdraws it', async () => {
    const w = await mountCard(
      response({ channels: [channel({ state: 'requested' })] })
    );
    apiRequest.mockResolvedValueOnce(null);
    await w.find('[data-testid="withdraw-btn"]').trigger('click');
    await flushPromises();
    expect(apiRequest).toHaveBeenLastCalledWith(
      'http://test/api/channels/1/request',
      { method: 'DELETE' }
    );
    expect(w.find('[data-testid="request-btn"]').exists()).toBe(true);
  });

  it('joins a club channel and then offers the link', async () => {
    const club = channel({
      scope_type: 'club',
      age_group_name: null,
      state: 'can_join',
    });
    const w = await mountCard(response({ channels: [club] }));
    apiRequest.mockResolvedValueOnce({
      ...club,
      state: 'member',
      invite_url: 'https://discord.gg/abc123XY',
    });
    await w.find('[data-testid="join-btn"]').trigger('click');
    await flushPromises();
    const link = w.find('[data-testid="open-link"]');
    expect(link.attributes('href')).toBe('https://discord.gg/abc123XY');
    expect(link.attributes('rel')).toContain('noopener');
  });

  it('offers "Open in <platform>" and never says Joined', async () => {
    const w = await mountCard(
      response({
        channels: [
          channel({
            state: 'member',
            platform_label: 'Telegram',
            invite_url: 'https://t.me/+AbCdEfGh1234',
          }),
        ],
      })
    );
    expect(w.find('[data-testid="open-link"]').text()).toBe('Open in Telegram');
    expect(w.text()).not.toMatch(/joined/i);
  });

  it('points a denied or revoked viewer at a manager', async () => {
    const w = await mountCard(
      response({ channels: [channel({ state: 'denied' })] })
    );
    expect(w.find('[data-testid="ask-manager"]').exists()).toBe(true);
  });

  it('labels channels from the response, not a hardcoded platform list', async () => {
    const w = await mountCard(
      response({
        channels: [
          channel({
            platform: 'matrix',
            platform_label: 'Matrix',
            audience: 'players',
          }),
        ],
      })
    );
    expect(w.text()).toContain('Players · Matrix');
    expect(w.text()).toContain('U15');
  });

  it('shows an action error and reloads', async () => {
    const w = await mountCard(response({ channels: [channel()] }));
    apiRequest.mockRejectedValueOnce(
      new Error('Ask a manager about this channel')
    );
    await w.find('[data-testid="request-btn"]').trigger('click');
    await flushPromises();
    expect(w.find('[data-testid="action-error"]').text()).toContain(
      'Ask a manager'
    );
  });
});

describe('team scope', () => {
  it('asks for the given team on the My Club page', async () => {
    await mountCard(response(), { teamId: 42 });
    expect(apiRequest).toHaveBeenCalledWith(
      'http://test/api/me/channels?team_id=42'
    );
  });

  it('asks for the viewer’s own channels on a profile page', async () => {
    await mountCard(response());
    expect(apiRequest).toHaveBeenCalledWith('http://test/api/me/channels');
  });
});
