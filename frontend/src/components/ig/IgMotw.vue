<template>
  <!--
    Match of the Week share card (SB-1010).

    A broadcast graphic, not a poster. The first version of this was a UI card
    scaled up to 1080 and it read like one: the crests were an afterthought at
    108px, and the thing people actually recognise a fixture by was the
    smallest element on the card.

    So the crests lead, at 300px, on a floodlit ground. Everything else —
    kickoff, competition, the editorial line — arranges itself around them.

    Colour: MT navy and amber carry the series, and each side picks up its own
    club colour as a rim and a name rule when that club has a real one on
    file. Only 22 of 144 clubs currently do, so the neutral path is the one
    that has to look deliberate, not the exception.
  -->
  <div
    ref="root"
    class="ig-share-card ig-motw"
    data-testid="ig-share-card"
    data-template="motw"
    :data-mode="mode"
  >
    <!-- Ground. An uploaded photo takes over when there is one; otherwise the
         bundled pitch shot carries the floodlight. Painted as a background
         image rather than an <img> because html2canvas gets object-fit
         wrong — see [[feedback-html2canvas-object-fit]]. -->
    <div
      class="ground"
      :style="{ backgroundImage: `url(${groundImage})` }"
      aria-hidden="true"
    ></div>
    <div class="scrim" aria-hidden="true"></div>
    <div class="beam beam--left" aria-hidden="true"></div>
    <div class="beam beam--right" aria-hidden="true"></div>

    <header class="top">
      <div class="wordmark">
        <span class="wordmark-missing">MISSING</span
        ><span class="wordmark-table">TABLE</span>
        <!-- The landing page's own headline, so the wordmark and the line
             read as one thought: MLS Next publishes no standings, and that
             absence is what the name is about. -->
        <span class="wordmark-sub">The table you've been missing</span>
      </div>
      <MlsNextBadge v-if="isHomegrownLeague" class="mls-badge" />
    </header>

    <div class="plaque-wrap">
      <div class="plaque">Match of the Week</div>
      <div class="context">
        <span v-if="weekLabel" data-testid="ig-motw-week">{{ weekLabel }}</span>
        <span v-if="weekLabel" class="context-dot" aria-hidden="true">·</span>
        <span data-testid="ig-age-chip">{{ ageGroupLabel }}</span>
        <span class="context-dot" aria-hidden="true">·</span>
        <span data-testid="ig-meta">{{ metaLabel }}</span>
      </div>
    </div>

    <div class="fixture">
      <div class="side">
        <div class="crest-ring" :style="homeCrestStyle">
          <div class="crest" data-testid="ig-home-crest">
            <div
              v-if="homeLogoUrl"
              class="crest-img"
              :style="{ backgroundImage: `url(${homeLogoUrl})` }"
            ></div>
            <span v-else class="crest-initials">{{ homeInitials }}</span>
          </div>
        </div>
        <div
          class="team-name"
          :style="{ borderBottomColor: homeRuleColor }"
          data-testid="ig-home-name"
        >
          {{ homeTeamName }}
        </div>
        <div class="side-tag">Home</div>
      </div>

      <div class="centre">
        <template v-if="isResult">
          <div class="score" data-testid="ig-score">
            <span>{{ homeScore }}</span>
            <span class="score-dash">–</span>
            <span>{{ awayScore }}</span>
          </div>
          <div class="status" data-testid="ig-status">Full time</div>
        </template>
        <template v-else>
          <div class="date" data-testid="ig-date">{{ shortDateLabel }}</div>
          <!-- The kickoff is the call to action, so it is the biggest thing
               in the middle. When there is no time on file the slot says so
               rather than printing a plausible-looking one. -->
          <div v-if="kickoffLabel" class="kickoff" data-testid="ig-kickoff">
            {{ kickoffLabel }}
          </div>
          <div v-else class="kickoff kickoff--tbc" data-testid="ig-kickoff">
            Time TBC
          </div>
        </template>
      </div>

      <div class="side">
        <div class="crest-ring" :style="awayCrestStyle">
          <div class="crest" data-testid="ig-away-crest">
            <div
              v-if="awayLogoUrl"
              class="crest-img"
              :style="{ backgroundImage: `url(${awayLogoUrl})` }"
            ></div>
            <span v-else class="crest-initials">{{ awayInitials }}</span>
          </div>
        </div>
        <div
          class="team-name"
          :style="{ borderBottomColor: awayRuleColor }"
          data-testid="ig-away-name"
        >
          {{ awayTeamName }}
        </div>
        <div class="side-tag">Away</div>
      </div>
    </div>

    <IgScorers
      v-if="isResult && hasScorers"
      :home="homeScorers"
      :away="awayScorers"
      :hat-tricks="hatTricks"
      size="md"
      class="scorers"
    />

    <!-- The blurb finally has a labelled home. Without one the panel is not
         rendered at all — an empty "why it's the match of the week" box is
         the worst thing on a card whose whole job is to make a case. -->
    <section v-if="blurb" class="why" data-testid="ig-motw-blurb">
      <div class="why-label">
        <span class="why-star" aria-hidden="true">★</span>
        Why it's the match of the week
      </div>
      <p class="why-text">{{ blurb }}</p>
    </section>

    <!--
      The card is a recruiting surface, not just a graphic. Most teams in MT
      have scraped results and nobody managing them, so every share is a
      chance to bring in the parent who will (CLAUDE.md: every screen is
      either recruiting a manager or serving one). The domain leads, because
      that is the thing someone has to remember after the post scrolls past.
    -->
    <footer class="foot">
      <div class="foot-main">
        <span class="site" data-testid="ig-site">missingtable.com</span>
        <span class="cta" data-testid="ig-cta">
          Players &amp; fans — request an invite to follow your club
        </span>
      </div>
      <span class="handle" data-testid="ig-handle">@missingtable</span>
    </footer>
  </div>
