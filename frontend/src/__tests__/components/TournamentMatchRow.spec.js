/**
 * TournamentMatchRow.vue tests (SB-886).
 *
 * The row was three byte-identical copies inside TournamentMatchCenter (group
 * stage / knockout / untagged), so every fix had to be written three times.
 * This is the single component they collapsed into.
 *
 * Per CLAUDE.md the default fixture is a team with scraped matches and no user
 * data — a signed-out viewer looking at a scheduled fixture. The "my club"
 * cases are the special case, because they are the special case in production.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';

import TournamentMatchRow from '@/components/TournamentMatchRow.vue';

const IFA = { id: 19, name: 'IFA' };
const NVA = { id: 40, name: 'Northern Virginia Alliance' };

const mkMatch = (over = {}) => ({
  id: 3853,
  match_date: '2026-08-29',
  scheduled_kickoff: '2026-08-29T14:10:00Z',
  match_status: 'scheduled',
  home_team: IFA,
  away_team: NVA,
  home_team_club: { id: 1, name: 'IFA' },
  away_team_club: { id: 7, name: 'NVA' },
  home_score: null,
  away_score: null,
  tournament_round: 'group_stage',
  tournament_group: null,
  age_group: null,
  ...over,
});

const mountRow = (props = {}) =>
  mount(TournamentMatchRow, { props: { match: mkMatch(), ...props } });

// Thin space (U+2009) and nbsp are invisible in assertions; strip them.
const text = wrapper => wrapper.text().replace(/[\u2009\u00a0]/g, ' ');

describe('TournamentMatchRow — the default case: no user data', () => {
  it('shows vs for a fixture that has not kicked off', () => {
    expect(text(mountRow())).toContain('vs');
  });

  it('shows vs even when the row carries placeholder zeros', () => {
    // The prod shape before the backfill: scheduled, but 0-0 on the row.
    const wrapper = mountRow({
      match: mkMatch({ home_score: 0, away_score: 0 }),
    });

    expect(text(wrapper)).toContain('vs');
    expect(text(wrapper)).not.toContain('0 – 0');
  });

  it('renders the status, not a "Preview" pseudo-link', () => {
    const wrapper = mountRow();

    expect(wrapper.find('[data-testid="match-status-label"]').text()).toBe(
      'Scheduled'
    );
    expect(text(wrapper)).not.toContain('Preview');
  });

  it('applies no highlight rail when signed out', () => {
    expect(mountRow().attributes('data-mine')).toBe('false');
  });

  it('emits the match on click, so the whole row navigates', () => {
    const wrapper = mountRow();
    wrapper.trigger('click');

    expect(wrapper.emitted('select')).toHaveLength(1);
    expect(wrapper.emitted('select')[0][0].id).toBe(3853);
  });

  it('renders a dash rather than a blank when kickoff is unknown', () => {
    // Absent renders as absent — never as a guessed midnight.
    const wrapper = mountRow({
      match: mkMatch({ scheduled_kickoff: null }),
    });

    expect(text(wrapper)).toContain('—');
  });
});

describe('TournamentMatchRow — results', () => {
  it('renders a completed scoreline', () => {
    const wrapper = mountRow({
      match: mkMatch({
        home_score: 2,
        away_score: 1,
        match_status: 'completed',
      }),
    });

    expect(text(wrapper)).toContain('2 – 1');
    expect(wrapper.find('[data-testid="match-status-label"]').text()).toBe(
      'Final'
    );
  });

  it('marks a live-scored match', () => {
    const wrapper = mountRow({
      match: mkMatch({
        home_score: 1,
        away_score: 1,
        match_status: 'in_progress',
        scoring_mode: 'live',
      }),
    });

    const label = wrapper.find('[data-testid="match-status-label"]');
    expect(label.text()).toBe('Live');
    expect(label.classes()).toContain('animate-pulse');
  });

  it('marks a match under the status the database actually stores', () => {
    // The enum member is `live`; the vocabulary here only knew `in_progress`,
    // so a match genuinely under way rendered no status at all (SB-910).
    const wrapper = mountRow({
      match: mkMatch({
        home_score: 1,
        away_score: 1,
        match_status: 'live',
        scoring_mode: 'live',
      }),
    });

    expect(wrapper.find('[data-testid="match-status-label"]').text()).toBe(
      'Live'
    );
  });

  it('says In Progress, without a pulse, when nobody is live-scoring', () => {
    const wrapper = mountRow({
      match: mkMatch({
        home_score: 1,
        away_score: 1,
        match_status: 'live',
        scoring_mode: 'manual',
      }),
    });

    const label = wrapper.find('[data-testid="match-status-label"]');
    expect(label.text()).toBe('In Progress');
    expect(label.classes()).not.toContain('animate-pulse');
  });

  it('shows the scoreline of a match under way', () => {
    const wrapper = mountRow({
      match: mkMatch({
        home_score: 2,
        away_score: 3,
        match_status: 'live',
        scoring_mode: 'manual',
      }),
    });

    expect(wrapper.text()).toContain('2');
    expect(wrapper.text()).toContain('3');
  });

  it('renders nothing rather than guessing for an unknown status', () => {
    const wrapper = mountRow({
      match: mkMatch({ match_status: 'something_new' }),
    });

    expect(wrapper.find('[data-testid="match-status-label"]').exists()).toBe(
      false
    );
  });
});

describe('TournamentMatchRow — highlighting the viewer club', () => {
  it('rails the row when the club is the viewer own', () => {
    const wrapper = mountRow({ myClubId: 1 });

    expect(wrapper.attributes('data-mine')).toBe('true');
    expect(wrapper.classes()).toContain('border-l-accent-400');
  });

  it('matches on the away side too', () => {
    expect(mountRow({ myClubId: 7 }).attributes('data-mine')).toBe('true');
  });

  it('falls back to team id for profiles that carry only that', () => {
    expect(mountRow({ myTeamId: 19 }).attributes('data-mine')).toBe('true');
  });

  it('leaves another club match unrailed', () => {
    const wrapper = mountRow({ myClubId: 999 });

    expect(wrapper.attributes('data-mine')).toBe('false');
    expect(wrapper.classes()).toContain('border-l-transparent');
  });
});

describe('TournamentMatchRow — chips', () => {
  it('hides the age chip unless asked for it', () => {
    const wrapper = mountRow({
      match: mkMatch({ age_group: { id: 2, name: 'U15' } }),
    });

    expect(wrapper.findAll('[data-variant="age"]')).toHaveLength(0);
  });

  it('shows the age chip when the tournament spans ages', () => {
    const wrapper = mountRow({
      match: mkMatch({ age_group: { id: 2, name: 'U15' } }),
      showAgeChip: true,
    });

    // Mobile and desktop copies both render; both should say U15.
    const chips = wrapper.findAll('[data-variant="age"]');
    expect(chips.length).toBeGreaterThan(0);
    expect(chips[0].text()).toBe('U15');
  });

  it('shows the round chip only on knockout rows', () => {
    const wrapper = mountRow({
      match: mkMatch({ tournament_round: 'semifinal' }),
      showRoundChip: true,
    });

    expect(wrapper.findAll('[data-variant="round"]').length).toBeGreaterThan(0);
  });

  it('uses themed chips rather than hardcoded light-only palettes', () => {
    // The old inline chips were bg-indigo-100 / bg-purple-100 with no dark
    // variant, so they rendered as pale blocks on a navy card.
    const wrapper = mountRow({
      match: mkMatch({ age_group: { id: 2, name: 'U15' } }),
      showAgeChip: true,
    });

    const classes = wrapper
      .findAll('[data-variant="age"]')[0]
      .classes()
      .join(' ');
    expect(classes).toMatch(/dark:/);
    expect(classes).not.toMatch(/bg-indigo-100|bg-purple-100/);
  });
});

describe('TournamentMatchRow — a past match that never got a result (SB-889)', () => {
  // "Scheduled" is a claim about the future. On a fixture that kicked off in
  // June it is false in the same way "0 - 0" was: a confident statement the
  // data does not support.

  it('reads "Not reported" once the date has passed', () => {
    const wrapper = mountRow({
      match: mkMatch({ match_date: '2020-06-05', match_status: 'scheduled' }),
    });

    const label = wrapper.find('[data-testid="match-status-label"]');
    expect(label.text()).toBe('Not reported');
    expect(label.attributes('data-missing-result')).toBe('true');
  });

  it('still shows vs, not a score, for that match', () => {
    // The two must agree: no result in the status column, no result in the
    // score slot.
    const wrapper = mountRow({
      match: mkMatch({
        match_date: '2020-06-05',
        match_status: 'scheduled',
        home_score: 0,
        away_score: 0,
      }),
    });

    expect(text(wrapper)).toContain('vs');
    expect(text(wrapper)).not.toContain('0 – 0');
  });

  it('keeps saying Cancelled for a cancelled match, however old', () => {
    const wrapper = mountRow({
      match: mkMatch({ match_date: '2020-06-05', match_status: 'cancelled' }),
    });

    expect(wrapper.find('[data-testid="match-status-label"]').text()).toBe(
      'Cancelled'
    );
  });

  it('keeps saying Final for a completed match', () => {
    const wrapper = mountRow({
      match: mkMatch({
        match_date: '2020-06-05',
        match_status: 'completed',
        home_score: 2,
        away_score: 1,
      }),
    });

    expect(wrapper.find('[data-testid="match-status-label"]').text()).toBe(
      'Final'
    );
  });
});

describe('TournamentMatchRow — inline scoring (SB-906)', () => {
  it('shows no edit control to a viewer who may not edit', () => {
    const wrapper = mountRow();
    expect(wrapper.find('[data-testid="edit-score-button"]').exists()).toBe(
      false
    );
  });

  it('offers an edit control when the viewer may edit this match', () => {
    const wrapper = mountRow({ canEdit: true });
    expect(wrapper.find('[data-testid="edit-score-button"]').exists()).toBe(
      true
    );
  });

  it('opens empty boxes for an unscored match — absent is not 0-0', async () => {
    const wrapper = mountRow({ canEdit: true });
    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    expect(wrapper.find('[data-testid="edit-home-score"]').element.value).toBe(
      ''
    );
    expect(wrapper.find('[data-testid="edit-away-score"]').element.value).toBe(
      ''
    );
  });

  it('seeds the boxes from an existing score', async () => {
    const wrapper = mountRow({
      canEdit: true,
      match: mkMatch({
        home_score: 2,
        away_score: 1,
        match_status: 'completed',
      }),
    });
    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    expect(wrapper.find('[data-testid="edit-home-score"]').element.value).toBe(
      '2'
    );
    expect(wrapper.find('[data-testid="edit-away-score"]').element.value).toBe(
      '1'
    );
  });

  it('does not open the match detail when the editor is clicked', async () => {
    const wrapper = mountRow({ canEdit: true });
    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    await wrapper.find('[data-testid="edit-home-score"]').trigger('click');
    expect(wrapper.emitted('select')).toBeUndefined();
  });

  it('refuses to save a half-entered score', async () => {
    const wrapper = mountRow({ canEdit: true });
    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    await wrapper.find('[data-testid="edit-home-score"]').setValue('2');
    const save = wrapper.find('[data-testid="save-score-button"]');
    expect(save.attributes('disabled')).toBeDefined();
    await save.trigger('click');
    expect(wrapper.emitted('save')).toBeUndefined();
  });

  it('emits the entered score', async () => {
    const wrapper = mountRow({ canEdit: true });
    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    await wrapper.find('[data-testid="edit-home-score"]').setValue('3');
    await wrapper.find('[data-testid="edit-away-score"]').setValue('1');
    await wrapper.find('[data-testid="save-score-button"]').trigger('click');

    const [payload] = wrapper.emitted('save')[0];
    expect(payload.match.id).toBe(3853);
    expect(payload.home_score).toBe(3);
    expect(payload.away_score).toBe(1);
    expect(payload.home_penalty_score).toBeUndefined();
  });

  it('keeps a 0-0 result distinct from no result', async () => {
    const wrapper = mountRow({ canEdit: true });
    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    await wrapper.find('[data-testid="edit-home-score"]').setValue('0');
    await wrapper.find('[data-testid="edit-away-score"]').setValue('0');
    await wrapper.find('[data-testid="save-score-button"]').trigger('click');

    const [payload] = wrapper.emitted('save')[0];
    expect(payload.home_score).toBe(0);
    expect(payload.away_score).toBe(0);
  });

  it('hides penalty inputs on a level group-stage score', async () => {
    const wrapper = mountRow({ canEdit: true });
    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    await wrapper.find('[data-testid="edit-home-score"]').setValue('1');
    await wrapper.find('[data-testid="edit-away-score"]').setValue('1');
    expect(wrapper.find('[data-testid="penalty-editor"]').exists()).toBe(false);
  });

  it('shows penalty inputs only on a level bracket-round score', async () => {
    const wrapper = mountRow({
      canEdit: true,
      match: mkMatch({ tournament_round: 'semifinal' }),
    });
    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    await wrapper.find('[data-testid="edit-home-score"]').setValue('2');
    await wrapper.find('[data-testid="edit-away-score"]').setValue('1');
    expect(wrapper.find('[data-testid="penalty-editor"]').exists()).toBe(false);

    await wrapper.find('[data-testid="edit-away-score"]').setValue('2');
    expect(wrapper.find('[data-testid="penalty-editor"]').exists()).toBe(true);
  });

  it('emits the shootout alongside a level bracket score', async () => {
    const wrapper = mountRow({
      canEdit: true,
      match: mkMatch({ tournament_round: 'final' }),
    });
    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    await wrapper.find('[data-testid="edit-home-score"]').setValue('1');
    await wrapper.find('[data-testid="edit-away-score"]').setValue('1');
    await wrapper.find('[data-testid="edit-home-penalty"]').setValue('5');
    await wrapper.find('[data-testid="edit-away-penalty"]').setValue('4');
    await wrapper.find('[data-testid="save-score-button"]').trigger('click');

    const [payload] = wrapper.emitted('save')[0];
    expect(payload.home_penalty_score).toBe(5);
    expect(payload.away_penalty_score).toBe(4);
  });

  it('closes the editor once the parent reports the save finished', async () => {
    const wrapper = mountRow({ canEdit: true });
    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    await wrapper.setProps({ saving: true });
    await wrapper.setProps({ saving: false });
    expect(
      wrapper.find('[data-testid="tournament-score-editor"]').exists()
    ).toBe(false);
  });

  it('keeps the typed score on the row when the save fails', async () => {
    const wrapper = mountRow({ canEdit: true });
    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    await wrapper.find('[data-testid="edit-home-score"]').setValue('4');
    await wrapper.setProps({ saving: true });
    await wrapper.setProps({ saving: false, saveError: 'Network error' });

    expect(wrapper.find('[data-testid="edit-home-score"]').element.value).toBe(
      '4'
    );
    expect(text(wrapper)).toContain('Network error');
  });

  it('cancels back to the score pill without emitting', async () => {
    const wrapper = mountRow({ canEdit: true });
    await wrapper.find('[data-testid="edit-score-button"]').trigger('click');
    await wrapper.find('[data-testid="cancel-score-button"]').trigger('click');
    expect(
      wrapper.find('[data-testid="tournament-score-editor"]').exists()
    ).toBe(false);
    expect(wrapper.emitted('save')).toBeUndefined();
  });
});
