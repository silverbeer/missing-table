<template>
  <!--
    Match of the Week share card (SB-1010).

    Its own template rather than a badge bolted onto the other four. MOTW is a
    weekly series, and a series wants one recognisable frame — someone should
    know what this is from the thumbnail, before reading a word of it.

    Amber is constant here even though every other template takes its accent
    from the clubs. The colour IS the label: change it per club and the series
    stops looking like a series. Club colour still appears, as the bar under
    each name.
  -->
  <div
    ref="root"
    class="ig-share-card ig-motw"
    data-testid="ig-share-card"
    data-template="motw"
    :data-mode="mode"
  >
    <!-- Oversized watermark. Sits behind everything, clipped by the card, and
         does the work a background photo would if we had one. -->
    <div class="watermark" aria-hidden="true">MOTW</div>

    <header class="ribbon">
      <span class="ribbon-mark">MT</span>
      <span class="ribbon-text">Match of the Week</span>
      <span class="ribbon-diamond" aria-hidden="true">◆</span>
    </header>

    <div class="stage">
      <div class="meta-row">
        <span class="age-chip" data-testid="ig-age-chip">{{
          ageGroupLabel
        }}</span>
        <span class="meta" data-testid="ig-meta">{{ metaLabel }}</span>
        <MlsNextBadge v-if="isHomegrownLeague" class="mls-badge" />
      </div>

      <!-- Names stack instead of facing each other across a VS. At 1080 wide
           a side-by-side pair has to shrink to fit two long club names;
           stacked, both can stay big. -->
      <div class="fixture">
        <div class="team">
          <div class="team-head">
            <div class="crest" :class="{ 'crest-filled': !homeLogoUrl }">
              <img
                v-if="homeLogoUrl"
                :src="homeLogoUrl"
                :alt="`${homeTeamName} logo`"
                class="crest-img"
                crossorigin="anonymous"
              />
              <span v-else class="crest-initials">{{ homeInitials }}</span>
            </div>
            <span class="team-name" data-testid="ig-home-name">{{
              homeTeamName
            }}</span>
            <span
              v-if="isResult"
              class="team-score"
              data-testid="ig-home-score"
            >
              {{ homeScore }}
            </span>
          </div>
          <div class="team-bar" :style="{ background: homeColor }"></div>
        </div>

        <div class="separator">
          <span v-if="isResult" data-testid="ig-status">FULL TIME</span>
          <span v-else data-testid="ig-vs">VS</span>
        </div>

        <div class="team">
          <div class="team-head">
            <div class="crest" :class="{ 'crest-filled': !awayLogoUrl }">
              <img
                v-if="awayLogoUrl"
                :src="awayLogoUrl"
                :alt="`${awayTeamName} logo`"
                class="crest-img"
                crossorigin="anonymous"
              />
              <span v-else class="crest-initials">{{ awayInitials }}</span>
            </div>
            <span class="team-name" data-testid="ig-away-name">{{
              awayTeamName
            }}</span>
            <span
              v-if="isResult"
              class="team-score"
              data-testid="ig-away-score"
            >
              {{ awayScore }}
            </span>
          </div>
          <div class="team-bar" :style="{ background: awayColor }"></div>
        </div>
      </div>

      <!-- The editorial line, when the admin wrote one. No blurb means no
           empty quote marks sitting in the middle of the card. -->
      <p v-if="blurb" class="blurb" data-testid="ig-motw-blurb">{{ blurb }}</p>

      <IgScorers
        v-if="isResult && hasScorers"
        :home="homeScorers"
        :away="awayScorers"
        :hat-tricks="hatTricks"
        size="md"
      />

      <div class="when" data-testid="ig-when">
        <span>{{ shortDateLabel }}</span>
        <span v-if="kickoffLabel" class="when-dot" aria-hidden="true">·</span>
        <span v-if="kickoffLabel">{{ kickoffLabel }}</span>
      </div>
    </div>

    <footer class="footer">
      <span class="handle" data-testid="ig-handle">@missingtable</span>
      <span class="footer-tagline" data-testid="ig-tagline">{{ tagline }}</span>
    </footer>
  </div>
</template>

<script>
import { ref, toRefs } from 'vue';
import { useIgShareData } from '@/composables/useIgShareData';
import IgScorers from './IgScorers.vue';
import MlsNextBadge from './MlsNextBadge.vue';

export default {
  name: 'IgMotw',
  components: { IgScorers, MlsNextBadge },
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
    // The admin's editorial line, carried through from the pick.
    blurb: { type: String, default: null },
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
      circle at 12% 6%,
      rgba(245, 158, 11, 0.22),
      transparent 55%
    ),
    linear-gradient(180deg, #0a0e1a 0%, #131a2e 55%, #0a0e1a 100%);
  isolation: isolate;
}

.watermark {
  position: absolute;
  right: -70px;
  bottom: 40px;
  font-size: 340px;
  font-weight: 900;
  letter-spacing: -0.06em;
  line-height: 1;
  color: rgba(245, 158, 11, 0.06);
  z-index: 0;
  user-select: none;
}

.ribbon {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 34px 56px;
  background: #f59e0b;
  /* Dark label on amber: white on #F59E0B is 2.1:1 and unreadable at
     thumbnail size, which is the size that matters on Instagram. */
  color: #1f1300;
}

.ribbon-mark {
  font-size: 40px;
  font-weight: 900;
  letter-spacing: -0.02em;
  padding: 4px 14px;
  border: 4px solid #1f1300;
  border-radius: 10px;
}

.ribbon-text {
  flex: 1;
  font-size: 44px;
  font-weight: 800;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.ribbon-diamond {
  font-size: 34px;
}

.stage {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 40px;
  padding: 48px 56px;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 20px;
}

.age-chip {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: 0.06em;
  padding: 8px 20px;
  border-radius: 999px;
  background: #f59e0b;
  color: #1f1300;
}

.meta {
  flex: 1;
  font-size: 26px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.66);
}

.mls-badge {
  height: 64px;
}

.fixture {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.team {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.team-head {
  display: flex;
  align-items: center;
  gap: 26px;
}

.crest {
  width: 108px;
  height: 108px;
  flex-shrink: 0;
  border-radius: 999px;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.crest-filled {
  background: rgba(255, 255, 255, 0.12);
}

.crest-img {
  width: 84px;
  height: 84px;
  object-fit: contain;
}

.crest-initials {
  font-size: 44px;
  font-weight: 800;
  color: #ffffff;
}

.team-name {
  flex: 1;
  font-size: 62px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.04;
  overflow-wrap: anywhere;
}

.team-score {
  font-size: 82px;
  font-weight: 900;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
  color: #f59e0b;
}

.team-bar {
  height: 8px;
  border-radius: 999px;
  /* Club colour, dimmed — it identifies the side without competing with the
     amber that identifies the series. */
  opacity: 0.85;
}

.separator {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: 0.24em;
  color: rgba(255, 255, 255, 0.5);
  padding-left: 134px;
}

.blurb {
  margin: 0;
  font-size: 34px;
  line-height: 46px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
  border-left: 8px solid #f59e0b;
  padding-left: 26px;
}

.when {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 30px;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: #ffffff;
}

.when-dot {
  color: rgba(255, 255, 255, 0.4);
}

.footer {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 30px 56px;
  background: rgba(255, 255, 255, 0.05);
  border-top: 2px solid rgba(245, 158, 11, 0.35);
}

.handle {
  font-size: 30px;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.footer-tagline {
  font-size: 24px;
  color: rgba(255, 255, 255, 0.6);
}
</style>
