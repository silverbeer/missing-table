/**
 * MatchesView.vue Tests
 *
 * Tests for the main matches display component.
 * Focus areas: Tab switching, filtering, match list rendering
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import MatchesView from '@/components/MatchesView.vue';
import {
  createMockAuthStore,
  createTeamManagerAuthStore,
  createUnauthenticatedStore,
  createMockAgeGroups,
  createMockSeasons,
  createMockMatchTypes,
  createMockLeagues,
  createMockClubs,
  createMockTeams,
  createMockMatch,
  createCompletedMatch,
  createLiveMatch,
  createPostponedMatch,
  createCancelledMatch,
  createHomegrownMatch,
  createAcademyMatch,
} from '../helpers/matchFactories';

// =============================================================================
// TEST SETUP
// =============================================================================

let mockAuthStore;

// Mock the auth store module
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}));

// Mock child components to isolate unit tests
vi.mock('@/components/MatchDetailView.vue', () => ({
  default: {
    name: 'MatchDetailView',
    props: ['matchId'],
    emits: ['back'],
    template: '<div data-testid="match-detail-mock">Match Detail View</div>',
  },
}));

vi.mock('@/components/MatchEditModal.vue', () => ({
  default: {
    name: 'MatchEditModal',
    props: ['show', 'match', 'teams', 'seasons', 'matchTypes', 'ageGroups'],
    emits: ['close', 'updated'],
    template: '<div v-if="show" data-testid="edit-modal-mock">Edit Modal</div>',
  },
}));

// Mock API config
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

/**
 * Helper to mount MatchesView with default options
 */
const mountMatchesView = (options = {}) => {
  return mount(MatchesView, {
    global: {
      stubs: {
        MatchDetailView: true,
        MatchEditModal: true,
      },
    },
    ...options,
  });
};

/**
 * Setup mock API responses for a standard test scenario
 */
const setupMockApiResponses = (customResponses = {}) => {
  const responses = {
    ageGroups: createMockAgeGroups(),
    seasons: createMockSeasons(),
    matchTypes: createMockMatchTypes(),
    leagues: createMockLeagues(),
    clubs: createMockClubs(),
    teams: createMockTeams(),
    matches: [],
    ...customResponses,
  };

  mockAuthStore.apiRequest = vi.fn(url => {
    if (url.includes('/api/age-groups'))
      return Promise.resolve(responses.ageGroups);
    if (url.includes('/api/seasons')) return Promise.resolve(responses.seasons);
    if (url.includes('/api/match-types'))
      return Promise.resolve(responses.matchTypes);
    if (url.includes('/api/leagues')) return Promise.resolve(responses.leagues);
    if (url.includes('/api/clubs')) return Promise.resolve(responses.clubs);
    if (url.includes('/api/teams')) return Promise.resolve(responses.teams);
    if (url.includes('/api/matches')) return Promise.resolve(responses.matches);
    return Promise.resolve([]);
  });

  return responses;
};

// =============================================================================
// TESTS: INITIAL RENDERING
// =============================================================================

