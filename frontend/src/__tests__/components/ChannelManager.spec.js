/**
 * ChannelManager + ChannelForm (SB-1605): set up several chat channels for one
 * scope. One test per state — no channels, paused, populated — plus the
 * add / edit / pause / test / remove flows.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import ChannelManager from '@/components/notifications/ChannelManager.vue';

const apiRequest = vi.fn();

vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ apiRequest }) }));
vi.mock('@/config/api', () => ({ getApiBaseUrl: () => 'http://test' }));

const PLATFORMS = [
  {
    id: 'discord',
    label: 'Discord',
    icon: '💬',
    placeholder: 'https://discord.com/api/webhooks/…',
    destination_label: 'Webhook URL',
    setup_steps: ['Open channel settings.', 'Copy the webhook URL.'],
    destination_pattern: '^https://discord\\.com/api/webhooks/\\d+/[\\w-]+$',
    destination_error: 'Must be a Discord webhook URL',
    invite_pattern: '^https://discord\\.gg/[A-Za-z0-9]+$',
    invite_error: 'Must be a Discord invite link',
  },
  {
    id: 'telegram',
    label: 'Telegram',
    icon: '✈️',
    placeholder: '-100…',
    destination_label: 'Chat ID',
    setup_steps: ['Add the bot.'],
    destination_pattern: '^(@\\w+|-?\\d+)$',
    destination_error: 'Must be a chat ID',
    invite_pattern: '^https://t\\.me/\\+\\w+$',
    invite_error: 'Must be a private invite link',
  },
];

const EVENTS = [
  { id: 'kickoff', label: 'Kickoff' },
  { id: 'goal', label: 'Goals' },
  { id: 'fulltime', label: 'Full time' },
];

const WEBHOOK = 'https://discord.com/api/webhooks/123/abc';

const channel = overrides => ({
  id: 7,
  scope_type: 'club',
  club_id: 5,
  team_id: null,
  age_group_id: null,
  audience: 'fans',
  platform: 'discord',
  event_types: null,
  enabled: true,
  invite_url: null,
  label: null,
  hint: 'eCI-',
  last_delivery: null,
  last_delivery_known: true,
  ...overrides,
});

// Routes GETs to fixtures; writes go to `writes` so a test can set replies.
let channelRows;
let writes;
const route = (url, options = {}) => {
  const method = options.method || 'GET';
  if (method !== 'GET') return writes(url, options);
  if (url.endsWith('/notifications/platforms'))
    return Promise.resolve(PLATFORMS);
  if (url.endsWith('/notification-channels/event-types'))
    return Promise.resolve(EVENTS);
  if (url.includes('/notification-channels?'))
    return Promise.resolve(channelRows);
  return Promise.reject(new Error(`unexpected ${url}`));
};

const mountManager = async (props = { scopeType: 'club', clubId: 5 }) => {
  const wrapper = mount(ChannelManager, { props });
  await flushPromises();
  return wrapper;
};

const calls = method =>
  apiRequest.mock.calls.filter(([, o]) => (o?.method || 'GET') === method);

// A block body: a returned function would run as a cleanup hook.
beforeEach(() => {
  channelRows = [];
  writes = () => Promise.resolve({});
  apiRequest.mockReset();
  apiRequest.mockImplementation(route);
  globalThis.confirm = vi.fn(() => true);
});

describe('states', () => {
  it('no channels: says so and offers to add one', async () => {
    const w = await mountManager();
    expect(w.find('[data-testid="no-channels"]').exists()).toBe(true);
    expect(w.find('[data-testid="add-channel"]').exists()).toBe(true);
  });

  it('paused: labels the channel and resumes with PATCH', async () => {
    channelRows = [channel({ enabled: false })];
    const w = await mountManager();
    expect(w.find('[data-testid="paused-7"]').exists()).toBe(true);
    expect(
      w.find('[data-testid="test-7"]').attributes('disabled')
    ).toBeDefined();

    await w.find('[data-testid="toggle-7"]').setValue(true);
    await flushPromises();
    const [url, opts] = calls('PATCH')[0];
    expect(url).toBe('http://test/api/notification-channels/7');
    expect(JSON.parse(opts.body)).toEqual({ enabled: true });
  });

  it('populated: name, platform, audience and hint', async () => {
    channelRows = [
      channel({
        label: '#ifa-live',
        audience: 'players',
        invite_url: 'https://discord.gg/abc',
      }),
    ];
    const w = await mountManager();
    const row = w.find('[data-testid="channel-7"]');
    expect(row.text()).toContain('#ifa-live');
    expect(row.text()).toContain('Discord · Players · ends in eCI-');
    expect(w.find('[data-testid="invite-7"] a').attributes('href')).toBe(
      'https://discord.gg/abc'
    );
    expect(w.find('[data-testid="paused-7"]').exists()).toBe(false);
  });

  it('names an unlabelled channel after its platform', async () => {
    channelRows = [channel()];
    const w = await mountManager();
    expect(w.find('[data-testid="channel-7"]').text()).toContain(
      'Discord channel'
    );
  });

  it('warns when there is no invite link', async () => {
    channelRows = [channel()];
    const w = await mountManager();
    expect(w.find('[data-testid="invite-7"]').text()).toContain("can't join");
  });

  it('says so when channels cannot be loaded, and retries', async () => {
    apiRequest.mockImplementation((url, o) =>
      url.includes('/notification-channels?')
        ? Promise.reject(new Error('down'))
        : route(url, o)
    );
    const w = await mountManager();
    expect(w.find('[data-testid="load-error"]').exists()).toBe(true);

    apiRequest.mockImplementation(route);
    await w.find('[data-testid="load-error"] button').trigger('click');
    await flushPromises();
    expect(w.find('[data-testid="no-channels"]').exists()).toBe(true);
  });
});

describe('events summary: null and [] stay distinct', () => {
  it.each([
    [null, 'Every match event'],
    [[], 'Nothing: no events are selected'],
    [['goal', 'fulltime'], 'Goals, Full time'],
    [['fulltime', 'kickoff'], 'Kickoff, Full time'],
  ])('%j → %s', async (types, text) => {
    channelRows = [channel({ event_types: types })];
    const w = await mountManager();
    expect(w.find('[data-testid="events-7"]').text()).toBe(text);
  });
});

describe('last post', () => {
  it.each([
    [{ last_delivery: null, last_delivery_known: true }, 'Nothing posted yet'],
    [
      { last_delivery: null, last_delivery_known: false },
      'Delivery history unavailable',
    ],
    [
      {
        last_delivery: {
          status: 'failed',
          at: new Date().toISOString(),
          error: 'discord send failed: HTTP 404',
        },
      },
      'discord send failed: HTTP 404',
    ],
    [
      {
        last_delivery: {
          status: 'sent',
          at: new Date().toISOString(),
          error: null,
        },
      },
      'Posted',
    ],
  ])('%j', async (overrides, text) => {
    channelRows = [channel(overrides)];
    const w = await mountManager();
    expect(w.find('[data-testid="delivery-7"]').text()).toContain(text);
  });
});

describe('adding a channel', () => {
  const openForm = async w => {
    await w.find('[data-testid="add-channel"]').trigger('click');
    await flushPromises();
  };

  it('posts the scope, label and chosen events', async () => {
    let created = null;
    writes = (url, o) => {
      created = { url, body: JSON.parse(o.body) };
      return Promise.resolve(channel());
    };
    const w = await mountManager({
      scopeType: 'team',
      teamId: 3,
      ageGroupId: 9,
    });
    await openForm(w);
    await w.find('[data-testid="form-label"]').setValue('  #u15  ');
    await w.find('[data-testid="form-destination"]').setValue(WEBHOOK);
    await w.find('[data-testid="form-audience-players"]').setValue();
    await w.find('[data-testid="form-events-some"]').setValue();
    await w.find('[data-testid="form-event-goal"]').setValue(true);
    await w.find('[data-testid="channel-form"]').trigger('submit');
    await flushPromises();

    expect(created.url).toBe('http://test/api/notification-channels');
    expect(created.body).toEqual({
      scope_type: 'team',
      club_id: null,
      team_id: 3,
      age_group_id: 9,
      audience: 'players',
      platform: 'discord',
      destination: WEBHOOK,
      label: '#u15',
      invite_url: null,
      event_types: ['goal'],
    });
    expect(w.find('[data-testid="flash-success"]').exists()).toBe(true);
  });

  it('every event is null, not a list', async () => {
    let body = null;
    writes = (url, o) => {
      body = JSON.parse(o.body);
      return Promise.resolve(channel());
    };
    const w = await mountManager();
    await openForm(w);
    await w.find('[data-testid="form-destination"]').setValue(WEBHOOK);
    await w.find('[data-testid="channel-form"]').trigger('submit');
    await flushPromises();
    expect(body.event_types).toBeNull();
  });

  it('warns that no events means nothing posts', async () => {
    const w = await mountManager();
    await openForm(w);
    await w.find('[data-testid="form-events-some"]').setValue();
    expect(w.find('[data-testid="form-events-none"]').exists()).toBe(true);
  });

  it('checks the destination against the platform pattern', async () => {
    const w = await mountManager();
    await openForm(w);
    await w.find('[data-testid="form-destination"]').setValue('nope');
    expect(w.find('[data-testid="form-destination-error"]').text()).toBe(
      'Must be a Discord webhook URL'
    );
    expect(
      w.find('[data-testid="form-save"]').attributes('disabled')
    ).toBeDefined();
  });

  it('checks the invite link against the platform pattern', async () => {
    const w = await mountManager();
    await openForm(w);
    await w.find('[data-testid="form-destination"]').setValue(WEBHOOK);
    await w
      .find('[data-testid="form-invite"]')
      .setValue('https://evil.example');
    expect(w.find('[data-testid="form-invite-error"]').text()).toBe(
      'Must be a Discord invite link'
    );
  });

  it('uses the platform’s name for the destination and shows its steps', async () => {
    const w = await mountManager();
    await openForm(w);
    await w.find('[data-testid="form-platform"]').setValue('telegram');
    expect(w.find('[data-testid="channel-form"]').text()).toContain('Chat ID');
    expect(
      w.findAll('[data-testid="form-setup"] li').map(l => l.text())
    ).toEqual(['Add the bot.']);
  });

  it('shows the server’s reason when saving fails', async () => {
    writes = () =>
      Promise.reject(new Error('Slack is for players aged 17 and over'));
    const w = await mountManager();
    await openForm(w);
    await w.find('[data-testid="form-destination"]').setValue(WEBHOOK);
    await w.find('[data-testid="channel-form"]').trigger('submit');
    await flushPromises();
    expect(w.find('[data-testid="flash-error"]').text()).toContain('aged 17');
    expect(w.find('[data-testid="channel-form"]').exists()).toBe(true);
  });

  it('a global channel offers no audience and is for fans', async () => {
    let body = null;
    writes = (url, o) => {
      body = JSON.parse(o.body);
      return Promise.resolve(channel());
    };
    const w = await mountManager({ scopeType: 'global' });
    expect(
      apiRequest.mock.calls.some(([u]) =>
        u.endsWith('/notification-channels?scope_type=global')
      )
    ).toBe(true);
    await openForm(w);
    expect(w.find('[data-testid="form-audience-players"]').exists()).toBe(
      false
    );
    await w.find('[data-testid="form-destination"]').setValue(WEBHOOK);
    await w.find('[data-testid="channel-form"]').trigger('submit');
    await flushPromises();
    expect(body.audience).toBe('fans');
  });
});

describe('editing a channel', () => {
  it('keeps the destination when left blank, and clears a label', async () => {
    channelRows = [channel({ label: '#old', event_types: ['goal'] })];
    const w = await mountManager();
    await w.find('[data-testid="edit-7"]').trigger('click');
    expect(
      w.find('[data-testid="form-platform"]').attributes('disabled')
    ).toBeDefined();
    await w.find('[data-testid="form-label"]').setValue('');
    await w.find('[data-testid="channel-form"]').trigger('submit');
    await flushPromises();

    const [url, opts] = calls('PATCH')[0];
    expect(url).toBe('http://test/api/notification-channels/7');
    expect(JSON.parse(opts.body)).toEqual({
      label: null,
      invite_url: null,
      event_types: ['goal'],
    });
  });

  it('sends a replacement destination when one is typed', async () => {
    channelRows = [channel()];
    const w = await mountManager();
    await w.find('[data-testid="edit-7"]').trigger('click');
    await w
      .find('[data-testid="form-destination"]')
      .setValue('https://discord.com/api/webhooks/9/new');
    await w.find('[data-testid="channel-form"]').trigger('submit');
    await flushPromises();
    expect(JSON.parse(calls('PATCH')[0][1].body).destination).toBe(
      'https://discord.com/api/webhooks/9/new'
    );
  });
});

describe('actions', () => {
  it('pauses with PATCH, never DELETE', async () => {
    channelRows = [channel()];
    const w = await mountManager();
    await w.find('[data-testid="toggle-7"]').setValue(false);
    await flushPromises();
    expect(JSON.parse(calls('PATCH')[0][1].body)).toEqual({ enabled: false });
    expect(calls('DELETE')).toHaveLength(0);
  });

  it('sends a test and reports success', async () => {
    channelRows = [channel()];
    writes = () => Promise.resolve({ success: true, error: null });
    const w = await mountManager();
    await w.find('[data-testid="test-7"]').trigger('click');
    await flushPromises();
    expect(calls('POST')[0][0]).toBe(
      'http://test/api/notification-channels/7/test'
    );
    expect(w.find('[data-testid="flash-success"]').exists()).toBe(true);
  });

  it('reports a failed test with its reason', async () => {
    channelRows = [channel()];
    writes = () =>
      Promise.resolve({
        success: false,
        error: 'discord send failed: HTTP 404',
      });
    const w = await mountManager();
    await w.find('[data-testid="test-7"]').trigger('click');
    await flushPromises();
    expect(w.find('[data-testid="flash-error"]').text()).toContain('HTTP 404');
  });

  it('removes after confirming', async () => {
    channelRows = [channel()];
    const w = await mountManager();
    await w.find('[data-testid="remove-7"]').trigger('click');
    await flushPromises();
    expect(calls('DELETE')[0][0]).toBe(
      'http://test/api/notification-channels/7'
    );
    expect(w.emitted('changed')).toBeTruthy();
  });

  it('does nothing when removal is declined', async () => {
    channelRows = [channel()];
    globalThis.confirm = vi.fn(() => false);
    const w = await mountManager();
    await w.find('[data-testid="remove-7"]').trigger('click');
    await flushPromises();
    expect(calls('DELETE')).toHaveLength(0);
  });
});
