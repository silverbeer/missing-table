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

// Defaults to the manager case (canPersistPhoto: true) because most of
// these tests exercise the photo-upload path. SB-659 made persistence
// opt-in, so a viewer without edit rights skips the upload entirely —
// covered separately in the "photo persistence permission" block.
const mountModal = (props = {}) =>
  mount(IgShareModal, {
    props: {
      open: true,
      match: createMockMatch(),
      canPersistPhoto: true,
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

  describe('template picker', () => {
    it('always shows overlay, split, and stadium options', () => {
      const wrapper = mountModal();
      expect(wrapper.find('[data-testid="ig-template-overlay"]').exists()).toBe(
        true
      );
      expect(wrapper.find('[data-testid="ig-template-split"]').exists()).toBe(
        true
      );
      expect(wrapper.find('[data-testid="ig-template-stadium"]').exists()).toBe(
        true
      );
    });

    it('hides Tournament Round when the match has no tournament_round', () => {
      const wrapper = mountModal();
      expect(
        wrapper.find('[data-testid="ig-template-tournament-round"]').exists()
      ).toBe(false);
    });

    it('shows Tournament Round and defaults to it when round is set', () => {
      const wrapper = mountModal({
        match: createMockMatch({
          tournament_name: '2026 MLS NEXT Cup',
          tournament_round: 'quarterfinal',
        }),
      });
      const opt = wrapper.find('[data-testid="ig-template-tournament-round"]');
      expect(opt.exists()).toBe(true);
      expect(opt.attributes('aria-checked')).toBe('true');
    });

    it('defaults to overlay when no tournament round', () => {
      const wrapper = mountModal();
      expect(
        wrapper
          .find('[data-testid="ig-template-overlay"]')
          .attributes('aria-checked')
      ).toBe('true');
    });

    it('switches template when user clicks an option', async () => {
      const wrapper = mountModal();
      await wrapper.find('[data-testid="ig-template-split"]').trigger('click');
      expect(
        wrapper
          .find('[data-testid="ig-template-split"]')
          .attributes('aria-checked')
      ).toBe('true');
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

describe('IgShareModal — photo persistence permission (SB-659)', () => {
  beforeEach(() => {
    mockAuthStore = createMockAuthStore();
  });

  it('does not upload the photo when the viewer cannot persist', async () => {
    // A player generating a card for their own match: the photo stays in
    // their browser and no write is attempted. Previously the whole modal
    // was hidden from them; now it works, minus persistence.
    const wrapper = mountModal({ canPersistPhoto: false });

    const input = wrapper.find('[data-testid="ig-file-input"]');
    Object.defineProperty(input.element, 'files', {
      value: [makeFile()],
      configurable: true,
    });
    await input.trigger('change');
    await wrapper.find('[data-testid="ig-download-button"]').trigger('click');
    await flushPromises();

    expect(mockAuthStore.apiRequest).not.toHaveBeenCalled();
  });

  it('still lets that viewer generate a card', async () => {
    const wrapper = mountModal({ canPersistPhoto: false });
    await wrapper.find('[data-testid="ig-download-button"]').trigger('click');
    await flushPromises();

    // No upload error surfaced — skipping persistence is normal here, not
    // a failure the user should be told about.
    expect(wrapper.find('[data-testid="ig-upload-error"]').exists()).toBe(
      false
    );
  });
});

describe('IgShareModal — accent picker (SB-659)', () => {
  beforeEach(() => {
    mockAuthStore = createMockAuthStore();
  });

  it('offers both clubs plus the Missing Table default', () => {
    const wrapper = mountModal();
    expect(wrapper.find('[data-testid="ig-accent-home"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="ig-accent-away"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="ig-accent-mt"]').exists()).toBe(true);
  });

  it('defaults to auto when the viewer has no team in the match', () => {
    const wrapper = mountModal({ viewerTeamId: null });
    expect(wrapper.vm.accentPreference).toBe('auto');
  });

  it("defaults to the viewer's own club when they are the away team", () => {
    // The reported case: an IFA player looking at Red Bulls vs IFA should
    // get IFA's colors without touching the picker, even though the home
    // club would win the automatic resolution.
    const wrapper = mountModal({ viewerTeamId: 2 });
    expect(wrapper.vm.accentPreference).toBe('away');
  });

  it("defaults to the viewer's own club when they are the home team", () => {
    const wrapper = mountModal({ viewerTeamId: 1 });
    expect(wrapper.vm.accentPreference).toBe('home');
  });

  it('ignores a viewer team that is not playing in this match', () => {
    const wrapper = mountModal({ viewerTeamId: 999 });
    expect(wrapper.vm.accentPreference).toBe('auto');
  });

  it('disables a club whose color is the seeded placeholder gray', () => {
    const wrapper = mountModal({
      match: createMockMatch({
        home_team_club: { logo_url: null, primary_color: '#6B7280' },
      }),
    });
    const home = wrapper.find('[data-testid="ig-accent-home"]');
    expect(home.attributes('disabled')).toBeDefined();
    expect(wrapper.find('[data-testid="ig-accent-note"]').text()).toBeTruthy();
  });

  it('disables a club whose color is too dark to see on the card', () => {
    const wrapper = mountModal({
      match: createMockMatch({
        away_team_club: { logo_url: null, primary_color: '#000000' },
      }),
    });
    expect(
      wrapper.find('[data-testid="ig-accent-away"]').attributes('disabled')
    ).toBeDefined();
  });

  it('does not preselect the viewer club when that club is unusable', () => {
    // Falling back to auto is better than showing "IFA" selected while the
    // card renders a different color.
    const wrapper = mountModal({
      viewerTeamId: 1,
      match: createMockMatch({
        home_team_club: { logo_url: null, primary_color: '#6B7280' },
      }),
    });
    expect(wrapper.vm.accentPreference).toBe('auto');
  });

  it("defaults to the viewer's club when they have no team (club fan)", () => {
    // A club fan has club_id but no team_id, so team matching cannot help.
    const wrapper = mountModal({
      viewerTeamId: null,
      viewerClubId: 20,
      match: createMockMatch({
        home_team_club: { id: 10, logo_url: null, primary_color: '#B22222' },
        away_team_club: { id: 20, logo_url: null, primary_color: '#B38B00' },
      }),
    });
    expect(wrapper.vm.accentPreference).toBe('away');
  });

  it('prefers the team claim over the club claim', () => {
    // Team is the more specific affiliation; if the two ever disagree the
    // team the viewer actually plays for should win.
    const wrapper = mountModal({
      viewerTeamId: 1,
      viewerClubId: 20,
      match: createMockMatch({
        home_team_id: 1,
        away_team_id: 2,
        home_team_club: { id: 10, logo_url: null, primary_color: '#B22222' },
        away_team_club: { id: 20, logo_url: null, primary_color: '#B38B00' },
      }),
    });
    expect(wrapper.vm.accentPreference).toBe('home');
  });
});
