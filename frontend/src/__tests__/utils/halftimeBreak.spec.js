/**
 * Half-time break countdown helpers (SB-1353).
 */

import { describe, it, expect } from 'vitest';
import {
  BREAK_MINUTES,
  remainingSeconds,
  countdownText,
  isOverdue,
  expectedSecondHalfStart,
  shouldOfferBackdate,
} from '@/utils/halftimeBreak';

const HT = '2026-10-19T15:00:00.000Z';
const at = (min, sec = 0) => new Date(Date.parse(HT) + (min * 60 + sec) * 1000);

describe('remainingSeconds', () => {
  it('is a 10-minute break', () => {
    expect(BREAK_MINUTES).toBe(10);
    expect(remainingSeconds(HT, at(0))).toBe(600);
  });

  it('counts down', () => {
    expect(remainingSeconds(HT, at(2, 18))).toBe(462);
  });

  it('is zero at the end of the break', () => {
    expect(remainingSeconds(HT, at(10))).toBe(0);
    expect(Object.is(remainingSeconds(HT, at(10)), -0)).toBe(false);
  });

  it('goes negative when overdue', () => {
    expect(remainingSeconds(HT, at(12, 15))).toBe(-135);
  });

  it('is null without a halftime_start', () => {
    expect(remainingSeconds(null, at(1))).toBeNull();
    expect(remainingSeconds(undefined, at(1))).toBeNull();
    expect(remainingSeconds('not a date', at(1))).toBeNull();
  });

  it('accepts epoch-ms now', () => {
    expect(remainingSeconds(HT, at(5).getTime())).toBe(300);
  });
});

describe('countdownText', () => {
  it('formats time left', () => {
    expect(countdownText(462)).toBe('7:42');
    expect(countdownText(600)).toBe('10:00');
    expect(countdownText(5)).toBe('0:05');
    expect(countdownText(0)).toBe('0:00');
  });

  it('formats overdue time with a plus', () => {
    expect(countdownText(-135)).toBe('+2:15');
    expect(countdownText(-1)).toBe('+0:01');
  });

  it('is empty for null', () => {
    expect(countdownText(null)).toBe('');
  });
});

describe('isOverdue', () => {
  it('only once below zero', () => {
    expect(isOverdue(1)).toBe(false);
    expect(isOverdue(0)).toBe(false);
    expect(isOverdue(-1)).toBe(true);
    expect(isOverdue(null)).toBe(false);
  });
});

describe('expectedSecondHalfStart', () => {
  it('is the end of the break once it has passed', () => {
    expect(expectedSecondHalfStart(HT, at(14)).toISOString()).toBe(
      '2026-10-19T15:10:00.000Z'
    );
  });

  it('is never in the future', () => {
    expect(expectedSecondHalfStart(HT, at(4)).toISOString()).toBe(
      at(4).toISOString()
    );
  });

  it('is null without a halftime_start', () => {
    expect(expectedSecondHalfStart(null, at(4))).toBeNull();
  });
});

describe('shouldOfferBackdate', () => {
  it('needs the break end at least a minute in the past', () => {
    expect(shouldOfferBackdate(HT, at(9))).toBe(false);
    expect(shouldOfferBackdate(HT, at(10, 59))).toBe(false);
    expect(shouldOfferBackdate(HT, at(11))).toBe(true);
    expect(shouldOfferBackdate(null, at(30))).toBe(false);
  });
});
