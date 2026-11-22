/**
 * TournamentMatchRow.vue — which rounds offer shootout inputs (SB-1752).
 *
 * Shootout inputs follow SHOOTOUT_ROUNDS: every knockout round plus
 * `consolation` and `placement_final`. `showcase` (an exhibition) and group
 * stage never need to break a level score.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';

import TournamentMatchRow from '@/components/TournamentMatchRow.vue';

const mkMatch = round => ({
  id: 1,
  match_date: '2099-01-01',
  scheduled_kickoff: '2099-01-01T12:00:00Z',
  match_status: 'scheduled',
  home_team: { id: 19, name: 'IFA' },
  away_team: { id: 40, name: 'NVA' },
  home_team_club: null,
  away_team_club: null,
  home_score: null,
  away_score: null,
  tournament_round: round,
  tournament_group: null,
  age_group: null,
});

async function penaltyEditorShown(round, home = '1', away = '1') {
  const wrapper = mount(TournamentMatchRow, {
    props: { match: mkMatch(round), canEdit: true },
  });
  await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
  await wrapper.find('[data-testid="edit-home-score"]').setValue(home);
  await wrapper.find('[data-testid="edit-away-score"]').setValue(away);
  return wrapper.find('[data-testid="penalty-editor"]').exists();
}

describe('TournamentMatchRow — shootout inputs by round', () => {
  it.each(['placement_final', 'consolation'])(
    'offers shootout inputs on a level %s score',
    async round => {
      expect(await penaltyEditorShown(round)).toBe(true);
    }
  );

  it('does not offer shootout inputs on a level showcase score', async () => {
    expect(await penaltyEditorShown('showcase')).toBe(false);
  });

  it.each(['placement_final', 'consolation'])(
    'hides shootout inputs on a decided %s score',
    async round => {
      expect(await penaltyEditorShown(round, '2', '1')).toBe(false);
    }
  );

  it.each([
    'round_of_32',
    'round_of_16',
    'quarterfinal',
    'semifinal',
    'third_place',
    'final',
  ])('still offers shootout inputs on a level %s score', async round => {
    expect(await penaltyEditorShown(round)).toBe(true);
  });

  it.each(['group_stage', null])(
    'still hides shootout inputs on a level %s score',
    async round => {
      expect(await penaltyEditorShown(round)).toBe(false);
    }
  );
});
