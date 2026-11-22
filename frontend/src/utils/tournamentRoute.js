/**
 * The Tournaments tab's URLs (SB-1767).
 *
 * There is no router. `/tournaments` is the season index and
 * `/tournaments/<id>` is one tournament, so a tournament can be shared and
 * survives a hard reload. App.vue decides which tab a path opens;
 * TournamentMatchCenter decides index vs detail. Both read the path through
 * `parseTournamentPath`, so they cannot disagree about what it means.
 *
 * Pure: no window, no history — callers pass the pathname in.
 */

const TOURNAMENTS_RE = /^\/tournaments(?:\/([^/]*))?\/?$/;

/**
 * What a pathname asks the Tournaments tab for.
 *
 *   '/tournaments'      → { kind: 'index' }
 *   '/tournaments/12'   → { kind: 'detail', id: 12 }
 *   '/tournaments/abc'  → { kind: 'index' }  (not an id; still the tab)
 *   anything else       → null               (not a tournaments path)
 */
export function parseTournamentPath(pathname) {
  if (typeof pathname !== 'string') return null;
  const match = TOURNAMENTS_RE.exec(pathname);
  if (!match) return null;
  const segment = match[1];
  if (segment && /^\d+$/.test(segment)) {
    const id = Number(segment);
    if (Number.isSafeInteger(id) && id > 0) return { kind: 'detail', id };
  }
  return { kind: 'index' };
}

/** `/tournaments`, or `/tournaments/<id>` when an id is given. */
export function tournamentPath(id = null) {
  return id == null ? '/tournaments' : `/tournaments/${id}`;
}
