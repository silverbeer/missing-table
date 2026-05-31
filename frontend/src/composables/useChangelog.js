/**
 * useChangelog — load + parse the in-app changelog ("What's New").
 *
 * Source of truth is the repo-root CHANGELOG.md, copied to /changelog.md at
 * build time (scripts/copy-changelog.mjs). We fetch it, split it into release
 * sections on the `## [version] — title` headings, and render each body to
 * HTML with `marked`. "Seen" state is per-device in localStorage (matches
 * IosInstallTooltip) — used to chip releases that are new since the last visit.
 */

import { ref } from 'vue';
import { marked } from 'marked';

const SEEN_KEY = 'mt.changelog.lastSeenVersion';

const releases = ref([]);
const loaded = ref(false);
const loading = ref(false);
const error = ref(null);

// Heading form: "## [1.4.0] — Title"  or  "## [1.4.0]"
const HEADING_RE = /^##\s*\[([^\]]+)\]\s*(?:[—-]\s*(.*))?$/;

function parseChangelog(md) {
  const lines = md.split('\n');
  const out = [];
  let current = null;
  for (const line of lines) {
    const m = line.match(HEADING_RE);
    if (m) {
      if (current) out.push(current);
      current = { version: m[1].trim(), title: (m[2] || '').trim(), body: [] };
    } else if (current) {
      current.body.push(line);
    }
    // lines before the first release heading (the file's H1 + preamble) are ignored
  }
  if (current) out.push(current);
  return out.map(r => ({
    version: r.version,
    title: r.title,
    bodyHtml: marked.parse(r.body.join('\n').trim()),
  }));
}

// Compare dotted numeric versions: 1 if a>b, -1 if a<b, 0 if equal.
// Non-numeric/garbage segments sort as 0 so a malformed tag never crashes.
function compareVersions(a, b) {
  const pa = String(a)
    .split('.')
    .map(n => parseInt(n, 10) || 0);
  const pb = String(b)
    .split('.')
    .map(n => parseInt(n, 10) || 0);
  const len = Math.max(pa.length, pb.length);
  for (let i = 0; i < len; i++) {
    const d = (pa[i] || 0) - (pb[i] || 0);
    if (d !== 0) return d > 0 ? 1 : -1;
  }
  return 0;
}

function getLastSeen() {
  try {
    return localStorage.getItem(SEEN_KEY);
  } catch {
    return null;
  }
}

export function useChangelog() {
  const load = async () => {
    if (loaded.value || loading.value) return;
    loading.value = true;
    error.value = null;
    try {
      const res = await fetch('/changelog.md', { cache: 'no-cache' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const md = await res.text();
      releases.value = parseChangelog(md);
      loaded.value = true;
    } catch (err) {
      error.value = err.message || String(err);
      releases.value = [];
    } finally {
      loading.value = false;
    }
  };

  // A release is "new" if its version is strictly above the last-seen version.
  // With nothing seen yet, nothing is chipped (avoids flagging the whole list
  // as new on a user's first ever visit).
  const isNew = version => {
    const lastSeen = getLastSeen();
    if (!lastSeen) return false;
    return compareVersions(version, lastSeen) > 0;
  };

  // True when there is at least one release the user hasn't seen (newest >
  // last-seen). Also true on first visit (lastSeen null) so the page is
  // discoverable.
  const hasUnseen = () => {
    if (!releases.value.length) return false;
    const lastSeen = getLastSeen();
    if (!lastSeen) return true;
    return compareVersions(releases.value[0].version, lastSeen) > 0;
  };

  const markAllSeen = () => {
    if (!releases.value.length) return;
    try {
      localStorage.setItem(SEEN_KEY, releases.value[0].version);
    } catch {
      // private mode / storage disabled — best effort, ignore
    }
  };

  return {
    releases,
    loaded,
    loading,
    error,
    load,
    isNew,
    hasUnseen,
    markAllSeen,
  };
}

// Test-only: reset module-level singleton state.
export function _resetChangelogForTest() {
  releases.value = [];
  loaded.value = false;
  loading.value = false;
  error.value = null;
}

// Exported for unit tests.
export { parseChangelog, compareVersions };
