/**
 * MatchForm.vue Tests
 *
 * Tests for the match scheduling/scoring form component.
 * Focus areas: Form type toggle, dropdown population, validation, form submission
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import MatchForm from '@/components/MatchForm.vue';
import {
  createMockAuthStore,
  createMockSeasons,
  createMockAgeGroups,
  createMockMatchTypes,
  createMockDivisions,
  createMockTeams,
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

// Mock localStorage
const mockLocalStorage = {
  getItem: vi.fn(() => 'test-token'),
  setItem: vi.fn(),
  removeItem: vi.fn(),
};
Object.defineProperty(global, 'localStorage', { value: mockLocalStorage });

// Mock fetch for reference data
const createMockFetch = (overrides = {}) => {
  const defaultResponses = {
    '/api/active-seasons': createMockSeasons(),
    '/api/age-groups': createMockAgeGroups(),
    '/api/match-types': createMockMatchTypes(),
    '/api/divisions': createMockDivisions(),
    '/api/teams': createMockTeams(),
    '/api/check-match': { exists: false },
  };

  const responses = { ...defaultResponses, ...overrides };

  return vi.fn(url => {
    for (const [pattern, data] of Object.entries(responses)) {
      if (url.includes(pattern)) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(data),
        });
      }
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve([]),
    });
  });
};

/**
 * Helper to mount MatchForm with default options
 */
const mountMatchForm = (options = {}) => {
  return mount(MatchForm, {
    ...options,
  });
};

// =============================================================================
// TESTS: INITIAL RENDERING
// =============================================================================

