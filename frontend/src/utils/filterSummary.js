/**
 * The one line a closed filter panel shows instead of its rows (SB-1714).
 *
 * Mirrors the Android summary (SB-1680): only what is narrowing the list,
 * joined with " · ". A part that is not narrowing anything ("All", no
 * conference picked) is passed as null and dropped.
 */

export const SEPARATOR = ' · ';

/** Join the non-empty parts. */
export const filterSummary = parts =>
  (parts || []).filter(p => typeof p === 'string' && p.trim()).join(SEPARATOR);

/**
 * Name a multi-select: up to `max` names verbatim, then a count.
 * Nothing selected is null — "every conference" narrows nothing.
 */
export const listSummary = (names, noun, max = 2) => {
  const picked = (names || []).filter(Boolean);
  if (picked.length === 0) return null;
  if (picked.length <= max) return picked.join(', ');
  return `${picked.length} ${noun}`;
};
