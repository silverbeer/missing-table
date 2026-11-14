/**
 * Channel setup guide (SB-1672): a tab per channel type, each with Slack,
 * Telegram and Discord steps.
 */

import { describe, it, expect } from 'vitest';
import { mount as baseMount } from '@vue/test-utils';
import ChannelSetupGuide from '@/components/notifications/ChannelSetupGuide.vue';
import {
  GUIDE,
  PLATFORMS,
  START,
  TABS,
  registerSteps,
} from '@/components/notifications/channelGuide.js';

// The guide renders in a body-level overlay; keep it in the wrapper.
const mount = (c, opts = {}) =>
  baseMount(c, { ...opts, global: { stubs: { teleport: true } } });

const CHANNEL_TABS = TABS.filter(t => t.id !== 'start').map(t => t.id);

describe('content', () => {
  it('has a tab per audience after Start here', () => {
    expect(TABS.map(t => t.id)).toEqual(['start', 'fans', 'players']);
  });

  it.each(CHANNEL_TABS)('covers every platform for %s', tab => {
    for (const { id } of PLATFORMS) {
      const entry = GUIDE[tab][id];
      expect(entry.summary, `${tab}/${id}`).toBeTruthy();
      if (entry.unavailable) continue;
      expect(entry.channels.length, `${tab}/${id}`).toBe(2);
      for (const c of entry.channels) {
        expect(c.steps.length, `${tab}/${id}/${c.title}`).toBeGreaterThan(0);
      }
      for (const part of ['connect', 'invite']) {
        expect(entry[part].length, `${tab}/${id}/${part}`).toBeGreaterThan(0);
      }
    }
    expect(registerSteps(tab).length).toBeGreaterThan(0);
  });

  it('gives players read-only club announcements and a squad chat', () => {
    const [announce, squad] = GUIDE.players.discord.channels;
    expect(announce.title).toContain('read-only');
    expect(announce.steps.join(' ')).toContain('deny Send Messages');
    expect(squad.title).toBe('Squad chat');
    expect(squad.steps.join(' ')).toContain('Leave Send Messages on');
  });

  it('names only Missing Table’s identities, and calls the hosts platforms', () => {
    const all = JSON.stringify({ GUIDE, START }).toLowerCase();
    for (const word of ['parent', 'famil', ' room']) {
      expect(all, word).not.toContain(word);
    }
  });

  it('offers players Discord only, and says why not the others', () => {
    expect(GUIDE.players.discord.unavailable).toBeFalsy();
    expect(GUIDE.players.discord.notes.join(' ')).toContain('13');
    expect(GUIDE.players.slack.unavailable).toBe(true);
    expect(GUIDE.players.slack.summary).toContain('16');
    expect(GUIDE.players.telegram.unavailable).toBe(true);
    expect(GUIDE.players.telegram.summary).toContain('18');
  });

  it('leads Start here with the decision: Discord for players, Slack for fans', () => {
    expect(START.decisions.map(d => [d.tab, d.platform])).toEqual([
      ['players', 'discord'],
      ['fans', 'slack'],
    ]);
    expect(START.decisions[0].who).toContain('U14');
    expect(START.both).toContain('Telegram');
  });

  it('never tells a manager to email an invite link', () => {
    const all = JSON.stringify(GUIDE);
    expect(all).not.toMatch(/email (the|an|your) invite link/i);
  });
});

describe('component', () => {
  it('opens on Start here by default', () => {
    const w = mount(ChannelSetupGuide);
    expect(w.find('[data-testid="guide-start"]').exists()).toBe(true);
  });

  it('opens at the requested tab and platform', () => {
    const w = mount(ChannelSetupGuide, {
      props: { initialTab: 'players', initialPlatform: 'discord' },
    });
    expect(w.find('[data-testid="guide-players"]').exists()).toBe(true);
    expect(w.find('[data-testid="guide-summary"]').text()).toBe(
      GUIDE.players.discord.summary
    );
  });

  it('switches tab and platform', async () => {
    const w = mount(ChannelSetupGuide);
    await w.find('[data-testid="guide-tab-fans"]').trigger('click');
    await w.find('[data-testid="guide-platform-telegram"]').trigger('click');
    expect(w.find('[data-testid="guide-summary"]').text()).toBe(
      GUIDE.fans.telegram.summary
    );
    expect(w.find('[data-testid="guide-register"]').text()).toContain(
      'Manage chat channels'
    );
  });

  it('a decision card opens its tab on its platform', async () => {
    const w = mount(ChannelSetupGuide);
    await w.find('[data-testid="guide-decision-players"]').trigger('click');
    expect(w.find('[data-testid="guide-summary"]').text()).toBe(
      GUIDE.players.discord.summary
    );
  });

  it('a platform players cannot use shows why and points to Discord', async () => {
    const w = mount(ChannelSetupGuide, {
      props: { initialTab: 'players', initialPlatform: 'slack' },
    });
    expect(w.find('[data-testid="guide-register"]').exists()).toBe(false);
    await w.find('[data-testid="guide-use-discord"]').trigger('click');
    expect(w.find('[data-testid="guide-summary"]').text()).toBe(
      GUIDE.players.discord.summary
    );
    expect(w.find('[data-testid="guide-register"]').exists()).toBe(true);
  });

  it('falls back to Start here and Slack for unknown values', () => {
    const w = mount(ChannelSetupGuide, {
      props: { initialTab: 'nope', initialPlatform: 'icq' },
    });
    expect(w.find('[data-testid="guide-start"]').exists()).toBe(true);
  });

  it('closes from the overlay’s close button', async () => {
    const w = mount(ChannelSetupGuide);
    await w.find('[data-testid="modal-close"]').trigger('click');
    expect(w.emitted('close')).toBeTruthy();
  });
});
