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
    <!-- Brand panel -->
    <div class="panel">
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

    <!-- Red accent stripe between halves -->
    <div class="accent-stripe"></div>

    <!-- Photo half. background-image, not <img>, so html2canvas honors
         cover cropping (it stretches <img object-fit:cover>). -->
    <div class="photo-half">
      <div
        v-if="photoSrc"
        class="photo"
        data-testid="ig-photo"
        :style="{ backgroundImage: `url(${photoSrc})` }"
      ></div>
      <div v-else class="photo-fallback" data-testid="ig-photo-fallback"></div>
    </div>
  </div>
</template>

<script>
import { computed, ref, toRefs } from 'vue';
import { useIgShareData, IG_SHARE_TAGLINE } from '@/composables/useIgShareData';
import MlsNextBadge from './MlsNextBadge.vue';

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
  display: flex;
  background: #0a1224;
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue',
    Arial, sans-serif;
  color: #ffffff;
  isolation: isolate;
}

.panel {
  width: 520px;
  flex-shrink: 0;
  position: relative;
  padding: 56px 48px 48px;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(circle at 0% 0%, rgba(220, 38, 38, 0.18), transparent 55%),
    linear-gradient(180deg, #0f172a 0%, #0a1224 100%);
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
  height: 56px;
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
  font-size: 124px;
  font-weight: 900;
  line-height: 0.92;
  letter-spacing: -0.02em;
  margin: 0;
  text-transform: uppercase;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}

.matchup {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 32px;
  margin-bottom: 32px;
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
  background: #dc2626;
  margin: 0 -48px -48px;
  padding: 18px 48px;
  display: flex;
  flex-direction: column;
  gap: 6px;
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
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.95);
}

.accent-stripe {
  width: 8px;
  background: linear-gradient(180deg, #dc2626 0%, #b91c1c 100%);
  flex-shrink: 0;
}

.photo-half {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.photo,
.photo-fallback {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
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
