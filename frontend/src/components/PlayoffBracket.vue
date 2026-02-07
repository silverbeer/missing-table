<template>
  <div class="playoff-bracket">
    <!-- Loading -->
    <div v-if="loading" class="text-center py-8 text-gray-500">
      Loading bracket...
    </div>

    <!-- Error -->
    <div v-else-if="error" class="text-center py-4 text-red-600 text-sm">
      {{ error }}
    </div>

    <!-- No bracket -->
    <div
      v-else-if="bracket.length === 0"
      class="text-center py-8 text-gray-400 text-sm"
    >
      No playoff bracket available.
    </div>

    <!-- Bracket display -->
    <div v-else>
      <div v-for="tier in bracketTiers" :key="tier.key" class="tier-section">
        <h3 class="tier-header">{{ tier.label }}</h3>
        <div class="bracket-layout">
          <!-- Quarterfinals column -->
          <div class="bracket-column">
            <h4 class="round-header">Quarterfinals</h4>
            <div class="matchups matchups-qf">
              <div
                v-for="s in getSlotsByRound(tier.key, 'quarterfinal')"
                :key="s.id"
                class="matchup-card"
                :class="{
                  completed: s.match_status === 'completed',
                  forfeit: s.match_status === 'forfeit',
                }"
              >
                <div class="team-row" :class="{ winner: isWinner(s, 'home') }">
                  <span class="seed" v-if="s.home_seed">{{ s.home_seed }}</span>
                  <span class="team-name">{{ s.home_team_name || 'TBD' }}</span>
                  <span class="score">
                    {{ s.home_score ?? '' }}
                    <span
                      v-if="isForfeitTeam(s, 'home')"
                      class="forfeit-indicator"
                      >(F)</span
                    >
                  </span>
                </div>
                <div class="team-row" :class="{ winner: isWinner(s, 'away') }">
                  <span class="seed" v-if="s.away_seed">{{ s.away_seed }}</span>
                  <span class="team-name">{{ s.away_team_name || 'TBD' }}</span>
                  <span class="score">
                    {{ s.away_score ?? '' }}
                    <span
                      v-if="isForfeitTeam(s, 'away')"
                      class="forfeit-indicator"
                      >(F)</span
                    >
                  </span>
                </div>
                <!-- Match info and controls -->
                <div v-if="s.match_id" class="match-info">
                  <div class="match-date-row">
                    <span
                      v-if="!editingSlotId || editingSlotId !== s.id"
                      class="match-date"
                    >
                      {{ formatDate(s.match_date) }}
                      <span v-if="s.scheduled_kickoff">{{
                        formatTime(s.scheduled_kickoff)
                      }}</span>
                    </span>
                    <!-- Edit date/time inline -->
                    <div v-else class="edit-panel">
                      <div class="edit-datetime">
                        <input
                          type="date"
                          v-model="editDate"
                          class="date-input"
                        />
                        <input
                          type="time"
                          v-model="editTime"
                          class="time-input"
                        />
                        <button @click="saveDateTime(s)" class="save-btn">
                          Save
                        </button>
                        <button @click="cancelEdit" class="cancel-btn">
                          Cancel
                        </button>
                      </div>
                      <!-- Forfeit option (inside edit panel) -->
                      <div
                        v-if="canForfeitSlot(s) && forfeitSlotId !== s.id"
                        class="forfeit-link-row"
                      >
                        <button @click="startForfeit(s)" class="forfeit-link">
                          Declare Forfeit...
                        </button>
                      </div>
                      <!-- Forfeit dialog (expands below) -->
                      <div v-if="forfeitSlotId === s.id" class="forfeit-dialog">
                        <p class="forfeit-prompt">Which team is forfeiting?</p>
                        <label class="forfeit-radio">
                          <input
                            type="radio"
                            :value="s.home_team_id"
                            v-model="forfeitTeamId"
                          />
                          {{ s.home_team_name }}
                        </label>
                        <label class="forfeit-radio">
                          <input
                            type="radio"
                            :value="s.away_team_id"
                            v-model="forfeitTeamId"
                          />
                          {{ s.away_team_name }}
                        </label>
                        <div class="forfeit-actions">
                          <button
                            @click="confirmForfeit(s)"
                            class="forfeit-confirm-btn"
                            :disabled="!forfeitTeamId"
                          >
                            Confirm Forfeit
                          </button>
                          <button @click="cancelForfeit" class="cancel-btn">
                            Cancel
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                  <!-- Edit controls for managers -->
                  <div
                    v-if="canManageSlot(s) && editingSlotId !== s.id"
                    class="slot-controls"
                  >
                    <button
                      @click="startEditDateTime(s)"
                      class="edit-btn"
                      title="Edit date/time"
                    >
                      ✏️
                    </button>
                    <button
                      v-if="canAdvanceSlot(s)"
                      @click="advanceWinner(s)"
                      class="advance-btn"
                      title="Advance winner to next round"
                    >
                      ➡️ Advance
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Connector QF→SF -->
          <div class="connector-column connector-qf-sf">
            <div class="connector-pair">
              <div class="connector-line top"></div>
              <div class="connector-line bottom"></div>
              <div class="connector-merge"></div>
            </div>
            <div class="connector-pair">
              <div class="connector-line top"></div>
              <div class="connector-line bottom"></div>
              <div class="connector-merge"></div>
            </div>
          </div>

          <!-- Semifinals column -->
          <div class="bracket-column">
            <h4 class="round-header">Semifinals</h4>
            <div class="matchups matchups-sf">
              <div
                v-for="s in getSlotsByRound(tier.key, 'semifinal')"
                :key="s.id"
                class="matchup-card"
                :class="{
                  completed: s.match_status === 'completed',
                  forfeit: s.match_status === 'forfeit',
                }"
              >
                <div class="team-row" :class="{ winner: isWinner(s, 'home') }">
                  <span class="seed" v-if="s.home_seed">{{ s.home_seed }}</span>
                  <span class="team-name">{{ s.home_team_name || 'TBD' }}</span>
                  <span class="score">
                    {{ s.home_score ?? '' }}
                    <span
                      v-if="isForfeitTeam(s, 'home')"
                      class="forfeit-indicator"
                      >(F)</span
                    >
                  </span>
                </div>
                <div class="team-row" :class="{ winner: isWinner(s, 'away') }">
                  <span class="seed" v-if="s.away_seed">{{ s.away_seed }}</span>
                  <span class="team-name">{{ s.away_team_name || 'TBD' }}</span>
                  <span class="score">
                    {{ s.away_score ?? '' }}
                    <span
                      v-if="isForfeitTeam(s, 'away')"
                      class="forfeit-indicator"
                      >(F)</span
                    >
                  </span>
                </div>
                <!-- Match info and controls -->
                <div v-if="s.match_id" class="match-info">
                  <div class="match-date-row">
                    <span
                      v-if="!editingSlotId || editingSlotId !== s.id"
                      class="match-date"
                    >
                      {{ formatDate(s.match_date) }}
                      <span v-if="s.scheduled_kickoff">{{
                        formatTime(s.scheduled_kickoff)
                      }}</span>
                    </span>
                    <!-- Edit date/time inline -->
                    <div v-else class="edit-panel">
                      <div class="edit-datetime">
                        <input
                          type="date"
                          v-model="editDate"
                          class="date-input"
                        />
                        <input
                          type="time"
                          v-model="editTime"
                          class="time-input"
                        />
                        <button @click="saveDateTime(s)" class="save-btn">
                          Save
                        </button>
                        <button @click="cancelEdit" class="cancel-btn">
                          Cancel
                        </button>
                      </div>
                      <!-- Forfeit option (inside edit panel) -->
                      <div
                        v-if="canForfeitSlot(s) && forfeitSlotId !== s.id"
                        class="forfeit-link-row"
                      >
                        <button @click="startForfeit(s)" class="forfeit-link">
                          Declare Forfeit...
                        </button>
                      </div>
                      <!-- Forfeit dialog (expands below) -->
                      <div v-if="forfeitSlotId === s.id" class="forfeit-dialog">
                        <p class="forfeit-prompt">Which team is forfeiting?</p>
                        <label class="forfeit-radio">
                          <input
                            type="radio"
                            :value="s.home_team_id"
                            v-model="forfeitTeamId"
                          />
                          {{ s.home_team_name }}
                        </label>
                        <label class="forfeit-radio">
                          <input
                            type="radio"
                            :value="s.away_team_id"
                            v-model="forfeitTeamId"
                          />
                          {{ s.away_team_name }}
                        </label>
                        <div class="forfeit-actions">
                          <button
                            @click="confirmForfeit(s)"
                            class="forfeit-confirm-btn"
                            :disabled="!forfeitTeamId"
                          >
                            Confirm Forfeit
                          </button>
                          <button @click="cancelForfeit" class="cancel-btn">
                            Cancel
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                  <!-- Edit controls for managers -->
                  <div
                    v-if="canManageSlot(s) && editingSlotId !== s.id"
                    class="slot-controls"
                  >
                    <button
                      @click="startEditDateTime(s)"
                      class="edit-btn"
                      title="Edit date/time"
                    >
                      ✏️
                    </button>
                    <button
                      v-if="canAdvanceSlot(s)"
                      @click="advanceWinner(s)"
                      class="advance-btn"
                      title="Advance winner to next round"
                    >
                      ➡️ Advance
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Connector SF→Final -->
          <div class="connector-column connector-sf-final">
            <div class="connector-pair">
              <div class="connector-line top"></div>
              <div class="connector-line bottom"></div>
              <div class="connector-merge"></div>
            </div>
          </div>

          <!-- Final column -->
          <div class="bracket-column">
            <h4 class="round-header">Final</h4>
            <div class="matchups matchups-final">
              <div
                v-for="s in getSlotsByRound(tier.key, 'final')"
                :key="s.id"
                class="matchup-card final-card"
                :class="{
                  completed: s.match_status === 'completed',
                  forfeit: s.match_status === 'forfeit',
                }"
              >
                <div class="team-row" :class="{ winner: isWinner(s, 'home') }">
                  <span class="team-name">{{ s.home_team_name || 'TBD' }}</span>
                  <span class="score">
                    {{ s.home_score ?? '' }}
                    <span
                      v-if="isForfeitTeam(s, 'home')"
                      class="forfeit-indicator"
                      >(F)</span
                    >
                  </span>
                </div>
                <div class="team-row" :class="{ winner: isWinner(s, 'away') }">
                  <span class="team-name">{{ s.away_team_name || 'TBD' }}</span>
                  <span class="score">
                    {{ s.away_score ?? '' }}
                    <span
                      v-if="isForfeitTeam(s, 'away')"
                      class="forfeit-indicator"
                      >(F)</span
                    >
                  </span>
                </div>
                <!-- Match info and controls (no advance for final) -->
                <div v-if="s.match_id" class="match-info">
                  <div class="match-date-row">
                    <span
                      v-if="!editingSlotId || editingSlotId !== s.id"
                      class="match-date"
                    >
                      {{ formatDate(s.match_date) }}
                      <span v-if="s.scheduled_kickoff">{{
                        formatTime(s.scheduled_kickoff)
                      }}</span>
                    </span>
                    <!-- Edit date/time inline -->
                    <div v-else class="edit-panel">
                      <div class="edit-datetime">
                        <input
                          type="date"
                          v-model="editDate"
                          class="date-input"
                        />
                        <input
                          type="time"
                          v-model="editTime"
                          class="time-input"
                        />
                        <button @click="saveDateTime(s)" class="save-btn">
                          Save
                        </button>
                        <button @click="cancelEdit" class="cancel-btn">
                          Cancel
                        </button>
                      </div>
                      <!-- Forfeit option (inside edit panel) -->
                      <div
                        v-if="canForfeitSlot(s) && forfeitSlotId !== s.id"
                        class="forfeit-link-row"
                      >
                        <button @click="startForfeit(s)" class="forfeit-link">
                          Declare Forfeit...
                        </button>
                      </div>
                      <!-- Forfeit dialog (expands below) -->
                      <div v-if="forfeitSlotId === s.id" class="forfeit-dialog">
                        <p class="forfeit-prompt">Which team is forfeiting?</p>
                        <label class="forfeit-radio">
                          <input
                            type="radio"
                            :value="s.home_team_id"
                            v-model="forfeitTeamId"
                          />
                          {{ s.home_team_name }}
                        </label>
                        <label class="forfeit-radio">
                          <input
                            type="radio"
                            :value="s.away_team_id"
                            v-model="forfeitTeamId"
                          />
                          {{ s.away_team_name }}
                        </label>
                        <div class="forfeit-actions">
                          <button
                            @click="confirmForfeit(s)"
                            class="forfeit-confirm-btn"
                            :disabled="!forfeitTeamId"
                          >
                            Confirm Forfeit
                          </button>
                          <button @click="cancelForfeit" class="cancel-btn">
                            Cancel
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                  <!-- Edit controls for managers (no advance for final) -->
                  <div
                    v-if="canManageSlot(s) && editingSlotId !== s.id"
                    class="slot-controls"
                  >
                    <button
                      @click="startEditDateTime(s)"
                      class="edit-btn"
                      title="Edit date/time"
                    >
                      ✏️
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../config/api';

