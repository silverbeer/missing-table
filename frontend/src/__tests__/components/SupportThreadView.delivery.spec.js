/**
 * SupportThreadView delivery chip (SB-1821)
 *
 * Each outbound reply shows its Resend delivery status under the bubble.
 * email_status null means not tracked and renders nothing; inbound messages
 * never carry a chip.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import SupportThreadView from '@/components/admin/SupportThreadView.vue';
import { emailDeliveryChip } from '@/utils/emailDelivery';

const inbound = (overrides = {}) => ({
  id: 'in-1',
  direction: 'inbound',
  from_email: 'jane@example.com',
  body_text: 'Help please',
  created_at: '2026-11-27T12:00:00Z',
  ...overrides,
});

const outbound = (overrides = {}) => ({
  id: 'out-1',
  direction: 'outbound',
  from_email: 'support@contact.missingtable.com',
  body_text: 'Here you go',
  created_at: '2026-11-27T12:30:00Z',
  email_status: null,
  ...overrides,
});

const mountWith = messages =>
  mount(SupportThreadView, {
    props: {
      thread: {
        id: 't-1',
        case_number: 7,
        subject: 'Q',
        participant_email: 'jane@example.com',
        status: 'awaiting_user',
        unread_count: 0,
        messages,
      },
    },
  });

describe('SupportThreadView delivery chip', () => {
  it.each([
    ['sent', 'Sending…'],
    ['delayed', 'Delayed'],
    ['delivered', 'Delivered'],
    ['bounced', 'Bounced'],
    ['failed', 'Failed'],
    ['suppressed', 'Suppressed'],
    ['complained', 'Spam complaint'],
  ])('shows %s as "%s" under an outbound reply', (status, label) => {
    const wrapper = mountWith([outbound({ email_status: status })]);
    const chip = wrapper.find('[data-testid="message-delivery-out-1"]');
    expect(chip.exists()).toBe(true);
    expect(chip.text()).toBe(label);
  });

  it('renders nothing when the reply is not tracked', () => {
    const wrapper = mountWith([
      outbound({ email_status: null }),
      outbound({ id: 'out-2', email_status: undefined }),
    ]);
    expect(wrapper.find('[data-testid^="message-delivery-"]').exists()).toBe(
      false
    );
  });

  it('never puts a chip on an inbound message', () => {
    const wrapper = mountWith([inbound({ email_status: 'delivered' })]);
    expect(wrapper.find('[data-testid^="message-delivery-"]').exists()).toBe(
      false
    );
  });

  it('chips only the outbound bubble in a mixed thread', () => {
    const wrapper = mountWith([
      inbound(),
      outbound({ email_status: 'delivered' }),
    ]);
    const chips = wrapper.findAll('[data-testid^="message-delivery-"]');
    expect(chips).toHaveLength(1);
    expect(
      wrapper
        .find('[data-testid="message-out-1"]')
        .find('[data-testid="message-delivery-out-1"]')
        .exists()
    ).toBe(true);
  });

  it('carries the bounce reason in the title', () => {
    const wrapper = mountWith([
      outbound({
        email_status: 'bounced',
        email_status_detail: 'Permanent: General',
      }),
    ]);
    expect(
      wrapper.find('[data-testid="message-delivery-out-1"]').attributes('title')
    ).toBe('Email bounced: Permanent: General');
  });
});

describe('emailDeliveryChip', () => {
  it('is null for an unknown or absent status', () => {
    expect(emailDeliveryChip(null)).toBeNull();
    expect(emailDeliveryChip({})).toBeNull();
    expect(emailDeliveryChip({ email_status: 'opened' })).toBeNull();
  });
});
