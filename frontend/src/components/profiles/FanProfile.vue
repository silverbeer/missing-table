<template>
  <!-- Edit Profile Modal -->
  <div
    v-if="showEditProfile"
    class="modal-overlay"
    @click.self="showEditProfile = false"
  >
    <div class="edit-modal">
      <div class="modal-header">
        <h3>Edit Profile</h3>
        <button class="close-btn" @click="showEditProfile = false">
          &times;
        </button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label>Display Name</label>
          <input
            v-model="editForm.display_name"
            type="text"
            placeholder="Your display name"
          />
        </div>
        <div class="form-group">
          <label>Email</label>
          <input
            v-model="editForm.email"
            type="email"
            placeholder="your@email.com"
          />
        </div>
      </div>
      <div class="modal-footer">
        <button class="cancel-btn" @click="showEditProfile = false">
          Cancel
        </button>
        <button class="save-btn" @click="saveProfile" :disabled="saving">
          {{ saving ? 'Saving...' : 'Save Changes' }}
        </button>
      </div>
    </div>
  </div>

  <!-- My Team Picker Modal (SB-1543) -->
  <div
    v-if="showTeamPicker"
    class="modal-overlay"
    data-testid="team-picker"
    @click.self="closeTeamPicker"
  >
    <div class="edit-modal">
      <div class="modal-header">
        <h3>Pick your team</h3>
        <button class="close-btn" @click="closeTeamPicker">&times;</button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label for="pick-league">League</label>
          <select
            id="pick-league"
            v-model="pick.league"
            data-testid="pick-league"
            @change="onPickLeagueChange"
          >
            <option :value="null" disabled>Choose a league</option>
            <option v-for="l in leagueChoices" :key="l" :value="l">
              {{ l }}
            </option>
          </select>
        </div>
        <div v-if="pick.league" class="form-group">
          <label for="pick-age-group">Age group</label>
          <select
            id="pick-age-group"
            v-model="pick.ageGroupId"
            data-testid="pick-age-group"
            @change="pick.teamId = null"
          >
            <option :value="null" disabled>Choose an age group</option>
            <option v-for="ag in ageGroupChoices" :key="ag.id" :value="ag.id">
              {{ ag.name }}
            </option>
          </select>
        </div>
        <!-- Only when the club fields more than one squad at this league and
             age, e.g. three futsal teams at U14. -->
        <div v-if="squadChoices.length > 1" class="form-group">
          <label for="pick-squad">Team</label>
          <select
            id="pick-squad"
            v-model="pick.teamId"
            data-testid="pick-squad"
          >
            <option :value="null" disabled>Choose a team</option>
            <option
              v-for="o in squadChoices"
              :key="o.team_id"
              :value="o.team_id"
            >
              {{ o.name }}
            </option>
          </select>
        </div>
        <p
          v-if="teamSaveError"
          class="team-error"
          data-testid="team-save-error"
        >
          {{ teamSaveError }}
        </p>
      </div>
      <div class="modal-footer">
        <button class="cancel-btn" @click="closeTeamPicker">Cancel</button>
        <button
          class="save-btn"
          data-testid="save-team"
          :disabled="teamSaving || !pickedOption"
          @click="saveTeam"
        >
          {{ teamSaving ? 'Saving...' : 'Save' }}
        </button>
      </div>
    </div>
  </div>

  <div class="fan-dashboard">
    <!-- Hero Card with Club/League Info -->
    <div class="hero-card" :style="heroCardStyle">
      <div class="hero-logo">
        <img
          v-if="club?.logo_url"
          :src="club.logo_url"
          :alt="club.name"
          class="club-logo-img"
        />
        <div v-else-if="club" class="club-logo-placeholder">
          <span>{{ (club?.name || 'C').charAt(0).toUpperCase() }}</span>
        </div>
        <div v-else class="league-logo-placeholder">
          <span>⚽</span>
        </div>
      </div>
      <div class="hero-info">
        <div class="club-name-row">
          <h2 class="club-name">{{ club?.name || 'League Fan' }}</h2>
          <span class="role-badge">{{ club ? 'Club Fan' : 'Fan' }}</span>
        </div>

        <div v-if="club?.city" class="location-line">{{ club.city }}</div>

        <div class="fan-info">
          <span class="fan-name">{{ displayName }}</span>
          <span class="separator">|</span>
          <span class="member-since">
            Member since {{ formatDate(authStore.state.profile?.created_at) }}
          </span>
        </div>

        <div class="hero-stats">
          <div class="hero-stat">
            <span class="stat-number">{{ clubTeams.length || '—' }}</span>
            <span class="stat-label">{{ club ? 'Club Teams' : 'Teams' }}</span>
          </div>
          <div class="hero-stat">
            <span class="stat-number">{{ upcomingMatchCount }}</span>
            <span class="stat-label">Upcoming</span>
          </div>
          <div class="hero-stat">
            <span class="stat-number">{{ followedTeam ? '1' : '0' }}</span>
            <span class="stat-label">Following</span>
          </div>
        </div>

        <div class="hero-actions">
          <button class="action-btn primary" @click="openEditProfile">
            Edit Profile
          </button>
        </div>
        <LiveUpdatesTeaser variant="hero" />
      </div>
    </div>

    <!-- My Team (SB-1543): a fan's club + league + age group. Not picking
         one is a normal state, so the card prompts rather than warns. -->
    <div v-if="teamOptions" class="my-team-section" data-testid="my-team-card">
      <h3>My team</h3>
      <p v-if="teamOptions.status === 'no_club'" data-testid="my-team-no-club">
        Your account isn't linked to a club yet
      </p>
      <template v-else-if="currentOption">
        <div class="my-team-row">
          <span class="my-team-label" data-testid="my-team-label">
            {{ optionLabel(currentOption) }}
          </span>
          <div class="my-team-actions">
            <button
              class="link-btn my-team-btn"
              data-testid="change-team"
              @click="openTeamPicker"
            >
              Change
            </button>
            <button
              class="link-btn my-team-btn"
              data-testid="clear-team"
              :disabled="teamSaving"
              @click="clearTeam"
            >
              Clear
            </button>
          </div>
        </div>
      </template>
      <template v-else>
        <p class="my-team-hint" data-testid="my-team-prompt">
          Pick your team to personalize the app, and so MT AI knows who you mean
          when you ask about "my team".
        </p>
        <button
          class="action-btn my-team-pick-btn"
          data-testid="pick-team"
          @click="openTeamPicker"
        >
          Pick your team
        </button>
      </template>
      <p
        v-if="teamSaveError && !showTeamPicker"
        class="team-error"
        data-testid="team-card-error"
      >
        {{ teamSaveError }}
      </p>
    </div>

    <!-- Club Teams Section (for Club Fans) - Grouped by League > Division -->
    <div
      v-if="club && groupedTeams.length > 0"
      class="club-teams-section"
      :style="clubTeamsStyle"
    >
      <h3>{{ club.name }} Teams</h3>
      <div class="leagues-container">
        <div
          v-for="league in groupedTeams"
          :key="league.id"
          class="league-group"
        >
          <div class="league-header" :style="leagueHeaderStyle">
            <span class="league-icon">🏆</span>
            <span class="league-name">{{ league.name }}</span>
          </div>
          <div class="divisions-container">
            <div
              v-for="division in league.divisions"
              :key="division.id"
              class="division-group"
            >
              <div class="division-header" :style="divisionHeaderStyle">
                {{ division.name }}
              </div>
              <div class="age-groups-list">
                <div
                  v-for="ageGroup in division.ageGroups"
                  :key="ageGroup.id"
                  class="age-group-row"
                >
                  <span class="age-group-name">{{ ageGroup.name }}</span>
                  <div class="age-group-links">
                    <button
                      class="link-btn table-link"
                      :style="tableLinkStyle"
                      @click="
                        goToTableWithFilters(
                          ageGroup.id,
                          league.id,
                          division.id
                        )
                      "
                    >
                      Table
                    </button>
                    <button
                      class="link-btn matches-link"
                      :style="matchesLinkStyle"
                      @click="
                        goToMatchesWithFilters(
                          ageGroup.id,
                          league.id,
                          division.id
                        )
                      "
                    >
                      Matches
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Access Section -->
    <div class="quick-access-section">
      <h3>Quick Access</h3>
      <div class="quick-cards">
        <div class="quick-card" @click="goToStandings">
          <div class="quick-icon">📊</div>
          <div class="quick-content">
            <h4>League Standings</h4>
            <p>Check current league positions</p>
          </div>
          <div class="quick-arrow">&rarr;</div>
        </div>

        <div class="quick-card" @click="goToSchedule">
          <div class="quick-icon">📅</div>
          <div class="quick-content">
            <h4>Match Schedule</h4>
            <p>See upcoming fixtures</p>
          </div>
          <div class="quick-arrow">&rarr;</div>
        </div>

        <div class="quick-card" @click="goToTeams">
          <div class="quick-icon">👥</div>
          <div class="quick-content">
            <h4>All Teams</h4>
            <p>Explore team profiles</p>
          </div>
          <div class="quick-arrow">&rarr;</div>
        </div>
      </div>
    </div>

    <!-- Upcoming Matches -->
    <div v-if="upcomingMatches.length > 0" class="upcoming-section">
      <h3>Upcoming Matches</h3>
      <div class="matches-list">
        <div
          v-for="match in upcomingMatches.slice(0, 5)"
          :key="match.id"
          class="match-card"
        >
          <div class="match-date">
            {{ formatMatchDate(match.game_date) }}
          </div>
          <div class="match-teams">
            <span class="home-team">{{ match.home_team_name }}</span>
            <span class="vs">vs</span>
            <span class="away-team">{{ match.away_team_name }}</span>
          </div>
          <div class="match-type">{{ match.match_type_name || 'League' }}</div>
        </div>
      </div>
    </div>

    <!-- Fan Features -->
    <div class="features-section">
      <h3>Fan Features</h3>
      <p class="section-description">
        As a {{ club ? club.name : 'league' }} fan, you have access to these
        features:
      </p>
      <div class="features-grid">
        <div class="feature-card">
          <div class="feature-icon">📊</div>
          <h4>Live Standings</h4>
          <p>Track league positions in real-time</p>
        </div>

        <div class="feature-card">
          <div class="feature-icon">📅</div>
          <h4>Full Schedule</h4>
          <p>Access all upcoming fixtures</p>
        </div>

        <div class="feature-card">
          <div class="feature-icon">⚽</div>
          <h4>Match Results</h4>
          <p>View scores and match details</p>
        </div>

        <div class="feature-card">
          <div class="feature-icon">👥</div>
          <h4>Team Profiles</h4>
          <p>Explore all teams in the league</p>
        </div>
      </div>
    </div>
    <LiveUpdatesSection />
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';
import { hasAnyRole } from '../../utils/roles';
import LiveUpdatesTeaser from './LiveUpdatesTeaser.vue';
import LiveUpdatesSection from './LiveUpdatesSection.vue';

