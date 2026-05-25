<template>
  <!-- Match detail modal: overlays the tournament page when a row or bracket cell is clicked. -->
  <div
    v-if="selectedMatchId"
    class="fixed inset-0 z-50 bg-black/60 overflow-y-auto"
    @click.self="handleBackFromMatchDetail"
  >
    <div class="min-h-full flex items-start justify-center p-3 sm:p-6">
      <div
        class="relative w-full max-w-4xl bg-white rounded-lg shadow-2xl"
        @click.stop
      >
        <button
          type="button"
          aria-label="Close match details"
          class="absolute top-2 right-2 z-10 inline-flex items-center justify-center w-8 h-8 rounded-full text-gray-500 hover:text-gray-900 hover:bg-gray-100 transition-colors"
          @click="handleBackFromMatchDetail"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="w-5 h-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
        <MatchDetailView
          :matchId="selectedMatchId"
          @back="handleBackFromMatchDetail"
        />
      </div>
    </div>
  </div>

  <div
    :class="
      viewMode === 'bracket' || viewMode === 'standings'
        ? 'max-w-7xl mx-auto'
        : 'max-w-4xl mx-auto'
    "
  >
    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-12">
      <div
        class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"
      ></div>
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="bg-red-50 border border-red-200 rounded-md p-4"
    >
      <p class="text-red-800">{{ error }}</p>
    </div>

    <!-- No tournaments -->
    <div
      v-else-if="tournaments.length === 0"
      class="text-center py-16 text-gray-500"
    >
      <div class="text-5xl mb-4">🏆</div>
      <p class="text-lg font-medium text-gray-700">No active tournaments</p>
      <p class="text-sm mt-1">Check back soon for upcoming events.</p>
    </div>

    <template v-else>
      <!-- Tournament selector (only shown when multiple active) -->
      <div v-if="tournaments.length > 1" class="mb-6 flex flex-wrap gap-2">
        <button
          v-for="t in tournaments"
          :key="t.id"
          @click="selectTournament(t.id)"
          :class="[
            'px-4 py-2 rounded-full text-sm font-medium transition-colors',
            selectedId === t.id
              ? 'bg-brand-600 text-white'
              : 'bg-white border border-gray-300 text-gray-700 hover:border-brand-400',
          ]"
        >
          {{ t.name }}
        </button>
      </div>

      <!-- Tournament detail -->
      <div v-if="selected">
        <!-- Header card -->
        <div
          class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6"
        >
          <div class="flex flex-wrap items-start justify-between gap-4">
            <div class="flex items-start gap-4 min-w-0 flex-1">
              <img
                v-if="selected.logo_url"
                :src="selected.logo_url"
                :alt="`${selected.name} logo`"
                class="w-16 h-16 rounded-md object-contain bg-white border border-gray-100 shrink-0"
                data-testid="tournament-logo"
              />
              <div class="min-w-0 flex-1">
                <h2 class="text-2xl font-bold text-gray-900">
                  {{ selected.name }}
                </h2>
                <div
                  class="flex flex-wrap items-center gap-3 mt-2 text-sm text-gray-500"
                >
                  <span v-if="selected.start_date">
                    📅 {{ formatDate(selected.start_date) }}
                    <span v-if="selected.end_date">
                      – {{ formatDate(selected.end_date) }}</span
                    >
                  </span>
                  <span v-if="selected.location"
                    >📍 {{ selected.location }}</span
                  >
                  <span
                    v-for="ag in selected.age_groups || []"
                    :key="ag.id"
                    class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-brand-100 text-brand-700"
                  >
                    {{ ag.name }}
                  </span>
                </div>
                <p
                  v-if="selected.description"
                  class="mt-3 text-sm text-gray-600"
                >
                  {{ selected.description }}
                </p>
              </div>
            </div>
            <div class="flex flex-col items-end gap-3">
              <div class="text-right text-sm text-gray-500">
                <div class="text-2xl font-bold text-gray-800">
                  {{ selected.matches?.length ?? 0 }}
                </div>
                <div>matches tracked</div>
              </div>
              <!-- View toggle: List always shown; Bracket / Standings shown based on match round shape -->
              <div
                v-if="hasBracketRounds || hasStandingsRounds"
                class="inline-flex rounded-md border border-gray-300 bg-white p-0.5"
              >
                <button
                  type="button"
                  @click="viewMode = 'list'"
                  :class="[
                    'px-3 py-1 text-xs font-medium rounded transition-colors',
                    viewMode === 'list'
                      ? 'bg-brand-600 text-white'
                      : 'text-gray-600 hover:text-gray-900',
                  ]"
                >
                  List
                </button>
                <button
                  v-if="hasBracketRounds"
                  type="button"
                  @click="viewMode = 'bracket'"
                  :class="[
                    'px-3 py-1 text-xs font-medium rounded transition-colors',
                    viewMode === 'bracket'
                      ? 'bg-brand-600 text-white'
                      : 'text-gray-600 hover:text-gray-900',
                  ]"
                >
                  Bracket
                </button>
                <button
                  v-if="hasStandingsRounds"
                  type="button"
                  @click="viewMode = 'standings'"
                  :class="[
                    'px-3 py-1 text-xs font-medium rounded transition-colors',
                    viewMode === 'standings'
                      ? 'bg-brand-600 text-white'
                      : 'text-gray-600 hover:text-gray-900',
                  ]"
                >
                  Standings
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Match loading -->
        <div v-if="matchesLoading" class="flex justify-center py-8">
          <div
            class="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-600"
          ></div>
        </div>

        <template v-else-if="selected.matches && viewMode === 'list'">
          <!-- Age group filter -->
          <div
            v-if="availableAgeGroups.length > 1"
            class="mb-4 flex flex-wrap gap-2"
          >
            <button
              @click="ageGroupFilter = null"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                ageGroupFilter === null
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white border border-gray-300 text-gray-700 hover:border-indigo-400',
              ]"
            >
              All Ages
            </button>
            <button
              v-for="ag in availableAgeGroups"
              :key="ag.id"
              @click="ageGroupFilter = ag.id"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                ageGroupFilter === ag.id
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white border border-gray-300 text-gray-700 hover:border-indigo-400',
              ]"
            >
              {{ ag.name }}
            </button>
          </div>

          <!-- Team filter -->
          <div class="mb-4 flex flex-wrap items-center gap-3">
            <input
              v-model="teamFilter"
              type="text"
              placeholder="Filter by team…"
              class="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 w-full sm:w-48"
            />
            <span class="text-sm text-gray-500"
              >{{ filteredMatches.length }} match{{
                filteredMatches.length !== 1 ? 'es' : ''
              }}</span
            >
            <button
              v-if="teamFilter || ageGroupFilter"
              @click="
                teamFilter = '';
                ageGroupFilter = null;
              "
              class="text-sm text-brand-600 hover:text-brand-800"
            >
              clear all
            </button>
          </div>

          <!-- No matches -->
          <div
            v-if="selected.matches.length === 0"
            class="text-center py-10 text-gray-500"
          >
            No matches entered yet.
          </div>

          <!-- Group stage section -->
          <div v-if="groupStageMatches.length > 0" class="mb-6">
            <h3
              class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3"
            >
              Group Stage
            </h3>
            <div class="space-y-2">
              <div
                v-for="match in groupStageMatches"
                :key="match.id"
                @click="viewMatch(match)"
                class="bg-white rounded-lg border border-gray-200 px-3 sm:px-4 py-3 hover:border-brand-300 hover:shadow-sm transition-all cursor-pointer"
              >
                <!-- Mobile meta row -->
                <div class="flex items-center justify-between mb-1.5 sm:hidden">
                  <div class="flex items-center gap-1.5 min-w-0 flex-wrap">
                    <span class="text-xs text-gray-400">{{
                      formatMatchDate(match.match_date)
                    }}</span>
                    <span
                      v-if="match.scheduled_kickoff"
                      class="text-xs text-gray-400"
                      >· {{ formatKickoffTime(match.scheduled_kickoff) }}</span
                    >
                    <span
                      v-if="match.age_group"
                      class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-700"
                      >{{ match.age_group.name }}</span
                    >
                    <span
                      v-if="match.tournament_group"
                      class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600"
                      >{{ match.tournament_group }}</span
                    >
                  </div>
                  <div class="shrink-0 ml-2">
                    <span
                      v-if="match.match_status === 'completed'"
                      class="text-xs text-green-600 font-medium"
                      >Final</span
                    >
                    <span
                      v-else-if="match.match_status === 'in_progress'"
                      class="text-xs text-brand-600 font-medium animate-pulse"
                      >Live</span
                    >
                    <span
                      v-else-if="match.match_status === 'cancelled'"
                      class="text-xs text-red-500"
                      >Cancelled</span
                    >
                    <span
                      v-else
                      class="text-xs font-medium text-brand-600 hover:text-brand-800 hover:underline"
                      >Preview</span
                    >
                  </div>
                </div>
                <!-- Main row -->
                <div class="flex items-center gap-2 sm:gap-3">
                  <div
                    class="hidden sm:block w-24 shrink-0 text-xs text-gray-400"
                  >
                    <div>{{ formatMatchDate(match.match_date) }}</div>
                    <div v-if="match.scheduled_kickoff" class="text-gray-500">
                      {{ formatKickoffTime(match.scheduled_kickoff) }}
                    </div>
                  </div>
                  <div class="hidden sm:flex gap-1 shrink-0">
                    <span
                      v-if="match.age_group"
                      class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-700"
                      >{{ match.age_group.name }}</span
                    >
                    <span
                      v-if="match.tournament_group"
                      class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600"
                      >{{ match.tournament_group }}</span
                    >
                  </div>
                  <div class="flex-1 flex items-center gap-2 min-w-0">
                    <span
                      class="text-sm font-medium text-gray-900 text-right truncate flex-1"
                      >{{ match.home_team?.name }}</span
                    >
                    <span
                      :class="[
                        'text-xs sm:text-sm font-mono px-1.5 sm:px-2 py-0.5 rounded shrink-0',
                        match.home_score != null
                          ? 'bg-gray-900 text-white font-bold'
                          : 'text-gray-400',
                      ]"
                    >
                      {{
                        match.home_score != null && match.away_score != null
                          ? match.home_penalty_score != null
                            ? `${match.home_score}–${match.away_score} (${match.home_penalty_score}-${match.away_penalty_score}pk)`
                            : `${match.home_score}–${match.away_score}`
                          : 'vs'
                      }}
                    </span>
                    <span
                      class="text-sm font-medium text-gray-900 text-left truncate flex-1"
                      >{{ match.away_team?.name }}</span
                    >
                  </div>
                  <div class="hidden sm:block w-20 shrink-0 text-right">
                    <span
                      v-if="match.match_status === 'completed'"
                      class="text-xs text-green-600 font-medium"
                      >Final</span
                    >
                    <span
                      v-else-if="match.match_status === 'in_progress'"
                      class="text-xs text-brand-600 font-medium animate-pulse"
                      >Live</span
                    >
                    <span
                      v-else-if="match.match_status === 'cancelled'"
                      class="text-xs text-red-500"
                      >Cancelled</span
                    >
                    <span
                      v-else
                      class="text-xs font-medium text-brand-600 hover:text-brand-800 hover:underline"
                      >Preview</span
                    >
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Knockout section -->
          <div v-if="knockoutMatches.length > 0" class="mb-6">
            <h3
              class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3"
            >
              Knockout Rounds
            </h3>
            <div class="space-y-2">
              <div
                v-for="match in knockoutMatches"
                :key="match.id"
                @click="viewMatch(match)"
                class="bg-white rounded-lg border border-gray-200 px-3 sm:px-4 py-3 hover:border-brand-300 hover:shadow-sm transition-all cursor-pointer"
              >
                <!-- Mobile meta row -->
                <div class="flex items-center justify-between mb-1.5 sm:hidden">
                  <div class="flex items-center gap-1.5 min-w-0 flex-wrap">
                    <span class="text-xs text-gray-400">{{
                      formatMatchDate(match.match_date)
                    }}</span>
                    <span
                      v-if="match.scheduled_kickoff"
                      class="text-xs text-gray-400"
                      >· {{ formatKickoffTime(match.scheduled_kickoff) }}</span
                    >
                    <span
                      v-if="match.age_group"
                      class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-700"
                      >{{ match.age_group.name }}</span
                    >
                    <span
                      v-if="roundLabel(match)"
                      class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700"
                      >{{ roundLabel(match) }}</span
                    >
                  </div>
                  <div class="shrink-0 ml-2">
                    <span
                      v-if="match.match_status === 'completed'"
                      class="text-xs text-green-600 font-medium"
                      >Final</span
                    >
                    <span
                      v-else-if="match.match_status === 'in_progress'"
                      class="text-xs text-brand-600 font-medium animate-pulse"
                      >Live</span
                    >
                    <span
                      v-else-if="match.match_status === 'cancelled'"
                      class="text-xs text-red-500"
                      >Cancelled</span
                    >
                    <span
                      v-else
                      class="text-xs font-medium text-brand-600 hover:text-brand-800 hover:underline"
                      >Preview</span
                    >
                  </div>
                </div>
                <!-- Main row -->
                <div class="flex items-center gap-2 sm:gap-3">
                  <div
                    class="hidden sm:block w-24 shrink-0 text-xs text-gray-400"
                  >
                    <div>{{ formatMatchDate(match.match_date) }}</div>
                    <div v-if="match.scheduled_kickoff" class="text-gray-500">
                      {{ formatKickoffTime(match.scheduled_kickoff) }}
                    </div>
                  </div>
                  <div class="hidden sm:flex gap-1 shrink-0">
                    <span
                      v-if="match.age_group"
                      class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-700"
                      >{{ match.age_group.name }}</span
                    >
                    <span
                      v-if="roundLabel(match)"
                      class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700"
                      >{{ roundLabel(match) }}</span
                    >
                    <span
                      v-if="match.tournament_group"
                      class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600"
                      >{{ match.tournament_group }}</span
                    >
                  </div>
                  <div class="flex-1 flex items-center gap-2 min-w-0">
                    <span
                      class="text-sm font-medium text-gray-900 text-right truncate flex-1"
                      >{{ match.home_team?.name }}</span
                    >
                    <span
                      :class="[
                        'text-xs sm:text-sm font-mono px-1.5 sm:px-2 py-0.5 rounded shrink-0',
                        match.home_score != null
                          ? 'bg-gray-900 text-white font-bold'
                          : 'text-gray-400',
                      ]"
                    >
                      {{
                        match.home_score != null && match.away_score != null
                          ? match.home_penalty_score != null
                            ? `${match.home_score}–${match.away_score} (${match.home_penalty_score}-${match.away_penalty_score}pk)`
                            : `${match.home_score}–${match.away_score}`
                          : 'vs'
                      }}
                    </span>
                    <span
                      class="text-sm font-medium text-gray-900 text-left truncate flex-1"
                      >{{ match.away_team?.name }}</span
                    >
                  </div>
                  <div class="hidden sm:block w-20 shrink-0 text-right">
                    <span
                      v-if="match.match_status === 'completed'"
                      class="text-xs text-green-600 font-medium"
                      >Final</span
                    >
                    <span
                      v-else-if="match.match_status === 'in_progress'"
                      class="text-xs text-brand-600 font-medium animate-pulse"
                      >Live</span
                    >
                    <span
                      v-else-if="match.match_status === 'cancelled'"
                      class="text-xs text-red-500"
                      >Cancelled</span
                    >
                    <span
                      v-else
                      class="text-xs font-medium text-brand-600 hover:text-brand-800 hover:underline"
                      >Preview</span
                    >
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Untagged matches (no round set) -->
          <div v-if="untaggedMatches.length > 0" class="mb-6">
            <h3
              class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3"
            >
              Matches
            </h3>
            <div class="space-y-2">
              <div
                v-for="match in untaggedMatches"
                :key="match.id"
                @click="viewMatch(match)"
                class="bg-white rounded-lg border border-gray-200 px-3 sm:px-4 py-3 hover:border-brand-300 hover:shadow-sm transition-all cursor-pointer"
              >
                <!-- Mobile meta row -->
                <div class="flex items-center justify-between mb-1.5 sm:hidden">
                  <div class="flex items-center gap-1.5 min-w-0">
                    <span class="text-xs text-gray-400">{{
                      formatMatchDate(match.match_date)
                    }}</span>
                    <span
                      v-if="match.scheduled_kickoff"
                      class="text-xs text-gray-400"
                      >· {{ formatKickoffTime(match.scheduled_kickoff) }}</span
                    >
                    <span
                      v-if="match.age_group"
                      class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-700"
                      >{{ match.age_group.name }}</span
                    >
                  </div>
                  <div class="shrink-0 ml-2">
                    <span
                      v-if="match.match_status === 'completed'"
                      class="text-xs text-green-600 font-medium"
                      >Final</span
                    >
                    <span
                      v-else-if="match.match_status === 'in_progress'"
                      class="text-xs text-brand-600 font-medium animate-pulse"
                      >Live</span
                    >
                    <span
                      v-else-if="match.match_status === 'cancelled'"
                      class="text-xs text-red-500"
                      >Cancelled</span
                    >
                    <span
                      v-else
                      class="text-xs font-medium text-brand-600 hover:text-brand-800 hover:underline"
                      >Preview</span
                    >
                  </div>
                </div>
                <!-- Main row -->
                <div class="flex items-center gap-2 sm:gap-3">
                  <div
                    class="hidden sm:block w-24 shrink-0 text-xs text-gray-400"
                  >
                    <div>{{ formatMatchDate(match.match_date) }}</div>
                    <div v-if="match.scheduled_kickoff" class="text-gray-500">
                      {{ formatKickoffTime(match.scheduled_kickoff) }}
                    </div>
                  </div>
                  <div class="hidden sm:flex gap-1 shrink-0">
                    <span
                      v-if="match.age_group"
                      class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-700"
                      >{{ match.age_group.name }}</span
                    >
                  </div>
                  <div class="flex-1 flex items-center gap-2 min-w-0">
                    <span
                      class="text-sm font-medium text-gray-900 text-right truncate flex-1"
                      >{{ match.home_team?.name }}</span
                    >
                    <span
                      :class="[
                        'text-xs sm:text-sm font-mono px-1.5 sm:px-2 py-0.5 rounded shrink-0',
                        match.home_score != null
                          ? 'bg-gray-900 text-white font-bold'
                          : 'text-gray-400',
                      ]"
                    >
                      {{
                        match.home_score != null && match.away_score != null
                          ? match.home_penalty_score != null
                            ? `${match.home_score}–${match.away_score} (${match.home_penalty_score}-${match.away_penalty_score}pk)`
                            : `${match.home_score}–${match.away_score}`
                          : 'vs'
                      }}
                    </span>
                    <span
                      class="text-sm font-medium text-gray-900 text-left truncate flex-1"
                      >{{ match.away_team?.name }}</span
                    >
                  </div>
                  <div class="hidden sm:block w-20 shrink-0 text-right">
                    <span
                      v-if="match.match_status === 'completed'"
                      class="text-xs text-green-600 font-medium"
                      >Final</span
                    >
                    <span
                      v-else-if="match.match_status === 'in_progress'"
                      class="text-xs text-brand-600 font-medium animate-pulse"
                      >Live</span
                    >
                    <span
                      v-else-if="match.match_status === 'cancelled'"
                      class="text-xs text-red-500"
                      >Cancelled</span
                    >
                    <span
                      v-else
                      class="text-xs font-medium text-brand-600 hover:text-brand-800 hover:underline"
                      >Preview</span
                    >
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- ── Bracket view ── -->
        <template v-else-if="selected.matches && viewMode === 'bracket'">
          <!-- Selectors: age group + bracket group -->
          <div
            class="mb-5 flex flex-col sm:flex-row sm:items-center sm:flex-wrap gap-3"
          >
            <div
              v-if="bracketAgeGroups.length > 0"
              class="flex flex-wrap items-center gap-2"
            >
              <span
                class="text-xs font-semibold text-gray-500 uppercase tracking-wider mr-1"
                >Age</span
              >
              <button
                v-for="ag in bracketAgeGroups"
                :key="`bag-${ag.id}`"
                @click="bracketAgeGroupId = ag.id"
                :class="[
                  'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                  bracketAgeGroupId === ag.id
                    ? 'bg-indigo-600 text-white'
                    : 'bg-white border border-gray-300 text-gray-700 hover:border-indigo-400',
                ]"
              >
                {{ ag.name }}
              </button>
            </div>
            <div
              v-if="bracketGroups.length > 1"
              class="flex flex-wrap items-center gap-2"
            >
              <span
                class="text-xs font-semibold text-gray-500 uppercase tracking-wider mr-1"
                >Bracket</span
              >
              <button
                v-for="g in bracketGroups"
                :key="`bg-${g}`"
                @click="bracketGroup = g"
                :class="[
                  'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                  bracketGroup === g
                    ? 'bg-brand-600 text-white'
                    : 'bg-white border border-gray-300 text-gray-700 hover:border-brand-400',
                ]"
              >
                {{ g }}
              </button>
            </div>
          </div>

          <TournamentBracket
            :matches="bracketMatches"
            @match-click="viewMatch"
          />
        </template>

        <!-- ── Standings view ── -->
        <template v-else-if="selected.matches && viewMode === 'standings'">
          <!-- Selectors: age group + tournament group, reused pattern from Bracket -->
          <div
            class="mb-5 flex flex-col sm:flex-row sm:items-center sm:flex-wrap gap-3"
          >
            <div
              v-if="standingsAgeGroups.length > 1"
              class="flex flex-wrap items-center gap-2"
            >
              <span
                class="text-xs font-semibold text-gray-500 uppercase tracking-wider mr-1"
                >Age</span
              >
              <button
                v-for="ag in standingsAgeGroups"
                :key="`sag-${ag.id}`"
                @click="standingsAgeGroupId = ag.id"
                :class="[
                  'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                  standingsAgeGroupId === ag.id
                    ? 'bg-indigo-600 text-white'
                    : 'bg-white border border-gray-300 text-gray-700 hover:border-indigo-400',
                ]"
              >
                {{ ag.name }}
              </button>
            </div>
            <div
              v-if="standingsGroups.length > 1"
              class="flex flex-wrap items-center gap-2"
            >
              <span
                class="text-xs font-semibold text-gray-500 uppercase tracking-wider mr-1"
                >Bracket</span
              >
              <button
                v-for="g in standingsGroups"
                :key="`sg-${g}`"
                @click="standingsGroup = g"
                :class="[
                  'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                  standingsGroup === g
                    ? 'bg-brand-600 text-white'
                    : 'bg-white border border-gray-300 text-gray-700 hover:border-brand-400',
                ]"
              >
                {{ g }}
              </button>
            </div>
          </div>

          <TournamentStandings :matches="standingsMatches" />
        </template>
      </div>
    </template>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../config/api';