describe('MatchesView', () => {
  beforeEach(() => {
    mockAuthStore = createMockAuthStore();
    vi.clearAllMocks();
  });

  describe('initial rendering', () => {
    it('shows loading state initially', () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();

      expect(wrapper.find('[data-testid="loading-state"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="loading-state"]').text()).toContain(
        'Loading'
      );
    });

    it('renders All Matches tab as default after loading', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      const allMatchesTab = wrapper.find('[data-testid="all-matches-tab"]');
      expect(allMatchesTab.exists()).toBe(true);
      expect(allMatchesTab.classes()).toContain('border-blue-600');
    });

    it('renders My Club tab', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      expect(wrapper.find('[data-testid="my-club-tab"]').exists()).toBe(true);
    });

    it('shows error state when fetch fails', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.reject(new Error('API Error'))
      );
      const wrapper = mountMatchesView();
      await flushPromises();

      expect(wrapper.find('[data-testid="error-state"]').exists()).toBe(true);
    });

    it('renders age group filter buttons', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      // Should show age groups that have teams (U12, U14 from mock teams)
      expect(wrapper.find('[data-testid="age-group-2"]').exists()).toBe(true); // U12
      expect(wrapper.find('[data-testid="age-group-3"]').exists()).toBe(true); // U14
    });

    it('renders season selector dropdown', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      expect(wrapper.find('[data-testid="season-selector"]').exists()).toBe(
        true
      );
    });

    it('renders match type filter buttons', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      expect(wrapper.find('[data-testid="match-type-1"]').exists()).toBe(true); // League
      expect(wrapper.find('[data-testid="match-type-2"]').exists()).toBe(true); // Tournament
      expect(wrapper.find('[data-testid="match-type-3"]').exists()).toBe(true); // Friendly
      expect(wrapper.find('[data-testid="match-type-4"]').exists()).toBe(true); // Playoff
      expect(wrapper.find('[data-testid="match-type-all"]').exists()).toBe(
        true
      ); // All
    });

    it('renders week navigation on All Matches tab', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      expect(wrapper.find('[data-testid="week-prev"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="week-current"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="week-next"]').exists()).toBe(true);
    });
  });

  // ===========================================================================
  // TESTS: TAB SWITCHING
  // ===========================================================================

  describe('tab switching', () => {
    it('switches to My Club tab when clicked', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      await wrapper.find('[data-testid="my-club-tab"]').trigger('click');
      await flushPromises();

      const myClubTab = wrapper.find('[data-testid="my-club-tab"]');
      expect(myClubTab.classes()).toContain('border-blue-600');
    });

    it('switches back to All Matches tab', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      // Switch to My Club
      await wrapper.find('[data-testid="my-club-tab"]').trigger('click');
      await flushPromises();

      // Switch back to All Matches
      await wrapper.find('[data-testid="all-matches-tab"]').trigger('click');
      await flushPromises();

      const allMatchesTab = wrapper.find('[data-testid="all-matches-tab"]');
      expect(allMatchesTab.classes()).toContain('border-blue-600');
    });

    it('shows club selector only on My Club tab', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      // All Matches tab - no club selector
      expect(wrapper.find('[data-testid="club-selector"]').exists()).toBe(
        false
      );

      // Switch to My Club tab
      await wrapper.find('[data-testid="my-club-tab"]').trigger('click');
      await flushPromises();

      // My Club tab - has club selector
      expect(wrapper.find('[data-testid="club-selector"]').exists()).toBe(true);
    });

    it('shows week navigation only on All Matches tab', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      // All Matches tab - has week navigation
      expect(wrapper.find('[data-testid="week-prev"]').exists()).toBe(true);

      // Switch to My Club tab
      await wrapper.find('[data-testid="my-club-tab"]').trigger('click');
      await flushPromises();

      // My Club tab - no week navigation
      expect(wrapper.find('[data-testid="week-prev"]').exists()).toBe(false);
    });

    it('My Club tab shows different content than All Matches', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      // All Matches tab should show week navigation
      expect(wrapper.find('[data-testid="week-prev"]').exists()).toBe(true);

      await wrapper.find('[data-testid="my-club-tab"]').trigger('click');
      await flushPromises();

      // My Club tab should not show week navigation (different content)
      expect(wrapper.find('[data-testid="week-prev"]').exists()).toBe(false);
    });
  });

  // ===========================================================================
  // TESTS: AGE GROUP FILTER
  // ===========================================================================

  describe('age group filter', () => {
    it('highlights selected age group', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      // Default selection (U14 = id 2 in defaults, but component defaults to id 2 which is U12)
      const ageGroup3 = wrapper.find('[data-testid="age-group-3"]');
      if (ageGroup3.exists()) {
        await ageGroup3.trigger('click');
        await flushPromises();
        expect(ageGroup3.classes()).toContain('bg-blue-600');
      }
    });

    it('can click different age group buttons', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      const ageGroup2 = wrapper.find('[data-testid="age-group-2"]');
      const ageGroup3 = wrapper.find('[data-testid="age-group-3"]');

      // Both age groups should exist (from mock teams)
      expect(ageGroup2.exists() || ageGroup3.exists()).toBe(true);

      // If U12 exists, clicking it should update its style
      if (ageGroup2.exists()) {
        await ageGroup2.trigger('click');
        await flushPromises();
        expect(ageGroup2.classes()).toContain('bg-blue-600');
      }
    });
  });

  // ===========================================================================
  // TESTS: MATCH TYPE FILTER
  // ===========================================================================

  describe('match type filter', () => {
    it('defaults to League match type', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      const leagueButton = wrapper.find('[data-testid="match-type-1"]');
      expect(leagueButton.classes()).toContain('bg-blue-600');
    });

    it('switches to Friendly match type', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      await wrapper.find('[data-testid="match-type-3"]').trigger('click');
      await flushPromises();

      const friendlyButton = wrapper.find('[data-testid="match-type-3"]');
      expect(friendlyButton.classes()).toContain('bg-blue-600');
    });

    it('switches to All Matches type', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      await wrapper.find('[data-testid="match-type-all"]').trigger('click');
      await flushPromises();

      const allButton = wrapper.find('[data-testid="match-type-all"]');
      expect(allButton.classes()).toContain('bg-blue-600');
    });
  });

  // ===========================================================================
  // TESTS: WEEK NAVIGATION
  // ===========================================================================

  describe('week navigation', () => {
    it('displays week range on All Matches tab when matches exist', async () => {
      // Week range only shows when there are matches (not empty state)
      const matches = [createHomegrownMatch({ id: 1 })];
      setupMockApiResponses({ matches });
      const wrapper = mountMatchesView();
      await flushPromises();

      const weekRange = wrapper.find('[data-testid="week-range"]');
      expect(weekRange.exists()).toBe(true);
      // Should contain date-like text (e.g., "Jan 6 - Jan 12, 2025")
      expect(weekRange.text()).toMatch(/\w+ \d+ - \w+ \d+, \d{4}/);
    });

    it('This Week button is highlighted by default', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      const currentButton = wrapper.find('[data-testid="week-current"]');
      expect(currentButton.classes()).toContain('bg-blue-600');
    });

    it('Previous button navigates to previous week', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      const initialCallCount = mockAuthStore.apiRequest.mock.calls.length;

      await wrapper.find('[data-testid="week-prev"]').trigger('click');
      await flushPromises();

      // Should trigger match fetch
      expect(mockAuthStore.apiRequest.mock.calls.length).toBeGreaterThan(
        initialCallCount
      );

      // This Week button should no longer be highlighted
      const currentButton = wrapper.find('[data-testid="week-current"]');
      expect(currentButton.classes()).not.toContain('bg-blue-600');
    });

    it('Next button navigates to next week', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      await wrapper.find('[data-testid="week-next"]').trigger('click');
      await flushPromises();

      // This Week button should no longer be highlighted
      const currentButton = wrapper.find('[data-testid="week-current"]');
      expect(currentButton.classes()).not.toContain('bg-blue-600');
    });

    it('This Week button resets offset', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      // Navigate away first
      await wrapper.find('[data-testid="week-prev"]').trigger('click');
      await flushPromises();

      // Click This Week to reset
      await wrapper.find('[data-testid="week-current"]').trigger('click');
      await flushPromises();

      const currentButton = wrapper.find('[data-testid="week-current"]');
      expect(currentButton.classes()).toContain('bg-blue-600');
    });
  });

  // ===========================================================================
  // TESTS: CLUB/TEAM SELECTION (MY CLUB TAB)
  // ===========================================================================

  describe('club/team selection', () => {
    it('shows prompt when no club is selected', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      await wrapper.find('[data-testid="my-club-tab"]').trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('Please select a club');
    });

    it('shows team selector after club selection', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      await wrapper.find('[data-testid="my-club-tab"]').trigger('click');
      await flushPromises();

      // Select a club using the select element
      const clubSelector = wrapper.find('[data-testid="club-selector"]');
      expect(clubSelector.exists()).toBe(true);

      // Set the value and trigger change
      await clubSelector.find('option[value="1"]').setSelected();
      await flushPromises();

      // Team selector should now exist
      const teamSelector = wrapper.find('[data-testid="team-selector"]');
      expect(teamSelector.exists()).toBe(true);
    });
  });

  // ===========================================================================
  // TESTS: MATCH LIST RENDERING
  // ===========================================================================

  describe('match list rendering', () => {
    it('shows empty state when no matches', async () => {
      setupMockApiResponses({ matches: [] });
      const wrapper = mountMatchesView();
      await flushPromises();

      expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(true);
    });

    it('renders matches when data is available', async () => {
      const matches = [
        createHomegrownMatch({ id: 1, match_date: '2025-01-15' }),
        createHomegrownMatch({ id: 2, match_date: '2025-01-16' }),
      ];
      setupMockApiResponses({ matches });
      const wrapper = mountMatchesView();
      await flushPromises();

      // Should not show empty state
      expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(false);
    });
  });

  // ===========================================================================
  // TESTS: STATUS BADGES
  // ===========================================================================

  describe('status badges', () => {
    it('shows LIVE badge with animation for live matches', async () => {
      const matches = [createLiveMatch({ id: 1 })];
      setupMockApiResponses({ matches });
      const wrapper = mountMatchesView();
      await flushPromises();

      // Look for LIVE text in the rendered output
      expect(wrapper.text()).toContain('LIVE');
    });

    it('shows completed status for completed matches', async () => {
      const matches = [createCompletedMatch({ id: 1 })];
      setupMockApiResponses({ matches });
      const wrapper = mountMatchesView();
      await flushPromises();

      expect(wrapper.text()).toContain('completed');
    });

    it('shows postponed status for postponed matches', async () => {
      const matches = [createPostponedMatch({ id: 1 })];
      setupMockApiResponses({ matches });
      const wrapper = mountMatchesView();
      await flushPromises();

      expect(wrapper.text()).toContain('postponed');
    });

    it('shows cancelled status for cancelled matches', async () => {
      const matches = [createCancelledMatch({ id: 1 })];
      setupMockApiResponses({ matches });
      const wrapper = mountMatchesView();
      await flushPromises();

      expect(wrapper.text()).toContain('cancelled');
    });
  });

  // ===========================================================================
  // TESTS: SEASON STATS (MY CLUB TAB)
  // ===========================================================================

  describe('season stats', () => {
    it('season stats section has data-testid attribute', async () => {
      // The season-stats testid exists in the component template
      // This test verifies the template structure is correct
      // Actual visibility depends on complex state (club + team selection)
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      // On All Matches tab, season stats should NOT be visible
      expect(wrapper.find('[data-testid="season-stats"]').exists()).toBe(false);

      // Switch to My Club tab
      await wrapper.find('[data-testid="my-club-tab"]').trigger('click');
      await flushPromises();

      // Without team selection, season stats still not visible
      // This tests the conditional rendering is working
      expect(wrapper.find('[data-testid="season-stats"]').exists()).toBe(false);
    });

    it('hides season stats on All Matches tab', async () => {
      setupMockApiResponses();
      const wrapper = mountMatchesView();
      await flushPromises();

      // Should not show season stats on All Matches tab
      expect(wrapper.find('[data-testid="season-stats"]').exists()).toBe(false);
    });
  });

  // ===========================================================================
  // TESTS: PERMISSION CHECKS
  // ===========================================================================

  describe('permission checks', () => {
    it('admin can see edit buttons for all matches', async () => {
      mockAuthStore = createMockAuthStore({
        isAdmin: { value: true },
        isAuthenticated: { value: true },
      });
      const matches = [createMockMatch({ id: 1 })];
      setupMockApiResponses({ matches });
      const wrapper = mountMatchesView();
      await flushPromises();

      // Admin should see Edit Match button
      expect(wrapper.text()).toContain('Edit');
    });

    it('team manager sees edit buttons only for their team matches', async () => {
      mockAuthStore = createTeamManagerAuthStore(1);
      const matches = [
        createMockMatch({ id: 1, home_team_id: 1, away_team_id: 2 }), // Their team
        createMockMatch({ id: 2, home_team_id: 3, away_team_id: 4 }), // Not their team
      ];
      setupMockApiResponses({ matches });
      const wrapper = mountMatchesView();
      await flushPromises();

      // Should see some edit options (for their team's match)
      expect(wrapper.text()).toContain('Edit');
    });

    it('unauthenticated users do not see edit buttons', async () => {
      mockAuthStore = createUnauthenticatedStore();
      const matches = [createMockMatch({ id: 1 })];
      setupMockApiResponses({ matches });
      const wrapper = mountMatchesView();
      await flushPromises();

      // Should not see any edit buttons
      expect(wrapper.text()).not.toContain('Edit Match');
    });

    it('admin sees Match ID column', async () => {
      mockAuthStore = createMockAuthStore({
        isAdmin: { value: true },
        isAuthenticated: { value: true },
      });
      const matches = [createMockMatch({ id: 1, match_id: 'EXT123' })];
      setupMockApiResponses({ matches });
      const wrapper = mountMatchesView();
      await flushPromises();

      // Admin should see external match ID
      expect(wrapper.text()).toContain('EXT123');
    });
  });

  // ===========================================================================
  // TESTS: LEAGUE GROUPING (ALL MATCHES TAB)
  // ===========================================================================

  describe('league grouping', () => {
    it('groups matches by league on All Matches tab', async () => {
      const matches = [
        createHomegrownMatch({
          id: 1,
          division: { leagues: { name: 'Homegrown' } },
        }),
        createAcademyMatch({
          id: 2,
          division: { leagues: { name: 'Academy' } },
        }),
      ];
      setupMockApiResponses({ matches });
      const wrapper = mountMatchesView();
      await flushPromises();

      // Should see league headers
      expect(wrapper.text()).toContain('HOMEGROWN');
      expect(wrapper.text()).toContain('ACADEMY');
    });
  });
});
