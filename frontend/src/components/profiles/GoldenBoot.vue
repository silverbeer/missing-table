<template>
  <section class="golden-boot">
    <header class="gb-header">
      <h3 class="gb-title">Golden Boot</h3>
      <!-- Rendered only once the options exist. A <select> whose v-model is set
           before its v-for options have arrived keeps displaying the option that
           was there first, so the control would read "All" while the model — and
           the request — said League. -->
      <div v-if="filtersReady" class="gb-filters">
        <select
          v-model="selectedSeasonId"
          class="gb-filter"
          aria-label="Season"
        >
          <option v-for="s in seasons" :key="s.id" :value="s.id">
            {{ s.name }}
          </option>
        </select>
        <select
          v-model="selectedMatchTypeId"
          class="gb-filter"
          aria-label="Competition"
        >
          <option v-for="t in matchTypes" :key="t.id" :value="t.id">
            {{ t.name }}
          </option>
          <option v-if="leagueFlexIds" :value="LEAGUE_FLEX">
            League + Flex
          </option>
          <option value="all">All</option>
        </select>
      </div>
    </header>

    <div v-if="loading" class="gb-state">Loading season stats...</div>

    <div v-else-if="error" class="gb-state gb-state-error">{{ error }}</div>

    <!-- Absent is not zero (CLAUDE.md: "Most Teams Have No User Data"). An empty
         table would read as "nobody scored"; this says nothing has been logged. -->
    <div v-else-if="nothingLogged" class="gb-state gb-state-empty">
      <p class="gb-empty-title">Nothing recorded for this squad yet</p>
      <p class="gb-empty-hint">
        Appearances, goals and assists appear here once matches are scored in
        the app. Results from the league feed do not include who played or who
        scored.
      </p>
    </div>

    <table v-else class="gb-table">
      <thead>
        <tr>
          <th scope="col" class="gb-rank-col">#</th>
          <th scope="col" class="gb-player-col">Player</th>
          <th
            v-for="col in statColumns"
            :key="col.key"
            scope="col"
            class="gb-stat-col"
            :class="{ 'gb-col-active': sortKey === col.key }"
            :aria-sort="sortKey === col.key ? 'descending' : 'none'"
          >
            <button
              type="button"
              class="gb-sort-button"
              :aria-label="`Sort by ${col.label}${col.beta ? ' (beta)' : ''}`"
              @click="sortBy(col.key)"
            >
              {{ col.short }}
              <span v-if="col.beta" class="gb-beta-tag">Beta</span>
            </button>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in rows" :key="row.player_id" class="gb-row">
          <td class="gb-rank-col" :class="medalClass(index)">
            {{ index + 1 }}
          </td>
          <td class="gb-player-col">
            <span class="gb-jersey">#{{ row.jersey_number }}</span>
            <span class="gb-name">{{ playerName(row) }}</span>
          </td>
          <td
            v-for="col in statColumns"
            :key="col.key"
            class="gb-stat-col"
            :class="{ 'gb-col-active': sortKey === col.key }"
          >
            {{ row[col.field] }}
          </td>
        </tr>
      </tbody>
    </table>

    <p
      v-if="!loading && !error && !nothingLogged"
      class="gb-beta-note"
      data-testid="gb-beta-note"
    >
      GP and GS are in beta and may be incomplete. To correct a total,
      <SupportEmailLink
        subject="Golden Boot correction"
        :body="`Team ID: ${teamId}\nPlayer, match, and what should change:`"
        display-text="contact support"
      />
    </p>
  </section>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';
import SupportEmailLink from '@/components/SupportEmailLink.vue';

// Minutes are deliberately absent. They are recorded, but a substitution nobody
// logged silently understates a player, and a column that is quietly wrong is
// worse than a column that is missing. Everything here is either counted from
// an event (G, A, YC, RC) or from an appearance record (GP, GS).
//
// GP and GS are marked beta (SB-1614): they are only as good as the lineups that
// were logged, unlike the event counts.
const STAT_COLUMNS = [
  {
    key: 'gp',
    short: 'GP',
    label: 'games played',
    field: 'games_played',
    beta: true,
  },
  {
    key: 'gs',
    short: 'GS',
    label: 'games started',
    field: 'games_started',
    beta: true,
  },
  { key: 'goals', short: 'G', label: 'goals', field: 'total_goals' },
  { key: 'assists', short: 'A', label: 'assists', field: 'total_assists' },
  {
    key: 'yc',
    short: 'YC',
    label: 'yellow cards',
    field: 'total_yellow_cards',
  },
  { key: 'rc', short: 'RC', label: 'red cards', field: 'total_red_cards' },
];

