/**
 * Invitation email delivery chip (SB-1814).
 *
 * email_status comes from Resend webhooks. An invite with no tracked email
 * (the default: no address, or sent before tracking) shows no chip at all —
 * never "Not delivered".
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ref } from 'vue';
import { mount, flushPromises } from '@vue/test-utils';
import AdminInvites from '@/components/admin/AdminInvites.vue';
import { inviteDeliveryChip, inviteDeliveryHint } from '@/utils/inviteDelivery';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

const invite = (overrides = {}) => ({
  id: 'inv-1',
  invite_code: 'ABCDEFGHJKLM',
  invite_type: 'club_fan',
  club_id: 10,
  clubs: { name: 'IFA' },
  email: 'pat@example.com',
  status: 'pending',
  created_at: '2026-11-27T00:00:00Z',
  email_status: null,
  email_status_at: null,
  email_status_detail: null,
  ...overrides,
});

const jsonResponse = body =>
  Promise.resolve({ ok: true, json: () => Promise.resolve(body) });

const mountWith = async invites => {
  global.fetch = vi.fn(url =>
    url.includes('/api/invites/my-invites')
      ? jsonResponse(invites)
      : jsonResponse([])
  );
  const wrapper = mount(AdminInvites);
  await flushPromises();
  return wrapper;
};

beforeEach(() => {
  mockAuthStore = {
    userRole: ref('admin'),
    isAdmin: ref(true),
    isClubManager: ref(false),
    getAuthHeaders: () => ({ Authorization: 'Bearer t' }),
  };
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('inviteDeliveryChip', () => {
  it.each([
    ['sent', 'Sending…', 'bg-gray-100'],
    ['delayed', 'Delayed', 'bg-amber-100'],
    ['delivered', 'Delivered', 'bg-green-100'],
    ['bounced', 'Bounced', 'bg-red-100'],
    ['failed', 'Failed', 'bg-red-100'],
    ['suppressed', 'Suppressed', 'bg-red-100'],
    ['complained', 'Spam complaint', 'bg-red-100'],
  ])('%s renders as %s', (status, label, colour) => {
    const chip = inviteDeliveryChip(invite({ email_status: status }));
    expect(chip.label).toBe(label);
    expect(chip.classes).toContain(colour);
  });

  it('renders nothing when delivery is not tracked', () => {
    expect(inviteDeliveryChip(invite())).toBeNull();
    expect(inviteDeliveryChip(invite({ email_status: undefined }))).toBeNull();
    expect(inviteDeliveryChip(invite({ email_status: 'opened' }))).toBeNull();
  });

  it('puts the bounce reason in the title', () => {
    const chip = inviteDeliveryChip(
      invite({
        email_status: 'bounced',
        email_status_detail: 'Permanent: Suppressed',
      })
    );
    expect(chip.title).toContain('Permanent: Suppressed');
  });

  it('hints only on a bounce', () => {
    expect(inviteDeliveryHint(invite({ email_status: 'bounced' }))).toBe(
      'Check the address before resending'
    );
    expect(inviteDeliveryHint(invite({ email_status: 'failed' }))).toBeNull();
    expect(inviteDeliveryHint(invite())).toBeNull();
  });
});

describe('AdminInvites delivery chip', () => {
  const row = wrapper => wrapper.find('[data-testid="invite-row-inv-1"]');

  it('shows the chip under the status', async () => {
    const wrapper = await mountWith([invite({ email_status: 'delivered' })]);
    const chip = row(wrapper).find('[data-testid="invite-delivery-chip"]');
    expect(chip.exists()).toBe(true);
    expect(chip.text()).toBe('Delivered');
    expect(
      row(wrapper).find('[data-testid="invite-delivery-hint"]').exists()
    ).toBe(false);
  });

  it('shows no chip, and no "not delivered", when status is absent', async () => {
    const wrapper = await mountWith([invite()]);
    expect(wrapper.find('[data-testid="invite-delivery-chip"]').exists()).toBe(
      false
    );
    expect(wrapper.text()).not.toMatch(/not delivered/i);
  });

  it('shows the hint on a bounced invite', async () => {
    const wrapper = await mountWith([
      invite({
        email_status: 'bounced',
        email_status_detail: 'Permanent: General',
      }),
    ]);
    const chip = row(wrapper).find('[data-testid="invite-delivery-chip"]');
    expect(chip.text()).toBe('Bounced');
    expect(chip.attributes('title')).toContain('Permanent: General');
    expect(
      row(wrapper).find('[data-testid="invite-delivery-hint"]').text()
    ).toBe('Check the address before resending');
  });
});
