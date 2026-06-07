/**
 * Match Lineup Composable
 *
 * Shared logic for fetching and saving team rosters and lineups.
 * Used by both useLiveMatch (live matches) and MatchDetailView (pre-match).
 */

import { ref, isRef } from 'vue';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';

function unwrapMatchData(matchData) {
  return isRef(matchData) ? matchData.value : matchData;
}

export function useMatchLineup(matchId, matchData) {
  const authStore = useAuthStore();

  // Roster state
  const homeRoster = ref([]);
  const awayRoster = ref([]);

  // Lineup state
  const homeLineup = ref(null);
  const awayLineup = ref(null);
  const lineupLoading = ref(false);

  /**
   * Fetch rosters for both teams in the match.
   * Returns { home: [], away: [] } for compatibility with LiveAdminControls.
   */
  async function fetchTeamRosters() {
    const match = unwrapMatchData(matchData);
    if (!match) return { home: [], away: [] };

    const { home_team_id, away_team_id, season_id, age_group_id } = match;
    if (!season_id) return { home: [], away: [] };

    // SB-68: pass the match's age_group_id so the live-match path filters
    // strictly by age group. Without this, an IFA U15 match would pull
    // the IFA U14 roster (team_id is age-agnostic for umbrella clubs).
    const ageGroupParam =
      age_group_id != null ? `&age_group_id=${age_group_id}` : '';

    try {
      const [homeResponse, awayResponse] = await Promise.all([
        authStore.apiRequest(
          `${getApiBaseUrl()}/api/teams/${home_team_id}/roster?season_id=${season_id}${ageGroupParam}`
        ),
        authStore.apiRequest(
          `${getApiBaseUrl()}/api/teams/${away_team_id}/roster?season_id=${season_id}${ageGroupParam}`
        ),
      ]);

      homeRoster.value = homeResponse?.roster || [];
      awayRoster.value = awayResponse?.roster || [];

      return {
        home: homeRoster.value,
        away: awayRoster.value,
      };
    } catch (err) {
      // SB-118: propagate so callers can show an error + retry instead of
      // silently treating a failed fetch as an empty roster.
      console.error('Error fetching rosters:', err);
      throw err;
    }
  }

  /**
   * Fetch lineup for a single team.
   */
  async function fetchLineup(teamId) {
    try {
      const response = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/matches/${matchId}/lineup/${teamId}`
      );
      return response;
    } catch (err) {
      // SB-118: propagate — a failed fetch is not the same as "no lineup"
      console.error('Error fetching lineup:', err);
      throw err;
    }
  }

  /**
   * Fetch lineups for both teams, updating homeLineup/awayLineup refs.
   */
  async function fetchLineups() {
    const match = unwrapMatchData(matchData);
    if (!match) return;

    const { home_team_id, away_team_id } = match;
    lineupLoading.value = true;

    try {
      const [homeResponse, awayResponse] = await Promise.all([
        fetchLineup(home_team_id),
        fetchLineup(away_team_id),
      ]);

      homeLineup.value = homeResponse;
      awayLineup.value = awayResponse;
    } catch (err) {
      // SB-118: propagate so callers can show an error + retry
      console.error('Error fetching lineups:', err);
      throw err;
    } finally {
      lineupLoading.value = false;
    }
  }

  /**
   * Save lineup for a team. Updates the corresponding local ref.
   */
  async function saveLineup(teamId, formationName, positions) {
    try {
      const response = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/matches/${matchId}/lineup/${teamId}`,
        {
          method: 'PUT',
          body: JSON.stringify({
            formation_name: formationName,
            positions,
          }),
        }
      );

      // Update local state
      const match = unwrapMatchData(matchData);
      if (match) {
        if (teamId === match.home_team_id) {
          homeLineup.value = response;
        } else if (teamId === match.away_team_id) {
          awayLineup.value = response;
        }
      }

      return { success: true, lineup: response };
    } catch (err) {
      console.error('Error saving lineup:', err);
      return { success: false, error: err.message };
    }
  }

  return {
    // Roster state
    homeRoster,
    awayRoster,

    // Lineup state
    homeLineup,
    awayLineup,
    lineupLoading,

    // Methods
    fetchTeamRosters,
    fetchLineup,
    fetchLineups,
    saveLineup,
  };
}