// The "every competition" choice. A sentinel, not null, so the <select> and the
// model cannot disagree about which option is selected.
const ALL_COMPETITIONS = 'all';

// League and Flex totalled (SB-1599). Homegrown teams play both, and Flex is a
// child league of Homegrown, so for them one without the other is half a season.
const LEAGUE_FLEX = 'league-flex';

// A team names its home league directly, and each mapping names its division's
// league, so a team registered in Homegrown is found either way.
const playsHomegrown = team =>
  team?.league_name === 'Homegrown' ||
  (team?.team_mappings || []).some(
    m => m?.divisions?.leagues?.name === 'Homegrown'
  );

const FIELD_BY_KEY = Object.fromEntries(
  STAT_COLUMNS.map(c => [c.key, c.field])
);

export default {
  name: 'GoldenBoot',
  components: { SupportEmailLink },
  props: {
    teamId: { type: [Number, String], required: true },
    // The default competition depends on the whole club, not this squad.
    clubId: { type: [Number, String], default: null },
  },
  setup(props) {
    const authStore = useAuthStore();
    const loading = ref(true);
    const error = ref(null);
    const stats = ref([]);
    const sortKey = ref('goals');

    const seasons = ref([]);
    const matchTypes = ref([]);
    const selectedSeasonId = ref(null);
    // 'all' rather than null: a null-valued <option> carries no value attribute,
    // so the browser falls back to its label and the select reports "All" no
    // matter which entry Vue marked selected. An explicit sentinel keeps the DOM
    // and the model agreeing.
    const selectedMatchTypeId = ref(ALL_COMPETITIONS);
    const filtersReady = ref(false);

    const statColumns = STAT_COLUMNS;

    // [leagueId, flexId], or null when either type is not configured.
    const leagueFlexIds = computed(() => {
      const idOf = name =>
        matchTypes.value.find(t => (t.name || '').toLowerCase() === name)?.id;
      const league = idOf('league');
      const flex = idOf('flex');
      return league != null && flex != null ? [league, flex] : null;
    });

    const playerName = row => {
      const name = `${row.first_name || ''} ${row.last_name || ''}`.trim();
      return name || `#${row.jersey_number}`;
    };

    // Everyone who took part, not only scorers. An appearance is a
    // contribution, so a player with games and no goals belongs here — while a
    // squad member who has not played a minute does not, since a row of zeroes
    // says something untrue about them (SB-670).
    //
    // A recorded goal, assist or card also counts as taking part. It ought to
    // imply an appearance and normally does, but the appearance flags and the
    // event counters are written by different paths, and a scorer missing from
    // the scorers table would be a worse bug than one surplus row.
    const played = computed(() =>
      stats.value.filter(p => STAT_COLUMNS.some(col => (p[col.field] || 0) > 0))
    );

    const rows = computed(() => {
      const primary = FIELD_BY_KEY[sortKey.value] || 'total_goals';

      return [...played.value].sort((a, b) => {
        const byPrimary = (b[primary] || 0) - (a[primary] || 0);
        if (byPrimary !== 0) return byPrimary;
        // Goals then assists break the tie before a name does, so two players
        // level on the sorted column are separated by something they earned.
        if (primary !== 'total_goals') {
          const byGoals = (b.total_goals || 0) - (a.total_goals || 0);
          if (byGoals !== 0) return byGoals;
        }
        if (primary !== 'total_assists') {
          const byAssists = (b.total_assists || 0) - (a.total_assists || 0);
          if (byAssists !== 0) return byAssists;
        }
        return playerName(a).localeCompare(playerName(b));
      });
    });

    // Nobody took part in anything that was recorded. Distinct from "everyone
    // scored zero": one is a season nobody logged, the other a season nobody
    // scored in, and rendering the first as a table of zeroes is the
    // absent-as-zero pun the CLAUDE.md rule forbids.
    const nothingLogged = computed(() => !played.value.length);

    // Rank and medal follow the column being sorted, so the tint always marks
    // the leaders in what the reader is currently looking at.
    const medalClass = index => {
      if (index > 2) return '';
      // No medals for leading on nothing — sorted by goals on a team that has
      // not scored, the top three would otherwise be tinted for zero.
      const primary = FIELD_BY_KEY[sortKey.value] || 'total_goals';
      if (!(rows.value[0]?.[primary] || 0)) return '';
      if (index === 0) return 'gb-medal-gold';
      if (index === 1) return 'gb-medal-silver';
      return 'gb-medal-bronze';
    };

    const sortBy = key => {
      sortKey.value = key;
    };

    // Defaults: current season, league games only. A leaderboard that silently
    // folds friendlies and tournaments into one total is not comparable with the
    // league table beside it, so "All" has to be asked for. A club with a team
    // in Homegrown opens on League + Flex instead (SB-1599).
    //
    // A failed club lookup only costs that default, so it must not fail the
    // board: the club endpoint also answers 404 for a club with no teams.
    const fetchClubIsHomegrown = async () => {
      if (!props.clubId) return false;
      try {
        const teams = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/clubs/${props.clubId}/teams`,
          { method: 'GET' }
        );
        return Array.isArray(teams) && teams.some(playsHomegrown);
      } catch (err) {
        console.error('Error loading club teams for Golden Boot:', err);
        return false;
      }
    };

    const loadFilters = async () => {
      const [seasonList, typeList, clubIsHomegrown] = await Promise.all([
        authStore.apiRequest(`${getApiBaseUrl()}/api/seasons`, {
          method: 'GET',
        }),
        authStore.apiRequest(`${getApiBaseUrl()}/api/match-types`, {
          method: 'GET',
        }),
        fetchClubIsHomegrown(),
      ]);

      seasons.value = seasonList || [];
      matchTypes.value = typeList || [];

      const currentSeason =
        seasons.value.find(s => s.is_current) || seasons.value[0];
      selectedSeasonId.value = currentSeason?.id ?? null;

      const league = matchTypes.value.find(
        t => (t.name || '').toLowerCase() === 'league'
      );
      // No league type configured is not an error — fall back to every
      // competition rather than rendering an empty board.
      selectedMatchTypeId.value =
        clubIsHomegrown && leagueFlexIds.value
          ? LEAGUE_FLEX
          : (league?.id ?? ALL_COMPETITIONS);

      filtersReady.value = true;
      return !!currentSeason;
    };

    const fetchStats = async () => {
      if (!props.teamId || !filtersReady.value || !selectedSeasonId.value) {
        return;
      }
      loading.value = true;
      error.value = null;

      try {
        const params = new URLSearchParams({
          season_id: String(selectedSeasonId.value),
        });
        if (selectedMatchTypeId.value === LEAGUE_FLEX) {
          leagueFlexIds.value.forEach(id =>
            params.append('match_type_id', String(id))
          );
        } else if (selectedMatchTypeId.value !== ALL_COMPETITIONS) {
          params.set('match_type_id', String(selectedMatchTypeId.value));
        }

        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/teams/${props.teamId}/stats?${params}`,
          { method: 'GET' }
        );
        stats.value = Array.isArray(response)
          ? response
          : response?.players || [];
      } catch (err) {
        console.error('Error loading team stats:', err);
        error.value = 'Could not load season stats';
      } finally {
        loading.value = false;
      }
    };

    const init = async () => {
      loading.value = true;
      error.value = null;
      try {
        const hasSeason = await loadFilters();
        if (!hasSeason) {
          error.value = 'No season configured';
          loading.value = false;
          return;
        }
      } catch (err) {
        console.error('Error loading stat filters:', err);
        error.value = 'Could not load season stats';
        loading.value = false;
        return;
      }
      await fetchStats();
    };

    onMounted(init);
    watch(() => props.teamId, fetchStats);
    watch([selectedSeasonId, selectedMatchTypeId], fetchStats);

    return {
      loading,
      error,
      rows,
      nothingLogged,
      filtersReady,
      seasons,
      matchTypes,
      selectedSeasonId,
      selectedMatchTypeId,
      leagueFlexIds,
      LEAGUE_FLEX,
      sortKey,
      statColumns,
      playerName,
      medalClass,
      sortBy,
    };
  },
};
</script>

