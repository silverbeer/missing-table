import { describe, it, expect } from 'vitest';
import {
  DIVISION_SEPARATOR_ERROR,
  GROUP_SEPARATOR,
  GROUP_WHITESPACE,
  LABEL_SEPARATOR_ERROR,
  composeGroup,
  splitGroup,
} from '@/utils/tournamentGroups';

// The trimmed characters, as code points. Frozen with the format.
// prettier-ignore
const WHITESPACE_CODE_POINTS = [
  0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x20, 0x1c, 0x1d, 0x1e, 0x1f, 0x85, 0xa0, 0x1680,
  0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200a,
  0x2028, 0x2029, 0x202f, 0x205f, 0x3000, 0xfeff,
];

// [stored value, division, label]. The same table is in
// backend/tests/unit/test_tournament_groups.py — keep them identical, so a
// drift between the two implementations fails a test on one side.
const SPLIT_PARITY_CASES = [
  ['\ufeffHD \u00b7 A', 'HD', 'A'], // BOM: trim() strips it, str.strip() does not
  ['\u00a0HD \u00b7 A\u00a0', 'HD', 'A'], // NBSP padding
  ['\u0085HD \u00b7 A\u0085', 'HD', 'A'], // NEL: str.strip() strips it, trim() does not
  ['\u001cHD \u00b7 A\u001f', 'HD', 'A'],
  ['\u2003HD \u00b7 A\u3000', 'HD', 'A'],
  ['\t HD \u00b7 A \r\n', 'HD', 'A'],
  ['HD\u00a0 \u00b7 \ufeffA', 'HD', 'A'], // padding inside, next to the separator
  ['\ufeffBracket A\u0085', null, 'Bracket A'],
  ['\ufeff\u00a0\u0085', null, null],
  // Trimming the whole value first eats the separator's own space, so a
  // value with an empty side is a legacy label, not a half-empty pair.
  ['HD \u00b7 \ufeff', null, 'HD \u00b7'],
  ['\u0085 \u00b7 A', null, '\u00b7 A'],
  ['HD\u200b \u00b7 A', 'HD\u200b', 'A'], // zero-width space is not trimmed
  ['HD\u00a0\u00b7\u00a0A', null, 'HD\u00a0\u00b7\u00a0A'], // NBSPs do not make a separator
];

// [division, label] pairs composeGroup accepts; each must split back to itself.
const ROUND_TRIP_CASES = [
  ['HD', 'A'],
  ['AD', 'Showcase'],
  [null, 'Bracket A'],
  ['HD', 'A \u00b7 Late'], // separator in the label is legal with a division
  ['HD', 'A \u00b7 B \u00b7 C'],
  ['HD', '\u00b7 A'],
  ['\u00b7', 'A'],
  ['U15\u00b7B', 'A'],
  [null, 'U15\u00b7A'],
  [null, 'A \u00b7'],
];

// [division, label, message] composeGroup refuses.
const REJECTED_CASES = [
  ['HD \u00b7 X', 'A', DIVISION_SEPARATOR_ERROR],
  ['HD \u00b7 X', null, DIVISION_SEPARATOR_ERROR],
  ['HD \u00b7', 'A', DIVISION_SEPARATOR_ERROR], // would compose to "HD · · A"
  [null, 'A \u00b7 B', LABEL_SEPARATOR_ERROR],
  ['', 'A \u00b7 B', LABEL_SEPARATOR_ERROR],
  ['\ufeff', 'A \u00b7 B', LABEL_SEPARATOR_ERROR],
];

