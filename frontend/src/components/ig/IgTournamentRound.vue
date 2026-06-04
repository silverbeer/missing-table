<template>
  <!--
    Tournament Round template (SB-32). Mirrors IgSplit but uses the
    tournament round name (QUARTERFINAL / SEMIFINAL / FINAL) as the hero
    wordmark. Photo half is on the left to differentiate from Split.
    Only shown when match.tournament_round is set.
  -->
  <div
    ref="root"
    class="ig-share-card ig-tournament-round"
    data-testid="ig-share-card"
    data-template="tournament-round"
    :data-mode="mode"
  >
    <!-- Photo half (left). background-image, not <img>, so html2canvas
         honors cover cropping (it stretches <img object-fit:cover>). -->
    <div class="photo-half">
      <div
        v-if="photoSrc"
        class="photo"
        data-testid="ig-photo"
        :style="{ backgroundImage: `url(${photoSrc})` }"
      ></div>
      <div v-else class="photo-fallback" data-testid="ig-photo-fallback"></div>
    </div>

    <div class="accent-stripe"></div>

    <!-- Brand panel (right) -->
    <div class="panel">
      <div class="panel-top">
        <div class="panel-top-row">
          <div class="panel-top-text">
            <span class="brand-mark" data-testid="ig-brand-top"
              >missingtable.com</span
            >
            <span
              v-if="tournamentName"
              class="tournament"
              data-testid="ig-tournament"
            >
              {{ tournamentName.toUpperCase() }}
            </span>
            <span v-if="tournamentGroup" class="group" data-testid="ig-group">
              {{ tournamentGroup.toUpperCase() }}
            </span>
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
        <h1 class="hero-title" data-testid="ig-status">
          {{ (tournamentRoundLabel || '').toUpperCase() }}
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

        <div class="connector">
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
  </div>
</template>

<script>
import { computed, ref, toRefs } from 'vue';
import { useIgShareData } from '@/composables/useIgShareData';
import MlsNextBadge from './MlsNextBadge.vue';
import IgScorers from './IgScorers.vue';

export default {
  name: 'IgTournamentRound',
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
    return { root, ...data, photoCrossOrigin };
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

.photo-half {
  width: 520px;
  flex-shrink: 0;
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

.accent-stripe {
  width: 8px;
  background: linear-gradient(180deg, #dc2626 0%, #b91c1c 100%);
  flex-shrink: 0;
}

.panel {
  flex: 1;
  position: relative;
  padding: 56px 48px 0;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(
      circle at 100% 0%,
      rgba(220, 38, 38, 0.18),
      transparent 55%
    ),
    linear-gradient(180deg, #0f172a 0%, #0a1224 100%);
}

.panel-top {
  margin-bottom: 24px;
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
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.7);
}

.tournament {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: #ffffff;
}

.group {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.2em;
  color: rgba(255, 255, 255, 0.75);
}

.hero {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.hero-title {
  font-size: 120px;
  font-weight: 900;
  line-height: 0.92;
  letter-spacing: -0.02em;
  margin: 0;
  text-transform: uppercase;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  /* Slight italic for that "playoff" feel without needing a custom font */
  font-style: italic;
}

.matchup {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
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
  width: 130px;
  height: 130px;
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
  font-size: 42px;
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

.connector {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 90px;
}

.vs,
.score {
  font-size: 52px;
  font-weight: 900;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.92);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.footer-band {
  background: #dc2626;
  margin: 0 -48px;
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

.footer-tagline {
  text-align: center;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.95);
}
</style>
