/**
 * useMatchLineup Composable Tests
 *
 * Tests for the shared roster/lineup fetch and save logic.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref } from 'vue';
import { useMatchLineup } from '@/composables/useMatchLineup';

// =============================================================================
// TEST SETUP
// =============================================================================

let mockAuthStore;

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}));

vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

const createMatchData = (overrides = {}) => ({
  home_team_id: 10,
  away_team_id: 20,
  season_id: 3,
  ...overrides,
});

// =============================================================================
// TESTS
// =============================================================================

describe('useMatchLineup', () => {
  beforeEach(() => {
    mockAuthStore = {
      apiRequest: vi.fn(() => Promise.resolve(null)),
    };
    vi.clearAllMocks();
  });

  describe('fetchTeamRosters', () => {
    it('fetches rosters for both teams and returns them', async () => {
      const homeRosterData = [
        { id: 1, display_name: 'Player A', jersey_number: 7 },
      ];
      const awayRosterData = [
        { id: 2, display_name: 'Player B', jersey_number: 9 },
      ];

      mockAuthStore.apiRequest = vi.fn(url => {
        if (url.includes('/api/teams/10/roster'))
          return Promise.resolve({ roster: homeRosterData });
        if (url.includes('/api/teams/20/roster'))
          return Promise.resolve({ roster: awayRosterData });
        return Promise.resolve(null);
      });

      const matchData = ref(createMatchData());
      const { fetchTeamRosters, homeRoster, awayRoster } = useMatchLineup(
        1,
        matchData
      );

      const result = await fetchTeamRosters();

      expect(result.home).toEqual(homeRosterData);
      expect(result.away).toEqual(awayRosterData);
      expect(homeRoster.value).toEqual(homeRosterData);
      expect(awayRoster.value).toEqual(awayRosterData);
    });

    it('returns empty arrays when matchData is null', async () => {
      const matchData = ref(null);
      const { fetchTeamRosters } = useMatchLineup(1, matchData);

      const result = await fetchTeamRosters();

      expect(result).toEqual({ home: [], away: [] });
    });

    it('returns empty arrays when season_id is missing', async () => {
      const matchData = ref(createMatchData({ season_id: null }));
      const { fetchTeamRosters } = useMatchLineup(1, matchData);

      const result = await fetchTeamRosters();

      expect(result).toEqual({ home: [], away: [] });
      expect(mockAuthStore.apiRequest).not.toHaveBeenCalled();
    });

    it('returns empty arrays on API error', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.reject(new Error('Network error'))
      );

      const matchData = ref(createMatchData());
      const { fetchTeamRosters } = useMatchLineup(1, matchData);

      const result = await fetchTeamRosters();

      expect(result).toEqual({ home: [], away: [] });
    });
  });

  describe('fetchLineups', () => {
    it('fetches lineups for both teams', async () => {
      const homeLineupData = {
        formation_name: '4-3-3',
        positions: [{ player_id: 1, position: 'GK' }],
      };
      const awayLineupData = {
        formation_name: '4-4-2',
        positions: [{ player_id: 2, position: 'GK' }],
      };

      mockAuthStore.apiRequest = vi.fn(url => {
        if (url.includes('/lineup/10')) return Promise.resolve(homeLineupData);
        if (url.includes('/lineup/20')) return Promise.resolve(awayLineupData);
        return Promise.resolve(null);
      });

      const matchData = ref(createMatchData());
      const { fetchLineups, homeLineup, awayLineup } = useMatchLineup(
        1,
        matchData
      );

      await fetchLineups();

      expect(homeLineup.value).toEqual(homeLineupData);
      expect(awayLineup.value).toEqual(awayLineupData);
    });

    it('does nothing when matchData is null', async () => {
      const matchData = ref(null);
      const { fetchLineups } = useMatchLineup(1, matchData);

      await fetchLineups();

      expect(mockAuthStore.apiRequest).not.toHaveBeenCalled();
    });
  });

  describe('saveLineup', () => {
    it('saves lineup and updates home ref', async () => {
      const savedLineup = {
        formation_name: '4-3-3',
        positions: [{ player_id: 1, position: 'GK' }],
      };

      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve(savedLineup));

      const matchData = ref(createMatchData());
      const { saveLineup, homeLineup } = useMatchLineup(1, matchData);

      const result = await saveLineup(10, '4-3-3', [
        { player_id: 1, position: 'GK' },
      ]);

      expect(result.success).toBe(true);
      expect(result.lineup).toEqual(savedLineup);
      expect(homeLineup.value).toEqual(savedLineup);
    });

    it('saves lineup and updates away ref', async () => {
      const savedLineup = {
        formation_name: '4-4-2',
        positions: [{ player_id: 2, position: 'GK' }],
      };

      mockAuthStore.apiRequest = vi.fn(() => Promise.resolve(savedLineup));

      const matchData = ref(createMatchData());
      const { saveLineup, awayLineup } = useMatchLineup(1, matchData);

      const result = await saveLineup(20, '4-4-2', [
        { player_id: 2, position: 'GK' },
      ]);

      expect(result.success).toBe(true);
      expect(awayLineup.value).toEqual(savedLineup);
    });

    it('returns error on failure', async () => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.reject(new Error('Save failed'))
      );

      const matchData = ref(createMatchData());
      const { saveLineup } = useMatchLineup(1, matchData);

      const result = await saveLineup(10, '4-3-3', []);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Save failed');
    });
  });
});
