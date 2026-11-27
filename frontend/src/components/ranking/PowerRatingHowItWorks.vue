<template>
  <!--
    How the Power Rating works (SB-1811), opened from the Power Rating panel
    header. Plain language for parents; every number matches power-rating.md
    "The model", "What counts" and "Publication". The worked example is
    computed from powerRatingModel.js, so it cannot drift from the formula
    shown above it. z-[1300] like ManagerRolesView: it must sit above any
    overlay (z-[1200]) it is opened from. Teleported to <body> so no
    transformed ancestor can turn `fixed` into a clipped box.
  -->
  <Teleport to="body">
    <div
      class="fixed inset-0 z-[1300] bg-black/60 overflow-y-auto"
      role="dialog"
      aria-modal="true"
      aria-labelledby="pr-how-title"
      data-testid="pr-how-overlay"
      @click.self="$emit('close')"
    >
      <div class="min-h-full flex items-start justify-center p-3 sm:p-6">
        <article
          class="relative w-full max-w-2xl bg-card rounded-lg shadow-2xl text-fg"
          @click.stop
        >
          <button
            ref="closeButton"
            type="button"
            aria-label="Close how the Power Rating works"
            data-testid="pr-how-close"
            class="absolute top-3 right-3 z-10 inline-flex items-center justify-center w-8 h-8 rounded-full text-fg-muted hover:text-fg hover:bg-surface-alt"
            @click="$emit('close')"
          >
            ✕
          </button>

          <div class="p-5 sm:p-7 how-body">
            <h2 id="pr-how-title" class="text-xl font-bold mb-1 pr-8">
              How the Power Rating works
            </h2>
            <p class="text-fg-muted" data-testid="pr-how-source">
              {{ sourceLine }}
            </p>

            <section data-testid="pr-how-what">
              <h3>What it is</h3>
              <p>
                One rating for each Homegrown team in each age group, from U15
                to U19. It is built from League, Flex and tournament results and
                from how strong each opponent was. Every team starts at
                {{ fmt(START) }}, which is average.
              </p>
            </section>

            <section data-testid="pr-how-match">
              <h3>How a match changes it</h3>
              <p>
                Before each match the rating gap says what result to expect. The
                home team gets +{{ HOME_EDGE }} for playing at home; tournament
                matches have no home side. Do better than expected and the
                rating goes up; fall short and it goes down. The other team
                moves the opposite way.
              </p>
              <pre
                class="formula bg-surface-alt text-fg"
                data-testid="pr-how-formula"
              >
E = 1 / (1 + 10^(−(R_team − R_opp + H)/400))
new R = R + K × G × (S − E)</pre
              >
              <p class="text-fg-muted">
                R is a rating, H the home edge (+{{ HOME_EDGE }} at home, −{{
                  HOME_EDGE
                }}
                away, 0 at tournaments), S the result (1 for a win, ½ for a
                draw, 0 for a loss) and E the share of the points the team was
                expected to take.
              </p>
              <table class="how-table" data-testid="pr-how-table">
                <tbody>
                  <tr>
                    <th scope="row">K</th>
                    <td>
                      {{ K }} in every competition; {{ K_PROVISIONAL }} during a
                      team's first {{ PROVISIONAL_MATCHES }} rated matches, so a
                      new team finds its level quickly
                    </td>
                  </tr>
                  <tr class="border-t border-line">
                    <th scope="row">G</th>
                    <td>
                      1 for a draw or a 1-goal win · 1.5 for 2 goals · 1.75 for
                      3 goals or more
                    </td>
                  </tr>
                </tbody>
              </table>
              <p class="safeguard" data-testid="pr-how-safeguard">
                Winning by more than 3 goals earns nothing extra. That is a
                deliberate choice: there is no reward for running up the score
                on youth players.
              </p>
            </section>

            <section data-testid="pr-how-example">
              <h3>A worked example</h3>
              <p>
                A {{ fmt(EXAMPLE.home) }} home team meets a
                {{ fmt(EXAMPLE.away) }} visitor and is expected to take
                {{ pct(expected) }} of the points.
              </p>
              <ul>
                <li data-testid="pr-how-example-win">
                  A 2–0 win gains {{ K }} × 1.5 × {{ two(1 - expected) }} =
                  <strong>{{ winDelta }}</strong
                  >.
                </li>
                <li data-testid="pr-how-example-loss">
                  A 0–1 loss costs {{ K }} × {{ two(expected) }} =
                  <strong>{{ lossDelta }}</strong
                  >.
                </li>
              </ul>
            </section>

            <section data-testid="pr-how-counts">
              <h3>What counts</h3>
              <ul>
                <li>
                  A match decided on penalties counts as a draw, at its
                  regulation score.
                </li>
                <li>Forfeits are not rated: no football was played.</li>
                <li>
                  Matches against teams outside the ranked Homegrown teams, such
                  as academy sides with no Homegrown conference at that age or
                  visiting clubs at tournaments, are not rated.
                </li>
              </ul>
            </section>

            <section data-testid="pr-how-badges">
              <h3>Badges and tiers</h3>
              <ul>
                <li>
                  <strong>Provisional</strong>: fewer than
                  {{ PROVISIONAL_MATCHES }} rated matches, so the rating still
                  moves quickly. Teams with fewer than 6 matches are listed
                  apart and not ranked yet.
                </li>
                <li>
                  <strong>Low cross-conference data</strong>: fewer than 3
                  matches against other conferences, so its place against them
                  is less certain.
                </li>
                <li>
                  <strong>Pro academy</strong>: information only; it does not
                  change the rating.
                </li>
              </ul>
              <p>
                In the national list, teams are grouped by rating:
                <strong>Elite</strong> 1,700+, <strong>Contender</strong> 1,600+
                and <strong>Above average</strong> 1,500+.
              </p>
            </section>

            <section data-testid="pr-how-national">
              <h3>When there is a national list</h3>
              <p>
                Most matches are played inside a conference, so ratings in two
                conferences can only be compared when those conferences have
                played each other enough. A national list is shown only when one
                connected group holds at least 90% of the teams and every
                conference in it has at least 5 matches against other
                conferences. Otherwise each conference is shown on its own,
                because there is no evidence comparing them. MLS NEXT Fest is
                what connects the conferences.
              </p>
            </section>

            <section data-testid="pr-how-cadence">
              <h3>When it changes</h3>
              <p>
                Ratings are updated nightly, after results are checked. A
                corrected result re-computes the whole season in date order.
              </p>
            </section>
          </div>
        </article>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { formatDelta, formatRating } from '@/utils/powerRating';
