<template>
  <!-- Teleported to <body> so no ancestor can ever turn this into a clipped,
       non-fixed box. A `transform`, `filter` or `contain` anywhere up the tree
       would otherwise make `position: fixed` resolve against that ancestor
       instead of the viewport. -->
  <Teleport to="body">
    <div
      ref="overlay"
      class="fixed inset-0 z-50 bg-black/60 overflow-y-auto overscroll-contain"
      role="dialog"
      aria-modal="true"
      :aria-label="label"
      data-testid="modal-overlay"
      @click.self="close"
      @keydown.esc.stop.prevent="close"
      @keydown.tab="trapFocus"
    >
      <!-- Pinned to the OVERLAY, not the card, so it stays reachable at any
           scroll position. The old button was absolute on the card and left
           the viewport as soon as the user scrolled to read the content
           (SB-890). -->
      <button
        ref="closeButton"
        type="button"
        :aria-label="closeLabel"
        class="fixed top-3 right-3 sm:top-4 sm:right-4 z-10 inline-flex items-center justify-center w-9 h-9 rounded-full bg-card/90 backdrop-blur border border-line text-fg-muted shadow-lg hover:text-fg hover:bg-surface-alt transition-colors"
        data-testid="modal-close"
        @click="close"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          class="w-5 h-5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>

      <div class="min-h-full flex items-start justify-center p-3 sm:p-6">
        <div
          :class="['relative w-full bg-card rounded-lg shadow-2xl', maxWidth]"
          @click.stop
        >
          <slot />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue';

/**
 * A modal that can always be closed (SB-890).
 *
 * The previous inline overlay put its close button `absolute` on the card, had
 * no Escape handler, and left the page scrolling behind it. On a short window
 * the card outgrew the viewport, and scrolling to read it carried the only
 * visible exit off-screen — every escape route blocked at once.
 *
 * Three independent ways out, so no single failure traps anyone: the pinned
 * button, Escape, and a backdrop click.
 */
const props = defineProps({
  // Accessible name for the dialog.
  label: { type: String, default: 'Dialog' },
  closeLabel: { type: String, default: 'Close' },
  maxWidth: { type: String, default: 'max-w-4xl' },
});

const emit = defineEmits(['close']);

const overlay = ref(null);
const closeButton = ref(null);
let previouslyFocused = null;

const close = () => emit('close');

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

const focusable = () =>
  overlay.value
    ? [...overlay.value.querySelectorAll(FOCUSABLE)].filter(
        el => el.offsetParent !== null || el === closeButton.value
      )
    : [];

/**
 * Keep Tab inside the dialog. Without this, tabbing walks out into the page
 * behind — which is still there, just visually covered.
 */
const trapFocus = event => {
  const items = focusable();
  if (items.length === 0) return;
  const first = items[0];
  const last = items[items.length - 1];
  const active = document.activeElement;

  if (event.shiftKey && (active === first || !overlay.value.contains(active))) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus();
  }
};

/**
 * Lock the page behind the modal.
 *
 * `overflow: hidden` on body preserves the scroll position, so closing does not
 * jump the reader back to the top. The padding compensates for the scrollbar
 * that disappears with it, which would otherwise shift the whole layout
 * sideways as the modal opens.
 */
let previousOverflow = '';
let previousPaddingRight = '';

const lockScroll = () => {
  const { body } = document;
  const scrollbar = window.innerWidth - document.documentElement.clientWidth;
  previousOverflow = body.style.overflow;
  previousPaddingRight = body.style.paddingRight;
  body.style.overflow = 'hidden';
  if (scrollbar > 0) body.style.paddingRight = `${scrollbar}px`;
};

const unlockScroll = () => {
  const { body } = document;
  body.style.overflow = previousOverflow;
  body.style.paddingRight = previousPaddingRight;
};

onMounted(async () => {
  previouslyFocused = document.activeElement;
  lockScroll();
  await nextTick();
  // Focus the dialog itself rather than the first control, so a screen reader
  // announces the dialog before its contents, and Escape works immediately.
  closeButton.value?.focus();
});

onBeforeUnmount(() => {
  unlockScroll();
  // Return focus to whatever opened the modal — usually the match row — so the
  // reader does not land back at the top of the document.
  if (previouslyFocused instanceof HTMLElement) {
    previouslyFocused.focus();
  }
});

defineExpose({ close, label: props.label });
</script>
