<template>
  <!--
    Power Rating audit (SB-1812) over GET /api/admin/power-rating/audit: the
    teams whose Elo and Massey places, within their island, differ by more
    than the gap. Investigate, never auto-fix. Admin only.
  -->
  <div class="admin-power-rating-audit" data-testid="pr-audit">
    <div
      class="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-6"
    >
      <h2 class="text-xl font-semibold text-fg">Power Rating audit</h2>
      <button
        type="button"
        @click="recomputeNow"
        :disabled="recomputing"
        class="px-4 py-2 text-sm rounded-lg font-medium bg-brand-500 text-white disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="pr-audit-recompute"
      >
        {{ recomputing ? 'Recomputing...' : 'Recompute now' }}
      </button>
    </div>

    <div class="flex flex-col sm:flex-row sm:items-end gap-4 mb-4">
      <div>
        <h3 class="text-sm font-medium text-fg mb-2">Age Groups</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="age in AGE_GROUPS"
            :key="age"
            type="button"
            @click="selectedAgeGroup = age"
            :class="pillClass(selectedAgeGroup === age)"
            :data-testid="`pr-audit-age-${age}`"
          >
            {{ age }}
          </button>
        </div>
      </div>
      <div>
        <label
          for="pr-audit-min-gap"
          class="block text-sm font-medium text-fg mb-2"
          >Flag gaps above (places)</label
        >
        <input
          id="pr-audit-min-gap"
          v-model.number="minGapInput"
          type="number"
          min="0"
          step="1"
          @change="applyMinGap"
          class="w-24 px-3 py-2 text-sm bg-card border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
          data-testid="pr-audit-min-gap"
        />
      </div>
    </div>

    <!-- What the last "Recompute now" did, per age group -->
    <div
      v-if="recomputeError"
      class="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm"
      data-testid="pr-audit-recompute-error"
    >
      {{ recomputeError }}
    </div>
    <div
      v-if="recomputeSummary"
      class="mb-4 p-3 bg-brand-50 border border-brand-200 rounded text-sm text-fg"
      data-testid="pr-audit-recompute-summary"
    >
      <p class="font-medium mb-1">Recomputed {{ recomputeSummary.league }}</p>
      <ul class="space-y-0.5">
        <li
          v-for="ag in recomputeSummary.age_groups"
          :key="ag.age_group"
          :data-testid="`pr-audit-recompute-${ag.age_group}`"
        >
          {{ recomputeLine(ag) }}
        </li>
      </ul>
    </div>

    <div
      v-if="loading"
      class="text-center py-8 text-fg-muted"
      data-testid="pr-audit-loading"
    >
      Loading audit...
    </div>

    <div
      v-else-if="error"
      class="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm"
      data-testid="pr-audit-error"
    >
      {{ error }}
    </div>

    <template v-else-if="result">
      <div class="mb-4 space-y-1">
        <p
          v-if="summaryLine"
          class="text-sm font-medium text-fg"
          data-testid="pr-audit-summary"
        >
          {{ summaryLine }}
        </p>
        <p class="text-xs text-fg-muted" data-testid="pr-audit-scope">
          {{ result.scope }}
        </p>
        <p class="text-xs text-fg-muted" data-testid="pr-audit-note">
          {{ result.note }}
        </p>
      </div>

      <!-- No run, or nothing to compare: the API's reason -->
      <div
        v-if="result.reason"
        class="text-center py-8 text-fg-muted"
        data-testid="pr-audit-empty"
      >
        {{ result.reason }}
      </div>

      <div
        v-else-if="!rows.length"
        class="text-center py-8 text-fg-muted"
        data-testid="pr-audit-none-flagged"
      >
        No gaps above {{ result.min_gap }} places.
      </div>

      <template v-else>
        <!-- Desktop table -->
        <div
          class="hidden sm:block overflow-x-auto border border-line rounded-lg"
        >
          <table class="min-w-full text-sm" data-testid="pr-audit-table">
            <thead class="bg-surface-alt text-fg-muted text-xs uppercase">
              <tr>
                <th class="px-3 py-2 text-left">Team</th>
                <th class="px-3 py-2 text-left">Conference</th>
                <th class="px-3 py-2 text-right">Elo</th>
                <th class="px-3 py-2 text-right">Elo rank</th>
                <th class="px-3 py-2 text-right">Massey rank</th>
                <th class="px-3 py-2 text-right">Gap</th>
                <th class="px-3 py-2 text-right">MP</th>
                <th class="px-3 py-2 text-right">X-conf MP</th>
                <th class="px-3 py-2 text-left">Badges</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-line">
              <tr
                v-for="row in rows"
                :key="row.team_id"
                data-testid="pr-audit-row"
              >
                <td class="px-3 py-2 text-fg">{{ row.team }}</td>
                <td class="px-3 py-2 text-fg-muted">
                  {{ row.conference || '—' }}
                </td>
                <td class="px-3 py-2 text-right">
                  {{ formatRating(row.elo_rating) }}
                </td>
                <td class="px-3 py-2 text-right">{{ row.elo_rank }}</td>
                <td class="px-3 py-2 text-right">{{ row.massey_rank }}</td>
                <td class="px-3 py-2 text-right font-medium">
                  {{ formatGap(row.gap) }}
                </td>
                <td class="px-3 py-2 text-right">{{ row.mp }}</td>
                <td class="px-3 py-2 text-right">{{ row.xconf_mp }}</td>
                <td class="px-3 py-2 text-fg-muted">
                  {{ badgeText(row.badges) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Mobile: stacked rows -->
        <ul
          class="sm:hidden divide-y divide-line border border-line rounded-lg"
          data-testid="pr-audit-list"
        >
          <li
            v-for="row in rows"
            :key="row.team_id"
            class="p-3 text-sm"
            data-testid="pr-audit-item"
          >
            <div class="flex justify-between gap-2">
              <span class="font-medium text-fg">{{ row.team }}</span>
              <span class="font-medium">{{ formatGap(row.gap) }}</span>
            </div>
            <p class="text-xs text-fg-muted">
              {{ row.conference || '—' }} · Elo
              {{ formatRating(row.elo_rating) }}
            </p>
            <p class="text-xs text-fg-muted">
              Elo {{ row.elo_rank }} · Massey {{ row.massey_rank }} ·
              {{ row.mp }} MP · {{ row.xconf_mp }} cross-conf.
            </p>
            <p v-if="row.badges.length" class="text-xs text-fg-muted">
              {{ badgeText(row.badges) }}
            </p>
          </li>
        </ul>
      </template>
    </template>
  </div>
</template>

<script>
import { computed, onMounted, ref, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';
import { BADGES, formatRating, formatUpdated } from '@/utils/powerRating';

// The Power Rating covers Homegrown U15 to U19 (power-rating.md "Scope").
const AGE_GROUPS = ['U15', 'U16', 'U17', 'U19'];
const LEAGUE = 'Homegrown';
// About the worst 5% at the 2026-11-26 freeze (power-rating.md).
const DEFAULT_MIN_GAP = 30;
const MINUS = '−';

export default {
  name: 'AdminPowerRatingAudit',
  setup() {
    const authStore = useAuthStore();

    const selectedAgeGroup = ref('U15');
    const minGap = ref(DEFAULT_MIN_GAP);
    const minGapInput = ref(DEFAULT_MIN_GAP);

    const result = ref(null);
    const loading = ref(false);
    const error = ref('');

    const recomputing = ref(false);
    const recomputeSummary = ref(null);
    const recomputeError = ref('');

    const pillClass = active => [
      'px-4 py-2 text-sm rounded-lg font-medium transition-colors',
      active
        ? 'bg-brand-500 text-white shadow-sm'
        : 'bg-surface-alt text-fg-muted hover:bg-line',
    ];

    const rows = computed(() => result.value?.teams || []);

    const summaryLine = computed(() => {
      const r = result.value;
      if (!r?.run) return '';
      const parts = [`Run #${r.run.id}`];
      const updated = formatUpdated(r.run.computed_at);
      if (updated) parts.push(`updated ${updated}`);
      parts.push(`${r.teams_compared} teams compared`);
      parts.push(`${r.flagged_count} flagged above ${r.min_gap} places`);
      if (r.rank_correlation != null) {
        parts.push(`rank correlation ${r.rank_correlation.toFixed(2)}`);
      }
      return parts.join(' · ');
    });

    // Positive gap: Elo ranks the team higher than Massey does.
    const formatGap = gap => {
      if (gap > 0) return `+${gap} Elo higher`;
      if (gap < 0) return `${MINUS}${Math.abs(gap)} Massey higher`;
      return '0';
    };

    const badgeText = badges =>
      (badges || []).map(b => BADGES[b]?.label || b).join(', ') || '—';

    const recomputeLine = ag => {
      const parts = [`${ag.age_group}: ${ag.status}`];
      if (ag.run_id != null) parts.push(`run #${ag.run_id}`);
      if (ag.teams != null) parts.push(`${ag.teams} teams`);
      if (ag.reason) parts.push(ag.reason);
      return parts.join(' · ');
    };

    // A filter change mid-flight must not let the older answer land last.
    let requestId = 0;

    const fetchAudit = async () => {
      const id = ++requestId;
      loading.value = true;
      error.value = '';
      const params = new URLSearchParams({
        league: LEAGUE,
        age_group: selectedAgeGroup.value,
        min_gap: String(minGap.value),
      });
      try {
        const data = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/power-rating/audit?${params}`
        );
        if (id !== requestId) return;
        result.value = data;
      } catch (err) {
        if (id !== requestId) return;
        result.value = null;
        error.value =
          err?.message || 'The Power Rating audit is unavailable right now.';
      } finally {
        if (id === requestId) loading.value = false;
      }
    };

    const applyMinGap = () => {
      const value = Number(minGapInput.value);
      if (!Number.isInteger(value) || value < 0) {
        minGapInput.value = minGap.value;
        return;
      }
      minGap.value = value;
    };

    const recomputeNow = async () => {
      recomputing.value = true;
      recomputeError.value = '';
      try {
        recomputeSummary.value = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/admin/power-rating/recompute?league=${LEAGUE}`,
          { method: 'POST' }
        );
        await fetchAudit();
      } catch (err) {
        recomputeSummary.value = null;
        recomputeError.value =
          err?.message || 'Could not recompute the power rating.';
      } finally {
        recomputing.value = false;
      }
    };

    watch([selectedAgeGroup, minGap], fetchAudit);
    onMounted(fetchAudit);

    return {
      AGE_GROUPS,
      selectedAgeGroup,
      minGapInput,
      result,
      loading,
      error,
      recomputing,
      recomputeSummary,
      recomputeError,
      rows,
      summaryLine,
      pillClass,
      formatGap,
      formatRating,
      badgeText,
      recomputeLine,
      applyMinGap,
      recomputeNow,
    };
  },
};
</script>
