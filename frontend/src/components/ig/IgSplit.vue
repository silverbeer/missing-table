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
        <!-- Same tear, drawn twice: the accent copy sits a few px to the
             right so it peeks out along the rip like colored paper
             backing the torn sheet. Cheaper and sharper than a second
             generated path, and it keeps the two edges perfectly
             congruent. -->
        <path
          :d="panelPath"
          :fill="accentColor"
          transform="translate(7,0)"
          :opacity="0.9"
        />
        <path :d="panelPath" fill="#0B0B0D" />
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
          <!-- White chip + background-image (not <img>) so dark logos stay
               legible and html2canvas renders contain correctly — see
               [[feedback-html2canvas-object-fit]]. -->
          <div v-if="tournamentLogoUrl" class="tournament-logo">
            <div
              class="tournament-logo-img"
              data-testid="ig-tournament-logo"
              :style="{ backgroundImage: `url(${tournamentLogoUrl})` }"
            ></div>
          </div>
        </div>
      </div>

      <div class="hero">
        <span
          class="hero-eyebrow"
          data-testid="ig-eyebrow"
          :style="{ background: accentColor, color: accentTextColor }"
        >
          {{ ageGroupLabel }}
        </span>
        <h1 class="hero-title" data-testid="ig-status">
          <template v-if="isResult">FULL TIME</template>
          <template v-else>MATCH<br />PREVIEW</template>
        </h1>
      </div>

      <!-- Stacked home / VS / away. Three rows rather than a side-by-side
           trio: the panel is now too narrow for two team names abreast,
           and stacking lets each name run at a readable size instead of
           wrapping into a column an inch wide. -->
      <div class="matchup">
        <div class="team-row">
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

        <div class="vs-row">
          <template v-if="isResult">
            <div class="score" data-testid="ig-score">
              {{ homeScore }} – {{ awayScore }}
            </div>
          </template>
          <template v-else>
            <div class="vs" data-testid="ig-vs" :style="{ color: accentColor }">
              VS
            </div>
          </template>
          <div class="vs-rule" :style="{ background: accentColor }"></div>
        </div>

        <div class="team-row">
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

      <div
        class="footer-band"
        :style="{ background: accentColor, color: accentTextColor }"
      >
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
      // Strong lean: the panel gives up ~half its width by the bottom so
      // the photo opens out toward the lower right, where the action in
      // a match photo usually sits (feet, ball). A gentler angle wasted
      // the frame on flat panel.
      const topX = 600;
      const bottomX = 250;
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
  /* Neutral near-black rather than navy, so club accents read as the
     club's color instead of shifting blue against a blue ground. */
  background: #0b0b0d;
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
  width: 540px;
  height: 100%;
  z-index: 2;
  /* Right padding clears the diagonal torn edge so content stays inside
     the visible shape at every y. The tear now leans hard (600 -> 250 in
     the 620-wide path space), so the bottom of the panel is much
     narrower than the top — the footer band handles that with its own
     negative right margin rather than padding the whole column for the
     worst case, which would strand the headline in a thin gutter. */
  padding: 56px 96px 48px 48px;
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

.tournament-logo {
  height: 88px;
  width: 88px;
  flex-shrink: 0;
  margin-left: 8px;
  padding: 8px;
  box-sizing: border-box;
  background: #ffffff;
  border-radius: 12px;
}

.tournament-logo-img {
  width: 100%;
  height: 100%;
  background-size: contain;
  background-position: center;
  background-repeat: no-repeat;
}

.brand-mark {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #ffffff;
}

.meta {
  /* Tracked in a touch from the old 18px/0.18em so the longest real
     label — "PRESEASON FRIENDLY · 2026-2027" — stays on one line in the
     narrowed panel. */
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.12em;
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
  /* Sized to fit the narrowed panel's content width without crossing the
     torn edge. Anton is condensed, so this still reads far larger than
     the old 116px Inter did. */
  font-size: 88px;
  /* Anton ships a single 400 weight. Asking for 900 here would make the
     browser synthesise a fake bold on top of an already-heavy face. */
  font-weight: 400;
  line-height: 0.88;
  letter-spacing: 0.005em;
  margin: 0;
  text-transform: uppercase;
  font-family: Anton, 'Arial Narrow Bold', sans-serif;
  /* No font-style: italic and no skewX(). Anton has no italic cut, so
     both were synthesising a slant — and stacking them applied it
     twice. A real condensed face upright reads better than a faked
     oblique. */
  /* Solid white + layered shadow for depth. Avoid background-clip:text;
     html2canvas renders that as transparent in the downloaded PNG. */
  color: #ffffff;
  text-shadow:
    0 2px 0 rgba(0, 0, 0, 0.25),
    0 6px 24px rgba(0, 0, 0, 0.55);
}

.matchup {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
  margin-top: 28px;
  margin-bottom: 28px;
}

.team-row {
  display: flex;
  align-items: center;
  gap: 18px;
  min-width: 0;
}

.vs-row {
  display: flex;
  align-items: center;
  gap: 16px;
  /* Sit the VS under the crest lane so the three rows read as one
     stack rather than three unrelated lines. */
  padding-left: 22px;
}

.vs-rule {
  height: 3px;
  flex: 1;
  border-radius: 2px;
  opacity: 0.55;
}

.panel-scorers {
  position: relative;
  z-index: 1;
  margin-bottom: 28px;
}

.crest {
  width: 86px;
  height: 86px;
  flex-shrink: 0;
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
  font-family: Anton, 'Arial Narrow Bold', sans-serif;
  font-weight: 400;
  font-size: 40px;
  line-height: 1.02;
  letter-spacing: 0.01em;
  text-transform: uppercase;
  min-width: 0;
  word-break: break-word;
}

.vs {
  /* Anton at a big optical size, in the accent, is the "cooler VS" —
     a condensed display cut carrying color, rather than bold Inter. */
  font-family: Anton, 'Arial Narrow Bold', sans-serif;
  font-weight: 400;
  font-size: 46px;
  line-height: 1;
  letter-spacing: 0.06em;
  flex-shrink: 0;
}

.score {
  font-size: 56px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  color: #ffffff;
  white-space: nowrap;
}

.footer-band {
  /* Flat accent, set inline from accentColor so the band tracks the
     club's brand color. Previously a fixed red gradient, which both
     ignored the clubs and dated the card. */
  /* Runs out past the panel as a banner across the photo. The tear now
     ends far to the left at the bottom, so the band no longer has to
     reserve a wide right padding to stay inside the torn shape — it
     deliberately overhangs instead, which also stops the date and handle
     wrapping in a narrow column. */
  margin: 24px -190px -24px -24px;
  padding: 18px 32px;
  border-radius: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-weight: 700;
  letter-spacing: 0.04em;
  /* Soft drop shadow for lift. The inset white highlight went with the
     gradient — on a flat fill it just muddies the top edge. */
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.28);
}

.footer-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 20px;
  font-size: 21px;
}

.footer-date {
  text-transform: uppercase;
  white-space: nowrap;
}

.footer-handle {
  font-size: 21px;
  white-space: nowrap;
}

.footer-tagline {
  text-align: center;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.04em;
  /* Inherit the band's accent-aware text color rather than assuming
     white — the band is light when the accent is light. */
  color: inherit;
  opacity: 0.9;
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
