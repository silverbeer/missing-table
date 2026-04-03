<template>
  <div>
    <!-- Header -->
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-semibold text-gray-900">Tournaments</h3>
      <button
        @click="openCreateTournament"
        class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium"
      >
        Add Tournament
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-8">
      <div
        class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"
      ></div>
    </div>

    <!-- Error -->
    <div
      v-if="error"
      class="bg-red-50 border border-red-200 rounded-md p-4 mb-4"
    >
      <div class="text-red-800">{{ error }}</div>
    </div>

    <!-- Tournament list -->
    <div v-if="!loading" class="space-y-4">
      <div
        v-for="tournament in tournaments"
        :key="tournament.id"
        class="border border-gray-200 rounded-lg overflow-hidden"
      >
        <!-- Tournament row -->
        <div
          class="flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 cursor-pointer"
          @click="toggleTournament(tournament)"
        >
          <div class="flex items-center gap-4">
            <div>
              <div class="flex items-center gap-2">
                <span class="font-medium text-gray-900">{{
                  tournament.name
                }}</span>
                <span
                  class="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono bg-yellow-50 text-yellow-700 border border-yellow-200 select-all"
                  :title="tournament.id"
                >
                  {{ tournament.id }}
                </span>
                <span
                  v-if="!tournament.is_active"
                  class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600"
                >
                  Inactive
                </span>
                <span
                  v-for="ag in tournament.age_groups || []"
                  :key="ag.id"
                  class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700"
                >
                  {{ ag.name }}
                </span>
              </div>
              <div class="text-sm text-gray-500 mt-0.5">
                {{ formatDate(tournament.start_date) }}
                <span v-if="tournament.end_date">
                  – {{ formatDate(tournament.end_date) }}</span
                >
                <span v-if="tournament.location">
                  · {{ tournament.location }}</span
                >
              </div>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <span class="text-sm text-gray-500">
              {{ tournament.match_count ?? 0 }} match{{
                (tournament.match_count ?? 0) !== 1 ? 'es' : ''
              }}
            </span>
            <button
              @click.stop="openEditTournament(tournament)"
              class="text-blue-600 hover:text-blue-900 text-sm"
            >
              Edit
            </button>
            <button
              @click.stop="deleteTournament(tournament)"
              class="text-red-600 hover:text-red-900 text-sm"
            >
              Delete
            </button>
            <span class="text-gray-400 text-sm">
              {{ selectedTournamentId === tournament.id ? '▲' : '▼' }}
            </span>
          </div>
        </div>

        <!-- Expanded: match list + add match -->
        <div v-if="selectedTournamentId === tournament.id" class="p-4">
          <!-- Loading matches -->
          <div v-if="matchesLoading" class="flex justify-center py-4">
            <div
              class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"
            ></div>
          </div>

          <template v-else>
            <!-- Matches table -->
            <table
              v-if="selectedMatches.length > 0"
              class="min-w-full mb-4 text-sm"
            >
              <thead>
                <tr class="border-b border-gray-200">
                  <th
                    class="text-left py-2 pr-4 font-medium text-gray-500 text-xs uppercase"
                  >
                    Date
                  </th>
                  <th
                    class="text-left py-2 pr-4 font-medium text-gray-500 text-xs uppercase"
                  >
                    Round
                  </th>
                  <th
                    class="text-left py-2 pr-4 font-medium text-gray-500 text-xs uppercase"
                  >
                    Group
                  </th>
                  <th
                    class="text-left py-2 pr-4 font-medium text-gray-500 text-xs uppercase"
                  >
                    Home
                  </th>
                  <th
                    class="text-left py-2 pr-4 font-medium text-gray-500 text-xs uppercase"
                  >
                    Score
                  </th>
                  <th
                    class="text-left py-2 pr-4 font-medium text-gray-500 text-xs uppercase"
                  >
                    Away
                  </th>
                  <th
                    class="text-left py-2 pr-4 font-medium text-gray-500 text-xs uppercase"
                  >
                    Status
                  </th>
                  <th
                    class="text-right py-2 font-medium text-gray-500 text-xs uppercase"
                  >
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr v-for="match in selectedMatches" :key="match.id">
                  <td class="py-2 pr-4 text-gray-700">
                    {{ formatDate(match.match_date) }}
                  </td>
                  <td class="py-2 pr-4 text-gray-500">
                    {{ formatRound(match.tournament_round) }}
                  </td>
                  <td class="py-2 pr-4 text-gray-500">
                    {{ match.tournament_group || '—' }}
                  </td>
                  <td class="py-2 pr-4 font-medium text-gray-900">
                    {{ match.home_team?.name }}
                  </td>
                  <td class="py-2 pr-4 text-gray-700 font-mono">
                    <span v-if="match.home_score != null">
                      {{ match.home_score }} – {{ match.away_score }}
                      <span
                        v-if="match.home_penalty_score != null"
                        class="text-xs text-gray-500 ml-1"
                      >
                        ({{ match.home_penalty_score }}–{{
                          match.away_penalty_score
                        }}
                        pens)
                      </span>
                    </span>
                    <span v-else class="text-gray-400">vs</span>
                  </td>
                  <td class="py-2 pr-4 font-medium text-gray-900">
                    {{ match.away_team?.name }}
                  </td>
                  <td class="py-2 pr-4">
                    <span :class="statusClass(match.match_status)">
                      {{ match.match_status }}
                    </span>
                  </td>
                  <td class="py-2 text-right">
                    <button
                      @click="openEditMatch(match)"
                      class="text-blue-600 hover:text-blue-900 mr-3"
                    >
                      Edit
                    </button>
                    <button
                      @click="deleteMatch(match)"
                      class="text-red-600 hover:text-red-900"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>

            <p v-else class="text-gray-500 text-sm mb-4">No matches yet.</p>

            <button
              @click="openAddMatch(tournament)"
              class="bg-green-600 hover:bg-green-700 text-white px-3 py-1.5 rounded-md text-sm font-medium"
            >
              + Add Match
            </button>
          </template>
        </div>
      </div>

      <p
        v-if="!loading && tournaments.length === 0"
        class="text-gray-500 text-center py-8"
      >
        No tournaments yet. Click "Add Tournament" to create one.
      </p>
    </div>

    <!-- ===== Create / Edit Tournament Modal ===== -->
    <div
      v-if="showTournamentModal"
      class="modal-overlay"
      @click="closeTournamentModal"
    >
      <div class="modal-content" @click.stop>
        <div class="p-6">
          <h3 class="text-lg font-medium text-gray-900 mb-4">
            {{ editingTournament ? 'Edit Tournament' : 'New Tournament' }}
          </h3>
          <form @submit.prevent="saveTournament">
            <!-- Name -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-1"
                >Name *</label
              >
              <input
                v-model="tForm.name"
                type="text"
                required
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g. 2026 Generation adidas Cup"
              />
            </div>

            <!-- Dates -->
            <div class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Start Date *</label
                >
                <input
                  v-model="tForm.start_date"
                  type="date"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >End Date</label
                >
                <input
                  v-model="tForm.end_date"
                  type="date"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <!-- Location -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-1"
                >Location</label
              >
              <input
                v-model="tForm.location"
                type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g. IMG Academy, Bradenton FL"
              />
            </div>

            <!-- Age Groups (multi-select) -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-1"
                >Age Groups</label
              >
              <div class="flex flex-wrap gap-3">
                <label
                  v-for="ag in ageGroups"
                  :key="ag.id"
                  class="inline-flex items-center gap-1.5 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    :value="ag.id"
                    v-model="tForm.age_group_ids"
                    class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span class="text-sm text-gray-700">{{ ag.name }}</span>
                </label>
              </div>
            </div>

            <!-- Description -->
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-1"
                >Description</label
              >
              <textarea
                v-model="tForm.description"
                rows="2"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Optional notes about format, teams, etc."
              ></textarea>
            </div>

            <!-- Active -->
            <div class="mb-6 flex items-center gap-2">
              <input
                v-model="tForm.is_active"
                id="is_active"
                type="checkbox"
                class="h-4 w-4 text-blue-600 border-gray-300 rounded"
              />
              <label for="is_active" class="text-sm text-gray-700"
                >Visible to fans (active)</label
              >
            </div>

            <div class="flex justify-end gap-3">
              <button
                type="button"
                @click="closeTournamentModal"
                class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
              >
                Cancel
              </button>
              <button
                type="submit"
                :disabled="tFormLoading"
                class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50"
              >
                {{
                  tFormLoading
                    ? 'Saving...'
                    : editingTournament
                      ? 'Update'
                      : 'Create'
                }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- ===== Add / Edit Match Modal ===== -->
    <div v-if="showMatchModal" class="modal-overlay" @click="closeMatchModal">
      <div class="modal-content modal-content-wide" @click.stop>
        <div class="p-6">
          <h3 class="text-lg font-medium text-gray-900 mb-4">
            {{ editingMatch ? 'Edit Match' : 'Add Match' }}
          </h3>
          <form @submit.prevent="saveMatch">
            <!-- Our team + opponent -->
            <!-- Edit mode: show teams as read-only text with swap option -->
            <div
              v-if="editingMatch"
              class="mb-4 p-3 bg-gray-50 rounded-md border border-gray-200 flex items-center gap-2"
            >
              <span
                class="text-sm font-medium text-gray-900 flex-1 text-right"
                >{{ editingMatch.home_team?.name }}</span
              >
              <span class="text-xs text-gray-400 font-mono">vs</span>
              <span class="text-sm font-medium text-gray-900 flex-1">{{
                editingMatch.away_team?.name
              }}</span>
              <button
                type="button"
                @click="swapHomeAway"
                class="ml-2 text-xs text-blue-600 hover:text-blue-800 border border-blue-300 rounded px-2 py-0.5"
                title="Swap home and away teams"
              >
                ⇄ Swap
              </button>
            </div>
            <!-- Add mode: team selector + opponent input -->
            <div v-else class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Our Team *</label
                >
                <select
                  v-model="mForm.our_team_id"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option :value="null" disabled>— select —</option>
                  <option v-for="t in leagueTeams" :key="t.id" :value="t.id">
                    {{ t.name }}{{ t.league_name ? ` (${t.league_name})` : '' }}
                  </option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Opponent *</label
                >
                <input
                  v-model="mForm.opponent_name"
                  type="text"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Opponent team name"
                />
                <p class="text-xs text-gray-400 mt-1">
                  Created automatically if not in system
                </p>
              </div>
            </div>

            <!-- Home/Away toggle -->
            <div v-if="!editingMatch" class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-1"
                >Our Team Is</label
              >
              <div class="flex gap-4">
                <label class="flex items-center gap-2 cursor-pointer">
                  <input
                    v-model="mForm.is_home"
                    type="radio"
                    :value="true"
                    class="text-blue-600"
                  />
                  <span class="text-sm">Home</span>
                </label>
                <label class="flex items-center gap-2 cursor-pointer">
                  <input
                    v-model="mForm.is_home"
                    type="radio"
                    :value="false"
                    class="text-blue-600"
                  />
                  <span class="text-sm">Away</span>
                </label>
              </div>
            </div>

            <!-- Date + kickoff time -->
            <div class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Match Date *</label
                >
                <input
                  v-model="mForm.match_date"
                  type="date"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Kickoff Time</label
                >
                <input
                  v-model="mForm.scheduled_kickoff"
                  type="time"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <!-- Round + Group -->
            <div class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Round</label
                >
                <select
                  v-model="mForm.tournament_round"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">— none —</option>
                  <option value="group_stage">Group Stage</option>
                  <option value="round_of_16">Round of 16</option>
                  <option value="quarterfinal">Quarterfinal</option>
                  <option value="semifinal">Semifinal</option>
                  <option value="third_place">Third Place</option>
                  <option value="final">Final</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Group</label
                >
                <input
                  v-model="mForm.tournament_group"
                  type="text"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. Group A"
                />
              </div>
            </div>

            <!-- Age group + Season (hidden defaults when creating) -->
            <div v-if="!editingMatch" class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Age Group *</label
                >
                <select
                  v-model="mForm.age_group_id"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option :value="null" disabled>— select —</option>
                  <option v-for="ag in ageGroups" :key="ag.id" :value="ag.id">
                    {{ ag.name }}
                  </option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Season *</label
                >
                <select
                  v-model="mForm.season_id"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option :value="null" disabled>— select —</option>
                  <option v-for="s in seasons" :key="s.id" :value="s.id">
                    {{ s.name }}
                  </option>
                </select>
              </div>
            </div>

            <!-- Score + Status -->
            <div class="grid grid-cols-3 gap-4 mb-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Home Score</label
                >
                <input
                  v-model.number="mForm.home_score"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="—"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Away Score</label
                >
                <input
                  v-model.number="mForm.away_score"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="—"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Status</label
                >
                <select
                  v-model="mForm.match_status"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="scheduled">Scheduled</option>
                  <option value="completed">Completed</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </div>
            </div>

            <!-- Penalty Shootout Scores (only shown when regulation ends in a draw) -->
            <div
              v-if="
                mForm.home_score != null &&
                mForm.away_score != null &&
                mForm.home_score === mForm.away_score
              "
              class="grid grid-cols-2 gap-4 mb-6 p-3 bg-yellow-50 border border-yellow-200 rounded-md"
            >
              <div class="col-span-2 text-xs font-medium text-yellow-800 mb-1">
                Draw after regulation — enter penalty shootout scores (optional)
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Home PK Score</label
                >
                <input
                  v-model.number="mForm.home_penalty_score"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-yellow-500"
                  placeholder="—"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Away PK Score</label
                >
                <input
                  v-model.number="mForm.away_penalty_score"
                  type="number"
                  min="0"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-yellow-500"
                  placeholder="—"
                />
              </div>
            </div>
            <div v-else class="mb-6"></div>

            <div class="flex justify-end gap-3">
              <button
                type="button"
                @click="closeMatchModal"
                class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md"
              >
                Cancel
              </button>
              <button
                type="submit"
                :disabled="mFormLoading"
                class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50"
              >
                {{
                  mFormLoading
                    ? 'Saving...'
                    : editingMatch
                      ? 'Update'
                      : 'Add Match'
                }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';

const ROUND_LABELS = {
  group_stage: 'Group Stage',
  round_of_16: 'Round of 16',
  quarterfinal: 'Quarterfinal',
  semifinal: 'Semifinal',
  third_place: 'Third Place',
  final: 'Final',
};

export default {
  name: 'AdminTournaments',
  setup() {
    const authStore = useAuthStore();

    // ── reference data ──
    const ageGroups = ref([]);
    const seasons = ref([]);
    const allTeams = ref([]);

    // League teams = teams with a league association (league_id or league_name set
    // by DAO processing). Falls back to all teams so the dropdown is never empty.
    const leagueTeams = computed(() => {
      const withLeague = allTeams.value.filter(
        t => t.league_id != null || t.league_name
      );
      return withLeague.length > 0 ? withLeague : allTeams.value;
    });

    // ── tournament list ──
    const tournaments = ref([]);
    const loading = ref(true);
    const error = ref(null);

    // ── expanded tournament + its matches ──
    const selectedTournamentId = ref(null);
    const selectedMatches = ref([]);
    const matchesLoading = ref(false);
    // cache counts so the collapsed rows stay accurate
    const matchCountCache = ref({});

    // ── tournament modal ──
    const showTournamentModal = ref(false);
    const editingTournament = ref(null);
    const tFormLoading = ref(false);
    const tForm = ref(emptyTournamentForm());

    // ── match modal ──
    const showMatchModal = ref(false);
    const editingMatch = ref(null);
    const activeTournamentId = ref(null);
    const mFormLoading = ref(false);
    const mForm = ref(emptyMatchForm());

    // ─────────────────────────────────────────────
    // Helpers
    // ─────────────────────────────────────────────

    function emptyTournamentForm() {
      return {
        name: '',
        start_date: '',
        end_date: '',
        location: '',
        description: '',
        age_group_ids: [],
        is_active: true,
      };
    }

    function emptyMatchForm() {
      return {
        our_team_id: null,
        opponent_name: '',
        is_home: true,
        match_date: '',
        scheduled_kickoff: '',
        tournament_round: '',
        tournament_group: '',
        age_group_id: null,
        season_id: null,
        home_score: null,
        away_score: null,
        home_penalty_score: null,
        away_penalty_score: null,
        match_status: 'scheduled',
      };
    }

    const formatDate = d =>
      d ? new Date(d + 'T00:00:00').toLocaleDateString() : '';

    const formatRound = r => ROUND_LABELS[r] || r || '—';

    const statusClass = status => {
      const map = {
        scheduled: 'text-gray-500',
        completed: 'text-green-700 font-medium',
        cancelled: 'text-red-500',
        in_progress: 'text-blue-600 font-medium',
      };
      return map[status] || 'text-gray-500';
    };

    const matchCountFor = id => matchCountCache.value[id] ?? 0;

    // ─────────────────────────────────────────────
    // Data fetching
    // ─────────────────────────────────────────────

    const fetchReferenceData = async () => {
      const [teamsData, ageGroupsData, seasonsData] = await Promise.all([
        authStore.apiRequest(
          `${getApiBaseUrl()}/api/teams?for_match_edit=true`,
          { method: 'GET' }
        ),
        authStore.apiRequest(`${getApiBaseUrl()}/api/age-groups`, {
          method: 'GET',
        }),
        authStore.apiRequest(`${getApiBaseUrl()}/api/seasons`, {
          method: 'GET',
        }),
      ]);
      allTeams.value = teamsData || [];
      ageGroups.value = ageGroupsData || [];
      seasons.value = seasonsData || [];

      // Pre-select current season in match form default
      const currentSeason = seasons.value.find(s => {
        const now = new Date();
        return new Date(s.start_date) <= now && new Date(s.end_date) >= now;
      });
      if (currentSeason) mForm.value.season_id = currentSeason.id;
    };

    const fetchTournaments = async () => {
      try {
        loading.value = true;
        error.value = null;
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/tournaments`,
          { method: 'GET' }
        );
        tournaments.value = data || [];
        // seed count cache from full detail if we have it, else zero
        tournaments.value.forEach(t => {
          if (matchCountCache.value[t.id] == null)
            matchCountCache.value[t.id] = 0;
        });
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const fetchTournamentMatches = async tournamentId => {
      matchesLoading.value = true;
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/tournaments/${tournamentId}`,
          { method: 'GET' }
        );
        selectedMatches.value = data?.matches || [];
        matchCountCache.value[tournamentId] = selectedMatches.value.length;
        // Keep tournament.match_count in sync for the accordion header
        const t = tournaments.value.find(x => x.id === tournamentId);
        if (t) t.match_count = selectedMatches.value.length;
      } catch (err) {
        error.value = err.message;
      } finally {
        matchesLoading.value = false;
      }
    };

    // ─────────────────────────────────────────────
    // Tournament accordion
    // ─────────────────────────────────────────────

    const toggleTournament = async tournament => {
      if (selectedTournamentId.value === tournament.id) {
        selectedTournamentId.value = null;
        selectedMatches.value = [];
      } else {
        selectedTournamentId.value = tournament.id;
        await fetchTournamentMatches(tournament.id);
      }
    };

    // ─────────────────────────────────────────────
    // Tournament CRUD
    // ─────────────────────────────────────────────

    const openCreateTournament = () => {
      editingTournament.value = null;
      tForm.value = emptyTournamentForm();
      showTournamentModal.value = true;
    };

    const openEditTournament = tournament => {
      editingTournament.value = tournament;
      tForm.value = {
        name: tournament.name,
        start_date: tournament.start_date,
        end_date: tournament.end_date || '',
        location: tournament.location || '',
        description: tournament.description || '',
        age_group_ids: (tournament.age_groups || []).map(ag => ag.id),
        is_active: tournament.is_active,
      };
      showTournamentModal.value = true;
    };

    const saveTournament = async () => {
      tFormLoading.value = true;
      try {
        const payload = { ...tForm.value };
        if (!payload.end_date) payload.end_date = null;
        if (!payload.location) payload.location = null;
        if (!payload.description) payload.description = null;

        if (editingTournament.value) {
          await authStore.apiRequest(
            `${getApiBaseUrl()}/api/admin/tournaments/${editingTournament.value.id}`,
            { method: 'PUT', body: JSON.stringify(payload) }
          );
        } else {
          await authStore.apiRequest(
            `${getApiBaseUrl()}/api/admin/tournaments`,
            { method: 'POST', body: JSON.stringify(payload) }
          );
        }
        await fetchTournaments();
        closeTournamentModal();
      } catch (err) {
        error.value = err.message;
      } finally {
        tFormLoading.value = false;
      }
    };

    const deleteTournament = async tournament => {
      if (
        !confirm(
          `Delete "${tournament.name}"? Matches linked to it will be unlinked but not deleted.`
        )
      )
        return;
      try {
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/tournaments/${tournament.id}`,
          { method: 'DELETE' }
        );
        if (selectedTournamentId.value === tournament.id) {
          selectedTournamentId.value = null;
          selectedMatches.value = [];
        }
        await fetchTournaments();
      } catch (err) {
        error.value = err.message;
      }
    };

    const closeTournamentModal = () => {
      showTournamentModal.value = false;
      editingTournament.value = null;
      tForm.value = emptyTournamentForm();
    };

    // ─────────────────────────────────────────────
    // Match CRUD
    // ─────────────────────────────────────────────

    const openAddMatch = tournament => {
      editingMatch.value = null;
      activeTournamentId.value = tournament.id;
      // pre-fill age group from tournament if set
      const base = emptyMatchForm();
      if (tournament.age_group_id) base.age_group_id = tournament.age_group_id;
      mForm.value = base;
      showMatchModal.value = true;
    };

    const openEditMatch = match => {
      editingMatch.value = match;
      mForm.value = {
        our_team_id: null,
        opponent_name: '',
        is_home: true,
        match_date: match.match_date,
        scheduled_kickoff: match.scheduled_kickoff
          ? (() => {
              const d = new Date(match.scheduled_kickoff);
              return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
            })()
          : '',
        tournament_round: match.tournament_round || '',
        tournament_group: match.tournament_group || '',
        age_group_id: null,
        season_id: null,
        home_score: match.home_score ?? null,
        away_score: match.away_score ?? null,
        home_penalty_score: match.home_penalty_score ?? null,
        away_penalty_score: match.away_penalty_score ?? null,
        match_status: match.match_status,
      };
      showMatchModal.value = true;
    };

    const swapHomeAway = () => {
      if (!editingMatch.value) return;
      const m = editingMatch.value;
      // Swap the team objects in the local match record (display only)
      const tmp = m.home_team;
      m.home_team = m.away_team;
      m.away_team = tmp;
      // Also swap scores if set
      const tmpScore = mForm.value.home_score;
      mForm.value.home_score = mForm.value.away_score;
      mForm.value.away_score = tmpScore;
      // Flag for the save payload
      mForm.value._swap_teams = !mForm.value._swap_teams;
    };

    const saveMatch = async () => {
      mFormLoading.value = true;
      try {
        const kickoffDatetime = t =>
          t && mForm.value.match_date
            ? new Date(`${mForm.value.match_date}T${t}:00`).toISOString()
            : t || null;
        if (editingMatch.value) {
          // Update: score/status/round/group/date fields; optionally swap teams
          const isDrawn =
            mForm.value.home_score != null &&
            mForm.value.away_score != null &&
            mForm.value.home_score === mForm.value.away_score;
          const payload = {
            match_date: mForm.value.match_date,
            home_score: mForm.value.home_score,
            away_score: mForm.value.away_score,
            home_penalty_score: isDrawn ? mForm.value.home_penalty_score : null,
            away_penalty_score: isDrawn ? mForm.value.away_penalty_score : null,
            match_status: mForm.value.match_status,
            tournament_round: mForm.value.tournament_round || null,
            tournament_group: mForm.value.tournament_group || null,
            scheduled_kickoff: kickoffDatetime(mForm.value.scheduled_kickoff),
            ...(mForm.value._swap_teams ? { swap_home_away: true } : {}),
          };
          await authStore.apiRequest(
            `${getApiBaseUrl()}/api/admin/tournaments/${selectedTournamentId.value}/matches/${editingMatch.value.id}`,
            { method: 'PUT', body: JSON.stringify(payload) }
          );
        } else {
          const isDrawn =
            mForm.value.home_score != null &&
            mForm.value.away_score != null &&
            mForm.value.home_score === mForm.value.away_score;
          const payload = {
            our_team_id: mForm.value.our_team_id,
            opponent_name: mForm.value.opponent_name,
            is_home: mForm.value.is_home,
            match_date: mForm.value.match_date,
            age_group_id: mForm.value.age_group_id,
            season_id: mForm.value.season_id,
            tournament_round: mForm.value.tournament_round || null,
            tournament_group: mForm.value.tournament_group || null,
            scheduled_kickoff: kickoffDatetime(mForm.value.scheduled_kickoff),
            home_score: mForm.value.home_score,
            away_score: mForm.value.away_score,
            home_penalty_score: isDrawn ? mForm.value.home_penalty_score : null,
            away_penalty_score: isDrawn ? mForm.value.away_penalty_score : null,
            match_status: mForm.value.match_status,
          };
          await authStore.apiRequest(
            `${getApiBaseUrl()}/api/admin/tournaments/${activeTournamentId.value}/matches`,
            { method: 'POST', body: JSON.stringify(payload) }
          );
        }
        await fetchTournamentMatches(selectedTournamentId.value);
        closeMatchModal();
      } catch (err) {
        error.value = err.message;
      } finally {
        mFormLoading.value = false;
      }
    };

    const deleteMatch = async match => {
      if (!confirm('Delete this match?')) return;
      try {
        await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/tournaments/${selectedTournamentId.value}/matches/${match.id}`,
          { method: 'DELETE' }
        );
        await fetchTournamentMatches(selectedTournamentId.value);
      } catch (err) {
        error.value = err.message;
      }
    };

    const closeMatchModal = () => {
      showMatchModal.value = false;
      editingMatch.value = null;
      mForm.value = emptyMatchForm();
    };

    // ─────────────────────────────────────────────
    // Init
    // ─────────────────────────────────────────────

    onMounted(async () => {
      await Promise.all([fetchTournaments(), fetchReferenceData()]);
    });

    return {
      // data
      tournaments,
      loading,
      error,
      ageGroups,
      seasons,
      leagueTeams,
      selectedTournamentId,
      selectedMatches,
      matchesLoading,
      // tournament modal
      showTournamentModal,
      editingTournament,
      tFormLoading,
      tForm,
      // match modal
      showMatchModal,
      editingMatch,
      mFormLoading,
      mForm,
      // helpers
      formatDate,
      formatRound,
      statusClass,
      matchCountFor,
      // tournament actions
      toggleTournament,
      openCreateTournament,
      openEditTournament,
      saveTournament,
      deleteTournament,
      closeTournamentModal,
      // match actions
      openAddMatch,
      openEditMatch,
      swapHomeAway,
      saveMatch,
      deleteMatch,
      closeMatchModal,
    };
  },
};
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}
.modal-content {
  background: white;
  border-radius: 8px;
  max-width: 520px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}
.modal-content-wide {
  max-width: 680px;
}
</style>
