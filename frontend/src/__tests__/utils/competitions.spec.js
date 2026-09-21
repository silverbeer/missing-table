/**
 * Shared competition / league-hierarchy helpers (SB-1039, SB-1040).
 */
import { describe, it, expect } from 'vitest';
import {
  combinedLabel,
  combinedTitle,
  topLevelLeague,
  topLevelLeagueName,
  competitionOfLeague,
  competitionChip,
} from '@/utils/competitions';

const LEAGUES = [
  { id: 1, name: 'Homegrown', match_type_id: 1 },
  { id: 290, name: 'Flex', parent_league_id: 1, match_type_id: 5 },
  { id: 2, name: 'Academy', match_type_id: 1 },
  { id: 90, name: 'TSC League 1' },
];
const MATCH_TYPES = [
  { id: 1, name: 'League' },
  { id: 5, name: 'Flex' },
];

describe('combinedLabel / combinedTitle', () => {
  it('labels the combined view by what it combines', () => {
    expect(combinedLabel(['League', 'Flex'])).toBe('League + Flex');
    expect(combinedTitle(['League', 'Flex'])).toContain('League + Flex');
    expect(combinedTitle(['League', 'Flex'])).toContain('not a standing');
  });

  it('is empty when there is nothing to combine', () => {
    expect(combinedLabel([])).toBe('');
    expect(combinedTitle(undefined)).toBe('');
  });
});

describe('topLevelLeague', () => {
  it('resolves a child league to its parent', () => {
    expect(topLevelLeague(LEAGUES, 290).name).toBe('Homegrown');
  });

  it('returns a top-level league as itself', () => {
    expect(topLevelLeague(LEAGUES, 2).name).toBe('Academy');
    // No parent column at all: its own top level.
    expect(topLevelLeague(LEAGUES, 90).name).toBe('TSC League 1');
  });

  it('is null for an unknown or missing id', () => {
    expect(topLevelLeague(LEAGUES, 999)).toBeNull();
    expect(topLevelLeague(LEAGUES, null)).toBeNull();
  });

  it('does not hang on a cycle', () => {
    const loop = [
      { id: 1, name: 'A', parent_league_id: 2 },
      { id: 2, name: 'B', parent_league_id: 1 },
    ];
    expect(topLevelLeague(loop, 1)).toBeTruthy();
  });
});

describe('topLevelLeagueName', () => {
  it('files a Flex fixture under Homegrown', () => {
    const match = {
      division: {
        id: 309,
        name: 'Turnpike',
        league_id: 290,
        leagues: { id: 290, name: 'Flex' },
      },
    };
    expect(topLevelLeagueName(LEAGUES, match)).toBe('Homegrown');
  });

  it('falls back to the name the match carries when the id is unknown', () => {
    const match = { division: { leagues: { name: 'Academy' } } };
    expect(topLevelLeagueName([], match)).toBe('Academy');
  });

  it('is null when the match has no division', () => {
    expect(topLevelLeagueName(LEAGUES, {})).toBeNull();
  });
});

describe('competitionOfLeague', () => {
  it('names the competition a league conferences are tables of', () => {
    expect(competitionOfLeague(LEAGUES, MATCH_TYPES, 1)).toBe('League');
    expect(competitionOfLeague(LEAGUES, MATCH_TYPES, 290)).toBe('Flex');
  });

  it('is null when the league does not say', () => {
    expect(competitionOfLeague(LEAGUES, MATCH_TYPES, 90)).toBeNull();
    expect(competitionOfLeague(LEAGUES, MATCH_TYPES, 999)).toBeNull();
  });
});

describe('competitionChip (SB-1105)', () => {
  it('labels the chip with the competition the match carries', () => {
    expect(competitionChip({ match_type_name: 'Flex' }).label).toBe('Flex');
  });

  it('gives League and Flex different tints', () => {
    const league = competitionChip({ match_type_name: 'League' }).class;
    const flex = competitionChip({ match_type_name: 'Flex' }).class;
    expect(league).not.toBe(flex);
  });

  it('matches the tint case-insensitively', () => {
    expect(competitionChip({ match_type_name: 'FLEX' }).class).toBe(
      competitionChip({ match_type_name: 'Flex' }).class
    );
  });

  it('still chips a competition it has no tint for', () => {
    const chip = competitionChip({ match_type_name: 'Showcase' });
    expect(chip.label).toBe('Showcase');
    expect(chip.class).toBeTruthy();
  });

  it('is null when the match does not say — absent is not League', () => {
    expect(competitionChip({ match_type_name: null })).toBeNull();
    expect(competitionChip({})).toBeNull();
    expect(competitionChip(null)).toBeNull();
  });
});
