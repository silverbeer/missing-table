<template>
  <!--
    1080x1080 Instagram-square share card (SB-32). Pure presentational.
    Renders at exact output size; html2canvas captures it 1:1 — DO NOT change
    width/height or wrap in flex containers that resize it.
  -->
  <div
    ref="root"
    class="ig-share-card"
    data-testid="ig-share-card"
    :data-mode="mode"
  >
    <!-- Photo layer (full bleed) -->
    <img
      v-if="photoSrc"
      :src="photoSrc"
      class="ig-photo"
      data-testid="ig-photo"
      :crossorigin="photoCrossOrigin"
      alt=""
    />
    <div v-else class="ig-photo-fallback" data-testid="ig-photo-fallback">
      <div class="ig-photo-fallback-glow"></div>
    </div>

    <!-- Top gradient + chip row -->
    <div class="ig-top-overlay">
      <div class="ig-top-row">
        <span class="ig-chip ig-chip-age" data-testid="ig-age-chip">
          {{ ageGroupLabel }}
        </span>
        <span class="ig-chip-meta" data-testid="ig-meta">
          {{ metaLabel }}
        </span>
      </div>
    </div>

    <!-- Bottom gradient + content -->
    <div class="ig-bottom-overlay">
      <div class="ig-status-row">
        <span
          v-if="mode === 'result'"
          class="ig-status ig-status-final"
          data-testid="ig-status"
        >
          FINAL
        </span>
        <span
          v-else
          class="ig-status ig-status-preview"
          data-testid="ig-status"
        >
          MATCH PREVIEW
        </span>
      </div>

      <div class="ig-teams">
        <!-- Home -->
        <div class="ig-team ig-team-home">
          <div
            class="ig-logo"
            :style="{ boxShadow: `0 0 48px ${homeColor}66` }"
          >
            <img
              v-if="homeLogoUrl"
              :src="homeLogoUrl"
              :alt="`${homeTeamName} logo`"
              class="ig-logo-img"
              crossorigin="anonymous"
            />
            <span v-else class="ig-logo-initials">{{ homeInitials }}</span>
          </div>
          <div class="ig-team-name" data-testid="ig-home-name">
            {{ homeTeamName }}
          </div>
        </div>

        <!-- Score / VS -->
        <div class="ig-score-block">
          <template v-if="mode === 'result'">
            <div class="ig-score" data-testid="ig-score">
              <span>{{ homeScore }}</span>
              <span class="ig-score-dash">–</span>
              <span>{{ awayScore }}</span>
            </div>
          </template>
          <template v-else>
            <div class="ig-vs" data-testid="ig-vs">VS</div>
            <div
              v-if="kickoffLabel"
              class="ig-kickoff"
              data-testid="ig-kickoff"
            >
              {{ kickoffLabel }}
            </div>
          </template>
        </div>

        <!-- Away -->
        <div class="ig-team ig-team-away">
          <div
            class="ig-logo"
            :style="{ boxShadow: `0 0 48px ${awayColor}66` }"
          >
            <img
              v-if="awayLogoUrl"
              :src="awayLogoUrl"
              :alt="`${awayTeamName} logo`"
              class="ig-logo-img"
              crossorigin="anonymous"
            />
            <span v-else class="ig-logo-initials">{{ awayInitials }}</span>
          </div>
          <div class="ig-team-name" data-testid="ig-away-name">
            {{ awayTeamName }}
          </div>
        </div>
      </div>

      <div class="ig-footer">
        <span class="ig-date" data-testid="ig-date">{{ dateLabel }}</span>
        <span class="ig-brand" data-testid="ig-brand">missingtable.com</span>
      </div>
    </div>
  </div>
</template>

<script>
import { computed, ref } from 'vue';

const initialsFor = name => {
  if (!name) return '?';
  return name
    .split(' ')
    .map(word => word[0])
    .filter(Boolean)
    .join('')
    .slice(0, 3)
    .toUpperCase();
};

