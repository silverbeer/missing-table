<template>
  <!--
    Match of the Week (SB-1010).

    Deliberately a strip and not a billboard. The pick crosses every age group,
    so it is never the thing the person came to this tab for — it sits above
    Week Navigation as one line and only opens when asked.

    Closed, it withholds the fixture on purpose: one pick a week is small
    enough to be worth revealing rather than announcing, and the reveal is the
    only bit of theatre the schedule gets. The cost is real — a visitor who
    never clicks never learns who was picked — which is why the teaser still
    says there IS a pick, and why the picked row downstairs carries its own
    amber bar.
  -->
  <section
    class="motw"
    :class="{ 'motw--open': expanded }"
    data-testid="motw-hero"
    :data-state="state"
  >
    <div class="motw-rail" aria-hidden="true"></div>

    <button
      type="button"
      class="motw-toggle"
      data-testid="motw-disclosure"
      :aria-expanded="expanded"
      aria-controls="motw-panel"
      @click="expanded = !expanded"
    >
      <span class="motw-eyebrow">
        <span class="motw-diamond" aria-hidden="true">◆</span>
        Match of the Week
      </span>
      <span class="motw-teaser">{{ teaser }}</span>
      <span
        class="motw-chevron"
        :class="{ 'motw-chevron--open': expanded }"
        aria-hidden="true"
      >
        ▾
      </span>
    </button>

    <div
      v-if="expanded"
      id="motw-panel"
      class="motw-body"
      data-testid="motw-panel"
    >
      <div class="motw-top">
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

      <!--
        The line that makes the case. It is the only editorial writing in the
        product, and it is what fills the "Why it's the match of the week"
        panel on the share card — no line, no panel.

        Absent renders as absent for everyone; admins additionally get the
        way to write one, right here rather than in a settings screen, because
        the moment you want to write it is the moment you are looking at the
        pick.
      -->
      <div v-if="editing" class="motw-editor" data-testid="motw-blurb-editor">
        <label class="motw-editor-label" :for="editorId">
          Why is this the match of the week?
        </label>
        <textarea
          :id="editorId"
          ref="editorRef"
          v-model="draft"
          class="motw-editor-input"
          data-testid="motw-blurb-input"
          rows="2"
          :maxlength="BLURB_MAX"
          placeholder="Two unbeaten records, and only one of them leaves with it."
          @keydown.esc.stop="cancelEdit"
          @keydown.enter.meta.prevent="commit"
          @keydown.enter.ctrl.prevent="commit"
        ></textarea>
        <div class="motw-editor-foot">
          <span
            class="motw-editor-count"
            :class="{ 'motw-editor-count--near': remaining <= 40 }"
            data-testid="motw-blurb-count"
          >
            {{ remaining }} left
          </span>
          <button
            type="button"
            class="motw-button motw-button--quiet"
            data-testid="motw-blurb-cancel"
            @click="cancelEdit"
          >
            Cancel
          </button>
          <button
            type="button"
            class="motw-button motw-button--primary"
            data-testid="motw-blurb-save"
            :disabled="saving"
            @click="commit"
          >
            {{ saving ? 'Saving…' : 'Save line' }}
          </button>
        </div>
      </div>

      <template v-else>
        <p v-if="blurb" class="motw-blurb" data-testid="motw-blurb">
          {{ blurb }}
          <button
            v-if="canEdit"
            type="button"
            class="motw-blurb-edit"
            data-testid="motw-blurb-edit"
            @click="startEdit"
          >
            Edit
          </button>
        </p>
        <button
          v-else-if="canEdit"
          type="button"
          class="motw-blurb-add"
          data-testid="motw-blurb-add"
          @click="startEdit"
        >
          + Add a line about this match
        </button>
      </template>

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
import { computed, nextTick, ref, watch } from 'vue';
import ClubLogo from '@/components/shared/ClubLogo.vue';

