<template>
  <!--
    Stadium Scoreboard template (SB-32). No photo required. Echoes the
    existing inline MatchDetailView scoreboard at 1080×1080 with a
    branded missingtable.com top/bottom band. Best fallback when no
    action shot is available.
  -->
  <div
    ref="root"
    class="ig-share-card ig-stadium"
    data-testid="ig-share-card"
    data-template="stadium"
    :data-mode="mode"
  >
    <!-- Top brand band -->
    <div class="brand-band-top">
      <span class="brand-mark" data-testid="ig-brand-top"
        >missingtable.com</span
      >
      <MlsNextBadge v-if="isHomegrownLeague" class="brand-band-badge" />
      <img
        v-if="tournamentLogoUrl"
        :src="tournamentLogoUrl"
        class="tournament-logo"
        data-testid="ig-tournament-logo"
        alt=""
        crossorigin="anonymous"
      />
      <span class="meta" data-testid="ig-meta">{{ metaLabel }}</span>
    </div>

    <div class="stage">
      <!-- Status row -->
      <div class="status-row">
        <span class="age-chip" data-testid="ig-age-chip">{{
          ageGroupLabel
        }}</span>
        <span
          v-if="isResult"
          class="status status-final"
          data-testid="ig-status"
        >
          FINAL
        </span>
        <span v-else class="status status-preview" data-testid="ig-status">
          MATCH PREVIEW
        </span>
      </div>

      <!-- Scoreboard -->
      <div class="scoreboard">
        <div class="team-side">
          <div
            class="crest"
            :class="{ 'crest-filled': !homeLogoUrl }"
            :style="{ boxShadow: `0 0 64px ${homeColor}88` }"
          >
            <img
              v-if="homeLogoUrl"
              :src="homeLogoUrl"
              :alt="`${homeTeamName} logo`"
              class="crest-img"
              crossorigin="anonymous"
            />
            <span v-else class="crest-initials">{{ homeInitials }}</span>
          </div>
          <div class="team-name" data-testid="ig-home-name">
            {{ homeTeamName }}
          </div>
          <div class="team-tag">HOME</div>
        </div>

        <div class="center">
          <template v-if="isResult">
            <div class="score" data-testid="ig-score">
              <span>{{ homeScore }}</span>
              <span class="score-dash">–</span>
              <span>{{ awayScore }}</span>
            </div>
          </template>
          <template v-else>
            <div class="vs" data-testid="ig-vs">VS</div>
            <div v-if="kickoffLabel" class="kickoff" data-testid="ig-kickoff">
              {{ kickoffLabel }}
            </div>
          </template>
        </div>

        <div class="team-side">
          <div
            class="crest"
            :class="{ 'crest-filled': !awayLogoUrl }"
            :style="{ boxShadow: `0 0 64px ${awayColor}88` }"
          >
            <img
              v-if="awayLogoUrl"
              :src="awayLogoUrl"
              :alt="`${awayTeamName} logo`"
              class="crest-img"
              crossorigin="anonymous"
            />
            <span v-else class="crest-initials">{{ awayInitials }}</span>
          </div>
          <div class="team-name" data-testid="ig-away-name">
            {{ awayTeamName }}
          </div>
          <div class="team-tag">AWAY</div>
        </div>
      </div>

      <!-- Goal scorers (live-scored result only) -->
      <IgScorers
        v-if="isResult && hasScorers"
        :home="homeScorers"
        :away="awayScorers"
        :hat-tricks="hatTricks"
        size="lg"
      />

      <!-- Match details -->
      <div class="details">
        <div class="detail">
          <span class="detail-label">DATE</span>
          <span class="detail-value" data-testid="ig-date">
            {{ shortDateLabel }}
          </span>
        </div>
        <div v-if="kickoffLabel" class="detail">
          <span class="detail-label">KICKOFF</span>
          <span class="detail-value">{{ kickoffLabel }}</span>
        </div>
        <div class="detail">
          <span class="detail-label">AGE</span>
          <span class="detail-value">{{ ageGroupLabel }}</span>
        </div>
      </div>
    </div>

    <!-- Bottom brand band -->
    <div class="brand-band-bottom">
      <span class="handle" data-testid="ig-handle">@missingtable</span>
      <span class="footer-tagline" data-testid="ig-tagline">{{ tagline }}</span>
    </div>
  </div>
