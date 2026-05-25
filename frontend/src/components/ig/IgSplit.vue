<template>
  <!--
    Brand Split template (SB-32). Left = solid navy brand panel with big
    wordmark + crests + date. Right = photo. Inspired by MLS Next Pro
    match-preview cards.
  -->
  <div
    ref="root"
    class="ig-share-card ig-split"
    data-testid="ig-share-card"
    data-template="split"
    :data-mode="mode"
  >
    <!-- Brand panel. The torn-paper right edge is drawn by an inline SVG
         layered behind the content (clip-path is ignored by html2canvas
         so we paint the shape instead). The .panel container itself
         stays a clean absolutely-positioned flex column. -->
    <div class="panel">
      <svg
        class="panel-bg-svg"
        viewBox="0 0 620 1080"
        preserveAspectRatio="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <path :d="panelPath" fill="#0a1224" />
        <path :d="panelPath" fill="#0f172a" :opacity="0.6" />
      </svg>
      <div class="panel-top">
        <div class="panel-top-row">
          <div class="panel-top-text">
            <span class="brand-mark" data-testid="ig-brand-top"
              >missingtable.com</span
            >
            <span class="meta" data-testid="ig-meta">{{ metaLabel }}</span>
          </div>
          <MlsNextBadge v-if="isHomegrownLeague" class="mls-badge" />
        </div>
      </div>

      <div class="hero">
        <span class="hero-eyebrow" data-testid="ig-eyebrow">
          {{ ageGroupLabel }}
        </span>
        <h1 class="hero-title" data-testid="ig-status">
          <template v-if="isResult">FULL TIME</template>
          <template v-else>MATCH<br />PREVIEW</template>
        </h1>
      </div>

      <div class="matchup">
        <div class="crest-block">
          <div
            class="crest"
            :class="{ 'crest-filled': !homeLogoUrl }"
            :style="{ boxShadow: `0 0 36px ${homeColor}aa` }"
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
        </div>

        <div class="vs-block">
          <template v-if="isResult">
            <div class="score" data-testid="ig-score">
              {{ homeScore }} – {{ awayScore }}
            </div>
          </template>
          <template v-else>
            <div class="vs" data-testid="ig-vs">VS</div>
          </template>
        </div>

        <div class="crest-block">
          <div
            class="crest"
            :class="{ 'crest-filled': !awayLogoUrl }"
            :style="{ boxShadow: `0 0 36px ${awayColor}aa` }"
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
        </div>
      </div>

      <!-- Goal scorers (live-scored result only) -->
      <div v-if="isResult && hasScorers" class="panel-scorers">
        <IgScorers
          :home="homeScorers"
          :away="awayScorers"
          :hat-tricks="hatTricks"
          size="sm"
        />
      </div>

      <div class="footer-band">
        <div class="footer-row">
          <div class="footer-date" data-testid="ig-date">
            {{ shortDateLabel
            }}<span v-if="kickoffLabel"> · {{ kickoffLabel }}</span>
          </div>
          <div class="footer-handle" data-testid="ig-handle">@missingtable</div>
        </div>
        <div class="footer-tagline" data-testid="ig-tagline">
          {{ tagline }}
        </div>
      </div>
    </div>

    <!-- Photo layer (full bleed, behind panel). background-image, not <img>,
         so html2canvas honors cover cropping. -->
    <div
      v-if="photoSrc"
      class="photo"
      data-testid="ig-photo"
      :style="{ backgroundImage: `url(${photoSrc})` }"
    ></div>
    <div v-else class="photo-fallback" data-testid="ig-photo-fallback"></div>
  </div>
</template>

<script>
import { computed, ref, toRefs } from 'vue';
import { useIgShareData } from '@/composables/useIgShareData';
import MlsNextBadge from './MlsNextBadge.vue';
import IgScorers from './IgScorers.vue';

