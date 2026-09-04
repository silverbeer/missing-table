<template>
  <!--
    Match of the Week hero (SB-1010).

    One pick a week, so this card is allowed to be loud — amber is the only
    place in the app that uses accent-400 at full strength, and it earns it by
    appearing once. The diagonal tear echoes the IgSplit share template so the
    card on the site and the card on Instagram read as the same object.
  -->
  <section
    class="motw"
    data-testid="motw-hero"
    :data-state="state"
    aria-labelledby="motw-heading"
  >
    <div class="motw-rail" aria-hidden="true"></div>

    <div class="motw-body">
      <div class="motw-top">
        <h2 id="motw-heading" class="motw-eyebrow">
          <span class="motw-diamond" aria-hidden="true">◆</span>
          Match of the Week
        </h2>
        <!--
          One status line with three voices. It is never a countdown for a
          match that has already been played, which is the mistake that makes
          a featured card look abandoned by Monday.
        -->
        <span class="motw-status" :data-state="state" data-testid="motw-status">
          {{ statusLabel }}
        </span>
      </div>

      <div class="motw-fixture">
        <div class="motw-side">
          <ClubLogo
            :logo-url="homeClub.logo_url"
            :name="match.home_team_name"
            size="lg"
          />
          <span class="motw-team" data-testid="motw-home">{{
            match.home_team_name
          }}</span>
        </div>

        <div class="motw-middle">
          <!--
            Played matches show the score, unplayed ones show "vs". A scheduled
            match must never render 0–0: that is a result nobody recorded
            (CLAUDE.md rule 2).
          -->
          <span v-if="hasScore" class="motw-score" data-testid="motw-score">
            {{ match.home_score }}<span class="motw-dash">–</span
            >{{ match.away_score }}
          </span>
          <span v-else class="motw-vs" data-testid="motw-vs">vs</span>
        </div>

        <div class="motw-side motw-side--away">
          <span class="motw-team" data-testid="motw-away">{{
            match.away_team_name
          }}</span>
          <ClubLogo
            :logo-url="awayClub.logo_url"
            :name="match.away_team_name"
            size="lg"
          />
        </div>
      </div>

      <p class="motw-meta" data-testid="motw-meta">{{ metaLine }}</p>

      <!-- Absent blurb renders as absent, not as an empty line holding space. -->
      <p v-if="blurb" class="motw-blurb" data-testid="motw-blurb">
        {{ blurb }}
      </p>

      <div class="motw-actions">
        <button
          type="button"
          class="motw-button motw-button--primary"
          data-testid="motw-preview"
          @click="$emit('preview', match)"
        >
          {{ hasScore ? 'View match' : 'Preview' }}
        </button>
        <button
          v-if="canShare"
          type="button"
          class="motw-button"
          data-testid="motw-share"
          @click="$emit('share', match)"
        >
          Share to Instagram
        </button>
      </div>
    </div>
  </section>
</template>

<script>
import { computed } from 'vue';
import ClubLogo from '@/components/shared/ClubLogo.vue';

const DAY = 24 * 60 * 60 * 1000;
const HOUR = 60 * 60 * 1000;