describe('MatchForm', () => {
  beforeEach(() => {
    mockAuthStore = createMockAuthStore();
    global.fetch = createMockFetch();
    vi.clearAllMocks();
  });

  describe('initial rendering', () => {
    it('renders the form container', () => {
      const wrapper = mountMatchForm();

      expect(wrapper.find('[data-testid="match-form"]').exists()).toBe(true);
    });

    it('renders form type radio buttons', () => {
      const wrapper = mountMatchForm();

      expect(wrapper.find('[data-testid="form-type-schedule"]').exists()).toBe(
        true
      );
      expect(wrapper.find('[data-testid="form-type-score"]').exists()).toBe(
        true
      );
    });

    it('defaults to schedule form type', () => {
      const wrapper = mountMatchForm();

      const scheduleRadio = wrapper.find('[data-testid="form-type-schedule"]');
      expect(scheduleRadio.element.checked).toBe(true);
    });

    it('renders submit button with "Schedule Game" text by default', () => {
      const wrapper = mountMatchForm();

      expect(wrapper.find('[data-testid="submit-button"]').text()).toBe(
        'Schedule Game'
      );
    });
  });

  // ===========================================================================
  // TESTS: FORM TYPE TOGGLE
  // ===========================================================================

  describe('form type toggle', () => {
    it('switches to score mode when clicking score radio', async () => {
      const wrapper = mountMatchForm();

      await wrapper.find('[data-testid="form-type-score"]').setValue(true);

      expect(
        wrapper.find('[data-testid="form-type-score"]').element.checked
      ).toBe(true);
    });

    it('shows score inputs in score mode', async () => {
      const wrapper = mountMatchForm();

      await wrapper.find('[data-testid="form-type-score"]').setValue(true);

      expect(wrapper.find('[data-testid="score-section"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="home-score-input"]').exists()).toBe(
        true
      );
      expect(wrapper.find('[data-testid="away-score-input"]').exists()).toBe(
        true
      );
    });

    it('hides score inputs in schedule mode', () => {
      const wrapper = mountMatchForm();

      expect(wrapper.find('[data-testid="score-section"]').exists()).toBe(
        false
      );
    });

    it('changes submit button text to "Submit Score" in score mode', async () => {
      const wrapper = mountMatchForm();

      await wrapper.find('[data-testid="form-type-score"]').setValue(true);

      expect(wrapper.find('[data-testid="submit-button"]').text()).toBe(
        'Submit Score'
      );
    });
  });

  // ===========================================================================
  // TESTS: FORM FIELDS
  // ===========================================================================

  describe('form fields', () => {
    it('renders season select', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      expect(wrapper.find('[data-testid="season-select"]').exists()).toBe(true);
    });

    it('renders age group select', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      expect(wrapper.find('[data-testid="age-group-select"]').exists()).toBe(
        true
      );
    });

    it('renders match type select', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      expect(wrapper.find('[data-testid="match-type-select"]').exists()).toBe(
        true
      );
    });

    it('renders status select', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      expect(wrapper.find('[data-testid="status-select"]').exists()).toBe(true);
    });

    it('renders date input', () => {
      const wrapper = mountMatchForm();

      expect(wrapper.find('[data-testid="date-input"]').exists()).toBe(true);
    });

    it('renders home team select', () => {
      const wrapper = mountMatchForm();

      expect(wrapper.find('[data-testid="home-team-select"]').exists()).toBe(
        true
      );
    });

    it('renders away team select', () => {
      const wrapper = mountMatchForm();

      expect(wrapper.find('[data-testid="away-team-select"]').exists()).toBe(
        true
      );
    });

    it('renders submit button', () => {
      const wrapper = mountMatchForm();

      expect(wrapper.find('[data-testid="submit-button"]').exists()).toBe(true);
    });
  });

  // ===========================================================================
  // TESTS: REFERENCE DATA LOADING
  // ===========================================================================

  describe('reference data loading', () => {
    it('fetches active seasons on mount', async () => {
      mountMatchForm();
      await flushPromises();

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/active-seasons'),
        expect.any(Object)
      );
    });

    it('fetches age groups on mount', async () => {
      mountMatchForm();
      await flushPromises();

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/age-groups'),
        expect.any(Object)
      );
    });

    it('fetches match types on mount', async () => {
      mountMatchForm();
      await flushPromises();

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/match-types'),
        expect.any(Object)
      );
    });

    it('fetches divisions on mount', async () => {
      mountMatchForm();
      await flushPromises();

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/divisions'),
        expect.any(Object)
      );
    });

    it('populates season dropdown with fetched data', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      const seasonSelect = wrapper.find('[data-testid="season-select"]');
      expect(seasonSelect.text()).toContain('2023-2024');
      expect(seasonSelect.text()).toContain('2024-2025');
      expect(seasonSelect.text()).toContain('2025-2026');
    });

    it('populates age group dropdown with fetched data', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      const ageGroupSelect = wrapper.find('[data-testid="age-group-select"]');
      expect(ageGroupSelect.text()).toContain('U14');
      expect(ageGroupSelect.text()).toContain('U12');
    });

    it('populates match type dropdown with fetched data', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      const matchTypeSelect = wrapper.find('[data-testid="match-type-select"]');
      expect(matchTypeSelect.text()).toContain('League');
      expect(matchTypeSelect.text()).toContain('Tournament');
      expect(matchTypeSelect.text()).toContain('Friendly');
    });
  });

  // ===========================================================================
  // TESTS: DIVISION SECTION (LEAGUE MATCHES ONLY)
  // ===========================================================================

  describe('division section', () => {
    it('shows division section for League match type', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      // League is default, should show division section
      expect(wrapper.find('[data-testid="division-section"]').exists()).toBe(
        true
      );
    });

    it('hides division section for non-League match types', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      // Change to Friendly (id: 3)
      await wrapper.find('[data-testid="match-type-select"]').setValue(3);
      await flushPromises();

      expect(wrapper.find('[data-testid="division-section"]').exists()).toBe(
        false
      );
    });

    it('renders division select with options', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      const divisionSelect = wrapper.find('[data-testid="division-select"]');
      expect(divisionSelect.exists()).toBe(true);
      expect(divisionSelect.text()).toContain('Northeast');
      expect(divisionSelect.text()).toContain('Southeast');
    });
  });

  // ===========================================================================
  // TESTS: STATUS SELECT
  // ===========================================================================

  describe('status select', () => {
    it('defaults to scheduled status', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      const statusSelect = wrapper.find('[data-testid="status-select"]');
      expect(statusSelect.element.value).toBe('scheduled');
    });

    it('includes all status options', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      const statusSelect = wrapper.find('[data-testid="status-select"]');
      expect(statusSelect.text()).toContain('Scheduled');
      expect(statusSelect.text()).toContain('Completed');
      expect(statusSelect.text()).toContain('Postponed');
      expect(statusSelect.text()).toContain('Cancelled');
    });

    it('can change status value', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      await wrapper.find('[data-testid="status-select"]').setValue('completed');

      expect(wrapper.find('[data-testid="status-select"]').element.value).toBe(
        'completed'
      );
    });
  });

  // ===========================================================================
  // TESTS: TEAM DROPDOWNS
  // ===========================================================================

  describe('team dropdowns', () => {
    it('fetches teams based on match type and age group', async () => {
      mountMatchForm();
      await flushPromises();

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/teams'),
        expect.any(Object)
      );
    });

    it('populates team dropdowns with fetched data', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      const homeTeamSelect = wrapper.find('[data-testid="home-team-select"]');
      const awayTeamSelect = wrapper.find('[data-testid="away-team-select"]');

      expect(homeTeamSelect.text()).toContain('Blue Stars U14');
      expect(awayTeamSelect.text()).toContain('Red Hawks U14');
    });

    it('includes "Select Team" placeholder option', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      const homeTeamSelect = wrapper.find('[data-testid="home-team-select"]');
      expect(homeTeamSelect.text()).toContain('Select Team');
    });
  });

  // ===========================================================================
  // TESTS: PLAYING UP (SB-1443)
  // ===========================================================================

  describe('playing up', () => {
    // The registered list answers the match_type/age_group query; the full
    // list (for_match_edit) also holds an academy registered only a year up.
    const registered = createMockTeams().slice(0, 2);
    const academyU16 = {
      id: 50,
      name: 'Pro Academy',
      age_groups: [{ id: 4, name: 'U16' }],
    };

    beforeEach(() => {
      const base = createMockFetch();
      global.fetch = vi.fn(url => {
        if (url.includes('/api/teams?for_match_edit=true')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve([...registered, academyU16]),
          });
        }
        if (url.includes('/api/teams')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(registered),
          });
        }
        return base(url);
      });
    });

    const awayGroups = wrapper =>
      wrapper
        .find('[data-testid="away-team-select"]')
        .findAll('optgroup')
        .map(g => ({
          label: g.attributes('label'),
          teams: g.findAll('option').map(o => o.text()),
        }));

    it('offers teams from other age groups for a Friendly', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();
      wrapper.vm.selectedMatchType = 3;
      await flushPromises();

      expect(awayGroups(wrapper)).toEqual([
        { label: 'U14 teams', teams: ['Blue Stars U14', 'Red Hawks U14'] },
        { label: 'Other age groups (playing up)', teams: ['Pro Academy'] },
      ]);
    });

    it('offers teams from other age groups for a Tournament', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();
      wrapper.vm.selectedMatchType = 2;
      await flushPromises();

      expect(wrapper.find('[data-testid="away-team-select"]').text()).toContain(
        'Pro Academy'
      );
    });

    it('keeps League strict: registered teams only, no full-list fetch', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      const away = wrapper.find('[data-testid="away-team-select"]');
      expect(away.findAll('optgroup')).toHaveLength(0);
      expect(away.text()).not.toContain('Pro Academy');
      expect(global.fetch).not.toHaveBeenCalledWith(
        expect.stringContaining('for_match_edit'),
        expect.anything()
      );
    });

    it('submits a playing-up opponent with the selected age group', async () => {
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve({ id: 1 }));
      const wrapper = mountMatchForm();
      await flushPromises();
      wrapper.vm.selectedMatchType = 3;
      await flushPromises();

      wrapper.vm.matchData.date = '2026-10-28';
      wrapper.vm.matchData.homeTeam = 1;
      wrapper.vm.matchData.awayTeam = 50;
      await wrapper.vm.$nextTick();
      await wrapper.find('form').trigger('submit');
      await flushPromises();

      const body = JSON.parse(
        mockAuthStore.apiRequest.mock.calls.at(-1)[1].body
      );
      expect(body).toMatchObject({
        home_team_id: 1,
        away_team_id: 50,
        match_type_id: 3,
        age_group_id: 3,
      });
    });
  });

  // ===========================================================================
  // TESTS: FORM VALIDATION
  // ===========================================================================

  describe('form validation', () => {
    it('shows error when home and away teams are the same', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      // Set same team for both
      await wrapper.find('[data-testid="home-team-select"]').setValue(1);
      await wrapper.find('[data-testid="away-team-select"]').setValue(1);
      await wrapper.find('[data-testid="date-input"]').setValue('2025-01-15');

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(wrapper.find('[data-testid="message"]').exists()).toBe(true);
      expect(wrapper.text()).toContain('same');
    });

    it('shows error for League match without division', async () => {
      const wrapper = mountMatchForm();
      await flushPromises();

      // Set up valid teams first
      await wrapper.find('[data-testid="home-team-select"]').setValue(1);
      await wrapper.find('[data-testid="away-team-select"]').setValue(2);
      await wrapper.find('[data-testid="date-input"]').setValue('2025-01-15');

      // Clear division selection AFTER other setup
      wrapper.vm.selectedDivision = null;
      await wrapper.vm.$nextTick();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(wrapper.find('[data-testid="message"]').exists()).toBe(true);
      expect(wrapper.text()).toContain('Division');
    });
  });

  // ===========================================================================
  // TESTS: FORM SUBMISSION
  // ===========================================================================

  describe('form submission', () => {
    it('calls apiRequest on valid form submit', async () => {
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve({ id: 1 }));
      global.fetch = createMockFetch({
        '/api/check-match': { exists: false },
      });
      const wrapper = mountMatchForm();
      await flushPromises();

      // Ensure we have a division selected (required for League)
      expect(wrapper.vm.selectedDivision).toBeTruthy();

      // Set form values directly to avoid watcher resets
      wrapper.vm.matchData.date = '2025-01-15';
      wrapper.vm.matchData.homeTeam = 1;
      wrapper.vm.matchData.awayTeam = 2;
      await wrapper.vm.$nextTick();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(mockAuthStore.apiRequest).toHaveBeenCalled();
    });

    it('uses POST method for new match', async () => {
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve({ id: 1 }));
      global.fetch = createMockFetch({
        '/api/check-match': { exists: false },
      });
      const wrapper = mountMatchForm();
      await flushPromises();

      // Set form values directly to avoid watcher resets
      wrapper.vm.matchData.date = '2025-01-15';
      wrapper.vm.matchData.homeTeam = 1;
      wrapper.vm.matchData.awayTeam = 2;
      await wrapper.vm.$nextTick();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(mockAuthStore.apiRequest).toHaveBeenCalledWith(
        expect.stringContaining('/api/matches'),
        expect.objectContaining({ method: 'POST' })
      );
    });

    it('shows success message on successful submit', async () => {
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve({ id: 1 }));
      global.fetch = createMockFetch({
        '/api/check-match': { exists: false },
      });
      const wrapper = mountMatchForm();
      await flushPromises();

      // Set form values directly to avoid watcher resets
      wrapper.vm.matchData.date = '2025-01-15';
      wrapper.vm.matchData.homeTeam = 1;
      wrapper.vm.matchData.awayTeam = 2;
      await wrapper.vm.$nextTick();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(wrapper.find('[data-testid="message"]').exists()).toBe(true);
      expect(wrapper.text()).toContain('successfully');
    });

    it('resets form after successful submit', async () => {
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve({ id: 1 }));
      global.fetch = createMockFetch({
        '/api/check-match': { exists: false },
      });
      const wrapper = mountMatchForm();
      await flushPromises();

      // Set form values directly to avoid watcher resets
      wrapper.vm.matchData.date = '2025-01-15';
      wrapper.vm.matchData.homeTeam = 1;
      wrapper.vm.matchData.awayTeam = 2;
      await wrapper.vm.$nextTick();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      // Form resets after successful submission
      expect(wrapper.vm.matchData.date).toBe('');
      expect(wrapper.vm.matchData.homeTeam).toBe('');
    });

    it('shows error message on submission failure', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.reject(new Error('Network error'))
      );
      global.fetch = createMockFetch({
        '/api/check-match': { exists: false },
      });
      const wrapper = mountMatchForm();
      await flushPromises();

      // Set form values directly to avoid watcher resets
      wrapper.vm.matchData.date = '2025-01-15';
      wrapper.vm.matchData.homeTeam = 1;
      wrapper.vm.matchData.awayTeam = 2;
      await wrapper.vm.$nextTick();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(wrapper.find('[data-testid="message"]').exists()).toBe(true);
      expect(wrapper.text()).toContain('Error');
    });
  });

  // ===========================================================================
  // TESTS: SCORE MODE SUBMISSION
  // ===========================================================================

  describe('score mode submission', () => {
    it('includes scores in submission when in score mode', async () => {
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve({ id: 1 }));
      global.fetch = createMockFetch({
        '/api/check-match': { exists: false },
      });
      const wrapper = mountMatchForm();
      await flushPromises();

      // Set form type and values directly to avoid watcher resets
      wrapper.vm.formType = 'score';
      wrapper.vm.matchData.date = '2025-01-15';
      wrapper.vm.matchData.homeTeam = 1;
      wrapper.vm.matchData.awayTeam = 2;
      wrapper.vm.matchData.homeScore = 3;
      wrapper.vm.matchData.awayScore = 1;
      await wrapper.vm.$nextTick();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(mockAuthStore.apiRequest).toHaveBeenCalled();
      const callArgs = mockAuthStore.apiRequest.mock.calls[0];
      const body = JSON.parse(callArgs[1].body);
      expect(body.home_score).toBe(3);
      expect(body.away_score).toBe(1);
    });
  });

  // ===========================================================================
  // TESTS: DUPLICATE MATCH CHECK
  // ===========================================================================

  describe('duplicate match check', () => {
    it('checks for existing match before scheduling', async () => {
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve({ id: 1 }));
      global.fetch = createMockFetch({
        '/api/check-match': { exists: false },
      });
      const wrapper = mountMatchForm();
      await flushPromises();

      // Set form values directly to avoid watcher resets
      wrapper.vm.matchData.date = '2025-01-15';
      wrapper.vm.matchData.homeTeam = 1;
      wrapper.vm.matchData.awayTeam = 2;
      await wrapper.vm.$nextTick();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      // The check-match call happens during form submission (GET request without options)
      const fetchCalls = global.fetch.mock.calls;
      const checkMatchCall = fetchCalls.find(call =>
        call[0].includes('/api/check-match')
      );
      expect(checkMatchCall).toBeTruthy();
    });

    it('shows error when match already exists in schedule mode', async () => {
      global.fetch = createMockFetch({
        '/api/check-match': { exists: true, match_id: 99 },
      });

      const wrapper = mountMatchForm();
      await flushPromises();

      // Set form values directly to avoid watcher resets
      wrapper.vm.matchData.date = '2025-01-15';
      wrapper.vm.matchData.homeTeam = 1;
      wrapper.vm.matchData.awayTeam = 2;
      await wrapper.vm.$nextTick();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(wrapper.find('[data-testid="message"]').exists()).toBe(true);
      expect(wrapper.text()).toContain('already scheduled');
    });

    it('uses PUT to update existing match in score mode', async () => {
      global.fetch = createMockFetch({
        '/api/check-match': { exists: true, match_id: 99 },
      });
      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve({ id: 99 }));

      const wrapper = mountMatchForm();
      await flushPromises();

      // Set form type and values directly
      wrapper.vm.formType = 'score';
      wrapper.vm.matchData.date = '2025-01-15';
      wrapper.vm.matchData.homeTeam = 1;
      wrapper.vm.matchData.awayTeam = 2;
      wrapper.vm.matchData.homeScore = 2;
      wrapper.vm.matchData.awayScore = 1;
      await wrapper.vm.$nextTick();

      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(mockAuthStore.apiRequest).toHaveBeenCalledWith(
        expect.stringContaining('/api/matches/99'),
        expect.objectContaining({ method: 'PUT' })
      );
    });
  });
});
