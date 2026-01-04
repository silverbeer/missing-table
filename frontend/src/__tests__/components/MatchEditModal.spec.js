/**
 * MatchEditModal.vue Tests
 *
 * Tests for the match edit modal component.
 * Focus areas: Form rendering, field population, form submission
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import MatchEditModal from '@/components/MatchEditModal.vue';
import {
  createMockAuthStore,
  createMockMatch,
  createMockTeams,
  createMockSeasons,
  createMockMatchTypes,
  createMockAgeGroups,
} from '../helpers/matchFactories';

// =============================================================================
// TEST SETUP
// =============================================================================

let mockAuthStore;

// Mock the auth store module
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}));

// Mock API config
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

/**
 * Helper to mount MatchEditModal with default options
 */
const mountMatchEditModal = (options = {}) => {
  const defaultMatch = createMockMatch();
  return mount(MatchEditModal, {
    props: {
      show: true,
      match: defaultMatch,
      teams: createMockTeams(),
      seasons: createMockSeasons(),
      matchTypes: createMockMatchTypes(),
      ageGroups: createMockAgeGroups(),
      ...options.props,
    },
    ...options,
  });
};

// =============================================================================
// TESTS: VISIBILITY
// =============================================================================

describe('MatchEditModal', () => {
  beforeEach(() => {
    mockAuthStore = createMockAuthStore();
    vi.clearAllMocks();
  });

  describe('visibility', () => {
    it('renders modal when show is true', () => {
      const wrapper = mountMatchEditModal();

      expect(wrapper.find('[data-testid="edit-modal"]').exists()).toBe(true);
    });

    it('does not render modal when show is false', () => {
      const wrapper = mountMatchEditModal({
        props: { show: false, match: null },
      });

      expect(wrapper.find('[data-testid="edit-modal"]').exists()).toBe(false);
    });

    it('emits close when clicking overlay', async () => {
      const wrapper = mountMatchEditModal();

      await wrapper.find('[data-testid="edit-modal"]').trigger('click');

      expect(wrapper.emitted('close')).toBeTruthy();
    });
  });

  // ===========================================================================
  // TESTS: FORM FIELDS
  // ===========================================================================

  describe('form fields', () => {
    it('renders date input', () => {
      const wrapper = mountMatchEditModal();

      expect(wrapper.find('[data-testid="date-input"]').exists()).toBe(true);
    });

    it('renders match type select', () => {
      const wrapper = mountMatchEditModal();

      expect(wrapper.find('[data-testid="match-type-select"]').exists()).toBe(
        true
      );
    });

    it('renders home team select', () => {
      const wrapper = mountMatchEditModal();

      expect(wrapper.find('[data-testid="home-team-select"]').exists()).toBe(
        true
      );
    });

    it('renders away team select', () => {
      const wrapper = mountMatchEditModal();

      expect(wrapper.find('[data-testid="away-team-select"]').exists()).toBe(
        true
      );
    });

    it('renders status select', () => {
      const wrapper = mountMatchEditModal();

      expect(wrapper.find('[data-testid="status-select"]').exists()).toBe(true);
    });

    it('renders submit button', () => {
      const wrapper = mountMatchEditModal();

      expect(wrapper.find('[data-testid="submit-button"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="submit-button"]').text()).toContain(
        'Update Match'
      );
    });

    it('renders cancel button', () => {
      const wrapper = mountMatchEditModal();

      expect(wrapper.find('[data-testid="cancel-button"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="cancel-button"]').text()).toContain(
        'Cancel'
      );
    });
  });

  // ===========================================================================
  // TESTS: FORM POPULATION
  // ===========================================================================

  describe('form population', () => {
    it('populates date from match prop', async () => {
      const match = createMockMatch({ match_date: '2025-01-15' });
      const wrapper = mountMatchEditModal({
        props: {
          show: true,
          match,
          teams: createMockTeams(),
          seasons: createMockSeasons(),
          matchTypes: createMockMatchTypes(),
          ageGroups: createMockAgeGroups(),
        },
      });
      await flushPromises();
      await wrapper.vm.$nextTick();

      const dateInput = wrapper.find('[data-testid="date-input"]');
      expect(dateInput.exists()).toBe(true);
      expect(dateInput.element.value).toBe('2025-01-15');
    });

    it('populates status from match prop', async () => {
      const match = createMockMatch({ match_status: 'completed' });
      const wrapper = mountMatchEditModal({
        props: {
          show: true,
          match,
          teams: createMockTeams(),
          seasons: createMockSeasons(),
          matchTypes: createMockMatchTypes(),
          ageGroups: createMockAgeGroups(),
        },
      });
      await flushPromises();
      await wrapper.vm.$nextTick();

      const statusSelect = wrapper.find('[data-testid="status-select"]');
      expect(statusSelect.exists()).toBe(true);
      expect(statusSelect.element.value).toBe('completed');
    });

    it('renders form fields correctly', async () => {
      const wrapper = mountMatchEditModal();
      await flushPromises();

      // Verify all key form fields exist
      expect(wrapper.find('[data-testid="date-input"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="status-select"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="home-team-select"]').exists()).toBe(
        true
      );
      expect(wrapper.find('[data-testid="away-team-select"]').exists()).toBe(
        true
      );
    });
  });

  // ===========================================================================
  // TESTS: FORM SUBMISSION
  // ===========================================================================

  describe('form submission', () => {
    it('calls apiRequest with PATCH method on submit', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.resolve(createMockMatch())
      );
      const wrapper = mountMatchEditModal();
      await flushPromises();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(mockAuthStore.apiRequest).toHaveBeenCalled();
      const callArgs = mockAuthStore.apiRequest.mock.calls[0];
      expect(callArgs[0]).toContain('/api/matches/');
      expect(callArgs[1].method).toBe('PATCH');
    });

    it('emits updated and close on successful submit', async () => {
      const updatedMatch = createMockMatch({ id: 1, home_score: 5 });
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve(updatedMatch));
      const wrapper = mountMatchEditModal();
      await flushPromises();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(wrapper.emitted('updated')).toBeTruthy();
      expect(wrapper.emitted('close')).toBeTruthy();
    });

    it('shows loading state during submission', async () => {
      mockAuthStore.apiRequest = vi.fn(() => new Promise(() => {})); // Never resolves
      const wrapper = mountMatchEditModal();
      await flushPromises();

      await wrapper.find('form').trigger('submit');

      expect(wrapper.find('[data-testid="submit-button"]').text()).toContain(
        'Updating'
      );
    });

    it('shows error message on submission failure', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.reject(new Error('Network error'))
      );
      const wrapper = mountMatchEditModal();
      await flushPromises();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(wrapper.find('[data-testid="error-message"]').exists()).toBe(true);
    });

    it('shows session expired message for 401 error', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.reject(new Error('401 Unauthorized'))
      );
      const wrapper = mountMatchEditModal();
      await flushPromises();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(wrapper.text()).toContain('session');
    });
  });

  // ===========================================================================
  // TESTS: CANCEL BUTTON
  // ===========================================================================

  describe('cancel button', () => {
    it('emits close when clicking cancel', async () => {
      const wrapper = mountMatchEditModal();

      await wrapper.find('[data-testid="cancel-button"]').trigger('click');

      expect(wrapper.emitted('close')).toBeTruthy();
    });
  });

  // ===========================================================================
  // TESTS: AUDIT TRAIL
  // ===========================================================================

  describe('audit trail info', () => {
    it('shows external match ID when present', async () => {
      const match = createMockMatch({ match_id: 'EXT123' });
      const wrapper = mountMatchEditModal({
        props: {
          show: true,
          match,
          teams: createMockTeams(),
          seasons: createMockSeasons(),
          matchTypes: createMockMatchTypes(),
          ageGroups: createMockAgeGroups(),
        },
      });
      await flushPromises();

      expect(wrapper.text()).toContain('EXT123');
    });

    it('shows source badge when present', async () => {
      const match = createMockMatch({ source: 'match-scraper' });
      const wrapper = mountMatchEditModal({
        props: {
          show: true,
          match,
          teams: createMockTeams(),
          seasons: createMockSeasons(),
          matchTypes: createMockMatchTypes(),
          ageGroups: createMockAgeGroups(),
        },
      });
      await flushPromises();

      expect(wrapper.text()).toContain('Auto-scraped');
    });
  });
});
