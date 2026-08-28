/**
 * logoPlate.js — plate a tournament logo only when it needs one (SB-901).
 *
 * The share-card templates drew every tournament logo on a white chip. The
 * reason was sound — a dark logo vanishes against the dark card ground — but
 * applying it to every logo put a light crest in a white box that clashed with
 * the unplated MLS Next badge beside it.
 *
 * The rule these guard: **plating is the safe default.** No logo may ever end
 * up invisible because the check could not run.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import {
  LOGO_PLATE_MIN_CONTRAST,
  colorNeedsPlate,
  logoNeedsPlate,
  meanOpaqueColor,
} from '@/utils/logoPlate';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('colorNeedsPlate — measured against the real logo set', () => {
  it('leaves the Copa Rayados crest unplated', () => {
    // Sampled from the live PNG: mean of its opaque pixels, contrast 7.36
    // against the card ground.
    expect(colorNeedsPlate([144, 160, 179])).toBe(false);
  });

  it('leaves the National Academy Championships crest unplated', () => {
    // Contrast 7.60.
    expect(colorNeedsPlate([153, 163, 162])).toBe(false);
  });

  it('plates a near-black logo, which is the case the chip exists for', () => {
    // Contrast 1.01 against the card ground — invisible without a plate.
    expect(colorNeedsPlate([10, 10, 12])).toBe(true);
  });

  it('leaves white and mid-grey logos unplated', () => {
    expect(colorNeedsPlate([255, 255, 255])).toBe(false);
    expect(colorNeedsPlate([110, 110, 110])).toBe(false);
  });

  it('plates when the colour is unknown', () => {
    expect(colorNeedsPlate(null)).toBe(true);
  });

  it('uses the same threshold the accent picker already applies', () => {
    expect(LOGO_PLATE_MIN_CONTRAST).toBe(2.5);
  });
});

describe('meanOpaqueColor — the transparent surround must not count', () => {
  const fakeCanvas = data => {
    const ctx = {
      drawImage: vi.fn(),
      getImageData: () => ({ data: Uint8ClampedArray.from(data) }),
    };
    vi.spyOn(document, 'createElement').mockReturnValue({
      getContext: () => ctx,
      set width(_) {},
      set height(_) {},
    });
  };

  it('averages only pixels above the alpha cutoff', () => {
    // One opaque white pixel, one fully transparent black one. Averaging the
    // transparent pixel in would drag the answer toward black and make every
    // logo look like it needs a plate.
    fakeCanvas([255, 255, 255, 255, 0, 0, 0, 0]);

    expect(meanOpaqueColor({})).toEqual([255, 255, 255]);
  });

  it('returns null when nothing is opaque', () => {
    fakeCanvas([0, 0, 0, 0, 10, 10, 10, 5]);

    expect(meanOpaqueColor({})).toBeNull();
  });

  it('returns null when the canvas is tainted', () => {
    // A cross-origin logo served without CORS headers makes getImageData
    // throw. The caller must plate rather than propagate the error.
    vi.spyOn(document, 'createElement').mockReturnValue({
      getContext: () => ({
        drawImage: vi.fn(),
        getImageData: () => {
          throw new DOMException('Tainted canvases may not be exported.');
        },
      }),
      set width(_) {},
      set height(_) {},
    });

    expect(meanOpaqueColor({})).toBeNull();
  });
});

describe('logoNeedsPlate — every failure path plates', () => {
  it('plates when there is no url', async () => {
    await expect(logoNeedsPlate(null)).resolves.toBe(true);
    await expect(logoNeedsPlate('')).resolves.toBe(true);
  });

  it('plates when the image fails to load', async () => {
    class FailingImage {
      set src(_) {
        queueMicrotask(() => this.onerror?.());
      }
    }
    vi.stubGlobal('Image', FailingImage);

    await expect(logoNeedsPlate('https://example.test/logo.png')).resolves.toBe(
      true
    );
  });

  it('requests the image with crossOrigin so it can be sampled at all', async () => {
    // Without this, getImageData throws on every storage-hosted logo and the
    // feature silently degrades to always plating.
    const seen = {};
    class RecordingImage {
      set crossOrigin(v) {
        seen.crossOrigin = v;
      }
      set src(_) {
        queueMicrotask(() => this.onerror?.());
      }
    }
    vi.stubGlobal('Image', RecordingImage);

    await logoNeedsPlate('https://example.test/logo.png');

    expect(seen.crossOrigin).toBe('anonymous');
  });
});
