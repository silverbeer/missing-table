/**
 * The Tournaments tab's URLs (SB-1767): `/tournaments` is the season index,
 * `/tournaments/<id>` one tournament. Anything else is not the tab's.
 */

import { describe, it, expect } from 'vitest';
import { parseTournamentPath, tournamentPath } from '@/utils/tournamentRoute';

describe('parseTournamentPath', () => {
  it('reads the index', () => {
    expect(parseTournamentPath('/tournaments')).toEqual({ kind: 'index' });
    expect(parseTournamentPath('/tournaments/')).toEqual({ kind: 'index' });
  });

  it('reads a tournament id as a number', () => {
    expect(parseTournamentPath('/tournaments/12')).toEqual({
      kind: 'detail',
      id: 12,
    });
    expect(parseTournamentPath('/tournaments/12/')).toEqual({
      kind: 'detail',
      id: 12,
    });
  });

  it('treats a segment that is not an id as the index', () => {
    expect(parseTournamentPath('/tournaments/abc')).toEqual({ kind: 'index' });
    expect(parseTournamentPath('/tournaments/12abc')).toEqual({
      kind: 'index',
    });
    expect(parseTournamentPath('/tournaments/0')).toEqual({ kind: 'index' });
    expect(parseTournamentPath('/tournaments/-3')).toEqual({ kind: 'index' });
    expect(parseTournamentPath('/tournaments/99999999999999999999999')).toEqual(
      { kind: 'index' }
    );
  });

  it('is null for every other path', () => {
    for (const path of [
      '/',
      '',
      '/chat',
      '/privacy',
      '/tournament',
      '/tournamentsx',
      '/tournaments/12/matches',
      '/api/tournaments/12',
      '/auth/callback',
    ]) {
      expect(parseTournamentPath(path)).toBe(null);
    }
  });

  it('is null for a pathname that is not a string', () => {
    expect(parseTournamentPath(undefined)).toBe(null);
    expect(parseTournamentPath(null)).toBe(null);
    expect(parseTournamentPath(12)).toBe(null);
  });
});

describe('tournamentPath', () => {
  it('builds the index and detail paths', () => {
    expect(tournamentPath()).toBe('/tournaments');
    expect(tournamentPath(null)).toBe('/tournaments');
    expect(tournamentPath(12)).toBe('/tournaments/12');
  });

  it('round-trips through parseTournamentPath', () => {
    expect(parseTournamentPath(tournamentPath(7))).toEqual({
      kind: 'detail',
      id: 7,
    });
    expect(parseTournamentPath(tournamentPath())).toEqual({ kind: 'index' });
  });
});
