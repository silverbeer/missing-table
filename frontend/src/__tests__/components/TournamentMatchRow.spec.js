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

  it('marks a live match', () => {
    const wrapper = mountRow({
      match: mkMatch({
        home_score: 1,
        away_score: 1,
        match_status: 'in_progress',
      }),
    });

    const label = wrapper.find('[data-testid="match-status-label"]');
    expect(label.text()).toBe('Live');
    expect(label.classes()).toContain('animate-pulse');
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
