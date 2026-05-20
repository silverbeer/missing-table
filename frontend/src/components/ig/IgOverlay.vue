<template>
  <!--
    Photo Overlay template (SB-32). Photo full-bleed, text on dark
    gradient overlays. Best for hero action shots.
  -->
  <div
    ref="root"
    class="ig-share-card ig-overlay"
    data-testid="ig-share-card"
    data-template="overlay"
    :data-mode="mode"
  >
    <!-- Use background-image (not <img>) so html2canvas honors cover
         cropping; <img object-fit:cover> is rendered as fill by the
         library, stretching portrait photos. -->
    <div
      v-if="photoSrc"
      class="ig-photo"
      data-testid="ig-photo"
      :style="{ backgroundImage: `url(${photoSrc})` }"
    ></div>
    <div v-else class="ig-photo-fallback" data-testid="ig-photo-fallback">
      <div class="ig-photo-fallback-glow"></div>
      <!-- Centered watermark so the no-photo state doesn't look empty.
           Stylized soccer ball + wordmark, both heavily faded. -->
      <svg
        class="ig-photo-fallback-ball"
        viewBox="0 0 200 200"
        aria-hidden="true"
      >
        <circle
          cx="100"
          cy="100"
          r="92"
          fill="none"
          stroke="#ffffff"
          stroke-width="3"
        />
        <polygon points="100,42 124,60 116,90 84,90 76,60" fill="#ffffff" />
        <polygon
          points="100,158 124,140 116,110 84,110 76,140"
          fill="#ffffff"
          opacity="0.6"
        />
        <polygon
          points="36,86 60,68 76,90 64,118 40,114"
          fill="#ffffff"
          opacity="0.6"
        />
        <polygon
          points="164,86 140,68 124,90 136,118 160,114"
          fill="#ffffff"
          opacity="0.6"
        />
        <line
          x1="100"
          y1="42"
          x2="100"
          y2="14"
          stroke="#ffffff"
          stroke-width="2"
        />
        <line
          x1="100"
          y1="158"
          x2="100"
          y2="186"
          stroke="#ffffff"
          stroke-width="2"
        />
        <line
          x1="36"
          y1="86"
          x2="14"
          y2="70"
          stroke="#ffffff"
          stroke-width="2"
        />
        <line
          x1="164"
          y1="86"
          x2="186"
          y2="70"
          stroke="#ffffff"
          stroke-width="2"
        />
      </svg>
      <div class="ig-photo-fallback-brand">missingtable.com</div>
    </div>

    <div class="ig-top-overlay">
      <div class="ig-top-row">
        <span class="ig-chip ig-chip-age" data-testid="ig-age-chip">
          {{ ageGroupLabel }}
        </span>
        <span class="ig-chip-meta" data-testid="ig-meta">
          {{ metaLabel }}
        </span>
        <MlsNextBadge v-if="isHomegrownLeague" class="ig-mls-badge" />
      </div>
    </div>

    <div class="ig-bottom-overlay">
      <div class="ig-status-row">
        <span
          v-if="isResult"
          class="ig-status ig-status-final"
          data-testid="ig-status"
        >
          <span class="ig-status-text">FINAL</span>
        </span>
        <span
          v-else
          class="ig-status ig-status-preview"
          data-testid="ig-status"
        >
          <span class="ig-status-text">MATCH PREVIEW</span>
        </span>
      </div>

      <div class="ig-teams">
        <div class="ig-team ig-team-home">
          <div
            class="ig-logo"
            :class="{ 'ig-logo-filled': !homeLogoUrl }"
            :style="{ boxShadow: `0 0 56px ${homeColor}88` }"
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

        <div class="ig-score-block">
          <template v-if="isResult">
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

        <div class="ig-team ig-team-away">
          <div
            class="ig-logo"
            :class="{ 'ig-logo-filled': !awayLogoUrl }"
            :style="{ boxShadow: `0 0 56px ${awayColor}88` }"
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
      <div class="ig-tagline" data-testid="ig-tagline">{{ tagline }}</div>
    </div>
  </div>
</template>

<script>
import { computed, ref, toRefs } from 'vue';
import { useIgShareData, IG_SHARE_TAGLINE } from '@/composables/useIgShareData';
import MlsNextBadge from './MlsNextBadge.vue';

export default {
  name: 'IgOverlay',
  components: { MlsNextBadge },
  props: {
    match: { type: Object, required: true },
    photoSrc: { type: String, default: null },
    photoIsCrossOrigin: { type: Boolean, default: false },
    mode: {
      type: String,
      required: true,
      validator: v => ['preview', 'result'].includes(v),
    },
  },
  setup(props) {
    const root = ref(null);
    const { match, mode } = toRefs(props);
    const data = useIgShareData(match, mode);
    const photoCrossOrigin = computed(() =>
      props.photoIsCrossOrigin ? 'anonymous' : null
    );
    return { root, ...data, photoCrossOrigin, tagline: IG_SHARE_TAGLINE };
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
  z-index: 0;
}

.ig-photo {
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
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

.ig-photo-fallback-ball {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -55%);
  width: 420px;
  height: 420px;
  opacity: 0.1;
}

.ig-photo-fallback-brand {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, 220px);
  font-size: 48px;
  font-weight: 900;
  letter-spacing: 0.18em;
  color: rgba(255, 255, 255, 0.18);
  text-transform: uppercase;
  white-space: nowrap;
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

.ig-mls-badge {
  margin-left: auto;
  height: 108px;
}

.ig-chip {
  display: inline-flex;
  align-items: center;
  padding: 12px 22px;
  border-radius: 6px;
  font-size: 32px;
  font-weight: 900;
  letter-spacing: 0.08em;
  background: #0f172a;
  color: #ffffff;
  border: 2px solid #26d3e3;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.6);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.45);
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
  padding: 260px 56px 56px;
  display: flex;
  flex-direction: column;
  gap: 28px;
  background: linear-gradient(
    180deg,
    rgba(0, 0, 0, 0) 0%,
    rgba(0, 0, 0, 0.4) 35%,
    rgba(0, 0, 0, 0.85) 100%
  );
  z-index: 1;
}

.ig-status-row {
  display: flex;
  justify-content: center;
}

.ig-status {
  display: inline-flex;
  align-items: stretch;
  font-size: 30px;
  font-weight: 900;
  font-style: italic;
  letter-spacing: 0.18em;
  color: #ffffff;
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.55);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.55);
  border-radius: 4px;
  overflow: hidden;
  /* Slight skew gives a broadcast lower-third feel. The inner span
     un-skews so the text stays upright. */
  transform: skewX(-8deg);
}

.ig-status::before {
  content: '';
  width: 10px;
  background: #26d3e3;
  flex-shrink: 0;
}

.ig-status-text {
  display: inline-flex;
  align-items: center;
  padding: 14px 30px 14px 22px;
  transform: skewX(8deg);
}

.ig-status-final {
  background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
}

.ig-status-preview {
  background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%);
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
  width: 220px;
  height: 220px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ig-logo-filled {
  background: rgba(255, 255, 255, 0.96);
  overflow: hidden;
}

.ig-logo-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  filter: drop-shadow(0 6px 16px rgba(0, 0, 0, 0.45));
}

.ig-logo-initials {
  font-size: 78px;
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

.ig-tagline {
  text-align: center;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: rgba(255, 255, 255, 0.92);
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.7);
  padding-top: 4px;
}
</style>
