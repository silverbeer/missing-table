/**
 * useLiveMatch — stoppage time computeds (SB-67).
 *
 * The composable initializes its internal `currentTime` ref from Date.now()
 * at construction. We mock Date.now() to a fixed "fake now" before each
 * test so the elapsed clock has a deterministic value, then set
 * `matchState` directly and read the new SB-67 computeds.
 *
 * Subscription/network functions (subscribeToRealtime, fetchMatchState,
 * etc.) only run if the consumer calls initialize() — these tests skip
 * that and just inspect the reactive state.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

const FAKE_NOW = 1748966400000; // 2026-06-03T17:20:00Z, fixed.

vi.mock('@/config/supabase', () => ({
  supabase: {
    channel: vi.fn(() => ({
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn(),
    })),
    removeChannel: vi.fn(),
  },
}));

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAuthenticated: { value: true },
    isAdmin: { value: true },
    isClubManager: { value: false },
    isTeamManager: { value: false },
    userTeamId: { value: null },
    apiRequest: vi.fn(),
  }),
}));

vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://test.example',
}));

vi.mock('@/composables/useMatchLineup', () => ({
  useMatchLineup: () => ({
    homeLineup: { value: null },
    awayLineup: { value: null },
    homeRoster: { value: [] },
    awayRoster: { value: [] },
    lineupLoading: { value: false },
    fetchLineup: vi.fn(),
    fetchLineups: vi.fn(),
    saveLineup: vi.fn(),
    fetchTeamRosters: vi.fn(),
  }),
}));

beforeEach(() => {
  vi.spyOn(Date, 'now').mockReturnValue(FAKE_NOW);
});

import { useLiveMatch } from '@/composables/useLiveMatch';

// Helper: produce an ISO timestamp `seconds` before FAKE_NOW.
const isoSecondsAgo = seconds =>
  new Date(FAKE_NOW - seconds * 1000).toISOString();

describe('useLiveMatch — pre-stoppage clock', () => {
  it('isInStoppage is false before kickoff', () => {
    const live = useLiveMatch(1);
    live.matchState.value = { half_duration: 45 };
    expect(live.isInStoppage.value).toBe(false);
    expect(live.stoppageElapsedSeconds.value).toBe(0);
  });

  it('isInStoppage is false during regulation 1st half', () => {
    const live = useLiveMatch(1);
    live.matchState.value = {
      kickoff_time: isoSecondsAgo(20 * 60), // 20 minutes elapsed
      half_duration: 45,
    };
    expect(live.isInStoppage.value).toBe(false);
    expect(live.clockDisplayFormatted.value).toBe('20:00');
  });

  it('isInStoppage is false at halftime (clock paused between halves)', () => {
    const live = useLiveMatch(1);
    live.matchState.value = {
      kickoff_time: isoSecondsAgo(50 * 60),
      halftime_start: isoSecondsAgo(60), // halftime was called 1 min ago
      half_duration: 45,
    };
    expect(live.isInStoppage.value).toBe(false);
  });

  it('isInStoppage is false after fulltime', () => {
    const live = useLiveMatch(1);
    live.matchState.value = {
      kickoff_time: isoSecondsAgo(100 * 60),
      match_end_time: isoSecondsAgo(5),
      match_status: 'completed',
      half_duration: 45,
    };
    expect(live.isInStoppage.value).toBe(false);
  });
});

describe('useLiveMatch — 1st-half stoppage', () => {
  it('flips isInStoppage on at the half_duration boundary', () => {
    const live = useLiveMatch(1);
    // 45 minutes elapsed = exactly at boundary; need to go just past it.
    live.matchState.value = {
      kickoff_time: isoSecondsAgo(45 * 60 + 5), // 45:05
      half_duration: 45,
    };
    expect(live.isInStoppage.value).toBe(true);
    expect(Math.round(live.stoppageElapsedSeconds.value)).toBe(5);
    expect(live.clockDisplayFormatted.value).toBe('45+0:05');
  });

  it('formats deeper stoppage as 45+M:SS', () => {
    const live = useLiveMatch(1);
    live.matchState.value = {
      kickoff_time: isoSecondsAgo(45 * 60 + 165), // 45 + 2:45
      half_duration: 45,
    };
    expect(live.isInStoppage.value).toBe(true);
    expect(live.clockDisplayFormatted.value).toBe('45+2:45');
  });

  it('honours non-default half_duration (e.g. 30 min for younger ages)', () => {
    const live = useLiveMatch(1);
    live.matchState.value = {
      kickoff_time: isoSecondsAgo(30 * 60 + 90), // 30 + 1:30
      half_duration: 30,
    };
    expect(live.isInStoppage.value).toBe(true);
    expect(live.clockDisplayFormatted.value).toBe('30+1:30');
  });
});

describe('useLiveMatch — 2nd-half stoppage', () => {
  it('flips isInStoppage on at the 2 × half_duration boundary', () => {
    const live = useLiveMatch(1);
    // Kickoff 90+15 min ago, halftime came + went, 2nd half kicked off
    // such that elapsed (boundary measurement) = 90:15. The composable's
    // elapsedSeconds for second half is halfDurationSeconds + secondHalfElapsed,
    // so set second_half_start such that second-half elapsed is 45:15.
    live.matchState.value = {
      kickoff_time: isoSecondsAgo(120 * 60), // arbitrary, past
      halftime_start: isoSecondsAgo(80 * 60),
      second_half_start: isoSecondsAgo(45 * 60 + 15), // 45:15 of 2nd half
      half_duration: 45,
    };
    expect(live.isInStoppage.value).toBe(true);
    expect(live.clockDisplayFormatted.value).toBe('90+0:15');
  });

  it('formats deeper 2nd-half stoppage as 90+M:SS', () => {
    const live = useLiveMatch(1);
    live.matchState.value = {
      kickoff_time: isoSecondsAgo(150 * 60),
      halftime_start: isoSecondsAgo(80 * 60),
      second_half_start: isoSecondsAgo(45 * 60 + 200), // 45 + 3:20
      half_duration: 45,
    };
    expect(live.isInStoppage.value).toBe(true);
    expect(live.clockDisplayFormatted.value).toBe('90+3:20');
  });
});