export default {
  name: 'PlayoffBracket',
  props: {
    leagueId: { type: Number, required: true },
    seasonId: { type: Number, required: true },
    ageGroupId: { type: Number, required: true },
  },
  setup(props) {
    const authStore = useAuthStore();
    const bracket = ref([]);
    const loading = ref(false);
    const error = ref(null);

    // Edit state
    const editingSlotId = ref(null);
    const editDate = ref('');
    const editTime = ref('');

    // Forfeit state
    const forfeitSlotId = ref(null);
    const forfeitTeamId = ref(null);

    // Derive bracket tiers dynamically from bracket data
    const bracketTiers = computed(() => {
      const tierNames = [...new Set(bracket.value.map(s => s.bracket_tier))];
      // Sort alphabetically for consistent display
      tierNames.sort();
      return tierNames.map(name => ({
        key: name,
        label: name,
      }));
    });

    const getSlotsByRound = (tier, round) =>
      bracket.value
        .filter(s => s.bracket_tier === tier && s.round === round)
        .sort((a, b) => a.bracket_position - b.bracket_position);

    const isWinner = (s, side) => {
      if (s.match_status !== 'completed' && s.match_status !== 'forfeit')
        return false;
      if (s.home_score == null || s.away_score == null) return false;
      if (side === 'home') return s.home_score > s.away_score;
      return s.away_score > s.home_score;
    };

    const isForfeitTeam = (s, side) => {
      if (s.match_status !== 'forfeit') return false;
      // The forfeiting team is the one with score 0
      if (side === 'home') return s.home_score === 0 && s.away_score === 3;
      return s.away_score === 0 && s.home_score === 3;
    };

    // Authorization helpers
    const canManageSlot = slot => {
      if (!authStore.isAuthenticated.value) return false;
      if (authStore.isAdmin.value) return true;

      const userTeamId = authStore.userTeamId.value;
      if (authStore.isTeamManager.value && userTeamId) {
        return (
          slot.home_team_id === userTeamId || slot.away_team_id === userTeamId
        );
      }
      // Club managers can only manage slots involving their club's teams
      if (authStore.isClubManager.value) {
        const userClubId = authStore.userClubId.value;
        if (!userClubId) return false;
        return (
          slot.home_club_id === userClubId || slot.away_club_id === userClubId
        );
      }
      return false;
    };

    const canAdvanceSlot = slot => {
      if (!canManageSlot(slot)) return false;
      if (slot.match_status !== 'completed' && slot.match_status !== 'forfeit')
        return false;
      if (slot.round === 'final') return false;
      if (slot.home_score == null || slot.away_score == null) return false;
      if (slot.home_score === slot.away_score) return false; // Tied - admin must resolve

      // Admins can always advance
      if (authStore.isAdmin.value) return true;

      // Determine winner
      const winnerTeamId =
        slot.home_score > slot.away_score
          ? slot.home_team_id
          : slot.away_team_id;
      const winnerClubId =
        slot.home_score > slot.away_score
          ? slot.home_club_id
          : slot.away_club_id;

      // Team managers can only advance if their team won
      if (authStore.isTeamManager.value) {
        const userTeamId = authStore.userTeamId.value;
        return userTeamId === winnerTeamId;
      }

      // Club managers can only advance if their club's team won
      if (authStore.isClubManager.value) {
        const userClubId = authStore.userClubId.value;
        return userClubId === winnerClubId;
      }

      return false;
    };

    const canForfeitSlot = slot => {
      if (!canManageSlot(slot)) return false;
      if (slot.match_status !== 'scheduled' && slot.match_status !== 'live')
        return false;
      if (!slot.home_team_id || !slot.away_team_id) return false;
      return true;
    };

    // Date/time formatting
    const formatDate = dateStr => {
      if (!dateStr) return '';
      const date = new Date(dateStr + 'T00:00:00');
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
    };

    const formatTime = isoString => {
      if (!isoString) return '';
      // Parse ISO datetime string and convert to local time
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return '';
      return date.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
      });
    };

    // Extract local time (HH:MM) from ISO datetime string for time input
    const extractLocalTime = isoString => {
      if (!isoString) return '';
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return '';
      const hours = date.getHours().toString().padStart(2, '0');
      const minutes = date.getMinutes().toString().padStart(2, '0');
      return `${hours}:${minutes}`;
    };

    // Edit date/time
    const startEditDateTime = slot => {
      editingSlotId.value = slot.id;
      editDate.value = slot.match_date || '';
      editTime.value = extractLocalTime(slot.scheduled_kickoff);
    };

    const cancelEdit = () => {
      editingSlotId.value = null;
      editDate.value = '';
      editTime.value = '';
      forfeitSlotId.value = null;
      forfeitTeamId.value = null;
    };

    const saveDateTime = async slot => {
      try {
        const updateData = {};
        if (editDate.value) updateData.match_date = editDate.value;
        // Convert date + time to ISO datetime string for scheduled_kickoff
        if (editDate.value && editTime.value) {
          const localDateTime = new Date(`${editDate.value}T${editTime.value}`);
          updateData.scheduled_kickoff = localDateTime.toISOString();
        }

        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/matches/${slot.match_id}`,
          {
            method: 'PATCH',
            body: JSON.stringify(updateData),
          }
        );
        // Refresh bracket
        await fetchBracket();
        cancelEdit();
      } catch (err) {
        error.value = err.message || 'Failed to update date/time';
      }
    };

    // Advance winner
    const advanceWinner = async slot => {
      try {
        // Use the non-admin endpoint for team/club managers, admin endpoint for admins
        const endpoint = authStore.isAdmin.value
          ? `${getApiBaseUrl()}/api/admin/playoffs/advance`
          : `${getApiBaseUrl()}/api/playoffs/advance`;

        await authStore.apiRequest(endpoint, {
          method: 'POST',
          body: JSON.stringify({ slot_id: slot.id }),
        });
        // Refresh bracket to show updated state
        await fetchBracket();
      } catch (err) {
        error.value = err.message || 'Failed to advance winner';
      }
    };

    // Forfeit
    const startForfeit = slot => {
      forfeitSlotId.value = slot.id;
      forfeitTeamId.value = null;
    };

    const cancelForfeit = () => {
      forfeitSlotId.value = null;
      forfeitTeamId.value = null;
    };

    const confirmForfeit = async slot => {
      if (!forfeitTeamId.value) return;
      try {
        const endpoint = authStore.isAdmin.value
          ? `${getApiBaseUrl()}/api/admin/playoffs/forfeit`
          : `${getApiBaseUrl()}/api/playoffs/forfeit`;

        await authStore.apiRequest(endpoint, {
          method: 'POST',
          body: JSON.stringify({
            slot_id: slot.id,
            forfeit_team_id: forfeitTeamId.value,
          }),
        });
        cancelForfeit();
        await fetchBracket();
      } catch (err) {
        error.value = err.message || 'Failed to declare forfeit';
      }
    };

    const fetchBracket = async () => {
      if (!props.leagueId || !props.seasonId || !props.ageGroupId) return;
      try {
        loading.value = true;
        error.value = null;
        const params = new URLSearchParams({
          league_id: props.leagueId,
          season_id: props.seasonId,
          age_group_id: props.ageGroupId,
        });
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/playoffs/bracket?${params}`,
          { method: 'GET' }
        );
        bracket.value = data || [];
      } catch (err) {
        error.value = err.message || 'Failed to load bracket';
      } finally {
        loading.value = false;
      }
    };

    onMounted(fetchBracket);

    watch(
      () => [props.leagueId, props.seasonId, props.ageGroupId],
      fetchBracket
    );

    return {
      bracket,
      loading,
      error,
      bracketTiers,
      getSlotsByRound,
      isWinner,
      isForfeitTeam,
      canManageSlot,
      canAdvanceSlot,
      canForfeitSlot,
      formatDate,
      formatTime,
      editingSlotId,
      editDate,
      editTime,
      startEditDateTime,
      cancelEdit,
      saveDateTime,
      advanceWinner,
      forfeitSlotId,
      forfeitTeamId,
      startForfeit,
      cancelForfeit,
      confirmForfeit,
    };
  },
};
</script>

