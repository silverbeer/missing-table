/**
 * Long-press as a secondary gesture on a row whose primary gesture is a tap
 * (SB-1101).
 *
 * The match list gave every match two full-width buttons so that the rare act
 * (open, edit) had somewhere to live. Tap now does the common act, and the rare
 * one moves behind a long press. That only works if the long press cannot
 * possibly fire the tap as well, which is most of what is going on here.
 *
 * Pointer events rather than touch events: one code path covers finger, pen and
 * a held mouse button, and the browser's touch/mouse compatibility events never
 * enter the picture.
 */

import { onBeforeUnmount, ref } from 'vue';

/** Long enough not to fire while scrolling; short enough not to feel broken. */
const DEFAULT_DELAY_MS = 500;

/**
 * Finger travel that means "this is a scroll, not a press". A finger resting on
 * a phone drifts a few pixels; a scroll moves far more.
 */
const MOVE_TOLERANCE_PX = 10;

/**
 * @param {(event: PointerEvent) => void} onLongPress  fired once the press holds
 * @param {object} [options]
 * @param {number} [options.delay]
 * @returns handlers to spread onto an element, plus `didLongPress`
 */
export function useLongPress(onLongPress, { delay = DEFAULT_DELAY_MS } = {}) {
  let timer = null;
  let origin = null;
  // Set the moment the press fires and cleared on the next pointerdown — NOT
  // in the click handler, because a long press on touch may produce no click
  // at all. Clearing it on click would leave it stuck true on those platforms
  // and swallow the *following* genuine tap.
  const didLongPress = ref(false);
  // Only touch and pen get the context menu suppressed. A right-click on a
  // desktop row should still open the browser's own menu.
  let lastPointerType = 'mouse';

  const cancel = () => {
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
    origin = null;
  };

  const onPointerDown = event => {
    // Ignore secondary mouse buttons: right-click has its own meaning.
    if (event.pointerType === 'mouse' && event.button !== 0) return;

    lastPointerType = event.pointerType || 'mouse';
    didLongPress.value = false;
    origin = { x: event.clientX, y: event.clientY };

    timer = setTimeout(() => {
      timer = null;
      didLongPress.value = true;
      onLongPress(event);
    }, delay);
  };

  const onPointerMove = event => {
    if (timer === null || !origin) return;
    const dx = Math.abs(event.clientX - origin.x);
    const dy = Math.abs(event.clientY - origin.y);
    if (dx > MOVE_TOLERANCE_PX || dy > MOVE_TOLERANCE_PX) cancel();
  };

  /**
   * Wrap the row's click handler. Returns a handler that drops the click when
   * it is the tail of a long press.
   *
   * On Android a long press still delivers a click on pointerup; without this
   * the sheet would open and the row would navigate underneath it.
   */
  const guardClick = handler => event => {
    if (didLongPress.value) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    handler(event);
  };

  const onContextMenu = event => {
    if (lastPointerType === 'touch' || lastPointerType === 'pen') {
      event.preventDefault();
    }
  };

  onBeforeUnmount(cancel);

  return {
    didLongPress,
    /** Spread onto the pressable element. */
    handlers: {
      pointerdown: onPointerDown,
      pointermove: onPointerMove,
      pointerup: cancel,
      pointercancel: cancel,
      pointerleave: cancel,
      contextmenu: onContextMenu,
    },
    guardClick,
    cancel,
  };
}