</template>

<script>
import { ref, toRefs } from 'vue';
import { useIgShareData } from '@/composables/useIgShareData';
import MlsNextBadge from './MlsNextBadge.vue';
import IgScorers from './IgScorers.vue';

export default {
  name: 'IgStadium',
  components: { MlsNextBadge, IgScorers },
  props: {
    match: { type: Object, required: true },
    // Photo is unused by this template but accepted so the dispatcher
    // can pass props uniformly.
    photoSrc: { type: String, default: null },
    photoIsCrossOrigin: { type: Boolean, default: false },
    events: { type: Array, default: () => [] },
    mode: {
      type: String,
      required: true,
      validator: v => ['preview', 'result'].includes(v),
    },
  },
  setup(props) {
    const root = ref(null);
    const { match, mode, events } = toRefs(props);
    const data = useIgShareData(match, mode, events);
    return { root, ...data };
  },
};
</script>

<style scoped>
.ig-share-card {
  position: relative;
  width: 1080px;
  height: 1080px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue',
    Arial, sans-serif;
  color: #ffffff;
  background:
    radial-gradient(
      circle at 50% 0%,
      rgba(59, 130, 246, 0.18),
      transparent 60%
    ),
    radial-gradient(
      circle at 50% 100%,
      rgba(220, 38, 38, 0.12),
      transparent 55%
    ),
    linear-gradient(180deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
  isolation: isolate;
}

.brand-band-top,
.brand-band-bottom {
  background: #dc2626;
  padding: 24px 56px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 800;
  letter-spacing: 0.06em;
  flex-shrink: 0;
}

.brand-mark {
  font-size: 26px;
}

.brand-band-badge {
  height: 84px;
  margin-left: auto;
  margin-right: 24px;
}

.tournament-logo {
  height: 84px;
  width: 84px;
  object-fit: contain;
  margin-right: 16px;
}

.meta {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: rgba(255, 255, 255, 0.95);
}

.handle {
  font-size: 26px;
}

.footer-tagline {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: rgba(255, 255, 255, 0.95);
}

.stage {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 48px 56px;
  gap: 40px;
}

.status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.age-chip {
  display: inline-flex;
  align-items: center;
  padding: 12px 24px;
  border-radius: 6px;
  background: #0f172a;
  color: #ffffff;
  font-size: 32px;
  font-weight: 900;
  letter-spacing: 0.08em;
  border: 2px solid #26d3e3;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.45);
}

.status {
  display: inline-block;
  padding: 10px 28px;
  border-radius: 8px;
  font-size: 24px;
  font-weight: 800;
  letter-spacing: 0.2em;
}

.status-final {
  background: #16a34a;
}

.status-preview {
  background: rgba(255, 255, 255, 0.1);
  border: 2px solid rgba(255, 255, 255, 0.4);
}

.scoreboard {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 24px;
}

.team-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
}

.crest {
  width: 240px;
  height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.crest-filled {
  background: rgba(255, 255, 255, 0.96);
  overflow: hidden;
}

.crest-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  filter: drop-shadow(0 6px 16px rgba(0, 0, 0, 0.5));
}

.crest-initials {
  font-size: 84px;
  font-weight: 800;
  color: #0f172a;
}

.team-name {
  font-size: 36px;
  font-weight: 800;
  text-align: center;
  line-height: 1.15;
  word-break: break-word;
}

.team-tag {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.3em;
  color: rgba(255, 255, 255, 0.65);
}

.center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  min-width: 240px;
}

.score {
  display: flex;
  align-items: baseline;
  gap: 24px;
  font-size: 160px;
  font-weight: 900;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 60px rgba(255, 255, 255, 0.18);
}

.score-dash {
  font-size: 110px;
  opacity: 0.65;
}

.vs {
  font-size: 130px;
  font-weight: 900;
  letter-spacing: 0.04em;
}

.kickoff {
  font-size: 32px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.92);
}

.details {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  padding-top: 24px;
  border-top: 2px solid rgba(255, 255, 255, 0.15);
}

.detail {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-label {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.25em;
  color: rgba(255, 255, 255, 0.55);
}

.detail-value {
  font-size: 24px;
  font-weight: 700;
}
</style>
