/**
 * "Why this is the Match of the Week/Day" reasons (SB-1552, SB-1577).
 *
 * A reason is `{ text, kind }`. `kind` is free text on the API (≤40 chars) so
 * the agent can grow the vocabulary without a migration; the UI knows the
 * kinds below and gives anything else the default marker.
 */

export const REASON_TEXT_MAX = 200; // FeaturedReason.text in app.py
export const REASONS_MAX = 6; // MotwPick.reasons max_length

export const REASON_KINDS = [
  { value: 'standings', label: 'Table', icon: '📊' },
  { value: 'form', label: 'Form', icon: '🔥' },
  { value: 'stakes', label: 'Stakes', icon: '🏆' },
  { value: 'rivalry', label: 'Rivalry', icon: '⚔️' },
  { value: 'storyline', label: 'Storyline', icon: '📖' },
];

const BY_VALUE = Object.fromEntries(REASON_KINDS.map(k => [k.value, k]));

/** Marker for a reason's kind; unknown or missing kinds get the plain one. */
export function reasonMarker(kind) {
  return BY_VALUE[kind] || { value: null, label: null, icon: '▸' };
}

/** True only for a non-empty array: null and [] both render nothing. */
export function hasReasons(reasons) {
  return Array.isArray(reasons) && reasons.length > 0;
}

/**
 * Editor rows → the API's list. Blank lines are dropped, text is trimmed and
 * capped, empty kind becomes null. All lines removed saves `[]` (provided,
 * empty) — never null, which would mean "nobody ever wrote any".
 */
export function cleanReasons(rows) {
  return (rows || [])
    .map(r => ({
      text: String(r?.text ?? '')
        .trim()
        .slice(0, REASON_TEXT_MAX),
      kind: r?.kind ? String(r.kind) : null,
    }))
    .filter(r => r.text !== '')
    .slice(0, REASONS_MAX);
}
