import { describe, it, expect } from 'vitest';
import { pickDefaultAgeGroupId } from '@/utils/defaultAgeGroup';

const AGE_GROUPS = [
  { id: 1, name: 'U13' },
  { id: 2, name: 'U14' },
  { id: 3, name: 'U15' },
];

describe('pickDefaultAgeGroupId (SB-1286)', () => {
  it('falls back to U14 with no preference and no team', () => {
    expect(
      pickDefaultAgeGroupId({
        preferred: null,
        team: null,
        ageGroups: AGE_GROUPS,
      })
    ).toBe(2);
  });

  it("uses the team's age group with no preference", () => {
    expect(
      pickDefaultAgeGroupId({ preferred: null, team: 3, ageGroups: AGE_GROUPS })
    ).toBe(3);
  });

  it("prefers the preference over the team's age group", () => {
    expect(
      pickDefaultAgeGroupId({ preferred: 1, team: 3, ageGroups: AGE_GROUPS })
    ).toBe(1);
  });

  it('skips a preference naming an age group that no longer exists', () => {
    expect(
      pickDefaultAgeGroupId({ preferred: 99, team: 3, ageGroups: AGE_GROUPS })
    ).toBe(3);
    expect(
      pickDefaultAgeGroupId({
        preferred: 99,
        team: null,
        ageGroups: AGE_GROUPS,
      })
    ).toBe(2);
  });

  it('accepts string ids', () => {
    expect(
      pickDefaultAgeGroupId({
        preferred: '3',
        team: null,
        ageGroups: AGE_GROUPS,
      })
    ).toBe(3);
  });

  it('returns null when nothing matches and there is no U14', () => {
    expect(
      pickDefaultAgeGroupId({
        preferred: 9,
        team: null,
        ageGroups: [{ id: 5, name: 'U19' }],
      })
    ).toBeNull();
    expect(
      pickDefaultAgeGroupId({ preferred: 2, team: null, ageGroups: [] })
    ).toBeNull();
  });
});
