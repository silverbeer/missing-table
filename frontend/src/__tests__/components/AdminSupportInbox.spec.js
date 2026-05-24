/**
 * AdminSupportInbox.vue Tests (SB-35 Phase 3)
 *
 * Parent component — swaps between list and thread view based on the
 * composable's activeThread ref. Mock the composable so we control state.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref, computed } from 'vue';
import { mount } from '@vue/test-utils';

// State refs that the mocked composable will expose. Each test overrides
// what it cares about before mounting.
const threadsRef = ref({ items: [], nextCursor: null });
const activeThreadRef = ref(null);
const unreadCountRef = ref(0);
const loadingRef = ref(false);
const sendingRef = ref(false);
const errorRef = ref(null);
const currentStatusRef = ref('new,awaiting_admin');

const loadThreads = vi.fn(() => Promise.resolve());
const openThread = vi.fn(() => Promise.resolve());
const closeThread = vi.fn(() => {
  activeThreadRef.value = null;
});
const sendReply = vi.fn(() => Promise.resolve({ id: 'new-msg' }));
const setStatus = vi.fn(() => Promise.resolve());
const markAllRead = vi.fn(() => Promise.resolve());
const startPolling = vi.fn();
const stopPolling = vi.fn();

vi.mock('@/composables/useSupportInbox', () => ({
  useSupportInbox: () => ({
    threads: threadsRef,
    activeThread: activeThreadRef,
    unreadCount: unreadCountRef,
    loading: loadingRef,
    sending: sendingRef,
    error: errorRef,
    currentStatus: currentStatusRef,
    isThreadOpen: computed(() => activeThreadRef.value !== null),
    loadThreads,
    openThread,
    closeThread,
    sendReply,
    setStatus,
    markAllRead,
    fetchUnreadCount: vi.fn(),
    startPolling,
    stopPolling,
  }),
}));

import AdminSupportInbox from '@/components/admin/AdminSupportInbox.vue';

beforeEach(() => {
  // Reset state and call counts before each test.
  threadsRef.value = { items: [], nextCursor: null };
  activeThreadRef.value = null;
  unreadCountRef.value = 0;
  loadingRef.value = false;
  sendingRef.value = false;
  errorRef.value = null;
  currentStatusRef.value = 'new,awaiting_admin';
  loadThreads.mockClear();
  openThread.mockClear();
  closeThread.mockClear();
  sendReply.mockClear();
  setStatus.mockClear();
  markAllRead.mockClear();
  startPolling.mockClear();
  stopPolling.mockClear();
});

describe('AdminSupportInbox', () => {
  it('renders the list view by default and calls loadThreads + startPolling on mount', () => {
    const wrapper = mount(AdminSupportInbox);
    expect(wrapper.find('[data-testid="support-inbox-list"]').exists()).toBe(
      true
    );
    expect(wrapper.find('[data-testid="support-thread-view"]').exists()).toBe(
      false
    );
    expect(loadThreads).toHaveBeenCalled();
    expect(startPolling).toHaveBeenCalled();
  });

  it('renders the unread badge in the header when unreadCount > 0', async () => {
    unreadCountRef.value = 5;
    const wrapper = mount(AdminSupportInbox);
    const badge = wrapper.find('[data-testid="support-inbox-unread-badge"]');
    expect(badge.exists()).toBe(true);
    expect(badge.text()).toContain('5 unread');
  });

  it('renders the thread view when activeThread is set', () => {
    activeThreadRef.value = {
      id: 'thread-uuid',
      case_number: 1,
      subject: 'x',
      participant_email: 'j@x',
      status: 'awaiting_admin',
      unread_count: 0,
      messages: [],
    };
    const wrapper = mount(AdminSupportInbox);
    expect(wrapper.find('[data-testid="support-thread-view"]').exists()).toBe(
      true
    );
    expect(wrapper.find('[data-testid="support-inbox-list"]').exists()).toBe(
      false
    );
  });

  it('calls openThread when the list emits select', async () => {
    threadsRef.value = {
      items: [
        {
          id: 'uuid-1',
          case_number: 1,
          subject: 's',
          participant_email: 'a@b',
          status: 'new',
          unread_count: 0,
          last_message_at: new Date().toISOString(),
        },
      ],
      nextCursor: null,
    };
    const wrapper = mount(AdminSupportInbox);
    await wrapper.find('[data-testid="thread-row-1"]').trigger('click');
    expect(openThread).toHaveBeenCalledWith('uuid-1');
  });

  it('routes back to the list when the thread view emits back', async () => {
    activeThreadRef.value = {
      id: 'thread-uuid',
      case_number: 1,
      subject: 'x',
      participant_email: 'j@x',
      status: 'new',
      unread_count: 0,
      messages: [],
    };
    const wrapper = mount(AdminSupportInbox);
    await wrapper.find('[data-testid="thread-back"]').trigger('click');
    expect(closeThread).toHaveBeenCalled();
  });

  it('calls sendReply when the thread view emits reply', async () => {
    activeThreadRef.value = {
      id: 'thread-uuid',
      case_number: 1,
      subject: 'x',
      participant_email: 'j@x',
      status: 'awaiting_admin',
      unread_count: 0,
      messages: [],
    };
    const wrapper = mount(AdminSupportInbox);
    const textarea = wrapper.find('[data-testid="reply-textarea"]');
    await textarea.setValue('My reply');
    await wrapper
      .find('[data-testid="reply-composer"]')
      .trigger('submit.prevent');
    expect(sendReply).toHaveBeenCalledWith('My reply');
  });

  it('shows an error banner when the composable error ref is set', () => {
    errorRef.value = 'something went wrong';
    const wrapper = mount(AdminSupportInbox);
    expect(wrapper.text()).toContain('something went wrong');
  });

  it('calls openThread with the searched MT-N when the list emits search', async () => {
    const wrapper = mount(AdminSupportInbox);
    const input = wrapper.find('[data-testid="support-inbox-search"]');
    await input.setValue('42');
    await wrapper.find('form').trigger('submit.prevent');
    expect(openThread).toHaveBeenCalledWith('MT-42');
  });

  it('stops polling on unmount', () => {
    const wrapper = mount(AdminSupportInbox);
    wrapper.unmount();
    expect(stopPolling).toHaveBeenCalled();
  });
});
