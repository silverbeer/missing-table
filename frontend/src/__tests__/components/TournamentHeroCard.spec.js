/**
 * TournamentHeroCard.vue tests (SB-886).
 *
 * The card's job is to say where the tournament is in its own life before it
 * says what is in it. The cases that matter most are the absent ones: a viewer
 * with no club here, a tournament with no dates, a description that is not a
 * URL. Each degrades to nothing rather than to a placeholder.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { mount } from '@vue/test-utils';

import TournamentHeroCard from '@/components/TournamentHeroCard.vue';

const NOW = new Date(2026, 7, 28, 12, 0, 0); // Fri 28 Aug 2026, local noon

const tournament = (over = {}) => ({
  id: 5,
  name: 'Copa Rayados East Coast',
  start_date: '2026-08-29',
  end_date: '2026-08-30',
  location: 'Washington, DC',
  description:
    'https://system.gotsport.com/users/11093508/events/52496/schedules',
  logo_url: 'https://example.test/copa.png',
  age_groups: [{ id: 2, name: 'U15' }],
  ...over,
});

const mkMatch = (over = {}) => ({
  id: 3853,
  match_date: '2026-08-29',
  scheduled_kickoff: '2026-08-29T14:10:00Z',
  match_status: 'scheduled',
  home_team: { id: 19, name: 'IFA' },
  away_team: { id: 40, name: 'Northern Virginia Alliance' },
  home_team_club: { id: 1, name: 'IFA' },
  away_team_club: { id: 7, name: 'NVA' },
  home_score: null,
  away_score: null,
  ...over,
});

const mountCard = (props = {}) => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
  return mount(TournamentHeroCard, {
    props: { tournament: tournament(), matches: [mkMatch()], ...props },
  });
};

afterEach(() => {
  vi.useRealTimers();
});

describe('TournamentHeroCard — status ribbon', () => {
  it('says the tournament starts tomorrow', () => {
    const ribbon = mountCard().find('[data-testid="tournament-status-ribbon"]');

    expect(ribbon.exists()).toBe(true);
    expect(ribbon.attributes('data-state')).toBe('soon');
    expect(ribbon.text()).toContain('Starts tomorrow');
  });

  it('counts down to the first kickoff', () => {
    const wrapper = mountCard();

    // 12:00 local on the 28th to 14:10 UTC on the 29th.
    expect(wrapper.find('[data-testid="tournament-countdown"]').exists()).toBe(
      true
    );
  });

  it('renders no ribbon at all when the tournament has no dates', () => {
    // Unknown is not "upcoming". Absent renders as absent.
    const wrapper = mountCard({
      tournament: tournament({ start_date: null, end_date: null }),
    });

    expect(
      wrapper.find('[data-testid="tournament-status-ribbon"]').exists()
    ).toBe(false);
  });

  it('goes live when a match is in progress', () => {
    const wrapper = mountCard({
      matches: [mkMatch({ match_status: 'in_progress' })],
    });

    const ribbon = wrapper.find('[data-testid="tournament-status-ribbon"]');
    expect(ribbon.attributes('data-state')).toBe('live');
    expect(ribbon.text()).toContain('Live now');
  });
});

describe('TournamentHeroCard — the schedule URL', () => {
  it('renders a bare URL description as a named link', () => {
    const link = mountCard().find('[data-testid="tournament-schedule-link"]');

    expect(link.exists()).toBe(true);
    expect(link.text()).toContain('Schedule on GotSport');
    expect(link.attributes('href')).toContain('system.gotsport.com');
    expect(link.attributes('rel')).toContain('noopener');
  });

  it('renders prose descriptions as prose, not as a link', () => {
    const wrapper = mountCard({
      tournament: tournament({ description: 'Showcase event for U15 clubs.' }),
    });

    expect(
      wrapper.find('[data-testid="tournament-schedule-link"]').exists()
    ).toBe(false);
    expect(wrapper.find('[data-testid="tournament-description"]').text()).toBe(
      'Showcase event for U15 clubs.'
    );
  });

  it('renders neither when there is no description', () => {
    const wrapper = mountCard({
      tournament: tournament({ description: null }),
    });

    expect(
      wrapper.find('[data-testid="tournament-schedule-link"]').exists()
    ).toBe(false);
    expect(
      wrapper.find('[data-testid="tournament-description"]').exists()
    ).toBe(false);
  });
});

describe('TournamentHeroCard — your next match', () => {
  it('is absent for a signed-out visitor', () => {
    // The default state: no user data. The strip collapses rather than
    // rendering an empty promise.
    expect(
      mountCard().find('[data-testid="tournament-next-match"]').exists()
    ).toBe(false);
  });

  it('is absent for a club with no fixtures in this tournament', () => {
    expect(
      mountCard({ myClubId: 999 })
        .find('[data-testid="tournament-next-match"]')
        .exists()
    ).toBe(false);
  });

  it('names the next fixture for the viewer club', () => {
    const strip = mountCard({ myClubId: 1 }).find(
      '[data-testid="tournament-next-match"]'
    );

    expect(strip.exists()).toBe(true);
    expect(strip.text()).toContain('IFA');
    expect(strip.text()).toContain('Northern Virginia Alliance');
  });

  it('skips fixtures that have already been played', () => {
    const wrapper = mountCard({
      myClubId: 1,
      matches: [
        mkMatch({
          id: 1,
          match_status: 'completed',
          home_score: 2,
          away_score: 1,
        }),
        mkMatch({
          id: 2,
          scheduled_kickoff: '2026-08-30T13:50:00Z',
          away_team: { id: 55, name: 'Bethesda SC' },
        }),
      ],
    });

    const strip = wrapper.find('[data-testid="tournament-next-match"]');
    expect(strip.text()).toContain('Bethesda SC');
  });

  it('emits the match when the strip is clicked', () => {
    const wrapper = mountCard({ myClubId: 1 });
    wrapper.find('[data-testid="tournament-next-match"]').trigger('click');

    expect(wrapper.emitted('select-match')).toHaveLength(1);
  });
});

describe('TournamentHeroCard — quick stats', () => {
  it('dims a zero played count rather than presenting it as a result', () => {
    const stats = mountCard().findAll('[data-testid="tournament-stat"]');
    const played = stats.find(s => s.text().includes('Played'));

    expect(played.text()).toContain('0');
    expect(played.find('.text-fg-muted').exists()).toBe(true);
  });

  it('omits the "your matches" tile when the viewer has no club here', () => {
    // Otherwise it would read "0 Your matches" — a claim about a club that is
    // not in this tournament.
    const stats = mountCard().findAll('[data-testid="tournament-stat"]');

    expect(stats.some(s => s.text().includes('Your matches'))).toBe(false);
  });

  it('counts the viewer own matches when they have some', () => {
    const stats = mountCard({ myClubId: 1 }).findAll(
      '[data-testid="tournament-stat"]'
    );
    const mine = stats.find(s => s.text().includes('Your matches'));

    expect(mine).toBeDefined();
    expect(mine.text()).toContain('1');
  });

  it('counts distinct days, not matches', () => {
    const wrapper = mountCard({
      matches: [
        mkMatch({ id: 1, match_date: '2026-08-29' }),
        mkMatch({ id: 2, match_date: '2026-08-29' }),
        mkMatch({ id: 3, match_date: '2026-08-30' }),
      ],
    });
    const stats = wrapper.findAll('[data-testid="tournament-stat"]');
    const days = stats.find(s => s.text().includes('Days'));

    expect(days.text()).toContain('2');
  });
});
