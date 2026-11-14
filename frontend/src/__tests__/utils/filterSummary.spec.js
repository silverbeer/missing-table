import { describe, it, expect } from 'vitest';
import { filterSummary, listSummary } from '@/utils/filterSummary';

describe('filterSummary (SB-1714)', () => {
  it('joins the parts that narrow the list', () => {
    expect(filterSummary(['2026-2027', 'U15', null, 'Flex', ''])).toBe(
      '2026-2027 · U15 · Flex'
    );
  });

  it('is empty when nothing narrows', () => {
    expect(filterSummary([null, undefined, '  '])).toBe('');
    expect(filterSummary(undefined)).toBe('');
  });
});

describe('listSummary', () => {
  it('no selection narrows nothing — null, not "0 conferences"', () => {
    expect(listSummary([], 'conferences')).toBeNull();
  });

  it('names up to two, then counts', () => {
    expect(listSummary(['Northeast'], 'conferences')).toBe('Northeast');
    expect(listSummary(['Northeast', 'Empire'], 'conferences')).toBe(
      'Northeast, Empire'
    );
    expect(
      listSummary(['Northeast', 'Empire', 'Turnpike'], 'conferences')
    ).toBe('3 conferences');
  });
});
