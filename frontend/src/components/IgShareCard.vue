<template>
  <!--
    SB-32 share-card dispatcher. Renders the chosen template at exact
    1080×1080. Exposes a `root` ref that points at the inner template's
    root <div> so html2canvas can capture pixel-perfect output.
  -->
  <component
    :is="currentTemplate"
    ref="inner"
    :match="match"
    :photo-src="photoSrc"
    :photo-is-cross-origin="photoIsCrossOrigin"
    :mode="mode"
  />
</template>

<script>
import { computed, ref, watch } from 'vue';
import IgOverlay from './ig/IgOverlay.vue';
import IgSplit from './ig/IgSplit.vue';
import IgTournamentRound from './ig/IgTournamentRound.vue';
import IgStadium from './ig/IgStadium.vue';

const TEMPLATE_COMPONENTS = {
  overlay: IgOverlay,
  split: IgSplit,
  'tournament-round': IgTournamentRound,
  stadium: IgStadium,
};

export const SHARE_CARD_TEMPLATES = Object.keys(TEMPLATE_COMPONENTS);

export default {
  name: 'IgShareCard',
  components: { IgOverlay, IgSplit, IgTournamentRound, IgStadium },
  props: {
    match: { type: Object, required: true },
    photoSrc: { type: String, default: null },
    photoIsCrossOrigin: { type: Boolean, default: false },
    mode: {
      type: String,
      required: true,
      validator: v => ['preview', 'result'].includes(v),
    },
    template: {
      type: String,
      default: 'overlay',
      validator: v => SHARE_CARD_TEMPLATES.includes(v),
    },
  },
  setup(props) {
    const inner = ref(null);
    // `root` mirrors the inner template's root <div>. The IgShareModal
    // grabs this for html2canvas. Re-evaluated whenever the template
    // changes (component swap unmounts the old, mounts the new).
    const root = ref(null);

    const updateRoot = () => {
      root.value = inner.value?.root || null;
    };
    watch(inner, updateRoot, { flush: 'post' });
    watch(
      () => props.template,
      () => {
        // After Vue swaps the component, the new ref isn't bound yet —
        // wait a tick for the post-flush watcher above to fire.
      }
    );

    const currentTemplate = computed(
      () => TEMPLATE_COMPONENTS[props.template] || IgOverlay
    );

    return { inner, root, currentTemplate };
  },
};
</script>
