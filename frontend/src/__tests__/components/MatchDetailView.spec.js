/**
 * MatchDetailView.vue Tests
 *
 * Tests for the match detail/scoreboard component.
 * Focus areas: Loading states, scoreboard rendering, status badges
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import MatchDetailView from '@/components/MatchDetailView.vue';
import {
  createMockAuthStore,
  createMockMatch,
  createCompletedMatch,
  createLiveMatch,
  createPostponedMatch,
  createCancelledMatch,
  createTeamManagerAuthStore,
  createAuthenticatedUserStore,
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

// Mock html2canvas
vi.mock('html2canvas', () => ({
  default: vi.fn(() =>
    Promise.resolve({
      toBlob: callback => callback(new Blob(['test'], { type: 'image/png' })),
    })
  ),
}));

/**
 * Helper to mount MatchDetailView with default options
 */
const mountMatchDetailView = (options = {}) => {
  return mount(MatchDetailView, {
    props: {
      matchId: 1,
      ...options.props,
    },
    ...options,
  });
};

/**
 * Helper to create a mock apiRequest that returns different data based on URL
 * @param {Object} match - The match object to return for match requests
 * @param {Array} events - The events array to return for events requests (default: [])
 */
const createMockApiRequestForMatch = (match, events = []) => {
  return vi.fn(url => {
    if (url.includes('/live/events')) {
      return Promise.resolve(events);
    }
    return Promise.resolve(match);
  });
};

// =============================================================================
// TESTS: LOADING STATE
// =============================================================================