import {
  HOME_EDGE,
  K,
  K_PROVISIONAL,
  PROVISIONAL_MATCHES,
  START,
  expectedScore,
  ratingChange,
} from '@/utils/powerRatingModel';

const props = defineProps({
  // From the run's coverage, for "MT Power Rating, from N teams in MT".
  teamsInPool: { type: Number, default: null },
  ageGroup: { type: String, default: null },
});
const emit = defineEmits(['close']);

// power-rating.md UI → "How it works screen".
const EXAMPLE = { home: 1600, away: 1500 };

const fmt = formatRating;
const pct = v => `${Math.round(v * 100)}%`;
const two = v => v.toFixed(2);

const expected = expectedScore(EXAMPLE.home, EXAMPLE.away, HOME_EDGE);
const example = (goalsFor, goalsAgainst) =>
  formatDelta(
    ratingChange({
      rating: EXAMPLE.home,
      opponent: EXAMPLE.away,
      home: HOME_EDGE,
      goalsFor,
      goalsAgainst,
    })
  );
const winDelta = example(2, 0);
const lossDelta = example(0, 1);

const sourceLine = computed(() => {
  if (props.teamsInPool == null) {
    return 'MT Power Rating, from the teams in MT.';
  }
  const who = props.ageGroup ? `${props.ageGroup} teams` : 'teams';
  return `MT Power Rating, from ${props.teamsInPool.toLocaleString('en-US')} ${who} in MT.`;
});

const closeButton = ref(null);
const onKeydown = event => {
  if (event.key === 'Escape') emit('close');
};

onMounted(async () => {
  window.addEventListener('keydown', onKeydown);
  await nextTick();
  closeButton.value?.focus();
});
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown));
</script>

<style scoped>
.how-body h3 {
  font-size: 1rem;
  font-weight: 600;
  margin-top: 1.25rem;
  margin-bottom: 0.25rem;
}
.how-body p,
.how-body ul {
  font-size: 0.875rem;
  line-height: 1.5;
}
.how-body p + p,
.how-body p + ul,
.how-body ul + p {
  margin-top: 0.5rem;
}
.how-body ul {
  list-style: disc;
  padding-left: 1.25rem;
}
.how-body li + li {
  margin-top: 0.25rem;
}
.how-body .formula {
  margin: 0.75rem 0 0.5rem;
  padding: 0.625rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.8125rem;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.how-body .how-table {
  width: 100%;
  margin-top: 0.75rem;
  font-size: 0.875rem;
  line-height: 1.5;
  border-collapse: collapse;
}
.how-body .how-table th {
  width: 2rem;
  padding: 0.375rem 0.5rem 0.375rem 0;
  text-align: left;
  vertical-align: top;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.how-body .how-table td {
  padding: 0.375rem 0;
  vertical-align: top;
}
.how-body .safeguard {
  margin-top: 0.75rem;
  font-weight: 500;
}
</style>
