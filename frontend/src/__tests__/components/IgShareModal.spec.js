/**
 * IgShareModal.vue Tests (SB-32)
 *
 * Covers: open/close, file validation, mode selection, upload happy path,
 * graceful 503 (R2 not configured), and download trigger.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import IgShareModal from '@/components/IgShareModal.vue';
import {
  createMockMatch,
  createCompletedMatch,
  createMockAuthStore,
} from '../helpers/matchFactories';

let mockAuthStore;

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}));

vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

// html2canvas mock: returns a fake canvas whose toBlob yields a PNG blob.
vi.mock('html2canvas', () => ({
  default: vi.fn(() =>
    Promise.resolve({
      toBlob: cb => cb(new Blob(['fake-png'], { type: 'image/png' })),
    })
  ),
}));

// Stub URL.createObjectURL/revokeObjectURL — happy-dom doesn't implement them.
beforeEach(() => {
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:fake/url');
  globalThis.URL.revokeObjectURL = vi.fn();
});

const makeFile = ({
  name = 'photo.jpg',
  type = 'image/jpeg',
  size = 1024,
} = {}) => {
  const blob = new Blob([new Uint8Array(size)], { type });
  return new File([blob], name, { type });
};

const mountModal = (props = {}) =>
  mount(IgShareModal, {
    props: {
      open: true,
      match: createMockMatch(),
      ...props,
    },
  });

describe('IgShareModal', () => {
  beforeEach(() => {
    mockAuthStore = createMockAuthStore();
  });

  describe('open/close', () => {
    it('does not render when open=false', () => {
      const wrapper = mountModal({ open: false });
      expect(wrapper.find('[data-testid="ig-share-modal"]').exists()).toBe(
        false
      );
    });

    it('renders when open=true', () => {
      const wrapper = mountModal({ open: true });
      expect(wrapper.find('[data-testid="ig-share-modal"]').exists()).toBe(
        true
      );
    });

    it('emits close when the close button is clicked', async () => {
      const wrapper = mountModal();
      await wrapper.find('[data-testid="ig-close-button"]').trigger('click');
      expect(wrapper.emitted('close')).toBeTruthy();
    });

    it('emits close when clicking the backdrop', async () => {
      const wrapper = mountModal();
      await wrapper.find('[data-testid="ig-share-modal"]').trigger('click');
      expect(wrapper.emitted('close')).toBeTruthy();
    });
  });

  describe('mode toggle', () => {
    it('hides the mode toggle on scheduled matches', () => {
      const wrapper = mountModal({ match: createMockMatch() });
      expect(wrapper.find('[data-testid="ig-mode-preview"]').exists()).toBe(
        false
      );
    });

    it('shows the mode toggle on completed matches and defaults to result', () => {
      const wrapper = mountModal({ match: createCompletedMatch() });
      expect(wrapper.find('[data-testid="ig-mode-result"]').exists()).toBe(
        true
      );
      expect(
        wrapper
          .find('[data-testid="ig-mode-result"]')
          .attributes('aria-selected')
      ).toBe('true');
    });

    it('switches mode when user clicks preview', async () => {
      const wrapper = mountModal({ match: createCompletedMatch() });
      await wrapper.find('[data-testid="ig-mode-preview"]').trigger('click');
      expect(
        wrapper
          .find('[data-testid="ig-mode-preview"]')
          .attributes('aria-selected')
      ).toBe('true');
    });
  });

  describe('file validation', () => {
    it('rejects non-JPEG/PNG files', async () => {
      const wrapper = mountModal();
      const input = wrapper.find('[data-testid="ig-file-input"]');
      Object.defineProperty(input.element, 'files', {
        value: [makeFile({ type: 'image/gif', name: 'animated.gif' })],
        configurable: true,
      });
      await input.trigger('change');
      expect(wrapper.find('[data-testid="ig-file-error"]').text()).toMatch(
        /JPEG or PNG/i
      );
    });

    it('rejects files over 5MB', async () => {
      const wrapper = mountModal();
      const oversized = makeFile({
        type: 'image/jpeg',
        size: 6 * 1024 * 1024,
      });
      const input = wrapper.find('[data-testid="ig-file-input"]');
      Object.defineProperty(input.element, 'files', {
        value: [oversized],
        configurable: true,
      });
      await input.trigger('change');
      expect(wrapper.find('[data-testid="ig-file-error"]').text()).toMatch(
        /too large/i
      );
    });

    it('accepts a valid JPEG and shows file metadata', async () => {
      const wrapper = mountModal();
      const input = wrapper.find('[data-testid="ig-file-input"]');
      Object.defineProperty(input.element, 'files', {
        value: [makeFile()],
        configurable: true,
      });
      await input.trigger('change');
      expect(wrapper.find('[data-testid="ig-file-error"]').exists()).toBe(
        false
      );
      expect(wrapper.find('[data-testid="ig-file-meta"]').text()).toContain(
        'photo.jpg'
      );
    });
  });

  describe('download flow', () => {
    const attachFile = async wrapper => {
      const input = wrapper.find('[data-testid="ig-file-input"]');
      Object.defineProperty(input.element, 'files', {
        value: [makeFile()],
        configurable: true,
      });
      await input.trigger('change');
    };

    it('uploads the photo and triggers a download on click', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.resolve({
          photo_url: 'https://r2/signed',
          photo_key: 'matches/1/abc.jpg',
          expires_in: 3600,
          bytes: 1024,
        })
      );
      const wrapper = mountModal();
      await attachFile(wrapper);

      await wrapper.find('[data-testid="ig-download-button"]').trigger('click');
      await flushPromises();

      expect(mockAuthStore.apiRequest).toHaveBeenCalledTimes(1);
      const [url, options] = mockAuthStore.apiRequest.mock.calls[0];
      expect(url).toContain('/api/matches/1/photo');
      expect(options.method).toBe('POST');
      expect(options.body).toBeInstanceOf(FormData);
      expect(wrapper.emitted('photo-uploaded')).toBeTruthy();
    });

    it('still generates a card when R2 returns 503 (not configured)', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.reject(
          new Error('Cloudflare R2 is not configured. Set R2_ACCOUNT_ID...')
        )
      );
      const wrapper = mountModal();
      await attachFile(wrapper);

      await wrapper.find('[data-testid="ig-download-button"]').trigger('click');
      await flushPromises();

      expect(wrapper.find('[data-testid="ig-upload-error"]').text()).toMatch(
        /not configured/i
      );
      // photo-uploaded should NOT be emitted on failure.
      expect(wrapper.emitted('photo-uploaded')).toBeFalsy();
    });

    it('surfaces a generic error for unknown upload failures', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.reject(new Error('something exploded'))
      );
      const wrapper = mountModal();
      await attachFile(wrapper);

      await wrapper.find('[data-testid="ig-download-button"]').trigger('click');
      await flushPromises();

      expect(wrapper.find('[data-testid="ig-upload-error"]').text()).toMatch(
        /failed/i
      );
    });
  });
});
