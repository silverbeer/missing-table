/**
 * SupportInboxList.vue Tests (SB-35 Phase 3)
 *
 * Pure presentational component — receives `threads`, `loading`, `currentStatus`
 * via props and emits `select` / `filter` / `load-more` / `search`.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import SupportInboxList from '@/components/admin/SupportInboxList.vue';

const baseThread = (overrides = {}) => ({
  id: 'uuid-1',
  case_number: 1,
  subject: 'My Question',
  participant_email: 'jane@example.com',
  participant_name: 'Jane Doe',
  status: 'awaiting_admin',
  unread_count: 2,
  last_message_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
  message_count: 3,
  ...overrides,
});

const mountList = (props = {}) =>
  mount(SupportInboxList, {
    props: {
      threads: { items: [], nextCursor: null },
      loading: false,
      currentStatus: 'new,awaiting_admin',
      ...props,
    },
  });

describe('SupportInboxList', () => {
  it('renders the empty state when no threads', () => {
    const wrapper = mountList();
    expect(wrapper.find('[data-testid="support-inbox-empty"]').exists()).toBe(
      true
    );
  });

  it('renders a row per thread with case number, status pill, and participant', () => {
    const wrapper = mountList({
      threads: {
        items: [
          baseThread(),
          baseThread({ id: 'uuid-2', case_number: 2, status: 'new' }),
        ],
        nextCursor: null,
      },
    });
    expect(wrapper.find('[data-testid="thread-row-1"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="thread-row-2"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="thread-case-1"]').text()).toBe('MT-1');
    expect(wrapper.text()).toContain('Jane Doe');
    expect(wrapper.text()).toContain('jane@example.com');
  });

  it('emits select with the thread id when a row is clicked', async () => {
    const wrapper = mountList({
      threads: { items: [baseThread()], nextCursor: null },
    });
    await wrapper.find('[data-testid="thread-row-1"]').trigger('click');
    expect(wrapper.emitted('select')).toEqual([['uuid-1']]);
  });

  it('emits filter with the tab status when a status tab is clicked', async () => {
    const wrapper = mountList();
    await wrapper.find('[data-testid="status-tab-resolved"]').trigger('click');
    expect(wrapper.emitted('filter')).toEqual([['resolved']]);
  });

  it('emits search with normalized MT-N form on Go submit', async () => {
    const wrapper = mountList();
    const input = wrapper.find('[data-testid="support-inbox-search"]');
    await input.setValue('42');
    await wrapper.find('form').trigger('submit.prevent');
    expect(wrapper.emitted('search')).toEqual([['MT-42']]);
  });

  it('also accepts already-formatted MT-N input', async () => {
    const wrapper = mountList();
    const input = wrapper.find('[data-testid="support-inbox-search"]');
    await input.setValue('mt-7');
    await wrapper.find('form').trigger('submit.prevent');
    expect(wrapper.emitted('search')).toEqual([['MT-7']]);
  });

  it('shows the load-more button only when nextCursor is present', () => {
    const withCursor = mountList({
      threads: { items: [baseThread()], nextCursor: 'opaque-token' },
    });
    expect(
      withCursor.find('[data-testid="support-inbox-load-more"]').exists()
    ).toBe(true);

    const noCursor = mountList({
      threads: { items: [baseThread()], nextCursor: null },
    });
    expect(
      noCursor.find('[data-testid="support-inbox-load-more"]').exists()
    ).toBe(false);
  });

  it('emits load-more when the button is clicked', async () => {
    const wrapper = mountList({
      threads: { items: [baseThread()], nextCursor: 'opaque-token' },
    });
    await wrapper
      .find('[data-testid="support-inbox-load-more"]')
      .trigger('click');
    expect(wrapper.emitted('load-more')).toHaveLength(1);
  });

  it('shows the unread badge per row when unread_count > 0', () => {
    const wrapper = mountList({
      threads: {
        items: [
          baseThread({ unread_count: 3 }),
          baseThread({ id: 'uuid-2', case_number: 2, unread_count: 0 }),
        ],
        nextCursor: null,
      },
    });
    expect(wrapper.find('[data-testid="thread-unread-1"]').text()).toBe('3');
    expect(wrapper.find('[data-testid="thread-unread-2"]').exists()).toBe(
      false
    );
  });
});
