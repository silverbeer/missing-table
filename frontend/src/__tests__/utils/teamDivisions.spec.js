import { describe, it, expect } from 'vitest';
import {
  teamDivisionFor,
  teamDivisions,
  teamPlaysLeague,
} from '@/utils/teamDivisions';

const northeast = { id: 5, name: 'Northeast', league_id: 1 };
const turnpike = { id: 20, name: 'Turnpike', league_id: 2 };
const empire = { id: 21, name: 'Empire', league_id: 2 };

// One team, U16 (id 4) in Homegrown + two Flex conferences (SB-1468).
const ironbound = {
  id: 33,
  divisions_by_age_group: { 4: northeast },
  divisions_by_age_group_all: { 4: [northeast, turnpike, empire] },
};

describe('teamDivisions', () => {
  it('returns every division at the age group', () => {
    expect(teamDivisions(ironbound, 4)).toEqual([northeast, turnpike, empire]);
  });

  it('falls back to the single-division field for older payloads', () => {
    const legacy = { divisions_by_age_group: { 4: turnpike } };
    expect(teamDivisions(legacy, 4)).toEqual([turnpike]);
  });

  it('is empty, not an error, for a team with no division there', () => {
    expect(teamDivisions(ironbound, 9)).toEqual([]);
    expect(teamDivisions({ id: 1 }, 4)).toEqual([]);
  });
});

describe('teamPlaysLeague', () => {
  it('matches any division, not just the primary one', () => {
    expect(teamPlaysLeague(ironbound, 4, 1)).toBe(true);
    expect(teamPlaysLeague(ironbound, 4, 2)).toBe(true);
    expect(teamPlaysLeague(ironbound, 4, 3)).toBe(false);
  });
});

describe('teamDivisionFor', () => {
  it('prefers the division in the selected league', () => {
    expect(teamDivisionFor(ironbound, 4, { leagueId: 2 })).toBe(turnpike);
  });

  it('narrows by division when given', () => {
    expect(teamDivisionFor(ironbound, 4, { leagueId: 2, divisionId: 21 })).toBe(
      empire
    );
  });

  it('falls back to the primary division', () => {
    expect(teamDivisionFor(ironbound, 4)).toBe(northeast);
    expect(teamDivisionFor(ironbound, 4, { leagueId: 99 })).toBe(northeast);
  });

  it('is undefined when the team has no division at the age group', () => {
    expect(teamDivisionFor(ironbound, 9)).toBeUndefined();
  });
});
