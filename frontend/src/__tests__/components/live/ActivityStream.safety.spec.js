/**
 * ActivityStream — chat safety actions (SB-1324).
 * Report and Block on other people's chat; Delete on your own.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import ActivityStream from '@/components/live/ActivityStream.vue';

const ME = 'me-id';
const mine = {
  id: 1,
  event_type: 'message',
  created_by: ME,
  created_by_username: 'me',
  message: 'mine',
};
const theirs = {
  id: 2,
  event_type: 'message',
  created_by: 'them-id',
  created_by_username: 'them',
  message: 'theirs',
};

const mountStream = (props = {}) =>
  mount(ActivityStream, {
    props: {
      events: [mine, theirs],
      homeTeamId: 1,
      currentUserId: ME,
      ...props,
    },
  });

const row = (wrapper, index) => wrapper.findAll('.event')[index];

describe('ActivityStream chat actions', () => {
  it('shows Delete, not Report or Block, on your own message', () => {
    const r = row(mountStream(), 0);
    expect(r.find('[data-testid="delete-message"]').exists()).toBe(true);
    expect(r.find('[data-testid="report-message"]').exists()).toBe(false);
    expect(r.find('[data-testid="block-user"]').exists()).toBe(false);
  });

  it("shows Report and Block, not Delete, on someone else's message", () => {
    const r = row(mountStream(), 1);
    expect(r.find('[data-testid="report-message"]').exists()).toBe(true);
    expect(r.find('[data-testid="block-user"]').exists()).toBe(true);
    expect(r.find('[data-testid="delete-message"]').exists()).toBe(false);
  });

  it("a manager can still delete someone else's message", () => {
    const r = row(mountStream({ canDelete: true }), 1);
    expect(r.find('[data-testid="delete-message"]').exists()).toBe(true);
    expect(r.find('[data-testid="report-message"]').exists()).toBe(true);
  });

  it('shows no chat actions when signed out', () => {
    const wrapper = mountStream({ currentUserId: null });
    expect(wrapper.find('[data-testid="chat-actions"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="delete-message"]').exists()).toBe(false);
  });

  it('emits the event for Report and Block', async () => {
    const wrapper = mountStream();
    await row(wrapper, 1)
      .find('[data-testid="report-message"]')
      .trigger('click');
    await row(wrapper, 1).find('[data-testid="block-user"]').trigger('click');
    expect(wrapper.emitted('report-event')[0]).toEqual([theirs]);
    expect(wrapper.emitted('block-user')[0]).toEqual([theirs]);
  });

  it('offers no Block on a message with no recorded author', () => {
    const anon = { ...theirs, id: 3, created_by: null };
    const r = row(mountStream({ events: [anon] }), 0);
    expect(r.find('[data-testid="report-message"]').exists()).toBe(true);
    expect(r.find('[data-testid="block-user"]').exists()).toBe(false);
  });
});
