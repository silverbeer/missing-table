<template>
  <!--
    MLS Next league badge for the IG share card.

    The SVG is INLINED via v-html (not <img src>) because html2canvas
    drops <img>-sourced SVGs from its captured output — they show in
    the live browser preview but vanish from the downloaded PNG.
    Inlining the SVG markup makes html2canvas render it like any other
    DOM, so it shows up in both places.

    The ?raw import keeps the file at src/assets/leagues/mls-next.svg as
    the single source — replace that file to update the badge everywhere.
  -->
  <div
    class="mls-next-badge"
    data-testid="ig-mls-next-badge"
    v-html="svgMarkup"
  ></div>
</template>

<script>
import mlsNextSvg from '@/assets/leagues/mls-next.svg?raw';

export default {
  name: 'MlsNextBadge',
  setup() {
    return { svgMarkup: mlsNextSvg };
  },
};
</script>

<style scoped>
.mls-next-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.55));
}

.mls-next-badge :deep(svg) {
  height: 100%;
  width: auto;
  display: block;
}
</style>
