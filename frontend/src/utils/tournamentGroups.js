/**
 * Tournament group format (SB-1752).
 *
 * A tournament match carries one free-text `tournament_group`. Events that run
 * several competitions side by side (MLS NEXT Fest: Homegrown Division,
 * Academy Division) reuse the same labels in each — both have a "Group A" — so
 * the stored value is namespaced by division:
 *
 *   "HD · A"         division "HD", label "A"
 *   "HD · Showcase"  division "HD", label "Showcase"
 *   "Bracket A"      legacy, no division — displayed unchanged
 *
 * The format is frozen: bracket follows store this string, so changing the
 * separator orphans every follow already saved. This mirrors
 * `backend/dao/tournament_groups.py`; change one and change the other.
 *
 * The frozen format has three parts, and the two implementations must agree on
 * each byte for byte:
 *
 * - the separator, `GROUP_SEPARATOR`;
 * - the characters trimmed from a part, `GROUP_WHITESPACE` — an explicit list,
 *   because `trim()` and Python's `str.strip()` disagree (JS trims U+FEFF,
 *   Python trims U+001C-U+001F and U+0085);
 * - the compose rule: a division cannot contain the separator, nor can a label
 *   that has no division, since either would split back into different parts.
 *   A label containing the separator *with* a division is legal — the split
 *   is on the first separator only.
 */

// Space, U+00B7 MIDDLE DOT, space.
export const GROUP_SEPARATOR = ' \u00b7 ';

// Every character trimmed from a part: the union of what trim() and Python's
// str.strip() remove. Same literal as tournament_groups.py.
export const GROUP_WHITESPACE =
  '\t\n\u000b\u000c\r \u001c\u001d\u001e\u001f\u0085\u00a0\u1680' +
  '\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a' +
  '\u2028\u2029\u202f\u205f\u3000\ufeff';

export const DIVISION_SEPARATOR_ERROR =
  "A tournament group division cannot contain ' \u00b7 ' or end with ' \u00b7'";
export const LABEL_SEPARATOR_ERROR =
  "A tournament group label cannot contain ' \u00b7 ' unless a division is given";

// Trim GROUP_WHITESPACE from a part; null, empty and whitespace-only collapse
// to null.
function clean(part) {
  if (part === null || part === undefined) return null;
  const text = String(part);
  let start = 0;
  let end = text.length;
  while (start < end && GROUP_WHITESPACE.includes(text[start])) start += 1;
  while (end > start && GROUP_WHITESPACE.includes(text[end - 1])) end -= 1;
  return start === end ? null : text.slice(start, end);
}

/**
 * Build the stored `tournament_group` value from its two parts. A missing part
 * is left out, so a label on its own stays a legacy un-namespaced value.
 * Returns null when both are missing.
 *
 * Throws an Error for parts that would not split back into themselves: a
 * division that contains the separator (or ends with " ·", which forms one
 * with the separator that follows), and a label that contains the separator
 * when there is no division.
 */
export function composeGroup(division, label) {
  const d = clean(division);
  const l = clean(label);
  if (d && `${d}${GROUP_SEPARATOR}`.indexOf(GROUP_SEPARATOR) !== d.length) {
    throw new Error(DIVISION_SEPARATOR_ERROR);
  }
  if (l && !d && l.includes(GROUP_SEPARATOR)) {
    throw new Error(LABEL_SEPARATOR_ERROR);
  }
  if (d && l) return `${d}${GROUP_SEPARATOR}${l}`;
  return d || l;
}

/**
 * Split a stored `tournament_group` into `{ division, label }`. Splits on the
 * first separator only. A value with no separator is a legacy group: division
 * null, label the value as stored. Never throws — a stored value always
 * splits, whatever `composeGroup` would say about it today.
 */
export function splitGroup(value) {
  const v = clean(value);
  if (v === null) return { division: null, label: null };
  const at = v.indexOf(GROUP_SEPARATOR);
  if (at === -1) return { division: null, label: v };
  return {
    division: clean(v.slice(0, at)),
    label: clean(v.slice(at + GROUP_SEPARATOR.length)),
  };
}