<style scoped>
.playoff-bracket {
  overflow-x: auto;
}

.tier-section {
  margin-bottom: 2.5rem;
}

.tier-header {
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
  margin-bottom: 0.75rem;
  padding-bottom: 0.25rem;
  border-bottom: 1px solid #e5e7eb;
}

/* Bracket layout — 5 columns: QF | connectors | SF | connectors | Final */
.bracket-layout {
  display: grid;
  grid-template-columns: minmax(140px, 1fr) 32px minmax(140px, 1fr) 32px minmax(
      140px,
      1fr
    );
  gap: 0;
  align-items: start;
  min-width: 560px;
}

.round-header {
  font-size: 0.75rem;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  text-align: center;
  margin-bottom: 0.75rem;
}

/* Matchup cards */
.matchup-card {
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  overflow: hidden;
  background: #fff;
  font-size: 0.8125rem;
}

.matchup-card.completed {
  border-color: #86efac;
}

.matchup-card.forfeit {
  border-color: #fdba74;
}

.final-card {
  border-width: 2px;
  border-color: #fbbf24;
}

.final-card.completed {
  border-color: #22c55e;
}

.final-card.forfeit {
  border-color: #f97316;
}

.team-row {
  display: flex;
  align-items: center;
  padding: 0.375rem 0.5rem;
}

