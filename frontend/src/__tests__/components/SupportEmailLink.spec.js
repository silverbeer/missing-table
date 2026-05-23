/**
 * SupportEmailLink.vue Tests (SB-35)
 *
 * Renders the support address at runtime from JS constants so the literal
 * `support@contact.missingtable.com` string never appears in template source. Also
 * builds a properly-encoded mailto: href with optional subject + body.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import SupportEmailLink from '@/components/SupportEmailLink.vue';

describe('SupportEmailLink', () => {
  it('renders the support address as visible text by default', () => {
    const wrapper = mount(SupportEmailLink);
    expect(wrapper.text()).toBe('support@contact.missingtable.com');
  });

  it('uses displayText prop when provided instead of the raw address', () => {
    const wrapper = mount(SupportEmailLink, {
      props: { displayText: 'Contact support' },
    });
    expect(wrapper.text()).toBe('Contact support');
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
});