</template>

<script>
import { computed, ref, toRefs } from 'vue';
import { isUsableAccent, useIgShareData } from '@/composables/useIgShareData';
import IgScorers from './IgScorers.vue';
import MlsNextBadge from './MlsNextBadge.vue';
import pitchImage from '@/assets/hero-goal.png';

const MT_AMBER = '#f5a524';

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
    // Which pick in the series this is. Comes from the API rather than being
    // derived from a date here — see the note in MotwDAO.
    weekNumber: { type: Number, default: null },
  },
  setup(props) {
    const root = ref(null);
    const { match, mode, events } = toRefs(props);
    const data = useIgShareData(match, mode, events);

    const groundImage = computed(() => props.photoSrc || pitchImage);

    // isUsableAccent is the modal's own test — it rejects the seeded grey and
    // anything too dark to read against the card ground. My first pass here
    // only caught the grey, which let New England Revolution's #0A2240 paint
    // a navy rule onto a navy card: present in the DOM, invisible in the post.
    const homeColorUsable = computed(() => {
      const c = props.match?.home_team_club?.primary_color;
      return isUsableAccent(c) ? c : null;
    });
    const awayColorUsable = computed(() => {
      const c = props.match?.away_team_club?.primary_color;
      return isUsableAccent(c) ? c : null;
    });

    // Amber is the fallback rather than grey: a club with no colour on file
    // borrows the series colour instead of advertising the gap.
    const homeRuleColor = computed(() => homeColorUsable.value || MT_AMBER);
    const awayRuleColor = computed(() => awayColorUsable.value || MT_AMBER);

    // The crest disc stays white — club logos are drawn to sit on white, and
    // a coloured disc turns half of them into mud. The club colour appears as
    // the ring around it.
    // A real ring element, not a box-shadow spread: html2canvas renders a
    // 10px spread as a filled disc behind the crest, which ate the white
    // plate the club logos are drawn to sit on.
    const crestStyle = color => ({ background: color });
    const homeCrestStyle = computed(() => crestStyle(homeRuleColor.value));
    const awayCrestStyle = computed(() => crestStyle(awayRuleColor.value));

    // Counts picks, not calendar weeks. A season-week number is arithmetic
    // nobody recognises — this season's row begins six weeks before its first
    // real matchday — whereas "Week 1" on the first Match of the Week is
    // exactly what it says.
    const weekLabel = computed(() =>
      props.weekNumber ? `Week ${props.weekNumber}` : null
    );

    return {
      root,
      ...data,
      groundImage,
      homeCrestStyle,
      awayCrestStyle,
      homeRuleColor,
      awayRuleColor,
      weekLabel,
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
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 34px 56px 0;
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue',
    Arial, sans-serif;
  color: #ffffff;
  background: #060a14;
  isolation: isolate;
}

.ground {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center 62%;
  z-index: 0;
}

/* Heavy enough that white type holds anywhere on the card, including over the
   bright part of the pitch. */
.scrim {
  position: absolute;
  inset: 0;
  z-index: 1;
  background:
    linear-gradient(
      180deg,
      rgba(4, 8, 18, 0.94) 0%,
      rgba(4, 8, 18, 0.62) 42%,
      rgba(4, 8, 18, 0.96) 100%
    ),
    radial-gradient(
      ellipse 780px 460px at 50% 34%,
      rgba(10, 34, 64, 0.5),
      transparent 72%
    );
}

/* Two floodlights, drawn rather than photographed so they land in the same
   place whatever image sits underneath. */
.beam {
  position: absolute;
  top: -180px;
  width: 520px;
  height: 620px;
  z-index: 1;
  filter: blur(6px);
}

.beam--left {
  left: -120px;
  background: radial-gradient(
    ellipse at 50% 0%,
    rgba(215, 235, 255, 0.34),
    transparent 68%
  );
}

.beam--right {
  right: -120px;
  background: radial-gradient(
    ellipse at 50% 0%,
    rgba(215, 235, 255, 0.3),
    transparent 68%
  );
}

.top,
.plaque-wrap,
.fixture,
.why,
.foot,
.scorers {
  position: relative;
  z-index: 2;
}

.top {
  width: 100%;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.wordmark {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  font-size: 40px;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.wordmark-missing {
  color: #ffffff;
}

.wordmark-table {
  color: #f5a524;
}

.wordmark-sub {
  width: 100%;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.55);
  padding-top: 6px;
}

.mls-badge {
  height: 76px;
}

.plaque-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 18px 0 2px;
}

.plaque {
  background: #f5a524;
  color: #1a1206;
  font-size: 42px;
  font-weight: 900;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 14px 40px;
  border-radius: 8px;
}

.context {
  display: flex;
  align-items: center;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.72);
}

