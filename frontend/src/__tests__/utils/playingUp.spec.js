import { describe, it, expect } from 'vitest';
import { allowsPlayingUp, groupTeamsForMatch } from '@/utils/playingUp';

describe('allowsPlayingUp (SB-1443)', () => {
  it.each(['Friendly', 'Tournament', ' friendly '])('allows %s', name => {
    expect(allowsPlayingUp(name)).toBe(true);
  });

  it.each(['League', 'Flex', 'Playoff', '', null, undefined])(
    'keeps %s strict',
    name => {
      expect(allowsPlayingUp(name)).toBe(false);
    }
  );
});

describe('groupTeamsForMatch', () => {
  const registered = [
    { id: 1, name: 'IFA' },
    { id: 2, name: 'Boston Bolts' },
  ];
  const all = [
    { id: 2, name: 'Boston Bolts' },
    { id: 9, name: 'New England Revolution' },
    { id: 1, name: 'IFA' },
    { id: 7, name: 'Cedar Stars' },
  ];

  it('adds every unregistered team, sorted, when playing up', () => {
    expect(groupTeamsForMatch({ registered, all, playingUp: true })).toEqual({
      registered,
      others: [
        { id: 7, name: 'Cedar Stars' },
        { id: 9, name: 'New England Revolution' },
      ],
    });
  });

  it('offers no others when the match type is strict', () => {
    expect(groupTeamsForMatch({ registered, all, playingUp: false })).toEqual({
      registered,
      others: [],
    });
  });

  it('still offers others when nobody is registered', () => {
    const { registered: reg, others } = groupTeamsForMatch({
      registered: [],
      all,
      playingUp: true,
    });
    expect(reg).toEqual([]);
    expect(others).toHaveLength(4);
  });
});