// The default fixture is a legacy un-namespaced group ("Bracket A") — every
// tournament loaded before MLS NEXT Fest, and it must come back unchanged.
describe('tournamentGroups util', () => {
  it('separator is space, middle dot, space (frozen)', () => {
    expect(GROUP_SEPARATOR).toBe(' \u00b7 ');
  });

  describe('composeGroup', () => {
    it('namespaces a label by division', () => {
      expect(composeGroup('HD', 'A')).toBe('HD \u00b7 A');
      expect(composeGroup('HD', 'Showcase')).toBe('HD \u00b7 Showcase');
    });

    it('leaves a label with no division as a legacy value', () => {
      expect(composeGroup(null, 'Bracket A')).toBe('Bracket A');
      expect(composeGroup(undefined, 'Bracket A')).toBe('Bracket A');
      expect(composeGroup('', 'A')).toBe('A');
    });

    it('returns the division alone when there is no label', () => {
      expect(composeGroup('HD', null)).toBe('HD');
      expect(composeGroup('HD', '')).toBe('HD');
    });

    it.each([
      [null, null],
      [undefined, undefined],
      ['', ''],
      ['  ', null],
      [null, ' '],
    ])('returns null when both parts are missing (%j, %j)', (d, l) => {
      expect(composeGroup(d, l)).toBeNull();
    });

    it('trims both parts', () => {
      expect(composeGroup('  HD ', ' A  ')).toBe('HD \u00b7 A');
    });
  });

  describe('splitGroup', () => {
    it('splits a namespaced value', () => {
      expect(splitGroup('HD \u00b7 A')).toEqual({ division: 'HD', label: 'A' });
    });

    it('treats a legacy value as division null, label unchanged', () => {
      expect(splitGroup('Bracket A')).toEqual({
        division: null,
        label: 'Bracket A',
      });
    });

    it.each([null, undefined, '', '   '])('absent value %j is all null', v => {
      expect(splitGroup(v)).toEqual({ division: null, label: null });
    });

    it('splits on the first separator only', () => {
      expect(splitGroup('HD \u00b7 A \u00b7 Late')).toEqual({
        division: 'HD',
        label: 'A \u00b7 Late',
      });
    });

    it('trims the value', () => {
      expect(splitGroup('  HD \u00b7 A ')).toEqual({
        division: 'HD',
        label: 'A',
      });
    });

    it('a middle dot without surrounding spaces is not a separator', () => {
      expect(splitGroup('U15\u00b7A')).toEqual({
        division: null,
        label: 'U15\u00b7A',
      });
    });

    it.each([
      'HD \u00b7 X \u00b7 A',
      'A \u00b7 B',
      'HD \u00b7 \u00b7 A',
      ' \u00b7 ',
      '\u00b7 \u00b7 \u00b7',
    ])('never throws on a stored value %j', v => {
      // composeGroup would refuse some of these; a stored one still splits.
      expect(Object.keys(splitGroup(v)).sort()).toEqual(['division', 'label']);
    });
  });

  describe('whitespace', () => {
    it('trimmed set is frozen', () => {
      expect([...GROUP_WHITESPACE].map(c => c.codePointAt(0))).toEqual(
        WHITESPACE_CODE_POINTS
      );
    });

    it.each(WHITESPACE_CODE_POINTS)(
      'trims listed character U+%s',
      codePoint => {
        const pad = String.fromCodePoint(codePoint);
        expect(splitGroup(`${pad}HD \u00b7 A${pad}`)).toEqual({
          division: 'HD',
          label: 'A',
        });
        expect(composeGroup(`${pad}HD${pad}`, `${pad}A${pad}`)).toBe(
          'HD \u00b7 A'
        );
      }
    );

    it.each(SPLIT_PARITY_CASES)('split parity %j', (value, division, label) => {
      expect(splitGroup(value)).toEqual({ division, label });
    });
  });

  describe('round trip', () => {
    it.each(ROUND_TRIP_CASES)(
      'legal pair round-trips (%j, %j)',
      (division, label) => {
        expect(splitGroup(composeGroup(division, label))).toEqual({
          division,
          label,
        });
      }
    );

    it.each(REJECTED_CASES)(
      'rejects a pair that would not round-trip (%j, %j)',
      (division, label, message) => {
        expect(() => composeGroup(division, label)).toThrow(new Error(message));
      }
    );

    it('messages are frozen', () => {
      // Same text as tournament_groups.py.
      expect(DIVISION_SEPARATOR_ERROR).toBe(
        "A tournament group division cannot contain ' \u00b7 ' or end with ' \u00b7'"
      );
      expect(LABEL_SEPARATOR_ERROR).toBe(
        "A tournament group label cannot contain ' \u00b7 ' unless a division is given"
      );
    });
  });
});
