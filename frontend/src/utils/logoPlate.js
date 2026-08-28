/**
 * Does a logo need a white plate behind it to stay visible? (SB-901)
 *
 * The share-card templates used to draw every tournament logo on a white
 * rounded chip. The reason was sound — a dark logo vanishes against the dark
 * card ground — but it was applied to every logo regardless of need, so a
 * light crest ended up in a white box that clashed with the unplated MLS Next
 * badge beside it.
 *
 * This samples the logo and answers the question per-image.
 *
 * **Plating is the safe default.** Every failure path returns `true`: a logo
 * that cannot be sampled must never end up invisible because the check could
 * not run.
 */

import { CARD_GROUND } from '@/composables/useIgShareData';

/**
 * Reuses the threshold the accent picker already applies when it rejects a
 * club colour as "too dark or unset — would not be visible".
 *
 * Checked against the real logo set: Copa Rayados scores 7.36 and the 2026
 * National Academy Championships 7.60, while a near-black control lands at
 * 1.01. The boundary is nowhere near either group, so it is not tuned to one
 * image.
 */
export const LOGO_PLATE_MIN_CONTRAST = 2.5;

/** Pixels below this alpha are the transparent surround, not the artwork. */
const OPAQUE_ALPHA = 200;

/** Small enough to be cheap, large enough to survive a thin-lined crest. */
const SAMPLE_SIZE = 48;

const channelLuminance = v => {
  const s = v / 255;
  return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
};

const luminanceOf = ([r, g, b]) =>
  0.2126 * channelLuminance(r) +
  0.7152 * channelLuminance(g) +
  0.0722 * channelLuminance(b);

const hexToRgb = hex => {
  const h = hex.replace('#', '');
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
};

const contrast = (a, b) => {
  const la = luminanceOf(a);
  const lb = luminanceOf(b);
  const [hi, lo] = la > lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
};

/**
 * Mean colour of a logo's *opaque* pixels.
 *
 * Averaging the transparent surround would drag every logo toward whatever the
 * canvas was cleared to and make the answer meaningless, so alpha is the
 * filter rather than a weight.
 *
 * Returns null when the image cannot be read — a load failure, or a canvas
 * tainted by a cross-origin image served without CORS headers, where
 * `getImageData` throws.
 */
export function meanOpaqueColor(image) {
  try {
    const canvas = document.createElement('canvas');
    canvas.width = SAMPLE_SIZE;
    canvas.height = SAMPLE_SIZE;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return null;
    ctx.drawImage(image, 0, 0, SAMPLE_SIZE, SAMPLE_SIZE);

    const { data } = ctx.getImageData(0, 0, SAMPLE_SIZE, SAMPLE_SIZE);
    let r = 0;
    let g = 0;
    let b = 0;
    let n = 0;
    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3] > OPAQUE_ALPHA) {
        r += data[i];
        g += data[i + 1];
        b += data[i + 2];
        n += 1;
      }
    }
    if (n === 0) return null;
    return [Math.round(r / n), Math.round(g / n), Math.round(b / n)];
  } catch {
    // Tainted canvas, or no canvas support (jsdom). Caller plates.
    return null;
  }
}

/** Would this mean colour survive on the card ground unaided? */
export function colorNeedsPlate(rgb, ground = CARD_GROUND) {
  if (!rgb) return true;
  return contrast(rgb, hexToRgb(ground)) < LOGO_PLATE_MIN_CONTRAST;
}

/**
 * Load a logo and decide whether it needs a plate.
 *
 * Resolves `true` on every failure — a missing url, a load error, a tainted
 * canvas, or an image with no opaque pixels at all.
 */
export function logoNeedsPlate(url) {
  return new Promise(resolve => {
    if (!url || typeof document === 'undefined' || !window.Image) {
      resolve(true);
      return;
    }
    const img = new Image();
    // Required for getImageData to work on the storage-hosted logos. They are
    // served with `access-control-allow-origin: *`; anything that is not falls
    // back to plating rather than throwing.
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(colorNeedsPlate(meanOpaqueColor(img)));
    img.onerror = () => resolve(true);
    img.src = url;
  });
}
