/**
 * matchPermissions tests (SB-906).
 *
 * The rule was copy-pasted per screen and the copies drifted — MatchDetailView
 * granted every club manager without checking the club. These cases pin the
 * one rule, against both match shapes: the league list's flat team ids and the
 * tournament row's nested team + club objects.
 */

import { describe, it, expect } from 'vitest';
import {
  canEditMatch,
  matchTeamIds,
  matchClubIds,
} from '@/utils/matchPermissions';

// Tournament shape: teams and clubs are embedded.
const tournamentMatch = {
  id: 5995,
  home_team: { id: 19, name: 'IFA' },
  away_team: { id: 570, name: 'Alexandria SA' },
  home_team_club: { id: 1, name: 'IFA' },
  away_team_club: { id: 236, name: 'Alexandria SA' },
};

// League shape: flat ids, club only via a teams lookup.
const leagueMatch = { id: 42, home_team_id: 19, away_team_id: 570 };
const resolveClubId = teamId => ({ 19: 1, 570: 236 })[teamId] ?? null;

const viewer = over => ({
  isAdmin: false,
  isClubManager: false,
  isTeamManager: false,
  clubId: null,
  teamId: null,
  ...over,
});

describe('matchTeamIds / matchClubIds', () => {
  it('reads ids from the tournament shape', () => {
    expect(matchTeamIds(tournamentMatch)).toEqual({
      homeTeamId: 19,
      awayTeamId: 570,
    });
    expect(matchClubIds(tournamentMatch)).toEqual({
      homeClubId: 1,
      awayClubId: 236,
    });
  });

  it('reads ids from the league shape, clubs via the resolver', () => {
    expect(matchTeamIds(leagueMatch)).toEqual({
      homeTeamId: 19,
      awayTeamId: 570,
    });
    expect(matchClubIds(leagueMatch, resolveClubId)).toEqual({
      homeClubId: 1,
      awayClubId: 236,
    });
  });

  it('returns nulls rather than throwing on a missing match', () => {
    expect(matchTeamIds(null)).toEqual({ homeTeamId: null, awayTeamId: null });
    expect(matchClubIds(undefined)).toEqual({
      homeClubId: null,
      awayClubId: null,
    });
  });

  it('leaves clubs null when nothing can resolve them', () => {
    expect(matchClubIds(leagueMatch)).toEqual({
      homeClubId: null,
      awayClubId: null,
    });
  });
});

describe('canEditMatch — the default case: a signed-out viewer', () => {
  it('denies a viewer with no role', () => {
    expect(canEditMatch(tournamentMatch, viewer())).toBe(false);
  });

  it('denies when there is no viewer at all', () => {
    expect(canEditMatch(tournamentMatch, null)).toBe(false);
  });
});

describe('canEditMatch — admin', () => {
  it('allows any match', () => {
    expect(canEditMatch(tournamentMatch, viewer({ isAdmin: true }))).toBe(true);
    expect(
      canEditMatch({ id: 1, home_team_id: 900 }, viewer({ isAdmin: true }))
    ).toBe(true);
  });
});

describe('canEditMatch — club manager', () => {
  it('allows a match involving a team in their club', () => {
    const v = viewer({ isClubManager: true, clubId: 236 });
    expect(canEditMatch(tournamentMatch, v)).toBe(true);
  });

  it('denies a match between two other clubs', () => {
    const v = viewer({ isClubManager: true, clubId: 999 });
    expect(canEditMatch(tournamentMatch, v)).toBe(false);
  });

  it('resolves the club from the teams list on a league match', () => {
    const v = viewer({ isClubManager: true, clubId: 1 });
    expect(canEditMatch(leagueMatch, v, { resolveClubId })).toBe(true);
    expect(canEditMatch(leagueMatch, v)).toBe(false); // no resolver, no club
  });

  it('denies a club manager whose account carries no club', () => {
    expect(canEditMatch(tournamentMatch, viewer({ isClubManager: true }))).toBe(
      false
    );
  });
});

describe('canEditMatch — team manager', () => {
  it('allows their own team on either side', () => {
    expect(
      canEditMatch(tournamentMatch, viewer({ isTeamManager: true, teamId: 19 }))
    ).toBe(true);
    expect(
      canEditMatch(
        tournamentMatch,
        viewer({ isTeamManager: true, teamId: 570 })
      )
    ).toBe(true);
  });

  it('denies a match their team is not in', () => {
    expect(
      canEditMatch(
        tournamentMatch,
        viewer({ isTeamManager: true, teamId: 601 })
      )
    ).toBe(false);
  });

  it('does not grant a team manager their whole club', () => {
    // teamId matches nothing here; clubId alone must not open the door.
    const v = viewer({ isTeamManager: true, teamId: 601, clubId: 1 });
    expect(canEditMatch(tournamentMatch, v)).toBe(false);
  });
});