<style scoped>
.golden-boot {
  margin-top: 24px;
}

.gb-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.gb-title {
  font-size: 1.1rem;
  font-weight: 700;
  margin: 0;
  color: rgb(var(--color-fg));
}

.gb-filters {
  display: flex;
  gap: 8px;
}

.gb-filter {
  font-size: 0.8rem;
  color: rgb(var(--color-fg));
  background: rgb(var(--color-card));
  border: 1px solid rgb(var(--color-line));
  border-radius: 6px;
  padding: 3px 6px;
  cursor: pointer;
}

.gb-filter:hover {
  border-color: rgb(var(--color-fg-muted));
}

.gb-state {
  padding: 16px;
  font-size: 0.9rem;
  color: rgb(var(--color-fg-muted));
  background: rgb(var(--color-surface-alt));
  border-radius: 8px;
}

.gb-state-error {
  color: #b91c1c;
  background: rgb(185 28 28 / 0.1);
}

:global(.dark) .gb-state-error {
  color: #fca5a5;
}

.gb-empty-title {
  margin: 0 0 4px;
  font-weight: 600;
  color: rgb(var(--color-fg));
}

.gb-empty-hint {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.4;
}

.gb-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.gb-table thead th {
  padding: 8px 10px;
  border-bottom: 2px solid rgb(var(--color-line));
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: rgb(var(--color-fg-muted));
  text-align: left;
}