.team-row + .team-row {
  border-top: 1px solid #f3f4f6;
}

.team-row.winner {
  font-weight: 700;
  color: #15803d;
  background: #f0fdf4;
}

.seed {
  width: 1rem;
  text-align: right;
  color: #9ca3af;
  font-size: 0.6875rem;
  margin-right: 0.375rem;
  flex-shrink: 0;
}

.team-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.score {
  min-width: 1.25rem;
  text-align: right;
  font-family: ui-monospace, monospace;
  font-weight: 600;
  margin-left: 0.5rem;
}

.forfeit-indicator {
  color: #ea580c;
  font-size: 0.625rem;
  font-weight: 400;
  margin-left: 0.125rem;
}

/* Spacing between matchup cards per round */
.matchups-qf {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.matchups-sf {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  /* Vertically center between QF pairs */
  margin-top: 1.75rem;
}

.matchups-final {
  /* Vertically center between SF pair */
  margin-top: 4.25rem;
}

/* Connector lines */
.connector-column {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  padding-top: 1.75rem; /* align with round header */
}

.connector-pair {
  position: relative;
  flex: 1;
}

.connector-qf-sf .connector-pair {
  height: 5.5rem;
  margin-bottom: 0.5rem;
}

.connector-sf-final .connector-pair {
  height: 8.5rem;
  margin-top: 1.75rem;
}

.connector-line {
  position: absolute;
  right: 0;
  width: 50%;
  border-top: 2px solid #d1d5db;
}

.connector-line.top {
  top: 25%;
}

.connector-line.bottom {
  top: 75%;
}

.connector-merge {
  position: absolute;
  right: 0;
  top: 25%;
  height: 50%;
  border-right: 2px solid #d1d5db;
}

/* Match info and controls */
.match-info {
  padding: 0.25rem 0.5rem;
  background: #f9fafb;
  border-top: 1px solid #f3f4f6;
  font-size: 0.6875rem;
}

.match-date-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.match-date {
  color: #6b7280;
}

.slot-controls {
  display: flex;
  gap: 0.25rem;
  margin-top: 0.25rem;
}

.edit-btn,
.advance-btn {
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  border: 1px solid #e5e7eb;
  background: #fff;
  cursor: pointer;
  font-size: 0.625rem;
  transition: background-color 0.15s;
}

.edit-btn:hover {
  background: #f3f4f6;
}

.advance-btn {
  background: #dbeafe;
  border-color: #93c5fd;
  color: #1d4ed8;
}

.advance-btn:hover {
  background: #bfdbfe;
}

/* Edit panel wrapper */
.edit-panel {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.forfeit-link-row {
  margin-top: 0.125rem;
}

.forfeit-link {
  background: none;
  border: none;
  color: #c2410c;
  cursor: pointer;
  font-size: 0.5625rem;
  padding: 0;
  text-decoration: underline;
  opacity: 0.7;
  transition: opacity 0.15s;
}

.forfeit-link:hover {
  opacity: 1;
}

/* Forfeit dialog */
.forfeit-dialog {
  margin-top: 0.375rem;
  padding: 0.375rem;
  background: #fff7ed;
  border: 1px solid #fdba74;
  border-radius: 0.25rem;
}

.forfeit-prompt {
  font-weight: 600;
  color: #9a3412;
  margin-bottom: 0.25rem;
}

.forfeit-radio {
  display: block;
  margin-bottom: 0.125rem;
  color: #374151;
  cursor: pointer;
}

.forfeit-radio input {
  margin-right: 0.25rem;
}

.forfeit-actions {
  display: flex;
  gap: 0.25rem;
  margin-top: 0.25rem;
}

.forfeit-confirm-btn {
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  border: 1px solid #fdba74;
  background: #fed7aa;
  color: #9a3412;
  cursor: pointer;
  font-size: 0.625rem;
}

.forfeit-confirm-btn:hover {
  background: #fdba74;
}

.forfeit-confirm-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Edit datetime inline */
.edit-datetime {
  display: flex;
  gap: 0.25rem;
  align-items: center;
  flex-wrap: wrap;
}

.date-input,
.time-input {
  padding: 0.125rem 0.25rem;
  border: 1px solid #d1d5db;
  border-radius: 0.25rem;
  font-size: 0.625rem;
}

.date-input {
  width: 100px;
}

.time-input {
  width: 70px;
}

.save-btn,
.cancel-btn {
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  border: 1px solid #e5e7eb;
  cursor: pointer;
  font-size: 0.625rem;
}

.save-btn {
  background: #dcfce7;
  border-color: #86efac;
  color: #15803d;
}

.save-btn:hover {
  background: #bbf7d0;
}

.cancel-btn {
  background: #fee2e2;
  border-color: #fca5a5;
  color: #dc2626;
}

.cancel-btn:hover {
  background: #fecaca;
}

/* Mobile: stack vertically */
@media (max-width: 640px) {
  .bracket-layout {
    grid-template-columns: 1fr;
    min-width: unset;
    gap: 1rem;
  }

  .connector-column {
    display: none;
  }

  .matchups-sf,
  .matchups-final {
    margin-top: 0;
  }
}
</style>
