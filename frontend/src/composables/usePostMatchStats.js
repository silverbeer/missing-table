/**
 * Post-Match Stats Composable
 *
 * Shared logic for recording goals, substitutions, and player stats
 * for completed matches. Follows the useMatchLineup pattern.
 */

import { ref, isRef } from 'vue';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';

function unwrapMatchData(matchData) {
  return isRef(matchData) ? matchData.value : matchData;
}

export function usePostMatchStats(matchId, matchData) {
  const authStore = useAuthStore();

  // State
  const homeStats = ref([]);
  const awayStats = ref([]);
  const statsLoading = ref(false);
  const saving = ref(false);
  const error = ref(null);

  /**
   * Check if the current user can edit stats for a specific team.
   */
  function canEditTeam(teamId) {
    if (!authStore.isAuthenticated.value) return false;
    if (authStore.isAdmin.value) return true;
    if (authStore.isClubManager.value) return true;
    if (authStore.isTeamManager.value) {
      return authStore.userTeamId.value === teamId;
    }
    return false;
  }

  /**
   * Fetch player stats for a specific team in this match.
   */
  async function fetchTeamStats(teamId) {
    try {
      const response = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/matches/${matchId}/post-match/stats/${teamId}`
      );
      return response?.stats || [];
    } catch (err) {
      console.error('Error fetching team stats:', err);
      return [];
    }
  }

  /**
   * Fetch stats for both teams.
   */
  async function fetchAllStats() {
    const match = unwrapMatchData(matchData);
    if (!match) return;

    statsLoading.value = true;
    try {
      const [home, away] = await Promise.all([
        fetchTeamStats(match.home_team_id),
        fetchTeamStats(match.away_team_id),
      ]);
      homeStats.value = home;
      awayStats.value = away;
    } catch (err) {
      console.error('Error fetching all stats:', err);
    } finally {
      statsLoading.value = false;
    }
  }

  /**
   * Record a goal for a completed match.
   */
  async function addGoal(goalData) {
    error.value = null;
    try {
      const response = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/matches/${matchId}/post-match/goal`,
        {
          method: 'POST',
          body: JSON.stringify(goalData),
        }
      );
      return { success: true, event: response };
    } catch (err) {
      console.error('Error adding goal:', err);
      error.value = err.message || 'Failed to add goal';
      return { success: false, error: err.message };
    }
  }

  /**
   * Remove a goal event.
   */
  async function removeGoal(eventId) {
    error.value = null;
    try {
      await authStore.apiRequest(
        `${getApiBaseUrl()}/api/matches/${matchId}/post-match/goal/${eventId}`,
        { method: 'DELETE' }
      );
      return { success: true };
    } catch (err) {
      console.error('Error removing goal:', err);
      error.value = err.message || 'Failed to remove goal';
      return { success: false, error: err.message };
    }
  }

  /**
   * Record a substitution for a completed match.
   */
  async function addSubstitution(subData) {
    error.value = null;
    try {
      const response = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/matches/${matchId}/post-match/substitution`,
        {
          method: 'POST',
          body: JSON.stringify(subData),
        }
      );
      return { success: true, event: response };
    } catch (err) {
      console.error('Error adding substitution:', err);
      error.value = err.message || 'Failed to add substitution';
      return { success: false, error: err.message };
    }
  }

  /**
   * Remove a substitution event.
   */
  async function removeSubstitution(eventId) {
    error.value = null;
    try {
      await authStore.apiRequest(
        `${getApiBaseUrl()}/api/matches/${matchId}/post-match/substitution/${eventId}`,
        { method: 'DELETE' }
      );
      return { success: true };
    } catch (err) {
      console.error('Error removing substitution:', err);
      error.value = err.message || 'Failed to remove substitution';
      return { success: false, error: err.message };
    }
  }

  /**
   * Batch save player stats (started, minutes_played) for a team.
   */
  async function savePlayerStats(teamId, entries) {
    saving.value = true;
    error.value = null;
    try {
      const response = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/matches/${matchId}/post-match/stats/${teamId}`,
        {
          method: 'PUT',
          body: JSON.stringify({ players: entries }),
        }
      );

      // Update local state
      const match = unwrapMatchData(matchData);
      if (match) {
        if (teamId === match.home_team_id) {
          homeStats.value = response?.stats || [];
        } else if (teamId === match.away_team_id) {
          awayStats.value = response?.stats || [];
        }
      }

      return { success: true, stats: response?.stats };
    } catch (err) {
      console.error('Error saving player stats:', err);
      error.value = err.message || 'Failed to save player stats';
      return { success: false, error: err.message };
    } finally {
      saving.value = false;
    }
  }

  return {
    homeStats,
    awayStats,
    statsLoading,
    saving,
    error,
    canEditTeam,
    fetchTeamStats,
    fetchAllStats,
    addGoal,
    removeGoal,
    addSubstitution,
    removeSubstitution,
    savePlayerStats,
  };
}