describe('MatchDetailView', () => {
  beforeEach(() => {
    mockAuthStore = createMockAuthStore();
    vi.clearAllMocks();
  });

  describe('loading state', () => {
    it('shows loading state initially', () => {
      mockAuthStore.apiRequest = vi.fn(() => new Promise(() => {})); // Never resolves
      const wrapper = mountMatchDetailView();

      expect(wrapper.find('[data-testid="loading-state"]').exists()).toBe(true);
      expect(wrapper.text()).toContain('Loading match details');
    });

    it('hides loading state after data loads', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.resolve(createMockMatch())
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="loading-state"]').exists()).toBe(
        false
      );
    });
  });

  // ===========================================================================
  // TESTS: ERROR STATE
  // ===========================================================================

  describe('error state', () => {
    it('shows error message when fetch fails', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.reject(new Error('Network error'))
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="error-state"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="error-message"]').exists()).toBe(true);
    });

    it('shows retry button on error', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.reject(new Error('Network error'))
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="retry-button"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="retry-button"]').text()).toContain(
        'Try Again'
      );
    });

    it('retry button calls fetchMatch again', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.reject(new Error('Network error'))
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      const initialCallCount = mockAuthStore.apiRequest.mock.calls.length;

      await wrapper.find('[data-testid="retry-button"]').trigger('click');
      await flushPromises();

      expect(mockAuthStore.apiRequest.mock.calls.length).toBeGreaterThan(
        initialCallCount
      );
    });

    it('shows 401 error as login required message', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.reject(new Error('401 Unauthorized'))
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.text()).toContain('logged in');
    });

    it('shows 404 error as match not found', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.reject(new Error('404 Not Found'))
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.text()).toContain('not found');
    });
  });

  // ===========================================================================
  // TESTS: SCOREBOARD RENDERING
  // ===========================================================================

  describe('scoreboard rendering', () => {
    it('renders scoreboard when match loads', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.resolve(createMockMatch())
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="scoreboard"]').exists()).toBe(true);
    });

    it('displays home team name', async () => {
      const match = createMockMatch({ home_team_name: 'Blue Stars U14' });
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve(match));
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.text()).toContain('Blue Stars U14');
    });

    it('displays away team name', async () => {
      const match = createMockMatch({ away_team_name: 'Red Hawks U14' });
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve(match));
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.text()).toContain('Red Hawks U14');
    });

    it('shows dash for scheduled match scores', async () => {
      const match = createMockMatch({ home_score: null, away_score: null });
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve(match));
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="home-score"]').text()).toBe('-');
      expect(wrapper.find('[data-testid="away-score"]').text()).toBe('-');
    });

    it('shows scores for completed matches', async () => {
      const match = createCompletedMatch({ home_score: 3, away_score: 1 });
      mockAuthStore.apiRequest = createMockApiRequestForMatch(match);
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="home-score"]').text()).toBe('3');
      expect(wrapper.find('[data-testid="away-score"]').text()).toBe('1');
    });

    it('shows team initials when no logo', async () => {
      const match = createMockMatch({
        home_team_name: 'Blue Stars',
        home_team_club: { logo_url: null, primary_color: '#3B82F6' },
      });
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve(match));
      const wrapper = mountMatchDetailView();
      await flushPromises();

      // Should show initials like "BS"
      expect(wrapper.text()).toContain('BS');
    });
  });

  // ===========================================================================
  // TESTS: STATUS BADGES
  // ===========================================================================

  describe('status badges', () => {
    it('shows LIVE badge for live matches', async () => {
      mockAuthStore.apiRequest =
        createMockApiRequestForMatch(createLiveMatch());
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="status-badge"]').exists()).toBe(true);
      expect(wrapper.text()).toContain('LIVE');
    });

    it('shows completed status badge', async () => {
      mockAuthStore.apiRequest = createMockApiRequestForMatch(
        createCompletedMatch()
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="status-badge"]').text()).toContain(
        'completed'
      );
    });

    it('shows scheduled status badge', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.resolve(createMockMatch())
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="status-badge"]').text()).toContain(
        'scheduled'
      );
    });

    it('shows postponed status badge', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.resolve(createPostponedMatch())
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="status-badge"]').text()).toContain(
        'postponed'
      );
    });

    it('shows cancelled status badge', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.resolve(createCancelledMatch())
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="status-badge"]').text()).toContain(
        'cancelled'
      );
    });
  });

  // ===========================================================================
  // TESTS: MATCH DETAILS
  // ===========================================================================

  describe('match details', () => {
    it('displays match date', async () => {
      const match = createMockMatch({ match_date: '2025-01-15' });
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve(match));
      const wrapper = mountMatchDetailView();
      await flushPromises();

      // Date format is like "Wed, Jan 15, 2025" (may vary by timezone)
      expect(wrapper.text()).toMatch(/Jan.*1[45].*2025/);
    });

    it('displays match type', async () => {
      const match = createMockMatch({ match_type_name: 'League' });
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve(match));
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.text()).toContain('League');
    });

    it('displays season name', async () => {
      const match = createMockMatch({ season_name: '2025-2026' });
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve(match));
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.text()).toContain('2025-2026');
    });

    it('displays age group', async () => {
      const match = createMockMatch({ age_group_name: 'U14' });
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve(match));
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.text()).toContain('U14');
    });

    it('displays division when available', async () => {
      const match = createMockMatch({ division_name: 'Northeast' });
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve(match));
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.text()).toContain('Northeast');
    });

    it('displays league when available', async () => {
      const match = createMockMatch({
        division: { leagues: { name: 'Homegrown' } },
      });
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve(match));
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.text()).toContain('Homegrown');
    });
  });

  // ===========================================================================
  // TESTS: NAVIGATION
  // ===========================================================================

  describe('navigation', () => {
    it('renders back button', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.resolve(createMockMatch())
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="back-button"]').exists()).toBe(true);
    });

    it('emits back event when clicking back button', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.resolve(createMockMatch())
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      await wrapper.find('[data-testid="back-button"]').trigger('click');

      expect(wrapper.emitted('back')).toBeTruthy();
    });
  });

  // ===========================================================================
  // TESTS: SHARE BUTTON
  // ===========================================================================

  describe('share button', () => {
    it('renders share button', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.resolve(createMockMatch())
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="share-button"]').exists()).toBe(true);
    });

    it('shows "Copy to Clipboard" text initially', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.resolve(createMockMatch())
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="share-button"]').text()).toContain(
        'Copy to Clipboard'
      );
    });
  });

  // ===========================================================================
  // TESTS: PROP WATCHING
  // ===========================================================================

  describe('prop watching', () => {
    it('fetches new match when matchId prop changes', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.resolve(createMockMatch())
      );
      const wrapper = mountMatchDetailView({ props: { matchId: 1 } });
      await flushPromises();

      const initialCallCount = mockAuthStore.apiRequest.mock.calls.length;

      await wrapper.setProps({ matchId: 2 });
      await flushPromises();

      expect(mockAuthStore.apiRequest.mock.calls.length).toBeGreaterThan(
        initialCallCount
      );
    });
  });

  // ===========================================================================
  // TESTS: PRE-MATCH LINEUP SECTION
  // ===========================================================================

  describe('pre-match lineup section', () => {
    it('shows lineup toggle for admin on scheduled match', async () => {
      // Default mockAuthStore is admin
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.resolve(createMockMatch())
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="lineup-section"]').exists()).toBe(
        true
      );
      expect(wrapper.find('[data-testid="lineup-toggle"]').text()).toContain(
        'Starting Lineup'
      );
    });

    it('hides lineup section for non-manager users', async () => {
      mockAuthStore = createAuthenticatedUserStore();
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.resolve(createMockMatch())
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="lineup-section"]').exists()).toBe(
        false
      );
    });

    it('hides lineup section for completed matches', async () => {
      mockAuthStore.apiRequest = createMockApiRequestForMatch(
        createCompletedMatch()
      );
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="lineup-section"]').exists()).toBe(
        false
      );
    });

    it('hides lineup section for live matches', async () => {
      mockAuthStore.apiRequest =
        createMockApiRequestForMatch(createLiveMatch());
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="lineup-section"]').exists()).toBe(
        false
      );
    });

    it('shows lineup section for team manager on their team match', async () => {
      mockAuthStore = createTeamManagerAuthStore(1, 1);
      const match = createMockMatch({
        home_team_id: 1,
        away_team_id: 2,
      });
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve(match));
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="lineup-section"]').exists()).toBe(
        true
      );
    });

    it('hides lineup section for team manager on unrelated match', async () => {
      mockAuthStore = createTeamManagerAuthStore(99, 99);
      const match = createMockMatch({
        home_team_id: 1,
        away_team_id: 2,
      });
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve(match));
      const wrapper = mountMatchDetailView();
      await flushPromises();

      expect(wrapper.find('[data-testid="lineup-section"]').exists()).toBe(
        false
      );
    });

    it('toggle button expands lineup content', async () => {
      mockAuthStore.apiRequest = vi.fn(url => {
        if (url.includes('/roster')) return Promise.resolve({ roster: [] });
        if (url.includes('/lineup')) return Promise.resolve(null);
        return Promise.resolve(createMockMatch());
      });
      const wrapper = mountMatchDetailView();
      await flushPromises();

      // Lineup content should not be visible initially
      expect(wrapper.find('[data-testid="lineup-tab-home"]').exists()).toBe(
        false
      );

      // Click toggle
      await wrapper.find('[data-testid="lineup-toggle"]').trigger('click');
      await flushPromises();

      // After expanding and loading, should show no-roster message (empty rosters)
      expect(wrapper.find('[data-testid="no-roster-message"]').exists()).toBe(
        true
      );
    });
  });
});
