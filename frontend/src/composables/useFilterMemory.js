/**
 * Remembered filter state for the Table and Matches tabs (SB-1112).
 *
 * Both tabs are `v-if` in App.vue, so they unmount on leave and re-mount on
 * their defaults — set U15 / Northeast / Flex, glance at the other tab, and
 * you are back on U14. This stores what the viewer last had and hands it back
 * on the next mount.
 *
 * Two rules shape the whole thing:
 *
 * 1. **Stored ids are claims about data that may have moved.** A saved
 *    division from a season the viewer no longer has, restored blindly,
 *    strands them on an empty list with nothing on screen explaining why —
 *    worse than the reset this replaces. Nothing is applied without being
 *    checked against the lists the component actually fetched, which is why
 *    this module reads but never restores on its own.
 * 2. **localStorage is allowed to fail.** Safari's private mode throws on
 *    write, and a remembered filter is never worth a blank tab. Every access
 *    is wrapped; a failure degrades to "no memory", not to an error.
 */

// Bump when the stored shape changes: a stale entry is then dropped whole
// rather than half-applied.
const VERSION = 'v1';
const PREFIX = 'mt.filters';

/** Per viewer — two people on one iPad must not inherit each other's filters. */
const storageKey = (view, userKey) =>
  `${PREFIX}.${VERSION}.${view}.${userKey || 'anon'}`;

/**
 * Keep only the ids that exist in `available`, as numbers.
 *
 * Used for the division chips, where dropping the unknown ones and keeping
 * the rest is right: all of them unknown lands on `[]`, which is the "every
 * division" state (SB-1007), not an empty table.
 */
export const keepKnownIds = (saved, available) => {
  if (!Array.isArray(saved)) return [];
  const known = new Set(
    (available || []).map(item => Number(item?.id ?? item))
  );
  return saved.map(Number).filter(id => known.has(id));
};

/** The saved id when the list still has it, otherwise null. */
export const knownId = (saved, available) => {
  if (saved === null || saved === undefined || saved === '') return null;
  const known = new Set(
    (available || []).map(item => Number(item?.id ?? item))
  );
  return known.has(Number(saved)) ? Number(saved) : null;
};

/** The saved name when the list still has it, otherwise null. Case-exact. */
export const knownName = (saved, available) => {
  if (!saved) return null;
  const known = new Set((available || []).map(item => item?.name ?? item));
  return known.has(saved) ? saved : null;
};

/**
 * Read and write one tab's remembered filters.
 *
 * `userKey` is read at call time rather than captured, so a sign-in or
 * sign-out moves subsequent reads and writes to the other viewer's key
 * without the component re-mounting.
 */
export const useFilterMemory = (view, userKey) => {
  const key = () => storageKey(view, userKey?.());

  const load = () => {
    try {
      const raw = window.localStorage.getItem(key());
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : null;
    } catch {
      return null;
    }
  };

  const save = filters => {
    try {
      window.localStorage.setItem(key(), JSON.stringify(filters));
    } catch {
      // Private mode, a full quota, storage disabled. The tab still works.
    }
  };

  const clear = () => {
    try {
      window.localStorage.removeItem(key());
    } catch {
      // Nothing to do, and nothing worth failing a render over.
    }
  };

  return { load, save, clear };
};
