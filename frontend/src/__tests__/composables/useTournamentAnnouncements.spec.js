/**
 * useTournamentAnnouncements (SB-1797): the Tournaments tab dot.
 *
 * Dot while an active tournament carries an announcement this browser has
 * not seen; opening the tab marks it seen; an edited announcement is new
 * again; a failed fetch means no dot, never an error.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({}) }));

import {
  useTournamentAnnouncements,
  announcementText,
  announcementKey,
  hashText,
  SEEN_STORAGE_KEY,
  _resetTournamentAnnouncements,
} from '@/composables/useTournamentAnnouncements';

const LINE = 'Every MLS NEXT Fest match scored live';
const FEST = {
  id: 6,
  name: 'MLS NEXT Fest',
  is_active: true,
  announcement: LINE,
};
const PLAIN = {
  id: 7,
  name: 'Winter Cup',
  is_active: true,
  announcement: null,
};

const list =
  (...ts) =>
  () =>
    Promise.resolve(ts);

beforeEach(() => {
  localStorage.clear();
  _resetTournamentAnnouncements();
  vi.spyOn(console, 'warn').mockImplementation(() => {});
});

describe('announcementText', () => {
  it('trims, and treats blank or missing as absent', () => {
    expect(announcementText({ announcement: `  ${LINE} ` })).toBe(LINE);
    expect(announcementText({ announcement: '   ' })).toBe(null);
    expect(announcementText({ announcement: null })).toBe(null);
    expect(announcementText({})).toBe(null);
    expect(announcementText(null)).toBe(null);
  });
});

describe('announcementKey', () => {
  it('is the id plus a hash of the text', () => {
    expect(announcementKey(FEST)).toBe(`6:${hashText(LINE)}`);
    expect(announcementKey(PLAIN)).toBe(null);
  });

  it('changes when the text changes', () => {
    expect(hashText(LINE)).not.toBe(hashText(`${LINE}!`));
  });
});

describe('useTournamentAnnouncements', () => {
  it('shows the dot for an unseen announcement', async () => {
    const a = useTournamentAnnouncements();
    await a.load(list(FEST, PLAIN));
    expect(a.hasUnseen.value).toBe(true);
  });

  it('no announcements: no dot', async () => {
    const a = useTournamentAnnouncements();
    await a.load(list(PLAIN));
    expect(a.hasUnseen.value).toBe(false);
  });

  it('ignores an inactive tournament', async () => {
    const a = useTournamentAnnouncements();
    await a.load(list({ ...FEST, is_active: false }));
    expect(a.hasUnseen.value).toBe(false);
  });

  it('marking seen clears the dot and persists it', async () => {
    const a = useTournamentAnnouncements();
    await a.load(list(FEST));
    a.markSeen();
    expect(a.hasUnseen.value).toBe(false);
    expect(JSON.parse(localStorage.getItem(SEEN_STORAGE_KEY))).toEqual([
      announcementKey(FEST),
    ]);
  });

  it('a seen announcement shows no dot on the next load', async () => {
    localStorage.setItem(
      SEEN_STORAGE_KEY,
      JSON.stringify([announcementKey(FEST)])
    );
    _resetTournamentAnnouncements();
    const a = useTournamentAnnouncements();
    await a.load(list(FEST));
    expect(a.hasUnseen.value).toBe(false);
  });

  it('a changed announcement shows the dot again', async () => {
    localStorage.setItem(
      SEEN_STORAGE_KEY,
      JSON.stringify([announcementKey(FEST)])
    );
    _resetTournamentAnnouncements();
    const a = useTournamentAnnouncements();
    await a.load(list({ ...FEST, announcement: 'Fest finals streamed live' }));
    expect(a.hasUnseen.value).toBe(true);
  });

  it('a failed fetch shows no dot', async () => {
    const a = useTournamentAnnouncements();
    await a.load(() => Promise.reject(new Error('offline')));
    expect(a.hasUnseen.value).toBe(false);
  });

  it('a corrupt seen list is treated as empty', async () => {
    localStorage.setItem(SEEN_STORAGE_KEY, '{not json');
    _resetTournamentAnnouncements();
    const a = useTournamentAnnouncements();
    await a.load(list(FEST));
    expect(a.hasUnseen.value).toBe(true);
  });

  it('fetches once per app load', async () => {
    const fetcher = vi.fn(list(FEST));
    const a = useTournamentAnnouncements();
    await a.load(fetcher);
    await a.load(fetcher);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('marking seen before the list arrives keeps nothing and shows the dot after', async () => {
    const a = useTournamentAnnouncements();
    a.markSeen();
    expect(localStorage.getItem(SEEN_STORAGE_KEY)).toBe(null);
    await a.load(list(FEST));
    expect(a.hasUnseen.value).toBe(true);
  });
});
