import { describe, it, expect } from 'vitest';
import {
  cleanReasons,
  hasReasons,
  reasonMarker,
  REASONS_MAX,
  REASON_TEXT_MAX,
} from '@/utils/featuredReasons';

describe('featuredReasons (SB-1577)', () => {
  it('hasReasons is true only for a non-empty array', () => {
    expect(hasReasons(null)).toBe(false);
    expect(hasReasons(undefined)).toBe(false);
    expect(hasReasons([])).toBe(false);
    expect(hasReasons([{ text: 'x' }])).toBe(true);
  });

  it('knows the standard kinds and defaults the rest', () => {
    expect(reasonMarker('standings').icon).toBe('📊');
    expect(reasonMarker('form').label).toBe('Form');
    expect(reasonMarker('something-new')).toEqual({
      value: null,
      label: null,
      icon: '▸',
    });
    expect(reasonMarker(null).icon).toBe('▸');
  });

  it('trims, drops blank rows and nulls an empty kind', () => {
    expect(
      cleanReasons([
        { text: '  1st vs 3rd ', kind: 'standings' },
        { text: '   ', kind: 'form' },
        { text: 'Unbeaten', kind: '' },
      ])
    ).toEqual([
      { text: '1st vs 3rd', kind: 'standings' },
      { text: 'Unbeaten', kind: null },
    ]);
  });

  it('all rows removed saves [], never null', () => {
    expect(cleanReasons([])).toEqual([]);
    expect(cleanReasons([{ text: '' }])).toEqual([]);
  });

  it('caps the count and the text length at the API limits', () => {
    const rows = Array.from({ length: 9 }, (_, i) => ({ text: `r${i}` }));
    expect(cleanReasons(rows)).toHaveLength(REASONS_MAX);
    const long = cleanReasons([{ text: 'x'.repeat(500) }]);
    expect(long[0].text).toHaveLength(REASON_TEXT_MAX);
  });
});
