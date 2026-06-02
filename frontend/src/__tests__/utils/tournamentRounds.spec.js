import { describe, it, expect } from 'vitest';
import {
  TOURNAMENT_ROUNDS,
  ROUND_LABELS_SHORT,
  ROUND_LABELS_LONG,
  roundLabel,
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
});
