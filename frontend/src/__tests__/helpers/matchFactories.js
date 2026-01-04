/**
 * Mock Data Factories for Match Component Tests
 *
 * These factory functions create test data for:
 * - MatchesView.vue
 * - MatchDetailView.vue
 * - MatchEditModal.vue
 * - MatchForm.vue
 */

// =============================================================================
// REFERENCE DATA FACTORIES
// =============================================================================

export const createMockAgeGroups = () => [
  { id: 1, name: 'U10' },
  { id: 2, name: 'U12' },
  { id: 3, name: 'U14' },
  { id: 4, name: 'U16' },
  { id: 5, name: 'U19' },
];

export const createMockSeasons = () => [
  {
    id: 1,
    name: '2023-2024',
    start_date: '2023-08-01',
    end_date: '2024-07-31',
  },
  {
    id: 2,
    name: '2024-2025',
    start_date: '2024-08-01',
    end_date: '2025-07-31',
  },
  {
    id: 3,
    name: '2025-2026',
    start_date: '2025-08-01',
    end_date: '2026-07-31',
  },
];

export const createMockMatchTypes = () => [
  { id: 1, name: 'League' },
  { id: 2, name: 'Tournament' },
  { id: 3, name: 'Friendly' },
  { id: 4, name: 'Playoff' },
];

export const createMockLeagues = () => [
  { id: 1, name: 'Homegrown' },
  { id: 2, name: 'Academy' },
];

export const createMockDivisions = () => [
  { id: 1, name: 'Northeast', league_id: 1, leagues: { name: 'Homegrown' } },
  { id: 2, name: 'Southeast', league_id: 1, leagues: { name: 'Homegrown' } },
  { id: 3, name: 'West', league_id: 2, leagues: { name: 'Academy' } },
];

export const createMockClubs = () => [
  {
    id: 1,
    name: 'Blue Stars FC',
    logo_url: '/logos/blue-stars.png',
    primary_color: '#3B82F6',
  },
  {
    id: 2,
    name: 'Red Hawks SC',
    logo_url: '/logos/red-hawks.png',
    primary_color: '#EF4444',
  },
  {
    id: 3,
    name: 'Green Valley United',
    logo_url: null,
    primary_color: '#22C55E',
  },
];

// =============================================================================
// TEAM FACTORIES
// =============================================================================

export const createMockTeam = (overrides = {}) => ({
  id: 1,
  name: 'Blue Stars U14',
  club_id: 1,
  club_name: 'Blue Stars FC',
  age_groups: [{ id: 3, name: 'U14' }],
  divisions_by_age_group: {
    3: { id: 1, name: 'Northeast', league_id: 1, league_name: 'Homegrown' },
  },
  ...overrides,
});

export const createMockTeams = () => [
  createMockTeam({ id: 1, name: 'Blue Stars U14', club_id: 1 }),
  createMockTeam({
    id: 2,
    name: 'Red Hawks U14',
    club_id: 2,
    club_name: 'Red Hawks SC',
  }),
  createMockTeam({
    id: 3,
    name: 'Academy Elite U14',
    club_id: 3,
    club_name: 'Green Valley United',
    divisions_by_age_group: {
      3: { id: 3, name: 'West', league_id: 2, league_name: 'Academy' },
    },
  }),
  createMockTeam({
    id: 4,
    name: 'Blue Stars U12',
    club_id: 1,
    age_groups: [{ id: 2, name: 'U12' }],
    divisions_by_age_group: {
      2: { id: 1, name: 'Northeast', league_id: 1, league_name: 'Homegrown' },
    },
  }),
];

// =============================================================================
// MATCH FACTORIES
// =============================================================================

export const createMockMatch = (overrides = {}) => ({
  id: 1,
  match_date: '2025-01-15',
  home_team_id: 1,
  away_team_id: 2,
  home_team_name: 'Blue Stars U14',
  away_team_name: 'Red Hawks U14',
  home_score: null,
  away_score: null,
  match_status: 'scheduled',
  match_type_id: 1,
  match_type_name: 'League',
  season_id: 3,
  season_name: '2025-2026',
  age_group_id: 3,
  age_group_name: 'U14',
  division_id: 1,
  division_name: 'Northeast',
  division: { leagues: { name: 'Homegrown' } },
  source: 'manual',
  match_id: null,
  created_at: '2025-01-01T10:00:00Z',
  updated_at: '2025-01-01T10:00:00Z',
  home_team_club: {
    logo_url: '/logos/blue-stars.png',
    primary_color: '#3B82F6',
  },
  away_team_club: {
    logo_url: '/logos/red-hawks.png',
    primary_color: '#EF4444',
  },
  ...overrides,
});

export const createCompletedMatch = (overrides = {}) =>
  createMockMatch({
    match_status: 'completed',
    home_score: 3,
    away_score: 1,
    ...overrides,
  });

export const createLiveMatch = (overrides = {}) =>
  createMockMatch({
    match_status: 'live',
    home_score: 2,
    away_score: 2,
    ...overrides,
  });

export const createPostponedMatch = (overrides = {}) =>
  createMockMatch({
    match_status: 'postponed',
    ...overrides,
  });

export const createCancelledMatch = (overrides = {}) =>
  createMockMatch({
    match_status: 'cancelled',
    ...overrides,
  });

