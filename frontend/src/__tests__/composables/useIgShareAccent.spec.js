/**
 * Accent-color resolution for the Instagram share cards (SB-628).
 *
 * The accent drives the eyebrow chip, the footer band and the torn-edge
 * underlay, so getting it wrong is visible on every shared post. Two
 * failure modes matter and neither is caught by "does it return a color":
 *
 *  - The seeded placeholder gray is not a brand color. 105 of 127 clubs
 *    carry it, so treating it as one would paint nearly every card the
 *    same dead gray.
 *  - Several clubs that DO set a color set a dark one (navy, near-black).
 *    Those are invisible on the dark card ground, so the accent would
 *    silently vanish on exactly the fixtures where a club bothered.
 */

import { describe, it, expect } from 'vitest';
import { ref } from 'vue';
import { useIgShareData, MT_ACCENT } from '@/composables/useIgShareData';

const makeMatch = (homeColor, awayColor) => ({
  home_team_name: 'Home FC',
  away_team_name: 'Away FC',
  home_team_club: homeColor ? { primary_color: homeColor } : null,
  away_team_club: awayColor ? { primary_color: awayColor } : null,
  match_date: '2026-08-23',
  age_group_name: 'U15',
  match_type_name: 'Friendly',
  season_name: '2026-2027',
});

const accentFor = (homeColor, awayColor) => {
  const { accentColor } = useIgShareData(
    ref(makeMatch(homeColor, awayColor)),
    ref('preview'),
    ref([])
  );
  return accentColor.value.toUpperCase();
};

const accentTextFor = (homeColor, awayColor) => {
  const { accentTextColor } = useIgShareData(
    ref(makeMatch(homeColor, awayColor)),
    ref('preview'),
    ref([])
  );
  return accentTextColor.value.toUpperCase();
};

describe('IG share accent color', () => {
  it('prefers the home club brand color when it is real and visible', () => {
    expect(accentFor('#B22222', '#B38B00')).toBe('#B22222');
  });

  it('falls through to the away club when home is the placeholder gray', () => {
    // The real NYCFC vs IFA case: NYCFC carries the seeded #6B7280,
    // IFA has actual gold.
    expect(accentFor('#6B7280', '#B38B00')).toBe('#B38B00');
  });

  it('treats the seeded secondary gray as a placeholder too', () => {
    expect(accentFor('#374151', '#B38B00')).toBe('#B38B00');
  });

  it('falls back to MT yellow when neither club has a real color', () => {
    expect(accentFor('#6B7280', '#6B7280')).toBe(MT_ACCENT.toUpperCase());
  });

  it('falls back to MT yellow when no club data is present at all', () => {
    expect(accentFor(null, null)).toBe(MT_ACCENT.toUpperCase());
  });

  it('rejects dark club colors that would vanish on the dark ground', () => {
    // Real values from the clubs table. Each is a genuine brand color and
    // each is unusable as an accent here.
    for (const dark of ['#00008B', '#0A2240', '#0b0a0f', '#000000']) {
      expect(accentFor(dark, null)).toBe(MT_ACCENT.toUpperCase());
    }
  });

  it('skips a dark home color but still uses a visible away color', () => {
    expect(accentFor('#000000', '#B38B00')).toBe('#B38B00');
  });

  it('ignores malformed color values rather than emitting them', () => {
    expect(accentFor('not-a-color', null)).toBe(MT_ACCENT.toUpperCase());
  });

  it('accepts 3-digit hex shorthand', () => {
    expect(accentFor('#FF0', null)).toBe('#FF0');
  });
});

describe('preseason friendly labelling', () => {
  const metaFor = overrides => {
    const { metaLabel } = useIgShareData(
      ref({
        home_team_name: 'Home FC',
        away_team_name: 'Away FC',
        match_type_name: 'Friendly',
        season_name: '2026-2027',
        ...overrides,
      }),
      ref('preview'),
      ref([])
    );
    return metaLabel.value;
  };

  it('labels a friendly just after the season opens as preseason', () => {
    // The real fixture: 2026-2027 opens 2026-08-01, match is 22 days in.
    expect(
      metaFor({ match_date: '2026-08-23', season_start_date: '2026-08-01' })
    ).toContain('PRESEASON FRIENDLY');
  });

  it('does NOT label a mid-season friendly as preseason', () => {
    // The Oct 2025 friendlies sit 40 days after the 2025-2026 opening.
    // Calling these preseason would be plainly wrong on a public post.
    const label = metaFor({
      match_date: '2025-10-11',
      season_start_date: '2025-09-01',
      season_name: '2025-2026',
    });
    expect(label).not.toContain('PRESEASON');
    expect(label).toContain('FRIENDLY');
  });

  it('never labels a non-friendly as preseason', () => {
    expect(
      metaFor({
        match_type_name: 'League',
        match_date: '2026-08-23',
        season_start_date: '2026-08-01',
      })
    ).not.toContain('PRESEASON');
  });

  it('prefers an explicit preseason_end_date over the date window', () => {
    // Once seasons.preseason_end_date exists it must win, including when
    // it disagrees with the heuristic.
    expect(
      metaFor({
        match_date: '2026-09-20',
        season_start_date: '2026-08-01',
        preseason_end_date: '2026-09-30',
      })
    ).toContain('PRESEASON FRIENDLY');

    expect(
      metaFor({
        match_date: '2026-08-23',
        season_start_date: '2026-08-01',
        preseason_end_date: '2026-08-10',
      })
    ).not.toContain('PRESEASON');
  });

  it('falls back to plain Friendly when the season start is unknown', () => {
    // Older payloads have no season_start_date; guessing would be worse
    // than saying less.
    const label = metaFor({ match_date: '2026-08-23' });
    expect(label).not.toContain('PRESEASON');
    expect(label).toContain('FRIENDLY');
  });
});

describe('IG share accent text color', () => {
  it('uses dark text on a light accent', () => {
    expect(accentTextFor('#FFC400', null)).toBe('#0B0B0D');
  });

  it('uses white text on a mid/dark accent', () => {
    expect(accentTextFor('#B22222', null)).toBe('#FFFFFF');
  });

  it('pairs dark text with the MT yellow fallback', () => {
    // The fallback path and the contrast-aware text color have to agree,
    // or the default card ships white-on-yellow.
    expect(accentTextFor('#6B7280', '#6B7280')).toBe('#0B0B0D');
  });
});
