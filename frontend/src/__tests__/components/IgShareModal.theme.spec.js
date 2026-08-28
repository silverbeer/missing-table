/**
 * IgShareModal theming guard (SB-897).
 *
 * The bug: the modal chrome was pinned light (`background: #ffffff` and 37
 * other hardcoded hexes) while some of its text picked up the semantic token.
 * In dark mode that rendered the dark theme's foreground on a white panel.
 *
 * Measured on production before the fix, dark mode, modal open:
 *
 *   .ig-modal-panel background   rgb(255, 255, 255)
 *   disabled template label      rgb(232, 238, 247)
 *   contrast                     1.11 : 1      (WCAG AA wants 4.5)
 *
 *   8 of 28 text nodes failed AA; six sat at 1.11.
 *
 * jsdom does not apply `<style scoped>`, so computed-style assertions are not
 * available here. This reads the component source instead and fails if a
 * hardcoded colour comes back — which is exactly how the regression would
 * return.
 */

import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(
  resolve(here, '../../components/IgShareModal.vue'),
  'utf8'
);
const styleBlock = source.split('<style scoped>')[1] ?? '';

/**
 * The one colour that is deliberately fixed: the letterbox behind the
 * 1080x1080 preview. The card is dark-designed whatever theme the author is
 * using — it is an exported image, not UI — so tokenising it would make the
 * preview disagree with the PNG people actually post.
 */
const ALLOWED_FIXED = ['#0f172a'];

describe('IgShareModal — chrome follows the theme', () => {
  it('has no hardcoded hex colours beyond the preview letterbox', () => {
    const hexes = styleBlock.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [];
    const unexpected = hexes.filter(
      h => !ALLOWED_FIXED.includes(h.toLowerCase())
    );

    expect(unexpected).toEqual([]);
  });

  it('does not paint text or surfaces with the literal keyword white', () => {
    // `color: white` on a token-coloured background is the other half of the
    // same bug, just pointed the other way.
    expect(styleBlock).not.toMatch(/:\s*white\s*;/);
  });

  it('uses the app semantic tokens for panel, text and borders', () => {
    for (const token of [
      '--color-card',
      '--color-surface-alt',
      '--color-fg',
      '--color-fg-muted',
      '--color-line',
    ]) {
      expect(styleBlock).toContain(token);
    }
  });

  it('keeps the preview letterbox fixed, with a comment saying why', () => {
    // Guards against a future "tokenise everything" pass silently changing
    // what the exported card looks like.
    expect(styleBlock).toMatch(/Deliberately NOT a theme token/);
    expect(styleBlock).toContain('#0f172a');
  });

  it('states disabled options with colour rather than fading them out', () => {
    // `opacity: 0.45` over a fixed white panel is what produced 1.11:1.
    expect(styleBlock).toMatch(
      /\.ig-accent-disabled\s*\{[^}]*--color-fg-muted/
    );
  });
});