export default {
  name: 'MotwHero',
  components: { ClubLogo },
  props: {
    match: { type: Object, required: true },
    blurb: { type: String, default: null },
    // Generating a share card is open to anyone signed in (SB-659), so the
    // button is hidden rather than shown-and-failing for logged-out viewers.
    canShare: { type: Boolean, default: false },
  },
  emits: ['preview', 'share'],
  setup(props) {
    const homeClub = computed(() => props.match.home_team_club || {});
    const awayClub = computed(() => props.match.away_team_club || {});

    const state = computed(() => {
      const status = props.match.match_status;
      if (status === 'live') return 'live';
      if (['completed', 'forfeit'].includes(status)) return 'final';
      return 'upcoming';
    });

    // A scheduled match with scores already on it would be a data problem, so
    // this asks the status, not the numbers. Both scores must be present:
    // one-sided is a half-entered result, not a 0.
    const hasScore = computed(
      () =>
        state.value !== 'upcoming' &&
        props.match.home_score !== null &&
        props.match.home_score !== undefined &&
        props.match.away_score !== null &&
        props.match.away_score !== undefined
    );

    const kickoff = computed(() => {
      const raw = props.match.scheduled_kickoff;
      if (!raw) return null;
      const parsed = new Date(raw);
      return Number.isNaN(parsed.getTime()) ? null : parsed;
    });

    const statusLabel = computed(() => {
      if (state.value === 'live') return 'Live now';
      if (state.value === 'final') return 'Full time';
      if (!kickoff.value) return 'Time TBC';

      const delta = kickoff.value.getTime() - Date.now();
      if (delta <= 0) return 'Kicking off';
      if (delta >= DAY) {
        const days = Math.round(delta / DAY);
        return `Kicks off in ${days} day${days === 1 ? '' : 's'}`;
      }
      const hours = Math.max(1, Math.round(delta / HOUR));
      return `Kicks off in ${hours} hour${hours === 1 ? '' : 's'}`;
    });

    const metaLine = computed(() => {
      // Every part is skipped when absent rather than printed as "Unknown" —
      // a featured card is the wrong place to advertise a gap in the data.
      const parts = [props.match.age_group_name, props.match.division_name]
        .filter(Boolean)
        .filter(part => part !== 'Unknown');

      if (kickoff.value) {
        parts.push(
          kickoff.value.toLocaleString(undefined, {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
          })
        );
      } else if (props.match.match_date) {
        parts.push(props.match.match_date);
      }

      return parts.join(' · ');
    });

    return {
      homeClub,
      awayClub,
      state,
      hasScore,
      statusLabel,
      metaLine,
    };
  },
};
</script>

<style scoped>
.motw {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  border: 1px solid rgb(var(--color-line));
  background: rgb(var(--color-card));
  margin-bottom: 24px;
}

.motw-rail {
  position: absolute;
  inset: 0 auto 0 0;
  width: 6px;
  background: #f59e0b;
}

.motw-body {
  position: relative;
  padding: 20px 24px 22px 30px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.motw-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.motw-eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #b45309;
  margin: 0;
}

:global(.dark) .motw-eyebrow {
  color: #f59e0b;
}

.motw-diamond {
  font-size: 10px;
}

.motw-status {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgb(var(--color-surface-alt));
  color: rgb(var(--color-fg-muted));
  border: 1px solid rgb(var(--color-line));
}

.motw-status[data-state='live'] {
  background: #dc2626;
  border-color: #dc2626;
  color: #ffffff;
}

/* Sides size to their content and sit next to the middle, rather than each
   taking half the card and pushing the names to opposite edges. */
.motw-fixture {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.motw-side {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.motw-team {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: rgb(var(--color-fg));
  overflow-wrap: anywhere;
}

.motw-middle {
  flex-shrink: 0;
  padding: 0 4px;
}

.motw-vs {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgb(var(--color-fg-muted));
}

.motw-score {
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: rgb(var(--color-fg));
  font-variant-numeric: tabular-nums;
}

.motw-dash {
  color: rgb(var(--color-fg-muted));
  padding: 0 6px;
}

.motw-meta {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--color-fg-muted));
}

.motw-blurb {
  margin: 0;
  font-size: 15px;
  line-height: 22px;
  color: rgb(var(--color-fg));
  max-width: 62ch;
}

.motw-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  padding-top: 4px;
}

.motw-button {
  min-height: 40px;
  padding: 0 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  border: 1px solid rgb(var(--color-line));
  background: rgb(var(--color-surface-alt));
  color: rgb(var(--color-fg));
  cursor: pointer;
}

.motw-button:hover {
  border-color: #f59e0b;
}

.motw-button--primary {
  background: #f59e0b;
  border-color: #f59e0b;
  /* Amber is a light surface in both themes, so the label stays dark — white
     on #F59E0B is 2.1:1 and unreadable. */
  color: #1f1300;
}

.motw-button--primary:hover {
  background: #d97f06;
  border-color: #d97f06;
}

/* Stack the fixture on narrow screens: three columns of team names at 375px
   turns both names into one letter per line. */
@media (max-width: 640px) {
  .motw-fixture {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .motw-side--away {
    flex-direction: row-reverse;
    justify-content: flex-start;
    text-align: left;
  }

  .motw-team {
    font-size: 18px;
  }
}
</style>
