import { describe, it, expect } from 'vitest';
import {
  TOURNAMENT_ROUNDS,
  ROUND_LABELS_SHORT,
  ROUND_LABELS_LONG,
  roundLabel,
  KNOCKOUT_ROUNDS,
  KNOCKOUT_ROUND_ORDER,
  BRACKET_ROUNDS,
  BRACKET_ROUND_ORDER,
  SHOOTOUT_ROUNDS,
} from '@/utils/tournamentRounds';

describe('tournamentRounds util', () => {
  it('derives short label maps from the canonical source', () => {
    expect(ROUND_LABELS_SHORT.quarterfinal).toBe('QF');
    expect(ROUND_LABELS_SHORT.round_of_16).toBe('R16');
  });

  it('derives long label maps from the canonical source', () => {
    expect(ROUND_LABELS_LONG.quarterfinal).toBe('Quarterfinal');
    expect(ROUND_LABELS_LONG.round_of_16).toBe('Round of 16');
  });

  it('keeps short and long maps in sync with the canonical keys', () => {
    const keys = Object.keys(TOURNAMENT_ROUNDS);
    expect(Object.keys(ROUND_LABELS_SHORT)).toEqual(keys);
    expect(Object.keys(ROUND_LABELS_LONG)).toEqual(keys);
  });

  it('roundLabel returns the long label by default', () => {
    expect(roundLabel('semifinal')).toBe('Semifinal');
  });

  it('roundLabel returns the short label when requested', () => {
    expect(roundLabel('semifinal', { short: true })).toBe('SF');
  });

  it('roundLabel returns null for unknown or empty rounds', () => {
    expect(roundLabel('not_a_round')).toBeNull();
    expect(roundLabel(null)).toBeNull();
    expect(roundLabel(undefined)).toBeNull();
  });

  // SB-1752: MLS NEXT Fest round keys.
  it('labels the showcase, consolation and placement_final rounds', () => {
    expect(roundLabel('showcase')).toBe('Showcase');
    expect(roundLabel('showcase', { short: true })).toBe('Showcase');
    expect(roundLabel('consolation')).toBe('Consolation');
    expect(roundLabel('consolation', { short: true })).toBe('Consolation');
    expect(roundLabel('placement_final')).toBe('Placement Final');
    expect(roundLabel('placement_final', { short: true })).toBe('Placement');
  });
});

describe('tournament round sets', () => {
  const NEW_KEYS = ['showcase', 'consolation', 'placement_final'];

  it('knockout rounds are the six elimination rounds, in playing order', () => {
    expect(KNOCKOUT_ROUND_ORDER).toEqual([
      'round_of_32',
      'round_of_16',
      'quarterfinal',
      'semifinal',
      'third_place',
      'final',
    ]);
    expect([...KNOCKOUT_ROUNDS]).toEqual(KNOCKOUT_ROUND_ORDER);
  });

  it('bracket rounds are the knockout rounds without third place', () => {
    expect(BRACKET_ROUND_ORDER).toEqual([
      'round_of_32',
      'round_of_16',
      'quarterfinal',
      'semifinal',
      'final',
    ]);
    expect([...BRACKET_ROUNDS]).toEqual(BRACKET_ROUND_ORDER);
  });

  it.each(NEW_KEYS)('%s is neither a knockout nor a bracket round', key => {
    expect(KNOCKOUT_ROUNDS.has(key)).toBe(false);
    expect(BRACKET_ROUNDS.has(key)).toBe(false);
  });

  it('a tournament whose only finals are placement finals has no bracket round', () => {
    const matches = [
      { tournament_round: 'group_stage' },
      { tournament_round: 'placement_final' },
    ];
    expect(matches.some(m => BRACKET_ROUNDS.has(m.tournament_round))).toBe(
      false
    );
  });

  it('group stage is in none of the sets', () => {
    expect(KNOCKOUT_ROUNDS.has('group_stage')).toBe(false);
    expect(BRACKET_ROUNDS.has('group_stage')).toBe(false);
    expect(SHOOTOUT_ROUNDS.has('group_stage')).toBe(false);
  });

  it('shootouts cover every knockout round plus consolation and placement', () => {
    for (const round of KNOCKOUT_ROUND_ORDER) {
      expect(SHOOTOUT_ROUNDS.has(round)).toBe(true);
    }
    expect(SHOOTOUT_ROUNDS.has('consolation')).toBe(true);
    expect(SHOOTOUT_ROUNDS.has('placement_final')).toBe(true);
    expect(SHOOTOUT_ROUNDS.has('showcase')).toBe(false);
  });

  it('every round in a set has a label', () => {
    for (const round of SHOOTOUT_ROUNDS) {
      expect(TOURNAMENT_ROUNDS[round]).toBeDefined();
    }
  });
});
