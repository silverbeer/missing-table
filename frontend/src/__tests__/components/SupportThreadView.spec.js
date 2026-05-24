/**
 * SupportThreadView.vue Tests (SB-35 Phase 3)
 *
 * Pure presentational — gets `thread` (with `messages`) + `sending` via props;
 * emits `back` / `reply` / `set-status` / `mark-all-read`.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import SupportThreadView from '@/components/admin/SupportThreadView.vue';

const makeThread = (overrides = {}) => ({
  id: 'thread-uuid',
  case_number: 42,
  subject: 'My Question',
  participant_email: 'jane@example.com',
  participant_name: 'Jane Doe',
  status: 'awaiting_admin',
  unread_count: 2,
  messages: [
    {
      id: 'msg-1',
      direction: 'inbound',
      from_email: 'jane@example.com',
      from_name: 'Jane Doe',
      subject: '[MT-42] My Question',
      body_text: 'Hi support, need help.',
      body_html: '<p>Hi support, need help.</p>',
      had_attachments: false,
      created_at: '2026-05-23T12:00:00Z',
      read_at: null,
    },
    {
      id: 'msg-2',
      direction: 'outbound',
      from_email: 'support@contact.missingtable.com',
      from_name: 'Support',
      subject: 'Re: [MT-42] My Question',
      body_text: 'Hi Jane!',
      body_html: null,
      had_attachments: false,
      created_at: '2026-05-23T12:30:00Z',
      read_at: '2026-05-23T12:30:00Z',
    },
  ],
  ...overrides,
});

const mountThread = (props = {}) =>
  mount(SupportThreadView, {
    props: {
      thread: makeThread(),
      sending: false,
      ...props,
    },
  });

describe('SupportThreadView', () => {
  it('renders the case number and status pill in the header', () => {
    const wrapper = mountThread();
    expect(wrapper.find('[data-testid="thread-case-number"]').text()).toBe(
      'MT-42'
    );
    expect(wrapper.find('[data-testid="thread-status-pill"]').text()).toBe(
      'Awaiting admin'
    );
  });

  it('renders messages chronologically with direction-aware data attributes', () => {
    const wrapper = mountThread();
    const messages = wrapper.findAll('[data-direction]');
    expect(messages).toHaveLength(2);
    expect(messages[0].attributes('data-direction')).toBe('inbound');
    expect(messages[1].attributes('data-direction')).toBe('outbound');
  });

  it('renders sanitized HTML body via v-html with a data-testid hook for the regression test', () => {
    /**
     * Regression hook: the backend already sanitizes inbound HTML via bleach.
     * The data-testid below is the canonical anchor for any future test that
     * wants to verify we DON'T re-sanitize or strip content here.
     */
    const wrapper = mountThread();
    const htmlNode = wrapper.find('[data-testid="message-body-html"]');
    expect(htmlNode.exists()).toBe(true);
    expect(htmlNode.html()).toContain('<p>Hi support, need help.</p>');
  });

  it('falls back to plain text when body_html is null', () => {
    const wrapper = mountThread();
    // msg-2 has body_html=null → renders text body
    expect(wrapper.find('[data-testid="message-body-text"]').exists()).toBe(
      true
    );
  });

  it('shows the attachments-stripped notice when had_attachments is true', () => {
    const wrapper = mountThread({
      thread: makeThread({
        messages: [
          {
            id: 'm-att',
            direction: 'inbound',
            from_email: 'j@x',
            body_text: 'see attached',
            body_html: null,
            had_attachments: true,
            created_at: '2026-05-23T12:00:00Z',
          },
        ],
      }),
    });
    expect(
      wrapper.find('[data-testid="message-attachments-notice"]').exists()
    ).toBe(true);
  });

  it('emits reply with the textarea body and clears the textarea on submit', async () => {
    const wrapper = mountThread();
    const textarea = wrapper.find('[data-testid="reply-textarea"]');
    await textarea.setValue('Here is my answer.');
    await wrapper
      .find('[data-testid="reply-composer"]')
      .trigger('submit.prevent');
    expect(wrapper.emitted('reply')).toEqual([['Here is my answer.']]);
    expect(textarea.element.value).toBe('');
  });

  it('disables the submit button when sending is true', () => {
    const wrapper = mountThread({ sending: true });
    const btn = wrapper.find('[data-testid="reply-submit"]');
    expect(btn.attributes('disabled')).toBeDefined();
    expect(btn.text()).toContain('Sending');
  });

  it('disables the submit button when the textarea is empty', () => {
    const wrapper = mountThread();
    const btn = wrapper.find('[data-testid="reply-submit"]');
    expect(btn.attributes('disabled')).toBeDefined();
  });

  it('shows the Mark all read button only when unread_count > 0 and emits the event', async () => {
    const withUnread = mountThread();
    const btn = withUnread.find('[data-testid="thread-mark-all-read"]');
    expect(btn.exists()).toBe(true);
    await btn.trigger('click');
    expect(withUnread.emitted('mark-all-read')).toHaveLength(1);

    const noUnread = mountThread({ thread: makeThread({ unread_count: 0 }) });
    expect(noUnread.find('[data-testid="thread-mark-all-read"]').exists()).toBe(
      false
    );
  });

  it('emits set-status when a dropdown option is chosen', async () => {
    const wrapper = mountThread();
    await wrapper
      .find('[data-testid="thread-status-dropdown"]')
      .trigger('click');
    await wrapper
      .find('[data-testid="thread-status-resolved"]')
      .trigger('click');
    expect(wrapper.emitted('set-status')).toEqual([['resolved']]);
  });

  it('emits back when the back button is clicked', async () => {
    const wrapper = mountThread();
    await wrapper.find('[data-testid="thread-back"]').trigger('click');
    expect(wrapper.emitted('back')).toHaveLength(1);
  });
});