// Create matches for different leagues (for league grouping tests)
export const createHomegrownMatch = (overrides = {}) =>
  createMockMatch({
    division: { leagues: { name: 'Homegrown' } },
    ...overrides,
  });

export const createAcademyMatch = (overrides = {}) =>
  createMockMatch({
    division: { leagues: { name: 'Academy' } },
    home_team_id: 3,
    away_team_id: 4,
    home_team_name: 'Academy Elite U14',
    away_team_name: 'Academy Stars U14',
    ...overrides,
  });

// Create a collection of matches for list rendering tests
export const createMockMatchList = () => [
  createCompletedMatch({
    id: 1,
    match_date: '2025-01-10',
    home_score: 2,
    away_score: 1,
  }),
  createCompletedMatch({
    id: 2,
    match_date: '2025-01-12',
    home_score: 0,
    away_score: 3,
  }),
  createLiveMatch({ id: 3, match_date: '2025-01-15' }),
  createMockMatch({ id: 4, match_date: '2025-01-20' }), // scheduled
  createPostponedMatch({ id: 5, match_date: '2025-01-22' }),
];

// Create matches for season stats testing
export const createSeasonMatchList = () => [
  // Fall segment matches (Aug-Dec)
  createCompletedMatch({
    id: 1,
    match_date: '2025-09-15',
    home_score: 3,
    away_score: 1,
    home_team_id: 1,
    away_team_id: 2,
  }), // Win
  createCompletedMatch({
    id: 2,
    match_date: '2025-10-01',
    home_score: 2,
    away_score: 2,
    home_team_id: 1,
    away_team_id: 3,
  }), // Draw
  createCompletedMatch({
    id: 3,
    match_date: '2025-11-15',
    home_score: 0,
    away_score: 2,
    home_team_id: 2,
    away_team_id: 1,
  }), // Win (away)
  // Spring segment matches (Jan-Jul)
  createCompletedMatch({
    id: 4,
    match_date: '2026-01-20',
    home_score: 1,
    away_score: 3,
    home_team_id: 1,
    away_team_id: 2,
  }), // Loss
  createCompletedMatch({
    id: 5,
    match_date: '2026-02-10',
    home_score: 4,
    away_score: 0,
    home_team_id: 1,
    away_team_id: 3,
  }), // Win
];

// =============================================================================
// AUTH STORE FACTORIES
// =============================================================================

export const createMockAuthStore = (overrides = {}) => ({
  state: {
    loading: false,
    error: null,
    user: { id: 1 },
    session: { access_token: 'test-token' },
    profile: { role: 'admin', team_id: null, club_id: null },
    ...overrides.state,
  },
  isAuthenticated: { value: true },
  isAdmin: { value: true },
  isTeamManager: { value: false },
  isClubManager: { value: false },
  canBrowseAll: { value: true },
  userTeamId: { value: null },
  userClubId: { value: null },
  apiRequest: vi.fn(() => Promise.resolve([])),
  ...overrides,
});

// Convenience factory for team manager auth
export const createTeamManagerAuthStore = (teamId = 1, clubId = 1) =>
  createMockAuthStore({
    state: {
      loading: false,
      error: null,
      user: { id: 1 },
      session: { access_token: 'test-token' },
      profile: { role: 'team_manager', team_id: teamId, club_id: clubId },
    },
    isAdmin: { value: false },
    isTeamManager: { value: true },
    canBrowseAll: { value: false },
    userTeamId: { value: teamId },
    userClubId: { value: clubId },
  });

// Convenience factory for regular authenticated user
export const createAuthenticatedUserStore = () =>
  createMockAuthStore({
    state: {
      loading: false,
      error: null,
      user: { id: 1 },
      session: { access_token: 'test-token' },
      profile: { role: 'player', team_id: 1, club_id: 1 },
    },
    isAdmin: { value: false },
    isTeamManager: { value: false },
    canBrowseAll: { value: false },
    userTeamId: { value: 1 },
    userClubId: { value: 1 },
  });

// Convenience factory for unauthenticated state
export const createUnauthenticatedStore = () =>
  createMockAuthStore({
    state: {
      loading: false,
      error: null,
      user: null,
      session: null,
      profile: null,
    },
    isAuthenticated: { value: false },
    isAdmin: { value: false },
    isTeamManager: { value: false },
    canBrowseAll: { value: false },
    userTeamId: { value: null },
    userClubId: { value: null },
  });

// =============================================================================
// API RESPONSE HELPERS
// =============================================================================

/**
 * Creates a mock apiRequest function that returns different data based on URL
 * @param {Object} responses - Map of URL patterns to response data
 */
export const createMockApiRequest = (responses = {}) => {
  const defaultResponses = {
    '/api/age-groups': createMockAgeGroups(),
    '/api/seasons': createMockSeasons(),
    '/api/match-types': createMockMatchTypes(),
    '/api/leagues': createMockLeagues(),
    '/api/clubs': createMockClubs(),
    '/api/teams': createMockTeams(),
    '/api/matches': createMockMatchList(),
  };

  const mergedResponses = { ...defaultResponses, ...responses };

  return vi.fn(url => {
    // Find matching response based on URL pattern
    for (const [pattern, data] of Object.entries(mergedResponses)) {
      if (url.includes(pattern)) {
        return Promise.resolve(data);
      }
    }
    return Promise.resolve([]);
  });
};
