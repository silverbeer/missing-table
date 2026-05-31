/**
 * useChangelog tests — parsing, version compare, seen-state.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  useChangelog,
  parseChangelog,
  compareVersions,
  _resetChangelogForTest,
} from '@/composables/useChangelog';

const SAMPLE = `# Changelog

Preamble that should be ignored.

## [1.4.0] — Follow brackets + score-first notifications

### Added
- Follow a tournament bracket.

## [1.3.1]

- Baseline.
`;

beforeEach(() => {
  _resetChangelogForTest();
  localStorage.clear();
  vi.restoreAllMocks();
});

describe('parseChangelog', () => {
  it('splits into releases newest-first, ignoring the preamble', () => {
    const releases = parseChangelog(SAMPLE);
    expect(releases.map(r => r.version)).toEqual(['1.4.0', '1.3.1']);
    expect(releases[0].title).toBe(
      'Follow brackets + score-first notifications'
    );
    // Body rendered to HTML by marked.
    expect(releases[0].bodyHtml).toContain('<li>');
    expect(releases[0].bodyHtml).toContain('Follow a tournament bracket');
  });

  it('handles a heading with no title', () => {
    const releases = parseChangelog(SAMPLE);
    expect(releases[1].version).toBe('1.3.1');
    expect(releases[1].title).toBe('');
  });
});

describe('compareVersions', () => {
  it('orders dotted numeric versions', () => {
    expect(compareVersions('1.4.0', '1.3.1')).toBe(1);
    expect(compareVersions('1.3.1', '1.4.0')).toBe(-1);
    expect(compareVersions('1.4.0', '1.4.0')).toBe(0);
    expect(compareVersions('1.4.1', '1.4.0')).toBe(1);
  });

  it('treats garbage segments as zero without throwing', () => {
    expect(() => compareVersions('x.y', '1.0')).not.toThrow();
    expect(compareVersions('1.0', 'x.y')).toBe(1);
  });
});

describe('useChangelog.load', () => {
  it('fetches /changelog.md and populates releases', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve(SAMPLE),
    });

    const { load, releases, loaded } = useChangelog();
    await load();

    expect(global.fetch).toHaveBeenCalledWith(
      '/changelog.md',
      expect.objectContaining({ cache: 'no-cache' })
    );
    expect(loaded.value).toBe(true);
    expect(releases.value).toHaveLength(2);
  });

  it('sets error and empty releases on fetch failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 });
    const { load, error, releases } = useChangelog();
    await load();
    expect(error.value).toContain('404');
    expect(releases.value).toEqual([]);
  });
});

describe('useChangelog seen-state', () => {
  async function loaded() {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve(SAMPLE),
    });
    const c = useChangelog();
    await c.load();
    return c;
  }

  it('isNew is false on first visit (nothing seen yet)', async () => {
    const { isNew } = await loaded();
    expect(isNew('1.4.0')).toBe(false);
  });

  it('isNew flags versions above the last-seen', async () => {
    localStorage.setItem('mt.changelog.lastSeenVersion', '1.3.1');
    const { isNew } = await loaded();
    expect(isNew('1.4.0')).toBe(true);
    expect(isNew('1.3.1')).toBe(false);
  });

  it('hasUnseen true when newest > last-seen, false once caught up', async () => {
    localStorage.setItem('mt.changelog.lastSeenVersion', '1.3.1');
    const c = await loaded();
    expect(c.hasUnseen()).toBe(true);
    c.markAllSeen();
    expect(localStorage.getItem('mt.changelog.lastSeenVersion')).toBe('1.4.0');
    expect(c.hasUnseen()).toBe(false);
    expect(c.isNew('1.4.0')).toBe(false);
  });
});
