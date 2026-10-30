/**
 * SupportEmailLink.vue Tests (SB-35)
 *
 * Renders the support address at runtime from JS constants so the literal
 * `support@contact.missingtable.com` string never appears in template source. Also
 * builds a properly-encoded mailto: href with optional subject + body.
 *
 * SB-1461: desktop fallbacks for browsers with no mail client — a Gmail
 * compose link and a copy-to-clipboard button.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import SupportEmailLink from '@/components/SupportEmailLink.vue';

describe('SupportEmailLink', () => {
  it('renders the support address as visible text by default', () => {
    const wrapper = mount(SupportEmailLink);
    expect(wrapper.find('[data-testid="support-email-link"]').text()).toBe(
      'support@contact.missingtable.com'
    );
  });

  it('uses displayText prop when provided instead of the raw address', () => {
    const wrapper = mount(SupportEmailLink, {
      props: { displayText: 'Contact support' },
    });
    expect(wrapper.find('[data-testid="support-email-link"]').text()).toBe(
      'Contact support'
    );
  });

  it('renders a mailto: href pointing at the support address', () => {
    const wrapper = mount(SupportEmailLink);
    const link = wrapper.find('a');
    expect(link.attributes('href')).toBe(
      'mailto:support@contact.missingtable.com'
    );
  });

  it('appends an encoded subject param when subject prop is set', () => {
    const wrapper = mount(SupportEmailLink, {
      props: { subject: '[MT-42] Login trouble' },
    });
    const href = wrapper.find('a').attributes('href');
    expect(href).toBe(
      'mailto:support@contact.missingtable.com?subject=%5BMT-42%5D%20Login%20trouble'
    );
  });

  it('appends an encoded body param when body prop is set', () => {
    const wrapper = mount(SupportEmailLink, {
      props: { body: 'Hi support team,\n\nI need help.' },
    });
    const href = wrapper.find('a').attributes('href');
    expect(href).toContain('body=Hi%20support%20team%2C%0A%0AI%20need%20help.');
  });

  it('combines subject and body with & separator', () => {
    const wrapper = mount(SupportEmailLink, {
      props: { subject: 'Hello', body: 'World' },
    });
    const href = wrapper.find('a').attributes('href');
    expect(href).toBe(
      'mailto:support@contact.missingtable.com?subject=Hello&body=World'
    );
  });

  describe('desktop fallbacks (SB-1461)', () => {
    afterEach(() => {
      vi.unstubAllGlobals();
      vi.useRealTimers();
    });

    it('links to Gmail compose addressed to support, opening in a new tab', () => {
      const wrapper = mount(SupportEmailLink);
      const gmail = wrapper.find('[data-testid="support-email-gmail"]');
      expect(gmail.attributes('href')).toBe(
        'https://mail.google.com/mail/?view=cm&fs=1&to=support%40contact.missingtable.com'
      );
      expect(gmail.attributes('target')).toBe('_blank');
      expect(gmail.attributes('rel')).toContain('noopener');
    });

    it('carries encoded subject and body into the Gmail link', () => {
      const wrapper = mount(SupportEmailLink, {
        props: { subject: '[MT-42] Help', body: 'Line 1\nLine 2' },
      });
      const href = wrapper
        .find('[data-testid="support-email-gmail"]')
        .attributes('href');
      expect(href).toContain('su=%5BMT-42%5D%20Help');
      expect(href).toContain('body=Line%201%0ALine%202');
    });

    it('copies the address to the clipboard and confirms', async () => {
      vi.useFakeTimers();
      const writeText = vi.fn().mockResolvedValue();
      vi.stubGlobal('navigator', { clipboard: { writeText } });
      const wrapper = mount(SupportEmailLink);
      const button = wrapper.find('[data-testid="support-email-copy"]');

      await button.trigger('click');
      await flushPromises();

      expect(writeText).toHaveBeenCalledWith(
        'support@contact.missingtable.com'
      );
      expect(button.text()).toBe('Copied');
      expect(
        wrapper.find('[data-testid="support-email-address"]').exists()
      ).toBe(false);

      vi.advanceTimersByTime(2000);
      await flushPromises();
      expect(button.text()).toBe('Copy address');
    });

    it('shows the address for manual selection when the clipboard fails', async () => {
      const writeText = vi.fn().mockRejectedValue(new Error('denied'));
      vi.stubGlobal('navigator', { clipboard: { writeText } });
      const wrapper = mount(SupportEmailLink);

      await wrapper.find('[data-testid="support-email-copy"]').trigger('click');
      await flushPromises();

      expect(wrapper.find('[data-testid="support-email-address"]').text()).toBe(
        'support@contact.missingtable.com'
      );
    });

    it('shows the address when the clipboard API is missing entirely', async () => {
      vi.stubGlobal('navigator', {});
      const wrapper = mount(SupportEmailLink);

      await wrapper.find('[data-testid="support-email-copy"]').trigger('click');
      await flushPromises();

      expect(
        wrapper.find('[data-testid="support-email-address"]').exists()
      ).toBe(true);
    });
  });
});
