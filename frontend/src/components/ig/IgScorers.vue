<template>
  <!--
    Goal-scorers block (SB-33). Shown on result cards when a match was
    live-scored. Two columns — home right-aligned, away left-aligned —
    one line per goal in chronological order, mirroring the in-app
    scoreboard. Braces (2 goals) glow gold; hat-tricks (3+) add a
    celebratory banner above the columns.

    Pure presentational: all data is derived in useIgShareData. The `size`
    prop ('lg' | 'sm') scales type so the block fits both the roomy
    Overlay/Stadium cards and the tighter Split/Tournament panels.
  -->
  <div
    class="ig-scorers"
    :class="`ig-scorers-${size}`"
    data-testid="ig-scorers"
  >
    <div
      v-if="hatTricks.length"
      class="ig-hat-banner"
      data-testid="ig-hat-banner"
    >
      <span
        v-for="ht in hatTricks"
        :key="ht.name"
        class="ig-hat-pill"
        data-testid="ig-hat-pill"
      >
        <span class="ig-hat-balls">
          <svg
            v-for="n in 3"
            :key="n"
            class="ig-ball ig-hat-ball"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="11" fill="#1f2937" />
            <polygon
              points="12,6.4 16.4,9.6 14.7,14.8 9.3,14.8 7.6,9.6"
              fill="#fbbf24"
            />
          </svg>
        </span>
        <span class="ig-hat-text">
          {{ ht.count > 3 ? `${ht.count} GOALS` : 'HAT-TRICK' }} ·
          {{ ht.name }}
        </span>
      </span>
    </div>

    <div class="ig-scorers-grid">
      <div class="ig-scorers-col ig-scorers-home">
        <div
          v-for="g in home"
          :key="g.id"
          class="ig-scorer"
          :class="{
            'ig-scorer-multi': g.isMultiGoal,
            'ig-scorer-hat': g.isHatTrick,
          }"
          data-testid="ig-scorer-home"
        >
          <span class="ig-scorer-text">
            <span class="ig-scorer-name">{{ g.name }}</span>
            <span class="ig-scorer-min">{{ g.minute }}</span>
          </span>
          <svg
            class="ig-ball ig-scorer-ball"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="11" fill="#ffffff" />
            <polygon
              points="12,6.4 16.4,9.6 14.7,14.8 9.3,14.8 7.6,9.6"
              fill="#0f172a"
            />
          </svg>
        </div>
      </div>

      <div class="ig-scorers-divider"></div>

      <div class="ig-scorers-col ig-scorers-away">
        <div
          v-for="g in away"
          :key="g.id"
          class="ig-scorer"
          :class="{
            'ig-scorer-multi': g.isMultiGoal,
            'ig-scorer-hat': g.isHatTrick,
          }"
          data-testid="ig-scorer-away"
        >
          <svg
            class="ig-ball ig-scorer-ball"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="11" fill="#ffffff" />
            <polygon
              points="12,6.4 16.4,9.6 14.7,14.8 9.3,14.8 7.6,9.6"
              fill="#0f172a"
            />
          </svg>
          <span class="ig-scorer-text">
            <span class="ig-scorer-name">{{ g.name }}</span>
            <span class="ig-scorer-min">{{ g.minute }}</span>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'IgScorers',
  props: {
    // Each entry: { id, name, minute, goalCount, isMultiGoal, isHatTrick }
    home: { type: Array, default: () => [] },
    away: { type: Array, default: () => [] },
    // Each entry: { name, count } for players with 3+ goals.
    hatTricks: { type: Array, default: () => [] },
    size: {
      type: String,
      default: 'lg',
      validator: v => ['lg', 'sm'].includes(v),
    },
  },
};
</script>

<style scoped>
.ig-scorers {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  width: 100%;
}

/* --- Hat-trick celebration banner --- */
.ig-hat-banner {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
}

.ig-hat-pill {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 10px 24px;
  border-radius: 999px;
  background: linear-gradient(135deg, #f59e0b 0%, #fde68a 50%, #f59e0b 100%);
  color: #1f2937;
  font-weight: 900;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  box-shadow: 0 6px 24px rgba(251, 191, 36, 0.5);
}

.ig-hat-balls {
  display: inline-flex;
  gap: 4px;
}

.ig-hat-text {
  white-space: nowrap;
}

/* --- Two-column scorer lists --- */
.ig-scorers-grid {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: start;
  gap: 28px;
  width: 100%;
}

.ig-scorers-divider {
  width: 2px;
  align-self: stretch;
  background: rgba(255, 255, 255, 0.22);
  border-radius: 2px;
}

.ig-scorers-col {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.ig-scorers-home {
  align-items: flex-end;
}

.ig-scorers-away {
  align-items: flex-start;
}

.ig-scorer {
  display: flex;
  align-items: center;
  gap: 12px;
  max-width: 100%;
}

.ig-scorer-text {
  display: inline-flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.ig-scorers-home .ig-scorer-text {
  justify-content: flex-end;
  text-align: right;
}

.ig-scorer-name {
  font-weight: 700;
  color: #ffffff;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.6);
  word-break: break-word;
}

.ig-scorer-min {
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

/* Brace+ : gold accent so a multi-goal game stands out. */
.ig-scorer-multi .ig-scorer-name {
  color: #fbbf24;
}

.ig-scorer-multi .ig-scorer-min {
  color: rgba(251, 191, 36, 0.85);
}

/* Hat-trick : brighter gold + glow. */
.ig-scorer-hat .ig-scorer-name {
  color: #fbbf24;
  text-shadow:
    0 0 16px rgba(251, 191, 36, 0.7),
    0 2px 8px rgba(0, 0, 0, 0.6);
}

.ig-ball {
  flex-shrink: 0;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.45));
}

/* --- Size variants --- */
.ig-scorers-lg .ig-scorer-name {
  font-size: 30px;
}
.ig-scorers-lg .ig-scorer-min {
  font-size: 26px;
}
.ig-scorers-lg .ig-scorer-ball {
  width: 30px;
  height: 30px;
}
.ig-scorers-lg .ig-hat-pill {
  font-size: 24px;
}
.ig-scorers-lg .ig-hat-ball {
  width: 24px;
  height: 24px;
}

.ig-scorers-sm .ig-scorers-grid {
  gap: 18px;
}
.ig-scorers-sm .ig-scorer {
  gap: 8px;
}
.ig-scorers-sm .ig-scorer-name {
  font-size: 20px;
}
.ig-scorers-sm .ig-scorer-min {
  font-size: 17px;
}
.ig-scorers-sm .ig-scorer-ball {
  width: 18px;
  height: 18px;
}
.ig-scorers-sm .ig-hat-pill {
  font-size: 16px;
  padding: 7px 16px;
  gap: 8px;
}
.ig-scorers-sm .ig-hat-ball {
  width: 16px;
  height: 16px;
}
</style>
