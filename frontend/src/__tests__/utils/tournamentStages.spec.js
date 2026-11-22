/**
 * tournamentStages — showcase, placement finals and consolation sections
 * (SB-1749).
 */

import { describe, it, expect } from 'vitest';
import {
  STAGE_ROUNDS,
  STAGE_ROUND_SECTIONS,
  buildStageSections,
  stageSectionTitle,
} from '@/utils/tournamentStages';
import {
  BRACKET_ROUNDS,
  KNOCKOUT_ROUNDS,
  TOURNAMENT_ROUNDS,
} from '@/utils/tournamentRounds';

const m = (id, round, group) => ({
  id,
  tournament_round: round,
  tournament_group: group,
});

const SHOWCASE = STAGE_ROUND_SECTIONS.find(s => s.round === 'showcase');
const PLACEMENT = STAGE_ROUND_SECTIONS.find(s => s.round === 'placement_final');

describe('stage rounds', () => {
  it('are the three Fest rounds, all real round keys', () => {
    expect([...STAGE_ROUNDS].sort()).toEqual([
      'consolation',
      'placement_final',
      'showcase',
    ]);
    for (const round of STAGE_ROUNDS) {
      expect(TOURNAMENT_ROUNDS[round]).toBeTruthy();
    }
  });

  it('none is a knockout or bracket round', () => {
    for (const round of STAGE_ROUNDS) {
      expect(KNOCKOUT_ROUNDS.has(round)).toBe(false);
      expect(BRACKET_ROUNDS.has(round)).toBe(false);
    }
  });
});

describe('stageSectionTitle', () => {
  it('uses the round title when there is no stage label', () => {
    expect(stageSectionTitle('Showcase', null)).toBe('Showcase');
    expect(stageSectionTitle('Showcase', '  ')).toBe('Showcase');
  });

  it('lets a label that already names the round stand alone', () => {
    expect(stageSectionTitle('Showcase', 'HD · Showcase')).toBe(
      'HD · Showcase'
    );
  });

  it('leads with the round when the label does not name it', () => {
    expect(stageSectionTitle('Placement Finals', 'HD · Group Play')).toBe(
      'Placement Finals — HD · Group Play'
    );
    expect(stageSectionTitle('Consolation', 'GA Cup Qualifier')).toBe(
      'Consolation — GA Cup Qualifier'
    );
  });
});

describe('buildStageSections', () => {
  it('is empty when the round has no matches', () => {
    expect(
      buildStageSections([m(1, 'group_stage', 'HD · A')], SHOWCASE)
    ).toEqual([]);
    expect(buildStageSections([], SHOWCASE)).toEqual([]);
    expect(buildStageSections(null, SHOWCASE)).toEqual([]);
  });

  it('makes one section per stage label, in label order', () => {
    const sections = buildStageSections(
      [
        m(1, 'showcase', 'HD · Showcase'),
        m(2, 'showcase', 'AD · Showcase'),
        m(3, 'showcase', 'HD · Showcase'),
        m(4, 'group_stage', 'HD · A'),
      ],
      SHOWCASE
    );
    expect(sections.map(s => s.title)).toEqual([
      'AD · Showcase',
      'HD · Showcase',
    ]);
    expect(sections[1].matches.map(x => x.id)).toEqual([1, 3]);
    expect(new Set(sections.map(s => s.key)).size).toBe(2);
  });

  it('puts matches with no label last, under the round title', () => {
    const sections = buildStageSections(
      [
        m(1, 'placement_final', null),
        m(2, 'placement_final', 'HD · Group Play'),
      ],
      PLACEMENT
    );
    expect(sections.map(s => s.title)).toEqual([
      'Placement Finals — HD · Group Play',
      'Placement Finals',
    ]);
  });
});