import TournamentBracket from './TournamentBracket.vue';
import TournamentStandings from './TournamentStandings.vue';
import MatchDetailView from './MatchDetailView.vue';

const KNOCKOUT_ROUNDS = new Set([
  'round_of_32',
  'round_of_16',
  'quarterfinal',
  'semifinal',
  'third_place',
  'final',
]);

const BRACKET_ROUNDS = new Set([
  'round_of_32',
  'round_of_16',
  'quarterfinal',
  'semifinal',
  'final',
]);

const ROUND_LABELS = {
  group_stage: 'Group Stage',
  round_of_32: 'R32',
  round_of_16: 'R16',
  quarterfinal: 'QF',
  semifinal: 'SF',
  third_place: '3rd Place',
  final: 'Final',
};

export default {
  name: 'TournamentMatchCenter',
  components: { TournamentBracket, TournamentStandings, MatchDetailView },
  setup() {
    const authStore = useAuthStore();

    const tournaments = ref([]);
    const loading = ref(true);
    const error = ref(null);

    const selectedId = ref(null);
    const selected = ref(null);
    const matchesLoading = ref(false);

    const teamFilter = ref('');
    const ageGroupFilter = ref(null);

    // ── view mode + bracket / standings selectors ──
    const viewMode = ref('list'); // 'list' | 'bracket' | 'standings'
    const bracketAgeGroupId = ref(null);
    const bracketGroup = ref(null);
    const standingsAgeGroupId = ref(null);
    const standingsGroup = ref(null);

    // ── inline match detail (preview) navigation ──
    // When set, MatchDetailView replaces the tournament page (same pattern
    // as MatchesView). Back button clears it.
    const selectedMatchId = ref(null);
    const viewMatch = match => {
      selectedMatchId.value = match.id;
    };
    const handleBackFromMatchDetail = () => {
      selectedMatchId.value = null;
    };

    // ── helpers ──

    const formatDate = d =>
      d
        ? new Date(d + 'T00:00:00').toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
          })
        : '';

    const formatMatchDate = d =>
      d
        ? new Date(d + 'T00:00:00').toLocaleDateString('en-US', {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
          })
        : '';

    const formatKickoffTime = iso =>
      iso
        ? new Date(iso).toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true,
          })
        : '';

    const roundLabel = match => ROUND_LABELS[match.tournament_round] || null;

    // ── data ──

    const fetchTournaments = async () => {
      try {
        loading.value = true;
        error.value = null;
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/tournaments`,
          { method: 'GET' }
        );
        tournaments.value = data || [];
        if (tournaments.value.length > 0) {
          await selectTournament(tournaments.value[0].id);
        }
      } catch (err) {
        error.value = err.message;
      } finally {
        loading.value = false;
      }
    };

    const selectTournament = async id => {
      selectedId.value = id;
      matchesLoading.value = true;
      teamFilter.value = '';
      ageGroupFilter.value = null;
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/tournaments/${id}`,
          { method: 'GET' }
        );
        selected.value = data;
      } catch (err) {
        error.value = err.message;
      } finally {
        matchesLoading.value = false;
      }
    };

    // ── filtered + sectioned matches ──

    const availableAgeGroups = computed(() => {
      const matches = selected.value?.matches ?? [];
      const seen = new Map();
      for (const m of matches) {
        if (m.age_group && !seen.has(m.age_group.id)) {
          seen.set(m.age_group.id, m.age_group);
        }
      }
      return [...seen.values()].sort((a, b) => a.name.localeCompare(b.name));
    });

    const filteredMatches = computed(() => {
      let matches = selected.value?.matches ?? [];
      if (ageGroupFilter.value !== null) {
        matches = matches.filter(m => m.age_group?.id === ageGroupFilter.value);
      }
      if (!teamFilter.value) return matches;
      const q = teamFilter.value.toLowerCase();
      return matches.filter(
        m =>
          m.home_team?.name?.toLowerCase().includes(q) ||
          m.away_team?.name?.toLowerCase().includes(q)
      );
    });

    const groupStageMatches = computed(() =>
      filteredMatches.value.filter(m => m.tournament_round === 'group_stage')
    );

    const knockoutMatches = computed(() =>
      filteredMatches.value
        .filter(m => KNOCKOUT_ROUNDS.has(m.tournament_round))
        .sort((a, b) => {
          const order = [
            'round_of_32',
            'round_of_16',
            'quarterfinal',
            'semifinal',
            'third_place',
            'final',
          ];
          return (
            order.indexOf(a.tournament_round) -
            order.indexOf(b.tournament_round)
          );
        })
    );

    const untaggedMatches = computed(() =>
      filteredMatches.value.filter(
        m =>
          !m.tournament_round ||
          (!KNOCKOUT_ROUNDS.has(m.tournament_round) &&
            m.tournament_round !== 'group_stage')
      )
    );

    // ── bracket-mode computed state ──

    // True when the selected tournament has at least one match tagged with
    // a single-elimination bracket round (drives the List|Bracket toggle).
    const hasBracketRounds = computed(() => {
      const matches = selected.value?.matches ?? [];
      return matches.some(m => BRACKET_ROUNDS.has(m.tournament_round));
    });

    const bracketAgeGroups = computed(() => {
      const matches = selected.value?.matches ?? [];
      const seen = new Map();
      for (const m of matches) {
        if (m.age_group && BRACKET_ROUNDS.has(m.tournament_round)) {
          seen.set(m.age_group.id, m.age_group);
        }
      }
      return [...seen.values()].sort((a, b) => a.name.localeCompare(b.name));
    });

    const bracketGroups = computed(() => {
      const matches = selected.value?.matches ?? [];
      const groups = new Set();
      for (const m of matches) {
        if (
          BRACKET_ROUNDS.has(m.tournament_round) &&
          (bracketAgeGroupId.value == null ||
            m.age_group?.id === bracketAgeGroupId.value) &&
          m.tournament_group
        ) {
          groups.add(m.tournament_group);
        }
      }
      // Stable order: Championship first if present, then alphabetical.
      const arr = [...groups];
      arr.sort((a, b) => {
        if (a === 'Championship') return -1;
        if (b === 'Championship') return 1;
        return a.localeCompare(b);
      });
      return arr;
    });

    const bracketMatches = computed(() => {
      const matches = selected.value?.matches ?? [];
      return matches.filter(
        m =>
          BRACKET_ROUNDS.has(m.tournament_round) &&
          (bracketAgeGroupId.value == null ||
            m.age_group?.id === bracketAgeGroupId.value) &&
          (bracketGroup.value == null ||
            m.tournament_group === bracketGroup.value)
      );
    });

    // Seed defaults when a tournament loads or its match set changes.
    watch(
      () => selected.value?.matches,
      () => {
        if (!hasBracketRounds.value) return;
        if (
          bracketAgeGroupId.value == null &&
          bracketAgeGroups.value.length > 0
        ) {
          bracketAgeGroupId.value = bracketAgeGroups.value[0].id;
        }
        if (bracketGroup.value == null && bracketGroups.value.length > 0) {
          bracketGroup.value = bracketGroups.value[0];
        }
      },
      { immediate: true }
    );

    // If user changes age group and the prior bracket group isn't available
    // for the new age group, fall back to the first available.
    watch(bracketAgeGroupId, () => {
      if (
        bracketGroup.value != null &&
        !bracketGroups.value.includes(bracketGroup.value)
      ) {
        bracketGroup.value = bracketGroups.value[0] ?? null;
      }
    });

    // ── standings-mode computed state ──
    // Same pattern as bracket-mode, but keyed off group_stage matches
    // grouped by `tournament_group` (e.g. 'U14 Boys Diamond Bracket A').

    const hasStandingsRounds = computed(() => {
      const matches = selected.value?.matches ?? [];
      return matches.some(
        m => m.tournament_round === 'group_stage' && m.tournament_group
      );
    });

    const standingsAgeGroups = computed(() => {
      const matches = selected.value?.matches ?? [];
      const seen = new Map();
      for (const m of matches) {
        if (
          m.age_group &&
          m.tournament_round === 'group_stage' &&
          m.tournament_group
        ) {
          seen.set(m.age_group.id, m.age_group);
        }
      }
      return [...seen.values()].sort((a, b) => a.name.localeCompare(b.name));
    });

    const standingsGroups = computed(() => {
      const matches = selected.value?.matches ?? [];
      const groups = new Set();
      for (const m of matches) {
        if (
          m.tournament_round === 'group_stage' &&
          m.tournament_group &&
          (standingsAgeGroupId.value == null ||
            m.age_group?.id === standingsAgeGroupId.value)
        ) {
          groups.add(m.tournament_group);
        }
      }
      return [...groups].sort((a, b) => a.localeCompare(b));
    });

    const standingsMatches = computed(() => {
      const matches = selected.value?.matches ?? [];
      return matches.filter(
        m =>
          m.tournament_round === 'group_stage' &&
          m.tournament_group &&
          (standingsAgeGroupId.value == null ||
            m.age_group?.id === standingsAgeGroupId.value) &&
          (standingsGroup.value == null ||
            m.tournament_group === standingsGroup.value)
      );
    });

    watch(
      () => selected.value?.matches,
      () => {
        if (!hasStandingsRounds.value) return;
        if (
          standingsAgeGroupId.value == null &&
          standingsAgeGroups.value.length > 0
        ) {
          standingsAgeGroupId.value = standingsAgeGroups.value[0].id;
        }
        if (standingsGroup.value == null && standingsGroups.value.length > 0) {
          standingsGroup.value = standingsGroups.value[0];
        }
      },
      { immediate: true }
    );

    watch(standingsAgeGroupId, () => {
      if (
        standingsGroup.value != null &&
        !standingsGroups.value.includes(standingsGroup.value)
      ) {
        standingsGroup.value = standingsGroups.value[0] ?? null;
      }
    });

    onMounted(fetchTournaments);

    return {
      tournaments,
      loading,
      error,
      selectedId,
      selected,
      matchesLoading,
      teamFilter,
      ageGroupFilter,
      availableAgeGroups,
      filteredMatches,
      groupStageMatches,
      knockoutMatches,
      untaggedMatches,
      formatDate,
      formatMatchDate,
      formatKickoffTime,
      roundLabel,
      selectTournament,
      viewMode,
      hasBracketRounds,
      bracketAgeGroups,
      bracketAgeGroupId,
      bracketGroups,
      bracketGroup,
      bracketMatches,
      hasStandingsRounds,
      standingsAgeGroups,
      standingsAgeGroupId,
      standingsGroups,
      standingsGroup,
      standingsMatches,
      selectedMatchId,
      viewMatch,
      handleBackFromMatchDetail,
    };
  },
};
</script>
