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
 *
 * Signed in, the same memory is also kept on the account (SB-1715) so it
 * follows the viewer to another device. The browser copy is still written
 * first and still read first; the server copy wins only when it was saved
 * later (`savedAt`, client clock). Server writes are debounced — a burst of
 * chip clicks is one request — and never block or fail the tab.
 */

import { getApiBaseUrl } from '../config/api';
import { useAuthStore } from '../stores/auth';

// Bump when the stored shape changes: a stale entry is then dropped whole
// rather than half-applied.
const VERSION = 'v1';
const PREFIX = 'mt.filters';

/** Per viewer — two people on one iPad must not inherit each other's filters. */
const storageKey = (view, userKey) =>
  `${PREFIX}.${VERSION}.${view}.${userKey || 'anon'}`;

// Panel open/closed (SB-1714). Per viewer since SB-1715; the per-browser key
// it used before is still read once, so nobody's choice resets on upgrade.
const PANEL_PREFIX = 'mt.filterPanel.v1';
const panelKey = (view, userKey) =>
  `${PANEL_PREFIX}.${view}.${userKey || 'anon'}`;
const legacyPanelKey = view => `${PANEL_PREFIX}.${view}`;

/** How long a burst of filter changes waits before one server write. */
export const SYNC_DEBOUNCE_MS = 1500;

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

const readJson = key => {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? parsed
      : null;
  } catch {
    return null;
  }
};

const write = (key, value) => {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Private mode, a full quota, storage disabled. The tab still works.
  }
};

const remove = key => {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Nothing to do, and nothing worth failing a render over.
  }
};

const withoutStamp = stored => {
  if (!stored) return null;
  const filters = { ...stored };
  delete filters.savedAt;
  return filters;
};

/**
 * The account side, over the auth store: the profile `/api/auth/me` loaded
 * (`filter_memory`), and a PUT per view. Signed out, there is no account
 * side — `entry` is undefined and `put` is never called.
 */
export const accountRemote = () => {
  let store = null;
  try {
    store = useAuthStore();
  } catch {
    return null;
  }
  const profile = () => store?.state?.profile ?? null;
  return {
    active: () => Boolean(store?.isAuthenticated?.value && profile()),
    entry: view => profile()?.filter_memory?.[view],
    // Keep the loaded profile in step, so a re-mount in this session reads
    // what was just saved rather than what /me said at sign-in.
    remember: (view, patch) => {
      const p = profile();
      if (!p) return;
      const memory = { ...(p.filter_memory || {}) };
      memory[view] = { ...(memory[view] || {}), ...patch };
      p.filter_memory = memory;
    },
    put: (view, body) =>
      store.apiRequest(`${getApiBaseUrl()}/api/auth/filter-memory/${view}`, {
        method: 'PUT',
        body: JSON.stringify(body),
        keepalive: true,
      }),
  };
};

// One pending server write per view and viewer, shared by every caller, so
// Table and its FilterPanel merge into one request instead of racing.
const pending = new Map();

const send = (id, job) => {
  pending.delete(id);
  clearTimeout(job.timer);
  Promise.resolve()
    .then(() => job.remote.put(job.view, job.body))
    .catch(() => {
      // The browser copy already has it; the next change tries again.
    });
};

/** Send every queued write now — the tab is going away. */
export const flushFilterMemory = () => {
  for (const [id, job] of [...pending]) send(id, job);
};

if (typeof window !== 'undefined') {
  window.addEventListener('pagehide', flushFilterMemory);
}

const queue = (remote, view, userKey, patch) => {
  if (!remote?.active?.() || !userKey) return;
  const id = `${view}.${userKey}`;
  const prior = pending.get(id);
  clearTimeout(prior?.timer);
  const job = {
    remote,
    view,
    body: { ...(prior?.body || {}), ...patch, saved_at: Date.now() },
  };
  job.timer = setTimeout(() => send(id, job), SYNC_DEBOUNCE_MS);
  pending.set(id, job);
};

/**
 * Read and write one tab's remembered filters.
 *
 * `userKey` is read at call time rather than captured, so a sign-in or
 * sign-out moves subsequent reads and writes to the other viewer's key
 * without the component re-mounting.
 *
 * `remote` is the account side; tests pass their own, `null` turns it off.
 */
export const useFilterMemory = (view, userKey, { remote } = {}) => {
  const account = remote === undefined ? accountRemote() : remote;
  const user = () => userKey?.();
  const key = () => storageKey(view, user());

  /** The newer of this browser's copy and the account's, without its stamp. */
  const load = () => {
    const local = readJson(key());
    const entry = user() ? account?.entry?.(view) : undefined;
    const server = entry && 'filters' in entry ? entry.filters : undefined;
    if (server === undefined) return withoutStamp(local);

    const localAt = Number(local?.savedAt) || 0;
    const serverAt = Number(server?.savedAt ?? entry.saved_at) || 0;
    if (serverAt <= localAt) return withoutStamp(local);

    // The account is newer: adopt it here too, or forget if it was cleared.
    if (server === null || typeof server !== 'object') {
      remove(key());
      return null;
    }
    write(key(), JSON.stringify(server));
    return withoutStamp(server);
  };

  const save = filters => {
    const stamped = { ...filters, savedAt: Date.now() };
    write(key(), JSON.stringify(stamped));
    if (!user()) return;
    account?.remember?.(view, { filters: stamped });
    queue(account, view, user(), { filters: stamped });
  };

  const clear = () => {
    remove(key());
    if (!user()) return;
    const forgotten = { filters: null, saved_at: Date.now() };
    account?.remember?.(view, forgotten);
    queue(account, view, user(), { filters: null });
  };

  /** Open until first closed; this browser's choice, then the account's. */
  const loadPanel = () => {
    try {
      const mine = window.localStorage.getItem(panelKey(view, user()));
      if (mine === 'open' || mine === 'closed') return mine === 'open';
      // Pre-SB-1715 per-browser choice: the first viewer to read it takes
      // it, so a second person on this browser starts from the default.
      const legacy = window.localStorage.getItem(legacyPanelKey(view));
      if (legacy === 'open' || legacy === 'closed') {
        window.localStorage.setItem(panelKey(view, user()), legacy);
        window.localStorage.removeItem(legacyPanelKey(view));
        return legacy === 'open';
      }
    } catch {
      // Unreadable storage: fall through to the account, then the default.
    }
    const remembered = user() ? account?.entry?.(view)?.panel_open : undefined;
    return typeof remembered === 'boolean' ? remembered : true;
  };

  const savePanel = open => {
    write(panelKey(view, user()), open ? 'open' : 'closed');
    if (!user()) return;
    account?.remember?.(view, { panel_open: open });
    queue(account, view, user(), { panel_open: open });
  };

  return { load, save, clear, loadPanel, savePanel };
};
