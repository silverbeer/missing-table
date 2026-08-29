/**
 * utils/swRoutes.js tests (SB-908).
 *
 * The split matters: reference data may be served stale, score-bearing data
 * may not. A tournament page rendered from a pre-match cache is how a final
 * score stayed invisible on 2026-08-29 while the API already had it.
 */

import { describe, it, expect } from 'vitest';
import { isReferenceApi, isResultsApi } from '@/utils/swRoutes';

describe('isResultsApi', () => {
  it.each([
    '/api/tournaments',
    '/api/tournaments/8',
    '/api/tournaments?season_id=184',
    '/api/standings',
    '/api/standings?age_group_id=3',
  ])('claims %s', path => {
    expect(isResultsApi(path)).toBe(true);
    // Never both — the two routes would race for the same request.
    expect(isReferenceApi(path)).toBe(false);
  });

  it('leaves reference data alone', () => {
    expect(isResultsApi('/api/teams')).toBe(false);
    expect(isResultsApi('/api/age-groups')).toBe(false);
  });
});

describe('isReferenceApi', () => {
  it.each([
    '/api/teams',
    '/api/teams/19',
    '/api/match-types',
    '/api/seasons',
    '/api/age-groups',
    '/api/divisions',
    '/api/leagues',
    '/api/clubs?league_id=1',
  ])('claims %s', path => {
    expect(isReferenceApi(path)).toBe(true);
  });

  it('does not cache live match state, matches or auth', () => {
    for (const path of [
      '/api/matches',
      '/api/matches/3853/live',
      '/api/matches/live',
      '/api/auth/refresh',
    ]) {
      expect(isReferenceApi(path)).toBe(false);
      expect(isResultsApi(path)).toBe(false);
    }
  });

  it('does not match a path that merely contains a cached word', () => {
    expect(isReferenceApi('/api/teams-export')).toBe(false);
    expect(isResultsApi('/api/tournaments-archive')).toBe(false);
  });
});
