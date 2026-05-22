<template>
  <!--
    Brand Split template (SB-32). Left = navy brand panel with big
    wordmark + crests + date. Right = photo. Inspired by MLS Next Pro
    match-preview cards. The boundary between the two halves is rendered
    as an SVG `<path>` (not CSS clip-path) so html2canvas captures the
    torn-paper effect reliably in the downloaded PNG.
  -->
  <div
    ref="root"
    class="ig-share-card ig-split"
    data-testid="ig-share-card"
    data-template="split"
    :data-mode="mode"
  >
    <!-- Photo layer (full bleed, behind everything). background-image,
         not <img>, so html2canvas honors cover cropping. -->
    <div
      v-if="photoSrc"
      class="photo"
      data-testid="ig-photo"
      :style="{ backgroundImage: `url(${photoSrc})` }"
    ></div>
    <div v-else class="photo-fallback" data-testid="ig-photo-fallback"></div>

    <!-- SVG-rendered panel + footer shapes. html2canvas handles SVG
         paths reliably; CSS clip-path does NOT survive the capture. -->
    <svg
      class="panel-svg"
      viewBox="0 0 1080 1080"
      preserveAspectRatio="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        <linearGradient
          id="ig-split-grad"
          x1="0"
          y1="0"
          x2="0"
          y2="1080"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stop-color="#0f172a" />
          <stop offset="100%" stop-color="#0a1224" />
        </linearGradient>
        <radialGradient
          id="ig-split-glow"
          cx="0"
          cy="0"
          r="540"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stop-color="rgba(220, 38, 38, 0.18)" />
          <stop offset="100%" stop-color="rgba(220, 38, 38, 0)" />
        </radialGradient>
      </defs>
      <path :d="panelPath" fill="url(#ig-split-grad)" />
      <path :d="panelPath" fill="url(#ig-split-glow)" />
      <path :d="footerPath" fill="#dc2626" />
    </svg>

    <!-- Panel content sits on top of the SVG fills. No background. -->
    <div class="panel-content">
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
  </div>
</template>

<script>
import { computed, ref, toRefs } from 'vue';
import { useIgShareData, IG_SHARE_TAGLINE } from '@/composables/useIgShareData';
import MlsNextBadge from './MlsNextBadge.vue';

// Card height in SVG userSpace units (matches viewBox + .ig-share-card px).
const CARD_HEIGHT = 1080;
// Height of the red footer band (px).
const FOOTER_HEIGHT = 92;
const FOOTER_TOP = CARD_HEIGHT - FOOTER_HEIGHT;

