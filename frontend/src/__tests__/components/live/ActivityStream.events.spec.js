/**
 * ActivityStream — lineup events render as events, not chat (SB-1354).
 * Substitution and position_change rows show the minute and message,
 * never the chat Report/Block actions; only 'message' is chat.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import ActivityStream from '@/components/live/ActivityStream.vue';

const sub = {
  id: 10,
  event_type: 'substitution',
  team_id: 1,
  match_minute: 55,
  extra_time: null,
  created_by: 'them-id',
  message: 'SUB: Sam → Josh',
};
const pos = {
  id: 11,
  event_type: 'position_change',
  player_id: 7,
  position: 'ST',
  match_minute: 45,
  extra_time: 2,
  created_by: 'them-id',
  message: 'POS: Josh → ST',
};
const weird = {
  id: 12,
  event_type: 'something_new',
  created_by: 'them-id',
  message: 'mystery',
};

const mountStream = (props = {}) =>
  mount(ActivityStream, {
    props: {
      events: [sub, pos, weird],
      homeTeamId: 1,
      currentUserId: 'me-id',
      ...props,
    },
  });

const row = (wrapper, index) => wrapper.findAll('.event')[index];

describe('ActivityStream lineup events', () => {
  it('renders a substitution with its minute and message', () => {
    const r = row(mountStream(), 0);
    expect(r.classes()).toContain('event-substitution');
    expect(r.find('.sub-icon').exists()).toBe(true);
    expect(r.find('.match-minute').text()).toBe("55'");
    expect(r.find('.lineup-message').text()).toBe('SUB: Sam → Josh');
    expect(r.find('.team-badge').text()).toBe('HOME');
  });

  it('renders a position change with stoppage-time minute', () => {
    const r = row(mountStream(), 1);
    expect(r.classes()).toContain('event-position_change');
    expect(r.find('.position-icon').exists()).toBe(true);
    expect(r.find('.match-minute').text()).toBe("45+2'");
    expect(r.find('.lineup-message').text()).toBe('POS: Josh → ST');
  });

  it('shows no chat actions or username on non-message events', () => {
    const wrapper = mountStream({ canDelete: true });
    expect(wrapper.find('[data-testid="chat-actions"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="report-message"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="delete-message"]').exists()).toBe(false);
    expect(wrapper.find('.username').exists()).toBe(false);
    expect(wrapper.find('.message-icon').exists()).toBe(false);
  });

  it('renders an unknown type as a neutral event row', () => {
    const r = row(mountStream(), 2);
    expect(r.find('.other-icon').exists()).toBe(true);
    expect(r.find('.other-message').text()).toBe('mystery');
  });

  it('lets managers delete lineup events', async () => {
    const wrapper = mountStream({ canDelete: true });
    const btn = row(wrapper, 0).find('[data-testid="delete-event"]');
    expect(btn.exists()).toBe(true);
    await btn.trigger('click');
    expect(wrapper.emitted('delete-event')[0]).toEqual([10]);
    expect(row(wrapper, 1).find('[data-testid="delete-event"]').exists()).toBe(
      true
    );
  });

  it('hides delete on lineup events for non-managers', () => {
    const wrapper = mountStream();
    expect(wrapper.find('[data-testid="delete-event"]').exists()).toBe(false);
  });
});
