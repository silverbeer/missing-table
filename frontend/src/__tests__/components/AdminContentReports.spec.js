/**
 * AdminContentReports.vue — chat report review queue (SB-1324).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import AdminContentReports from '@/components/admin/AdminContentReports.vue';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({ getApiBaseUrl: () => 'http://api' }));

const report = (id, status, extra = {}) => ({
  id,
  status,
  reason: 'harassment',
  match_id: 10,
  event_id: 100 + id,
  reported_user_id: `author-${id}`,
  reported_username: `author${id}`,
  message_text: `message ${id}`,
  details: null,
  action: null,
  created_at: `2026-10-1${id}T10:00:00Z`,
  ...extra,
});

let reports;

beforeEach(() => {
  reports = [
    report(1, 'dismissed', { action: 'dismiss' }),
    report(2, 'pending'),
    report(3, 'pending', { reported_user_id: null }),
  ];
  mockAuthStore = {
    apiRequest: vi.fn((url, opts = {}) => {
      if (opts.method === 'PATCH') {
        const id = Number(url.split('/').pop());
        const { action } = JSON.parse(opts.body);
        return Promise.resolve({
          ...reports.find(r => r.id === id),
          status: action === 'dismiss' ? 'dismissed' : 'actioned',
          action,
        });
      }
      return Promise.resolve(reports);
    }),
  };
});

async function mountQueue() {
  const wrapper = mount(AdminContentReports);
  await flushPromises();
  return wrapper;
}

const patchCalls = () =>
  mockAuthStore.apiRequest.mock.calls.filter(([, o]) => o?.method === 'PATCH');

describe('AdminContentReports', () => {
  it('lists pending reports first', async () => {
    const wrapper = await mountQueue();
    const ids = wrapper
      .findAll('[data-testid^="report-"]')
      .map(n => n.attributes('data-testid'))
      .filter(t => /^report-\d+$/.test(t));
    expect(ids).toEqual(['report-3', 'report-2', 'report-1']);
    expect(wrapper.find('[data-testid="pending-count"]').text()).toContain('2');
  });

  it('dismisses with one PATCH', async () => {
    const wrapper = await mountQueue();
    await wrapper.find('[data-testid="dismiss-2"]').trigger('click');
    await flushPromises();

    expect(patchCalls()).toHaveLength(1);
    const [url, opts] = patchCalls()[0];
    expect(url).toBe('http://api/api/admin/content-reports/2');
    expect(JSON.parse(opts.body)).toEqual({ action: 'dismiss' });
    expect(wrapper.find('[data-testid="dismiss-2"]').exists()).toBe(false);
  });

  it('deletes the message only after confirming', async () => {
    const wrapper = await mountQueue();
    await wrapper.find('[data-testid="delete-message-2"]').trigger('click');
    expect(patchCalls()).toHaveLength(0);

    wrapper.findComponent({ name: 'ConfirmModal' }).vm.$emit('confirm');
    await flushPromises();

    expect(JSON.parse(patchCalls()[0][1].body)).toEqual({
      action: 'delete_message',
    });
  });

  it('bans the author only after confirming', async () => {
    const wrapper = await mountQueue();
    await wrapper.find('[data-testid="ban-user-2"]').trigger('click');
    expect(patchCalls()).toHaveLength(0);

    wrapper.findComponent({ name: 'ConfirmModal' }).vm.$emit('confirm');
    await flushPromises();

    expect(JSON.parse(patchCalls()[0][1].body)).toEqual({ action: 'ban_user' });
  });

  it('cancelling the confirmation sends nothing', async () => {
    const wrapper = await mountQueue();
    await wrapper.find('[data-testid="ban-user-2"]').trigger('click');
    wrapper.findComponent({ name: 'ConfirmModal' }).vm.$emit('cancel');
    await flushPromises();
    expect(patchCalls()).toHaveLength(0);
  });

  it("offers no ban when the author's account is gone", async () => {
    const wrapper = await mountQueue();
    expect(wrapper.find('[data-testid="ban-user-3"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="delete-message-3"]').exists()).toBe(
      true
    );
  });

  it('shows no actions on a resolved report', async () => {
    const wrapper = await mountQueue();
    expect(wrapper.find('[data-testid="dismiss-1"]').exists()).toBe(false);
  });

  it('filters by status through the API', async () => {
    const wrapper = await mountQueue();
    await wrapper
      .find('[data-testid="report-status-filter"]')
      .setValue('pending');
    await flushPromises();
    expect(mockAuthStore.apiRequest).toHaveBeenLastCalledWith(
      'http://api/api/admin/content-reports?status=pending'
    );
  });
});
