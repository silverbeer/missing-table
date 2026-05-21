<template>
  <!--
    MLS Next league badge for the IG share card.

    Rendered as a CSS background-image (not <img>) for html2canvas
    reliability — see [[feedback-html2canvas-object-fit]]. Native logo
    aspect ratio is preserved by setting the container's aspect-ratio
    to match the source PNG.

    The asset is bundled from src/assets/leagues/mls-next.png — replace
    that file (PNG, transparent background) to swap to a different
    official version. If you swap to an SVG, change the import below
    and the aspect-ratio if the new vector's ratio differs.
  -->
  <div
    class="mls-next-badge"
    data-testid="ig-mls-next-badge"
    :style="{ backgroundImage: `url(${logoUrl})` }"
  ></div>
</template>

<script>
import mlsNextLogo from '@/assets/leagues/mls-next.png';

export default {
  name: 'MlsNextBadge',
  setup() {
    return { logoUrl: mlsNextLogo };
  },
};
</script>

<style scoped>
.mls-next-badge {
  /* Source PNG is 330x258 (≈1.28:1). Container takes its height from the
     parent template (the .mls-badge / .ig-mls-badge / .brand-band-badge
     rule); width scales to preserve aspect ratio. */
  aspect-ratio: 330 / 258;
  height: 100%;
  background-size: contain;
  background-position: center;
  background-repeat: no-repeat;
  filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.55));
}
</style>