export default {
  name: 'IgShareCard',
  props: {
    match: {
      type: Object,
      required: true,
    },
    photoSrc: {
      type: String,
      default: null,
    },
    // When the photoSrc is a remote URL we render with crossorigin="anonymous"
    // so html2canvas can read pixels. For local blob: URLs we omit the attribute
    // to avoid a needless preflight failure.
    photoIsCrossOrigin: {
      type: Boolean,
      default: false,
    },
    mode: {
      type: String,
      required: true,
      validator: v => ['preview', 'result'].includes(v),
    },
  },
  setup(props) {
    const root = ref(null);

    const homeTeamName = computed(() => props.match.home_team_name || '');
    const awayTeamName = computed(() => props.match.away_team_name || '');
    const homeLogoUrl = computed(
      () => props.match.home_team_club?.logo_url || null
    );
    const awayLogoUrl = computed(
      () => props.match.away_team_club?.logo_url || null
    );
    const homeColor = computed(
      () => props.match.home_team_club?.primary_color || '#3B82F6'
    );
    const awayColor = computed(
      () => props.match.away_team_club?.primary_color || '#EF4444'
    );
    const homeScore = computed(() => props.match.home_score ?? 0);
    const awayScore = computed(() => props.match.away_score ?? 0);
    const homeInitials = computed(() => initialsFor(homeTeamName.value));
    const awayInitials = computed(() => initialsFor(awayTeamName.value));

    const ageGroupLabel = computed(() => props.match.age_group_name || 'MATCH');

    const metaLabel = computed(() => {
      const parts = [];
      if (props.match.match_type_name) parts.push(props.match.match_type_name);
      if (props.match.division_name) parts.push(props.match.division_name);
      else if (props.match.season_name) parts.push(props.match.season_name);
      return parts.join(' · ').toUpperCase();
    });

    const dateLabel = computed(() => {
      const date = props.match.match_date;
      if (!date) return '';
      const d = new Date(date + 'T00:00:00');
      return d.toLocaleDateString('en-US', {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric',
      });
    });

    const kickoffLabel = computed(() => {
      const iso = props.match.scheduled_kickoff;
      if (!iso) return null;
      const d = new Date(iso);
      return d.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      });
    });

    const photoCrossOrigin = computed(() =>
      props.photoIsCrossOrigin ? 'anonymous' : null
    );

    return {
      root,
      homeTeamName,
      awayTeamName,
      homeLogoUrl,
      awayLogoUrl,
      homeColor,
      awayColor,
      homeScore,
      awayScore,
      homeInitials,
      awayInitials,
      ageGroupLabel,
      metaLabel,
      dateLabel,
      kickoffLabel,
      photoCrossOrigin,
    };
  },
};
</script>

<style scoped>
.ig-share-card {
  position: relative;
  width: 1080px;
  height: 1080px;
  overflow: hidden;
  background: #0f172a;
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue',
    Arial, sans-serif;
  color: #ffffff;
  isolation: isolate;
}

.ig-photo,
.ig-photo-fallback {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: 0;
}

.ig-photo-fallback {
  background:
    radial-gradient(
      circle at 30% 30%,
      rgba(59, 130, 246, 0.4),
      transparent 55%
    ),
    radial-gradient(
      circle at 70% 70%,
      rgba(239, 68, 68, 0.35),
      transparent 55%
    ),
    linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
}

.ig-photo-fallback-glow {
  position: absolute;
  inset: 0;
  background: radial-gradient(
    circle at center,
    rgba(255, 255, 255, 0.05),
    transparent 60%
  );
}

.ig-top-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 200px;
  padding: 48px 56px 0;
  background: linear-gradient(
    180deg,
    rgba(0, 0, 0, 0.7) 0%,
    rgba(0, 0, 0, 0) 100%
  );
  z-index: 1;
}

.ig-top-row {
  display: flex;
  align-items: center;
  gap: 24px;
}

.ig-chip {
  display: inline-block;
  padding: 12px 24px;
  border-radius: 999px;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.08em;
  background: rgba(255, 255, 255, 0.95);
  color: #0f172a;
}

.ig-chip-meta {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.9);
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.6);
}

.ig-bottom-overlay {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 0 56px 56px;
  display: flex;
  flex-direction: column;
  gap: 28px;
  background: linear-gradient(
    180deg,
    rgba(0, 0, 0, 0) 0%,
    rgba(0, 0, 0, 0.4) 35%,
    rgba(0, 0, 0, 0.85) 100%
  );
  padding-top: 260px;
  z-index: 1;
}

.ig-status-row {
  display: flex;
  justify-content: center;
}

.ig-status {
  display: inline-block;
  padding: 10px 28px;
  border-radius: 8px;
  font-size: 24px;
  font-weight: 800;
  letter-spacing: 0.2em;
}

.ig-status-final {
  background: #16a34a;
  color: #ffffff;
}

.ig-status-preview {
  background: rgba(255, 255, 255, 0.12);
  border: 2px solid rgba(255, 255, 255, 0.4);
  color: #ffffff;
}

.ig-teams {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 32px;
}

.ig-team {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  min-width: 0;
}

.ig-logo {
  width: 200px;
  height: 200px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.96);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.ig-logo-img {
  width: 88%;
  height: 88%;
  object-fit: contain;
}

.ig-logo-initials {
  font-size: 72px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: 0.04em;
}

.ig-team-name {
  font-size: 38px;
  font-weight: 700;
  text-align: center;
  line-height: 1.15;
  text-shadow: 0 2px 12px rgba(0, 0, 0, 0.8);
  word-break: break-word;
  max-width: 100%;
}

.ig-score-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  min-width: 240px;
}

.ig-score {
  display: flex;
  align-items: baseline;
  gap: 24px;
  font-size: 140px;
  font-weight: 900;
  line-height: 1;
  text-shadow:
    0 4px 24px rgba(0, 0, 0, 0.8),
    0 0 40px rgba(255, 255, 255, 0.15);
  font-variant-numeric: tabular-nums;
}

.ig-score-dash {
  font-size: 100px;
  opacity: 0.7;
}

.ig-vs {
  font-size: 110px;
  font-weight: 900;
  line-height: 1;
  letter-spacing: 0.04em;
  text-shadow: 0 4px 20px rgba(0, 0, 0, 0.8);
}

.ig-kickoff {
  font-size: 32px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.6);
}

.ig-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 26px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.95);
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.6);
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.18);
}

.ig-brand {
  letter-spacing: 0.05em;
}
</style>
