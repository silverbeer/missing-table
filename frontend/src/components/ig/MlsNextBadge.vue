<template>
  <!--
    MLS Next league badge for the IG share card. Shown by each template
    when the match's league is "Homegrown". The asset at
    src/assets/leagues/mls-next.svg starts as a placeholder; replace
    that file with the official MLS Next logo to update every template
    at once (no code change needed).
  -->
  <div class="mls-next-badge" data-testid="ig-mls-next-badge">
    <img :src="logoUrl" alt="MLS Next" class="mls-next-logo" />
  </div>
</template>

<script>
import mlsNextLogo from '@/assets/leagues/mls-next.svg';

export default {
  name: 'MlsNextBadge',
  setup() {
    return { logoUrl: mlsNextLogo };
  },
};
</script>

<style scoped>
.mls-next-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.mls-next-logo {
  display: block;
  height: 100%;
  width: auto;
  filter: drop-shadow(0 2px 8px rgba(0, 0, 0, 0.55));
}
</style>