export default {
  name: 'IgSplit',
  components: { MlsNextBadge, IgScorers },
  props: {
    match: { type: Object, required: true },
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
    const photoCrossOrigin = computed(() =>
      props.photoIsCrossOrigin ? 'anonymous' : null
    );

    // SVG path describing the torn panel shape. The base x lerps from
    // `topX` to `bottomX` so the tear leans diagonally (panel is wider
    // at the top, narrower at the bottom). Deterministic pseudo-random
    // jaggies in between. The path is filled inside an inline <svg>
    // layered behind the panel content; using SVG (not CSS clip-path)
    // because html2canvas 1.4.1 ignores clip-path: polygon() during
    // capture, leaving the PNG with a straight edge.
    const panelPath = computed(() => {
      const topX = 600;
      const bottomX = 480;
      const height = 1080;
      const hash = n => {
        const s = Math.sin(n) * 43758.5453;
        return s - Math.floor(s);
      };
      const parts = ['M 0 0', `L ${topX} 0`];
      let y = 0;
      let i = 1;
      while (y < height) {
        const step = 16 + hash(i * 7) * 22;
        y = Math.min(y + step, height);
        if (y >= height) break;
        const baseX = topX + ((bottomX - topX) * y) / height;
        let xOffset = (hash(i * 13) - 0.5) * 28;
        if (hash(i * 17) > 0.72) {
          xOffset += (hash(i * 23) - 0.4) * 52;
        }
        const x = baseX + xOffset;
        parts.push(`L ${x.toFixed(1)} ${y.toFixed(1)}`);
        i++;
      }
      parts.push(`L ${bottomX} ${height}`);
      parts.push(`L 0 ${height}`);
      parts.push('Z');
      return parts.join(' ');
    });

    return {
      root,
      ...data,
      photoCrossOrigin,
      panelPath,
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
  background: #0a1224;
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue',
    Arial, sans-serif;
  color: #ffffff;
  isolation: isolate;
}

.panel {
  position: absolute;
  top: 0;
  left: 0;
  width: 620px;
  height: 100%;
  z-index: 2;
  /* Right padding clears the diagonal torn-edge (top ~600, bottom ~480)
     so content stays inside the visible shape at every y. */
  padding: 56px 140px 48px 48px;
  display: flex;
  flex-direction: column;
  /* No CSS background — the inline SVG below paints the torn-shape fill
     so the same shape shows up in both the live preview AND the
     html2canvas-rendered PNG. */
  background: transparent;
}

.panel-bg-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

/* Position the panel's content blocks so they paint above the absolutely
   positioned SVG background. Without an explicit z-index, the in-flow
   children would still paint above the abs SVG in most browsers, but
   html2canvas can be order-sensitive — being explicit keeps both
   renderers agreeing. */
.panel-top,
.hero,
.matchup,
.footer-band {
  position: relative;
  z-index: 1;
}

.panel-top {
  margin-bottom: 32px;
}

.panel-top-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.panel-top-text {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.mls-badge {
  height: 88px;
  flex-shrink: 0;
}

.brand-mark {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #ffffff;
}

.meta {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.18em;
  color: rgba(255, 255, 255, 0.75);
}

.hero {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 12px;
}

.hero-eyebrow {
  display: inline-block;
  align-self: flex-start;
  padding: 8px 18px;
  background: #dc2626;
  color: #ffffff;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 0.16em;
  border-radius: 4px;
}

.hero-title {
  font-size: 116px;
  font-weight: 900;
  line-height: 0.88;
  letter-spacing: -0.01em;
  margin: 0;
  text-transform: uppercase;
  font-family:
    Impact, 'Haettenschweiler', 'Arial Narrow Bold', 'Bebas Neue', 'Oswald',
    sans-serif;
  font-style: italic;
  transform: skewX(-4deg);
  transform-origin: left center;
  /* Solid white + layered shadow for depth. Avoid background-clip:text;
     html2canvas renders that as transparent in the downloaded PNG. */
  color: #ffffff;
  text-shadow:
    0 2px 0 rgba(0, 0, 0, 0.25),
    0 6px 24px rgba(0, 0, 0, 0.55);
}

.matchup {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 32px;
  margin-bottom: 32px;
}

.panel-scorers {
  position: relative;
  z-index: 1;
  margin-bottom: 28px;
}

.crest-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.crest {
  width: 120px;
  height: 120px;
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
  filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.5));
}

.crest-initials {
  font-size: 40px;
  font-weight: 800;
  color: #0f172a;
}

.team-name {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.15;
  text-align: center;
  word-break: break-word;
  max-width: 100%;
}

.vs-block {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 80px;
}

.vs {
  font-size: 56px;
  font-weight: 900;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.92);
}

.score {
  font-size: 56px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  color: #ffffff;
  white-space: nowrap;
}

.footer-band {
  /* Subtle gradient + warm inner highlight reads more polished than a
     flat fill. Diagonal so the right side (under the torn-paper crop)
     stays a touch brighter and catches the eye. */
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 55%, #b91c1c 100%);
  /* Inset from the panel edges so the rounded corners are visible. The
     right inset stays small because the torn-paper SVG crops further
     in; the left/bottom insets are the visible breathing room. */
  margin: 24px -116px -24px -24px;
  padding: 18px 124px 18px 28px;
  border-radius: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #ffffff;
  font-weight: 700;
  letter-spacing: 0.04em;
  /* Soft drop shadow + 1px top inner highlight = depth without
     ornament. html2canvas handles both. */
  box-shadow:
    0 10px 24px rgba(0, 0, 0, 0.28),
    inset 0 1px 0 rgba(255, 255, 255, 0.22);
}

.footer-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 22px;
}

.footer-date {
  text-transform: uppercase;
}

.footer-handle {
  font-size: 22px;
}

.footer-tagline {
  text-align: center;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.95);
}

.photo,
.photo-fallback {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
}

.photo {
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
}

.photo-fallback {
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
</style>