// Matches the API's own cap (MotwPick.blurb), so the textarea stops where
// the server would have rejected rather than after it.
const BLURB_MAX = 280;

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
    // Admins can write the editorial line. Everyone else sees it read-only.
    canEdit: { type: Boolean, default: false },
    saving: { type: Boolean, default: false },
  },
  emits: ['preview', 'share', 'save-blurb'],
  setup(props, { emit }) {
    const expanded = ref(false);

    const editing = ref(false);
    const draft = ref('');
    const editorRef = ref(null);
    const editorId = `motw-blurb-${Math.random().toString(36).slice(2, 8)}`;

    const remaining = computed(() => BLURB_MAX - draft.value.length);

    const startEdit = async () => {
      draft.value = props.blurb || '';
      editing.value = true;
      await nextTick();
      editorRef.value?.focus();
    };

    const cancelEdit = () => {
      editing.value = false;
      draft.value = '';
    };

    const commit = () => {
      // Empty means "no line", not "a line that is empty" — the card renders
      // the panel on presence, so a blank string would frame nothing.
      const trimmed = draft.value.trim();
      emit('save-blurb', trimmed === '' ? null : trimmed);
    };

    // The parent owns the save. When it lands, the new blurb arrives as a
    // prop and the editor steps out of the way; a failed save leaves the
    // editor open with the text still in it.
    watch(
      () => props.blurb,
      () => {
        if (editing.value && !props.saving) cancelEdit();
      }
    );
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

    // Closed-state copy. Says enough to be worth a click — that there is a
    // pick, and roughly when it is — without giving the fixture away.
    const teaser = computed(() => {
      if (state.value === 'live') return 'Being played right now — reveal';
      if (state.value === 'final') return 'Played — reveal the result';
      return 'Reveal this week’s pick';
    });

    return {
      expanded,
      teaser,
      BLURB_MAX,
      editing,
      draft,
      editorRef,
      editorId,
      remaining,
      startEdit,
      cancelEdit,
      commit,
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
  border-radius: 10px;
  border: 1px solid rgb(var(--color-line));
  background: rgb(var(--color-card));
  margin-bottom: 16px;
}

/* Closed, the strip is one row tall and reads as a control. Open, it earns a
   little more presence — but never the third of a screen the first version
   took. */
.motw--open {
  border-color: #f59e0b;
}

.motw-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 44px;
  padding: 10px 14px 10px 20px;
  background: transparent;
  border: 0;
  cursor: pointer;
  text-align: left;
}

.motw-toggle:hover .motw-teaser {
  color: rgb(var(--color-fg));
}

.motw-teaser {
  flex: 1;
  font-size: 13px;
  color: rgb(var(--color-fg-muted));
  min-width: 0;
}

.motw-chevron {
  flex-shrink: 0;
  font-size: 12px;
  color: rgb(var(--color-fg-muted));
  transition: transform 0.15s ease;
}

.motw-chevron--open {
  transform: rotate(180deg);
}

.motw-rail {
  position: absolute;
  inset: 0 auto 0 0;
  width: 6px;
  background: #f59e0b;
}

.motw-body {
  position: relative;
  padding: 4px 20px 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.motw-top {
  display: flex;
  align-items: center;
  gap: 16px;
}

.motw-eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #b45309;
  margin: 0;
  white-space: nowrap;
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
  font-size: 19px;
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
  font-size: 26px;
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

/* --- editorial line -------------------------------------------------- */

.motw-blurb-edit,
.motw-blurb-add {
  border: 0;
  background: none;
  padding: 0;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #b45309;
}

:global(.dark) .motw-blurb-edit,
:global(.dark) .motw-blurb-add {
  color: #f59e0b;
}

.motw-blurb-edit {
  margin-left: 8px;
}

.motw-blurb-add {
  align-self: flex-start;
  font-size: 14px;
}

.motw-blurb-edit:hover,
.motw-blurb-add:hover {
  text-decoration: underline;
}

.motw-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.motw-editor-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: rgb(var(--color-fg-muted));
}

.motw-editor-input {
  width: 100%;
  resize: vertical;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid rgb(var(--color-line));
  background: rgb(var(--color-surface-alt));
  color: rgb(var(--color-fg));
  font: inherit;
  font-size: 15px;
  line-height: 22px;
}

.motw-editor-input:focus {
  outline: 2px solid #f59e0b;
  outline-offset: 1px;
}

.motw-editor-foot {
  display: flex;
  align-items: center;
  gap: 10px;
}

.motw-editor-count {
  flex: 1;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: rgb(var(--color-fg-muted));
}

/* Only speaks up near the limit — a counter shouting from character one is
   noise on a field most people fill in twenty words. */
.motw-editor-count--near {
  color: #b45309;
  font-weight: 600;
}

:global(.dark) .motw-editor-count--near {
  color: #f59e0b;
}

.motw-button--quiet {
  background: transparent;
}

.motw-button:disabled {
  opacity: 0.6;
  cursor: default;
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
