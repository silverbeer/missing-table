<template>
  <section class="golden-boot">
    <header class="gb-header">
      <h3 class="gb-title">Golden Boot</h3>
      <span v-if="seasonName" class="gb-season">{{ seasonName }}</span>
    </header>

    <div v-if="loading" class="gb-state">Loading season stats...</div>

    <div v-else-if="error" class="gb-state gb-state-error">{{ error }}</div>

    <!-- Absent is not zero (CLAUDE.md: "Most Teams Have No User Data"). An empty
         table would read as "nobody scored"; this says nothing has been logged. -->
    <div v-else-if="!rows.length" class="gb-state gb-state-empty">
      <p class="gb-empty-title">No goals or assists recorded yet</p>
      <p class="gb-empty-hint">
        Goals and assists appear here once matches are scored in the app.
        Results from the league feed do not include who scored.
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
              :aria-label="`Sort by ${col.label}`"
              @click="sortBy(col.key)"
            >
              {{ col.short }}
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
  </section>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';

// Minutes are deliberately absent. They are recorded, but a substitution nobody
// logged silently understates a player, and a column that is quietly wrong is
// worse than a column that is missing. Everything here is either counted from
// an event (G, A, YC, RC) or from an appearance record (GP, GS).
const STAT_COLUMNS = [
  { key: 'gp', short: 'GP', label: 'games played', field: 'games_played' },
  { key: 'gs', short: 'GS', label: 'games started', field: 'games_started' },
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

const FIELD_BY_KEY = Object.fromEntries(
  STAT_COLUMNS.map(c => [c.key, c.field])
);

export default {
  name: 'GoldenBoot',
  props: {
    teamId: { type: [Number, String], required: true },
  },
  setup(props) {
    const authStore = useAuthStore();
    const loading = ref(true);
    const error = ref(null);
    const stats = ref([]);
    const seasonName = ref('');
    const sortKey = ref('goals');

    const statColumns = STAT_COLUMNS;

    const playerName = row => {
      const name = `${row.first_name || ''} ${row.last_name || ''}`.trim();
      return name || `#${row.jersey_number}`;
    };

    // Only players who did something. A roster listing every squad member at
    // 0 and 0 buries the four who scored, and reads as a judgement on the rest.
    const contributors = computed(() =>
      stats.value.filter(
        p => (p.total_goals || 0) > 0 || (p.total_assists || 0) > 0
      )
    );

    const rows = computed(() => {
      const primary = FIELD_BY_KEY[sortKey.value] || 'total_goals';

      return [...contributors.value].sort((a, b) => {
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

    // Rank and medal follow the column being sorted, so the tint always marks
    // the leaders in what the reader is currently looking at.
    const medalClass = index => {
      if (index === 0) return 'gb-medal-gold';
      if (index === 1) return 'gb-medal-silver';
      if (index === 2) return 'gb-medal-bronze';
      return '';
    };

    const sortBy = key => {
      sortKey.value = key;
    };

    const fetchStats = async () => {
      if (!props.teamId) return;
      loading.value = true;
      error.value = null;

      try {
        // Same current-season resolution the rest of the app uses.
        const seasons = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/seasons`,
          { method: 'GET' }
        );
        const season =
          (seasons || []).find(s => s.is_current) || (seasons || [])[0];
        if (!season) {
          error.value = 'No season configured';
          return;
        }
        seasonName.value = season.name || '';

        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/teams/${props.teamId}/stats?season_id=${season.id}`,
          { method: 'GET' }
        );
        stats.value = Array.isArray(response)
          ? response
          : response?.stats || [];
      } catch (err) {
        console.error('Error loading team stats:', err);
        error.value = 'Could not load season stats';
      } finally {
        loading.value = false;
      }
    };

    onMounted(fetchStats);
    watch(() => props.teamId, fetchStats);

    return {
      loading,
      error,
      rows,
      seasonName,
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
  margin-bottom: 8px;
}

.gb-title {
  font-size: 1.1rem;
  font-weight: 700;
  margin: 0;
  color: #111827;
}

.gb-season {
  font-size: 0.8rem;
  color: #6b7280;
}

.gb-state {
  padding: 16px;
  font-size: 0.9rem;
  color: #6b7280;
  background: #f9fafb;
  border-radius: 8px;
}

.gb-state-error {
  color: #b91c1c;
  background: #fef2f2;
}

.gb-empty-title {
  margin: 0 0 4px;
  font-weight: 600;
  color: #374151;
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
  border-bottom: 2px solid #e5e7eb;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #6b7280;
  text-align: left;
}

.gb-row td {
  padding: 9px 10px;
  border-bottom: 1px solid #f3f4f6;
  color: #111827;
}

.gb-row:hover td {
  background: #f9fafb;
}

.gb-rank-col {
  width: 42px;
  text-align: center;
  color: #6b7280;
  font-variant-numeric: tabular-nums;
}

.gb-player-col {
  text-align: left;
}

.gb-jersey {
  display: inline-block;
  min-width: 30px;
  color: #9ca3af;
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
  color: #374151;
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

.gb-sort-button:hover {
  color: #111827;
}

/* Active sort column: shaded body cells and an accent rule under the header,
   the way a league stats table marks what it is ordered by. */
.gb-table thead th.gb-col-active {
  color: #b91c1c;
  box-shadow: inset 0 -2px 0 0 #b91c1c;
}

.gb-row td.gb-col-active {
  background: #fafafa;
  font-weight: 700;
}

.gb-row:hover td.gb-col-active {
  background: #f3f4f6;
}

.gb-medal-gold,
.gb-medal-silver,
.gb-medal-bronze {
  font-weight: 700;
  color: #78350f;
  border-radius: 4px;
}

.gb-medal-gold {
  background: #fde68a;
}

.gb-medal-silver {
  background: #e5e7eb;
  color: #374151;
}

.gb-medal-bronze {
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
}
</style>
