/**
 * WhatsNewView tests — renders releases, chips unseen ones, marks seen on open.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { ref } from 'vue';

const loadMock = vi.fn().mockResolvedValue();
const markAllSeenMock = vi.fn();
const releasesRef = ref([]);
let isNewImpl;

vi.mock('@/composables/useChangelog', () => ({
  useChangelog: () => ({
    releases: releasesRef,
    loaded: ref(true),
    error: ref(null),
    load: loadMock,
    isNew: v => isNewImpl(v),
    markAllSeen: markAllSeenMock,
  }),
}));

import WhatsNewView from '@/components/WhatsNewView.vue';

beforeEach(() => {
  loadMock.mockClear();
  markAllSeenMock.mockClear();
  releasesRef.value = [
    {
      version: '1.4.0',
      title: 'Brackets',
      bodyHtml: '<ul><li>Follow</li></ul>',
    },
    { version: '1.3.1', title: '', bodyHtml: '<p>Baseline</p>' },
  ];
  isNewImpl = v => v === '1.4.0';
});

describe('WhatsNewView', () => {
  it('renders a row per release with rendered body', async () => {
    const wrapper = mount(WhatsNewView);
    await flushPromises();

    expect(
      wrapper.find('[data-testid="changelog-release-1.4.0"]').exists()
    ).toBe(true);
    expect(
      wrapper.find('[data-testid="changelog-release-1.3.1"]').exists()
    ).toBe(true);
    expect(wrapper.html()).toContain('Follow'); // v-html body
  });

  it('chips only releases that are new since last-seen', async () => {
    const wrapper = mount(WhatsNewView);
    await flushPromises();

    const chips = wrapper.findAll('[data-testid="changelog-new-chip"]');
    expect(chips).toHaveLength(1);
    const newRow = wrapper.find('[data-testid="changelog-release-1.4.0"]');
    expect(newRow.find('[data-testid="changelog-new-chip"]').exists()).toBe(
      true
    );
  });

  it('loads and marks all seen on open', async () => {
    mount(WhatsNewView);
    await flushPromises();
    expect(loadMock).toHaveBeenCalled();
    expect(markAllSeenMock).toHaveBeenCalled();
  });

  it('emits close on the close button', async () => {
    const wrapper = mount(WhatsNewView);
    await flushPromises();
    await wrapper.find('[data-testid="whats-new-close"]').trigger('click');
    expect(wrapper.emitted('close')).toBeTruthy();
  });
});