.context-dot {
  color: rgba(255, 255, 255, 0.4);
}

.fixture {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 0 0;
}

.side {
  width: 300px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* The crests lead. Everything else on this card is arranged around them. */
.crest-ring {
  width: 264px;
  height: 264px;
  border-radius: 999px;
  padding: 10px;
  box-shadow: 0 26px 70px rgba(0, 0, 0, 0.55);
}

.crest {
  width: 244px;
  height: 244px;
  border-radius: 999px;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.crest-img {
  width: 188px;
  height: 188px;
  background-size: contain;
  background-position: center;
  background-repeat: no-repeat;
}

.crest-initials {
  font-size: 104px;
  font-weight: 900;
  letter-spacing: -0.02em;
  color: #0a2240;
}

.team-name {
  display: inline-block;
  font-size: 35px;
  font-weight: 800;
  letter-spacing: -0.01em;
  line-height: 1.06;
  text-align: center;
  overflow-wrap: anywhere;
  padding-bottom: 14px;
  border-bottom: 7px solid transparent;
}

.side-tag {
  font-size: 19px;
  font-weight: 700;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.55);
}

.centre {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-bottom: 40px;
}

.date {
  font-size: 30px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.8);
}

.kickoff {
  white-space: nowrap;
  font-size: 76px;
  font-weight: 900;
  letter-spacing: -0.03em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.kickoff--tbc {
  font-size: 48px;
  letter-spacing: 0.02em;
  color: rgba(255, 255, 255, 0.78);
}

.score {
  display: flex;
  align-items: baseline;
  font-size: 108px;
  font-weight: 900;
  letter-spacing: -0.04em;
  font-variant-numeric: tabular-nums;
}

.score-dash {
  color: #f5a524;
  padding: 0 16px;
}

.status {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: #f5a524;
}

.scorers {
  width: 100%;
  padding-bottom: 12px;
}

.why {
  width: 100%;
  display: flex;
  flex-direction: column;
  background: rgba(8, 14, 28, 0.72);
  border: 2px solid rgba(245, 165, 36, 0.4);
  border-radius: 14px;
  padding: 18px 26px;
}

.why-label {
  display: flex;
  align-items: center;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #f5a524;
}

.why-star {
  font-size: 24px;
}

.why-text {
  margin: 0;
  font-size: 27px;
  line-height: 36px;
  color: rgba(255, 255, 255, 0.94);
}

.foot {
  width: calc(100% + 112px);
  margin: 0 -56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 56px 24px;
  background: rgba(4, 8, 18, 0.82);
  border-top: 3px solid #f5a524;
}

.foot-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.site {
  font-size: 40px;
  font-weight: 900;
  letter-spacing: 0.01em;
  color: #ffffff;
}

.cta {
  font-size: 23px;
  font-weight: 600;
  color: #f5a524;
}

.handle {
  flex-shrink: 0;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: rgba(255, 255, 255, 0.6);
}

/*
  Spacing below is margin, not flex `gap`. html2canvas 1.4.1 does not
  implement gap: the browser preview honoured it and the exported PNG
  collapsed every one to zero, which put the club-colour rules through the
  middle of the team names. Margins render identically in both.
*/
.wordmark-table {
  margin-left: 2px;
}

.week,
.context {
  margin-top: 10px;
}

.context-dot {
  margin: 0 12px;
}

.side .team-name {
  margin-top: 14px;
}

.side .side-tag {
  margin-top: 12px;
}

.centre .kickoff,
.centre .status,
.centre .score {
  margin-top: 10px;
}

.why-text {
  margin-top: 10px;
}

.why-star {
  margin-right: 12px;
}

.foot .handle {
  margin-left: 24px;
}

.foot-main .cta {
  margin-top: 4px;
}
</style>