export default {
  name: 'FanProfile',
  components: { LiveUpdatesTeaser, LiveUpdatesSection },
  emits: ['logout', 'navigate'],
  setup(props, { emit }) {
    const authStore = useAuthStore();
    const club = ref(null);
    const clubTeams = ref([]);
    const upcomingMatches = ref([]);
    const showEditProfile = ref(false);
    const saving = ref(false);

    // --- My team (SB-1543) ---
    // null until loaded; stays null for non-fans so the card does not render.
    const teamOptions = ref(null);
    const showTeamPicker = ref(false);
    const teamSaving = ref(false);
    const teamSaveError = ref(null);
    const pick = reactive({ league: null, ageGroupId: null, teamId: null });

    const editForm = reactive({
      display_name: '',
      email: '',
    });

    const displayName = computed(() => {
      return (
        authStore.state.profile?.display_name ||
        authStore.state.profile?.username ||
        'Fan'
      );
    });

    const followedTeam = computed(() => {
      return authStore.state.profile?.team || null;
    });

    const pickOptions = computed(() => teamOptions.value?.options || []);

    const sameSlot = (a, b) =>
      a.league_name === b.league_name && a.age_group?.id === b.age_group?.id;

    // "IFA · Homegrown · U15"; the team name is added only when the club has
    // more than one squad at that league and age (the futsal case).
    const optionLabel = option => {
      const parts = [
        option.club_name || teamOptions.value?.club?.name,
        option.league_name,
        option.age_group?.name,
      ];
      if (pickOptions.value.filter(o => sameSlot(o, option)).length > 1) {
        parts.push(option.name);
      }
      return parts.filter(Boolean).join(' · ');
    };

    const currentOption = computed(() => {
      const opts = teamOptions.value;
      if (!opts?.current_team_id || !opts?.current_age_group_id) return null;
      return (
        pickOptions.value.find(
          o =>
            o.team_id === opts.current_team_id &&
            o.age_group?.id === opts.current_age_group_id
        ) || null
      );
    });

    const leagueChoices = computed(() => [
      ...new Set(pickOptions.value.map(o => o.league_name)),
    ]);

    const ageGroupChoices = computed(() => {
      const seen = new Map();
      pickOptions.value
        .filter(o => o.league_name === pick.league && o.age_group)
        .forEach(o => {
          if (!seen.has(o.age_group.id)) seen.set(o.age_group.id, o.age_group);
        });
      return [...seen.values()];
    });

    const squadChoices = computed(() =>
      pickOptions.value.filter(
        o =>
          o.league_name === pick.league && o.age_group?.id === pick.ageGroupId
      )
    );

    // A single squad at the chosen league and age is selected automatically.
    const pickedOption = computed(() => {
      const squads = squadChoices.value;
      if (squads.length === 1) return squads[0];
      return squads.find(o => o.team_id === pick.teamId) || null;
    });

    const upcomingMatchCount = computed(() => {
      return upcomingMatches.value.length;
    });

    const clubColors = computed(() => {
      return {
        primary: club.value?.primary_color || '#1e3a8a',
        secondary: club.value?.secondary_color || '#3b82f6',
      };
    });

    const heroCardStyle = computed(() => {
      return {
        background: `linear-gradient(135deg, ${clubColors.value.primary} 0%, ${clubColors.value.secondary} 100%)`,
      };
    });

    // Club-themed styles for the teams section
    const clubTeamsStyle = computed(() => {
      return {
        '--club-primary': clubColors.value.primary,
        '--club-secondary': clubColors.value.secondary,
      };
    });

    const leagueHeaderStyle = computed(() => {
      return {
        background: `linear-gradient(135deg, ${clubColors.value.primary} 0%, ${clubColors.value.secondary} 100%)`,
      };
    });

    const divisionHeaderStyle = computed(() => {
      // Lighter version of primary color for division headers
      return {
        background: `${clubColors.value.primary}15`,
        color: clubColors.value.primary,
        borderLeft: `3px solid ${clubColors.value.primary}`,
      };
    });

    const tableLinkStyle = computed(() => {
      return {
        background: `${clubColors.value.secondary}20`,
        color: clubColors.value.primary,
      };
    });

    const matchesLinkStyle = computed(() => {
      return {
        background: `${clubColors.value.primary}20`,
        color: clubColors.value.primary,
      };
    });

    // Group teams by League > Division > Age Groups
    const groupedTeams = computed(() => {
      const leagues = {};

      clubTeams.value.forEach(team => {
        const leagueId = team.leagues?.id || team.league_id;
        const leagueName =
          team.leagues?.name || team.league_name || 'Unknown League';

        if (!leagues[leagueId]) {
          leagues[leagueId] = {
            id: leagueId,
            name: leagueName,
            divisions: {},
          };
        }

        // Process team_mappings for division and age group info
        const mappings = team.team_mappings || [];
        mappings.forEach(mapping => {
          const divisionId = mapping.divisions?.id || mapping.division_id;
          const divisionName = mapping.divisions?.name || 'Unknown Division';
          const ageGroupId = mapping.age_groups?.id || mapping.age_group_id;
          const ageGroupName = mapping.age_groups?.name || 'Unknown';

          if (!divisionId) return;

          if (!leagues[leagueId].divisions[divisionId]) {
            leagues[leagueId].divisions[divisionId] = {
              id: divisionId,
              name: divisionName,
              ageGroups: {},
            };
          }

          if (
            ageGroupId &&
            !leagues[leagueId].divisions[divisionId].ageGroups[ageGroupId]
          ) {
            leagues[leagueId].divisions[divisionId].ageGroups[ageGroupId] = {
              id: ageGroupId,
              name: ageGroupName,
              leagueId: leagueId,
              divisionId: divisionId,
            };
          }
        });
      });

      // Convert to sorted array
      return Object.values(leagues)
        .map(league => ({
          ...league,
          divisions: Object.values(league.divisions)
            .map(division => ({
              ...division,
              ageGroups: Object.values(division.ageGroups).sort((a, b) =>
                a.name.localeCompare(b.name, undefined, { numeric: true })
              ),
            }))
            .sort((a, b) => a.name.localeCompare(b.name)),
        }))
        .sort((a, b) => a.name.localeCompare(b.name));
    });

    const formatDate = dateString => {
      if (!dateString) return '';
      return new Date(dateString).toLocaleDateString('en-US', {
        month: 'short',
        year: 'numeric',
      });
    };

    const formatMatchDate = dateString => {
      if (!dateString) return '';
      return new Date(dateString).toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
      });
    };

    const fetchClub = async () => {
      const clubId = authStore.state.profile?.club_id;
      if (!clubId) return;

      try {
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/clubs/${clubId}`
        );
        if (response) {
          club.value = response;
          // Fetch club teams after getting club
          await fetchClubTeams(clubId);
        }
      } catch (error) {
        console.error('Error fetching club:', error);
      }
    };

    const fetchClubTeams = async clubId => {
      try {
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/clubs/${clubId}/teams`
        );
        if (response) {
          clubTeams.value = response;
        }
      } catch (error) {
        console.error('Error fetching club teams:', error);
      }
    };

    const fetchUpcomingMatches = async () => {
      try {
        const response = await fetch(`${getApiBaseUrl()}/api/matches/upcoming`);
        if (response.ok) {
          const matches = await response.json();
          // Filter to club teams if user is a club fan
          if (club.value && clubTeams.value.length > 0) {
            const teamIds = clubTeams.value.map(t => t.id);
            upcomingMatches.value = matches.filter(
              m =>
                teamIds.includes(m.home_team_id) ||
                teamIds.includes(m.away_team_id)
            );
          } else {
            upcomingMatches.value = matches.slice(0, 10);
          }
        }
      } catch (error) {
        console.error('Error fetching upcoming matches:', error);
      }
    };

    const fetchTeamOptions = async () => {
      if (
        !hasAnyRole(['team-fan', 'club-fan'], authStore.state.profile?.role)
      ) {
        return;
      }
      try {
        teamOptions.value = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/me/team-options`
        );
      } catch (error) {
        // A 403 means this account does not pick a team; leave the card out.
        console.error('Error fetching team options:', error);
        teamOptions.value = null;
      }
    };

    const openTeamPicker = () => {
      const current = currentOption.value;
      pick.league = current?.league_name ?? null;
      pick.ageGroupId = current?.age_group?.id ?? null;
      pick.teamId = current?.team_id ?? null;
      teamSaveError.value = null;
      showTeamPicker.value = true;
    };

    const closeTeamPicker = () => {
      showTeamPicker.value = false;
      teamSaveError.value = null;
    };

    const onPickLeagueChange = () => {
      pick.ageGroupId = null;
      pick.teamId = null;
    };

    const putTeam = async body => {
      teamSaving.value = true;
      teamSaveError.value = null;
      try {
        await authStore.apiRequest(`${getApiBaseUrl()}/api/me/team`, {
          method: 'PUT',
          body: JSON.stringify(body),
        });
        await Promise.all([authStore.fetchProfile(), fetchTeamOptions()]);
        return true;
      } catch (error) {
        // The API's detail ("That team and age group aren't in your club")
        // is the sentence the fan needs.
        teamSaveError.value = error.message || 'Could not save your team';
        return false;
      } finally {
        teamSaving.value = false;
      }
    };

    const saveTeam = async () => {
      const option = pickedOption.value;
      if (!option || teamSaving.value) return;
      const saved = await putTeam({
        team_id: option.team_id,
        age_group_id: option.age_group.id,
      });
      if (saved) showTeamPicker.value = false;
    };

    const clearTeam = async () => {
      if (teamSaving.value) return;
      await putTeam({});
    };

    const initEditForm = () => {
      editForm.display_name = authStore.state.profile?.display_name || '';
      editForm.email = authStore.state.profile?.email || '';
    };

    const openEditProfile = () => {
      initEditForm();
      showEditProfile.value = true;
    };

    const saveProfile = async () => {
      saving.value = true;
      try {
        const result = await authStore.updateProfile({
          display_name: editForm.display_name,
          email: editForm.email,
        });
        if (result.success) {
          showEditProfile.value = false;
        }
      } catch (error) {
        console.error('Error saving profile:', error);
      } finally {
        saving.value = false;
      }
    };

    const goToStandings = () => {
      emit('navigate', 'table');
    };

    const goToSchedule = () => {
      emit('navigate', 'scores');
    };

    const goToTeams = () => {
      // Teams tab may not exist - navigate to standings as fallback
      emit('navigate', 'table');
    };

    const goToTeam = team => {
      // Extract filter IDs from team data
      // The team object from get_club_teams includes:
      // - age_groups: array of {id, name} (processed by backend)
      // - team_mappings: raw data with nested age_groups and divisions
      // - leagues: {id, name} from foreign key
      // - league_id: direct column value

      // Get age group ID - try processed array first, then raw team_mappings
      const ageGroupId =
        team.age_groups?.[0]?.id ||
        team.team_mappings?.[0]?.age_groups?.id ||
        null;

      // Get league ID - try leagues object first, then direct column
      const leagueId = team.leagues?.id || team.league_id || null;

      // Get division ID from team_mappings
      const divisionId = team.team_mappings?.[0]?.divisions?.id || null;

      const filters = {
        ageGroupId,
        leagueId,
        divisionId,
      };

      console.log('Navigating to table with filters:', filters);
      console.log('Team data:', {
        age_groups: team.age_groups,
        team_mappings: team.team_mappings,
        leagues: team.leagues,
        league_id: team.league_id,
      });

      // Navigate to table with filters
      emit('navigate', 'table', filters);
    };

    const goToTableWithFilters = (ageGroupId, leagueId, divisionId) => {
      const filters = { ageGroupId, leagueId, divisionId };
      emit('navigate', 'table', filters);
    };

    const goToMatchesWithFilters = (ageGroupId, leagueId, divisionId) => {
      const filters = { ageGroupId, leagueId, divisionId };
      emit('navigate', 'scores', filters);
    };

    onMounted(async () => {
      fetchTeamOptions();
      await fetchClub();
      await fetchUpcomingMatches();
    });

    return {
      authStore,
      club,
      clubTeams,
      groupedTeams,
      upcomingMatches,
      showEditProfile,
      saving,
      editForm,
      displayName,
      followedTeam,
      teamOptions,
      showTeamPicker,
      teamSaving,
      teamSaveError,
      pick,
      currentOption,
      leagueChoices,
      ageGroupChoices,
      squadChoices,
      pickedOption,
      optionLabel,
      openTeamPicker,
      closeTeamPicker,
      onPickLeagueChange,
      saveTeam,
      clearTeam,
      upcomingMatchCount,
      heroCardStyle,
      clubTeamsStyle,
      leagueHeaderStyle,
      divisionHeaderStyle,
      tableLinkStyle,
      matchesLinkStyle,
      formatDate,
      formatMatchDate,
      openEditProfile,
      saveProfile,
      goToStandings,
      goToSchedule,
      goToTeams,
      goToTeam,
      goToTableWithFilters,
      goToMatchesWithFilters,
    };
  },
};
</script>

<style scoped>
.fan-dashboard {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
}

/* Hero Card */
.hero-card {
  display: flex;
  gap: 30px;
  padding: 30px;
  border-radius: 16px;
  color: white;
  margin-bottom: 30px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.hero-logo {
  flex-shrink: 0;
}

.club-logo-img {
  width: 120px;
  height: 120px;
  object-fit: contain;
  border-radius: 12px;
}

.club-logo-placeholder,
.league-logo-placeholder {
  width: 120px;
  height: 120px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.club-logo-placeholder span {
  font-size: 48px;
  font-weight: bold;
  color: white;
}

.league-logo-placeholder span {
  font-size: 48px;
}

.hero-info {
  flex: 1;
}

.club-name-row {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 8px;
}

.club-name {
  font-size: 28px;
  font-weight: 700;
  margin: 0;
}

.role-badge {
  background: rgba(255, 255, 255, 0.2);
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
}

.location-line {
  font-size: 14px;
  opacity: 0.9;
  margin-bottom: 10px;
}

.fan-info {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  font-size: 14px;
  opacity: 0.9;
}

.separator {
  opacity: 0.5;
}

.hero-stats {
  display: flex;
  gap: 30px;
  margin-bottom: 20px;
}

.hero-stat {
  text-align: center;
}

.stat-number {
  display: block;
  font-size: 28px;
  font-weight: 700;
}

.stat-label {
  display: block;
  font-size: 12px;
  opacity: 0.8;
  text-transform: uppercase;
}

.hero-actions {
  display: flex;
  gap: 12px;
}

.action-btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  font-size: 14px;
}

.action-btn.primary {
  background: white;
  color: #1e3a8a;
}

.action-btn.primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.action-btn.secondary {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.action-btn.secondary:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* My Team (SB-1543) */
.my-team-section {
  background: rgb(var(--color-card));
  border-radius: 12px;
  padding: 25px;
  margin-bottom: 25px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  color: rgb(var(--color-fg));
}

.my-team-section h3 {
  margin-bottom: 12px;
  font-size: 18px;
}

.my-team-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.my-team-label {
  font-weight: 600;
  font-size: 16px;
}

.my-team-actions {
  display: flex;
  gap: 8px;
}

.my-team-btn {
  background: rgb(var(--color-surface-alt));
  color: rgb(var(--color-fg));
}

.my-team-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.my-team-hint {
  color: rgb(var(--color-fg-muted));
  font-size: 14px;
  margin-bottom: 12px;
}

.action-btn.my-team-pick-btn {
  background: #3b82f6;
  color: white;
}

.team-error {
  margin-top: 10px;
  color: #dc2626;
  font-size: 14px;
}

/* Club Teams Section - Grouped Layout */
.club-teams-section {
  background: rgb(var(--color-card));
  border-radius: 12px;
  padding: 25px;
  margin-bottom: 25px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.club-teams-section h3 {
  color: rgb(var(--color-fg));
  margin-bottom: 20px;
  font-size: 18px;
}

.leagues-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.league-group {
  border: 1px solid rgb(var(--color-line));
  border-radius: 10px;
  overflow: hidden;
}

.league-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  /* Background set via inline style for club theming */
  color: white;
  font-weight: 600;
  font-size: 15px;
}

.league-icon {
  font-size: 18px;
}

.league-name {
  flex: 1;
}

.divisions-container {
  padding: 0;
}

.division-group {
  border-bottom: 1px solid rgb(var(--color-line));
}

.division-group:last-child {
  border-bottom: none;
}

.division-header {
  padding: 10px 16px;
  /* Background and color set via inline style for club theming */
  font-weight: 600;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.age-groups-list {
  padding: 0;
}

.age-group-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgb(var(--color-line));
  transition: background 0.15s;
}

.age-group-row:last-child {
  border-bottom: none;
}

.age-group-row:hover {
  background: rgb(var(--color-surface-alt));
}

.age-group-name {
  font-weight: 500;
  color: rgb(var(--color-fg));
  font-size: 14px;
}

.age-group-links {
  display: flex;
  gap: 8px;
}

.link-btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  border: none;
}

.link-btn.table-link {
  /* Background and color set via inline style for club theming */
}

.link-btn.table-link:hover {
  filter: brightness(0.9);
}

.link-btn.matches-link {
  /* Background and color set via inline style for club theming */
}

.link-btn.matches-link:hover {
  filter: brightness(0.9);
}

/* Quick Access */
.quick-access-section {
  background: rgb(var(--color-card));
  border-radius: 12px;
  padding: 25px;
  margin-bottom: 25px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.quick-access-section h3 {
  color: rgb(var(--color-fg));
  margin-bottom: 20px;
  font-size: 18px;
}

.quick-cards {
  display: grid;
  gap: 12px;
}

.quick-card {
  display: flex;
  align-items: center;
  padding: 18px;
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #bae6fd;
}

.quick-card:hover {
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
}

.quick-icon {
  font-size: 28px;
  margin-right: 18px;
}

.quick-content {
  flex: 1;
}

.quick-content h4 {
  margin: 0;
  color: #1e40af;
  font-size: 16px;
}

.quick-content p {
  margin: 4px 0 0;
  color: #3b82f6;
  font-size: 13px;
}

.quick-arrow {
  color: #3b82f6;
  font-size: 20px;
  font-weight: bold;
}

/* Upcoming Matches */
.upcoming-section {
  background: rgb(var(--color-card));
  border-radius: 12px;
  padding: 25px;
  margin-bottom: 25px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.upcoming-section h3 {
  color: rgb(var(--color-fg));
  margin-bottom: 20px;
  font-size: 18px;
}

.matches-list {
  display: grid;
  gap: 10px;
}

.match-card {
  display: grid;
  grid-template-columns: 100px 1fr 80px;
  align-items: center;
  padding: 15px;
  background: rgb(var(--color-surface-alt));
  border-radius: 8px;
  border: 1px solid rgb(var(--color-line));
}

.match-date {
  font-size: 12px;
  color: rgb(var(--color-fg-muted));
  font-weight: 500;
}

.match-teams {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.home-team,
.away-team {
  font-weight: 500;
  color: rgb(var(--color-fg));
}

.vs {
  color: rgb(var(--color-fg-muted));
  font-size: 12px;
}

.match-type {
  text-align: right;
  font-size: 11px;
  color: rgb(var(--color-fg-muted));
  text-transform: uppercase;
}

/* Features Section */
.features-section {
  background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
  border-radius: 12px;
  padding: 25px;
  margin-bottom: 25px;
  border: 1px solid #a7f3d0;
}

.features-section h3 {
  color: #047857;
  margin-bottom: 10px;
  font-size: 18px;
}

.section-description {
  color: #065f46;
  margin-bottom: 20px;
  font-size: 14px;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 15px;
}

.feature-card {
  background: rgb(var(--color-card));
  padding: 20px;
  border-radius: 10px;
  text-align: center;
  border: 1px solid #d1fae5;
  transition: all 0.2s;
}

.feature-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.15);
}

.feature-icon {
  font-size: 28px;
  margin-bottom: 10px;
}

.feature-card h4 {
  margin: 0 0 8px;
  color: #047857;
  font-size: 15px;
}

.feature-card p {
  margin: 0;
  color: rgb(var(--color-fg-muted));
  font-size: 13px;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.edit-modal {
  background: rgb(var(--color-card));
  border-radius: 12px;
  width: 90%;
  max-width: 450px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid rgb(var(--color-line));
}

.modal-header h3 {
  margin: 0;
  color: rgb(var(--color-fg));
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  color: rgb(var(--color-fg-muted));
  cursor: pointer;
}

.close-btn:hover {
  color: rgb(var(--color-fg));
}

.modal-body {
  padding: 20px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 600;
  color: rgb(var(--color-fg));
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 12px;
  border: 1px solid rgb(var(--color-line));
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
  background: rgb(var(--color-card));
  color: rgb(var(--color-fg));
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px;
  border-top: 1px solid rgb(var(--color-line));
}

.cancel-btn {
  padding: 10px 20px;
  background: rgb(var(--color-surface-alt));
  border: 1px solid rgb(var(--color-line));
  border-radius: 8px;
  color: rgb(var(--color-fg-muted));
  cursor: pointer;
  font-weight: 500;
}

.cancel-btn:hover {
  background: rgb(var(--color-line));
}

.save-btn {
  padding: 10px 20px;
  background: #3b82f6;
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  font-weight: 500;
}

.save-btn:hover:not(:disabled) {
  background: #2563eb;
}

.save-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Responsive */
@media (max-width: 768px) {
  .hero-card {
    flex-direction: column;
    text-align: center;
    padding: 25px;
  }

  .hero-logo {
    margin: 0 auto 20px;
  }

  .club-name-row {
    flex-direction: column;
    gap: 10px;
  }

  .fan-info {
    flex-direction: column;
    gap: 5px;
  }

  .separator {
    display: none;
  }

  .hero-stats {
    justify-content: center;
  }

  .hero-actions {
    flex-direction: column;
  }

  .match-card {
    grid-template-columns: 1fr;
    gap: 8px;
    text-align: center;
  }

  .match-type {
    text-align: center;
  }
}
</style>