export default {
  name: 'IgSplit',
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

    // Torn-paper edge points (deterministic). The base x lerps from
    // `topX` (wider at top) to `bottomX` (narrower at bottom), so the
    // tear leans diagonally. Pseudo-random jaggies (sin-based hash)
    // produce the same shape on every render.
    const tornEdgePoints = computed(() => {
      const topX = 600;
      const bottomX = 480;
      const hash = n => {
        const s = Math.sin(n) * 43758.5453;
        return s - Math.floor(s);
      };
      const points = [[topX, 0]];
      let y = 0;
      let i = 1;
      while (y < CARD_HEIGHT) {
        const step = 16 + hash(i * 7) * 22;
        y = Math.min(y + step, CARD_HEIGHT);
        if (y >= CARD_HEIGHT) break;
        const baseX = topX + ((bottomX - topX) * y) / CARD_HEIGHT;
        let xOffset = (hash(i * 13) - 0.5) * 28;
        if (hash(i * 17) > 0.72) {
          xOffset += (hash(i * 23) - 0.4) * 52;
        }
        points.push([baseX + xOffset, y]);
        i++;
      }
      points.push([bottomX, CARD_HEIGHT]);
      return points;
    });

    const panelPath = computed(() => {
      const pts = tornEdgePoints.value;
      const parts = ['M 0 0'];
      for (const [x, y] of pts) {
        parts.push(`L ${x.toFixed(1)} ${y.toFixed(1)}`);
      }
      parts.push(`L 0 ${CARD_HEIGHT}`);
      parts.push('Z');
      return parts.join(' ');
    });

    // Footer band: red strip at the bottom, bounded by the torn edge
    // (so it doesn't overrun into the photo half).
    const footerPath = computed(() => {
      const pts = tornEdgePoints.value;
      for (let idx = 0; idx < pts.length - 1; idx++) {
        const [x1, y1] = pts[idx];
        const [x2, y2] = pts[idx + 1];
        if (y1 <= FOOTER_TOP && y2 >= FOOTER_TOP) {
          const t = y2 === y1 ? 0 : (FOOTER_TOP - y1) / (y2 - y1);
          const startX = x1 + (x2 - x1) * t;
          const parts = [
            `M 0 ${FOOTER_TOP}`,
            `L ${startX.toFixed(1)} ${FOOTER_TOP}`,
          ];
          for (let j = idx + 1; j < pts.length; j++) {
            parts.push(`L ${pts[j][0].toFixed(1)} ${pts[j][1].toFixed(1)}`);
          }
          parts.push(`L 0 ${CARD_HEIGHT}`);
          parts.push('Z');
          return parts.join(' ');
        }
      }
      return '';
    });

    return {
      root,
      ...data,
      photoCrossOrigin,
      tagline: IG_SHARE_TAGLINE,
      panelPath,
      footerPath,
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

.panel-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 2;
  pointer-events: none;
}

.panel-content {
  position: absolute;
  top: 0;
  left: 0;
  width: 580px;
  height: 100%;
  z-index: 3;
  /* Right padding clears the diagonal torn-edge (top ~600, bottom ~480)
     so content stays within the visible polygon at every y. The bottom
     padding is 0 because the footer-band is absolutely positioned. */
  padding: 56px 140px 0 48px;
  display: flex;
  flex-direction: column;
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
  gap: 16px;
}

.hero-eyebrow {
  display: inline-block;
  align-self: flex-start;
  /* Asymmetric padding compensates for the trailing letter-spacing so
     the label (e.g. "U14") looks optically centered inside the chip. */
  padding: 8px 12px 8px 20px;
  background: #dc2626;
  color: #ffffff;
  font-size: 24px;
  font-weight: 800;
  letter-spacing: 0.14em;
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
  color: #ffffff;
  text-shadow:
    0 2px 0 rgba(0, 0, 0, 0.25),
    0 6px 24px rgba(0, 0, 0, 0.55);
}

.matchup {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 28px;
  margin-top: 48px;
  margin-bottom: 32px;
  padding-right: 12px;
}

.crest-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
  flex: 1;
  min-width: 0;
}

.crest {
  width: 128px;
  height: 128px;
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
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
  text-align: center;
  word-break: break-word;
  max-width: 100%;
}

.vs-block {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 84px;
  /* Match the crest height so VS sits aligned with the badges. */
  height: 128px;
}

.vs {
  font-family:
    Impact, 'Haettenschweiler', 'Arial Narrow Bold', 'Bebas Neue', 'Oswald',
    sans-serif;
  font-style: italic;
  font-size: 78px;
  font-weight: 900;
  letter-spacing: -0.02em;
  color: #dc2626;
  text-shadow:
    0 2px 0 rgba(0, 0, 0, 0.3),
    0 6px 18px rgba(0, 0, 0, 0.55);
  transform: skewX(-6deg);
  line-height: 1;
}

.score {
  font-family:
    Impact, 'Haettenschweiler', 'Arial Narrow Bold', 'Bebas Neue', 'Oswald',
    sans-serif;
  font-style: italic;
  font-size: 72px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  color: #ffffff;
  white-space: nowrap;
  text-shadow:
    0 2px 0 rgba(0, 0, 0, 0.3),
    0 6px 18px rgba(0, 0, 0, 0.55);
  transform: skewX(-6deg);
}

.footer-band {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 92px;
  padding: 18px 140px 18px 48px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  color: #ffffff;
  font-weight: 700;
  letter-spacing: 0.04em;
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
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.95);
}
</style>