.gb-row td {
  padding: 9px 10px;
  border-bottom: 1px solid rgb(var(--color-line));
  color: rgb(var(--color-fg));
}

.gb-row:hover td {
  background: rgb(var(--color-surface-alt));
}

.gb-rank-col {
  width: 42px;
  text-align: center;
  color: rgb(var(--color-fg-muted));
  font-variant-numeric: tabular-nums;
}

.gb-player-col {
  text-align: left;
}

.gb-jersey {
  display: inline-block;
  min-width: 30px;
  color: rgb(var(--color-fg-muted));
  font-variant-numeric: tabular-nums;
}

.gb-name {
  font-weight: 500;
}

.gb-stat-col {
  width: 44px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

/* A zero is a real measurement here, not a gap — but it should not compete with
   the numbers that carry the story. */
.gb-row td.gb-stat-col {
  color: rgb(var(--color-fg-muted));
}

.gb-table thead th.gb-stat-col {
  text-align: center;
}

.gb-sort-button {
  background: none;
  border: none;
  padding: 0;
  font: inherit;
  color: inherit;
  text-transform: inherit;
  letter-spacing: inherit;
  cursor: pointer;
}

/* Same amber as the nav's Beta badge. Fixed colours: the tint stays light in both
   themes, so the text on it stays dark. */
.gb-beta-tag {
  display: block;
  width: fit-content;
  margin: 2px auto 0;
  padding: 0 3px;
  font-size: 0.5625rem;
  font-weight: 700;
  line-height: 1.4;
  letter-spacing: 0.02em;
  color: #92400e;
  background-color: #fef3c7;
  border-radius: 9999px;
}

.gb-beta-note {
  margin: 10px 0 0;
  font-size: 0.78rem;
  line-height: 1.4;
  color: rgb(var(--color-fg-muted));
}

.gb-sort-button:hover {
  color: rgb(var(--color-fg));
}

/* Active sort column: shaded body cells and an accent rule under the header,
   the way a league stats table marks what it is ordered by. */
.gb-table thead th.gb-col-active {
  color: #b91c1c;
  box-shadow: inset 0 -2px 0 0 #b91c1c;
}

:global(.dark) .gb-table thead th.gb-col-active {
  color: #f87171;
  box-shadow: inset 0 -2px 0 0 #f87171;
}

.gb-row td.gb-col-active {
  background: rgb(var(--color-surface-alt));
  color: rgb(var(--color-fg));
  font-weight: 700;
}

.gb-row:hover td.gb-col-active {
  background: rgb(var(--color-line));
}

/* The tints stay light in both themes, so the text on them stays dark. Needs
   .gb-row td specificity, or the themed row colour lands on the tint. */
.gb-row td.gb-medal-gold,
.gb-row td.gb-medal-silver,
.gb-row td.gb-medal-bronze {
  font-weight: 700;
  color: #78350f;
  border-radius: 4px;
}

.gb-row td.gb-medal-gold {
  background: #fde68a;
}

.gb-row td.gb-medal-silver {
  background: #e5e7eb;
  color: #374151;
}

.gb-row td.gb-medal-bronze {
  background: #f5d0a9;
}

@media (max-width: 480px) {
  .gb-table {
    font-size: 0.85rem;
  }

  .gb-row td,
  .gb-table thead th {
    padding: 8px 6px;
  }

  .gb-stat-col {
    width: 34px;
  }

  .gb-jersey {
    min-width: 26px;
  }

  .gb-beta-tag {
    padding: 0 2px;
    font-size: 0.5rem;
  }
}
</style>
