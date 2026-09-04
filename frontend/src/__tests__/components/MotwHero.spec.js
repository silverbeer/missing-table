/**
 * MotwHero.vue tests (SB-1010).
 *
 * The hero is the one place in the app that announces a match as special, so
 * the states it can get wrong are expensive: a countdown on a match played
 * last week, or a 0–0 printed under a fixture nobody has played.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import MotwHero from '@/components/MotwHero.vue';

const HOUR = 60 * 60 * 1000;
const DAY = 24 * HOUR;

const makeMatch = (overrides = {}) => ({
  id: 1,
  match_date: '2026-09-05',
  scheduled_kickoff: new Date(Date.now() + 2 * DAY).toISOString(),
  home_team_name: 'NEFC',
  away_team_name: 'IFA',
  home_team_club: { logo_url: '/logos/nefc.png' },
  away_team_club: { logo_url: '/logos/ifa.png' },
  home_score: null,
  away_score: null,
  match_status: 'scheduled',
  age_group_name: 'U15',
  division_name: 'Northeast',
  ...overrides,
});

const mountHero = (props = {}) =>
  mount(MotwHero, {
    props: { match: makeMatch(), ...props },
    global: { stubs: { ClubLogo: true } },
  });

describe('MotwHero', () => {
  describe('the fixture', () => {
    it('names both teams', () => {
      const wrapper = mountHero();

      expect(wrapper.find('[data-testid="motw-home"]').text()).toBe('NEFC');
      expect(wrapper.find('[data-testid="motw-away"]').text()).toBe('IFA');
    });

    it('shows "vs" and no score before the match is played', () => {
      const wrapper = mountHero();

      expect(wrapper.find('[data-testid="motw-vs"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="motw-score"]').exists()).toBe(false);
    });

    it('shows the score once the match is complete', () => {
      const wrapper = mountHero({
        match: makeMatch({
          match_status: 'completed',
          home_score: 3,
          away_score: 1,
        }),
      });

      expect(wrapper.find('[data-testid="motw-score"]').text()).toContain('3');
      expect(wrapper.find('[data-testid="motw-score"]').text()).toContain('1');
      expect(wrapper.find('[data-testid="motw-vs"]').exists()).toBe(false);
    });

    it('never renders 0–0 for a scheduled match carrying stored zeros', () => {
      // A scheduled match with zeros on it is not a goalless draw — it is a
      // result nobody recorded (CLAUDE.md rule 2, SB-886).
      const wrapper = mountHero({
        match: makeMatch({ home_score: 0, away_score: 0 }),
      });

      expect(wrapper.find('[data-testid="motw-score"]').exists()).toBe(false);
      expect(wrapper.find('[data-testid="motw-vs"]').exists()).toBe(true);
    });

    it('treats a half-entered result as no result', () => {
      const wrapper = mountHero({
        match: makeMatch({
          match_status: 'completed',
          home_score: 2,
          away_score: null,
        }),
      });

      expect(wrapper.find('[data-testid="motw-score"]').exists()).toBe(false);
    });
  });

  describe('the status line', () => {
    it('counts down in days for a match days away', () => {
      const wrapper = mountHero();

      expect(wrapper.find('[data-testid="motw-status"]').text()).toBe(
        'Kicks off in 2 days'
      );
    });

    it('counts down in hours inside a day', () => {
      const wrapper = mountHero({
        match: makeMatch({
          scheduled_kickoff: new Date(Date.now() + 3 * HOUR).toISOString(),
        }),
      });

      expect(wrapper.find('[data-testid="motw-status"]').text()).toBe(
        'Kicks off in 3 hours'
      );
    });

    it('says full time instead of counting down to a played match', () => {
      // The countdown running on a finished match is what makes a featured
      // card look abandoned by Monday.
      const wrapper = mountHero({
        match: makeMatch({
          match_status: 'completed',
          home_score: 1,
          away_score: 0,
          scheduled_kickoff: new Date(Date.now() - 3 * DAY).toISOString(),
        }),
      });

      expect(wrapper.find('[data-testid="motw-status"]').text()).toBe(
        'Full time'
      );
    });

    it('says live while the match is under way', () => {
      const wrapper = mountHero({
        match: makeMatch({
          match_status: 'live',
          home_score: 1,
          away_score: 1,
        }),
      });

      expect(wrapper.find('[data-testid="motw-status"]').text()).toBe(
        'Live now'
      );
    });

    it('admits an unknown kick-off rather than inventing one', () => {
      const wrapper = mountHero({
        match: makeMatch({ scheduled_kickoff: null }),
      });

      expect(wrapper.find('[data-testid="motw-status"]').text()).toBe(
        'Time TBC'
      );
    });
  });

  describe('the meta line', () => {
    it('lists age group and division', () => {
      const text = mountHero().find('[data-testid="motw-meta"]').text();

      expect(text).toContain('U15');
      expect(text).toContain('Northeast');
    });

    it('omits a division the API could not name, rather than printing Unknown', () => {
      // "Unknown" on the one card the site is showing off is worse than a
      // shorter line.
      const wrapper = mountHero({
        match: makeMatch({ division_name: 'Unknown' }),
      });

      expect(wrapper.find('[data-testid="motw-meta"]').text()).not.toContain(
        'Unknown'
      );
    });

    it('falls back to the match date when there is no kick-off time', () => {
      const wrapper = mountHero({
        match: makeMatch({ scheduled_kickoff: null }),
      });

      expect(wrapper.find('[data-testid="motw-meta"]').text()).toContain(
        '2026-09-05'
      );
    });
  });

  describe('blurb and actions', () => {
    it('renders the blurb when there is one', () => {
      const wrapper = mountHero({ blurb: 'Two unbeaten records.' });

      expect(wrapper.find('[data-testid="motw-blurb"]').text()).toBe(
        'Two unbeaten records.'
      );
    });

    it('renders no blurb element at all when none was written', () => {
      // Absent renders as absent, not as an empty line holding space.
      expect(mountHero().find('[data-testid="motw-blurb"]').exists()).toBe(
        false
      );
    });

    it('hides the share button from logged-out viewers', () => {
      expect(mountHero().find('[data-testid="motw-share"]').exists()).toBe(
        false
      );
    });

    it('offers sharing to a signed-in viewer', () => {
      const wrapper = mountHero({ canShare: true });

      expect(wrapper.find('[data-testid="motw-share"]').exists()).toBe(true);
    });

    it('emits the match on preview and share', async () => {
      const wrapper = mountHero({ canShare: true });

      await wrapper.find('[data-testid="motw-preview"]').trigger('click');
      await wrapper.find('[data-testid="motw-share"]').trigger('click');

      expect(wrapper.emitted('preview')[0][0].id).toBe(1);
      expect(wrapper.emitted('share')[0][0].id).toBe(1);
    });

    it('calls the primary action "View match" once there is a result', () => {
      const wrapper = mountHero({
        match: makeMatch({
          match_status: 'completed',
          home_score: 2,
          away_score: 2,
        }),
      });

      expect(wrapper.find('[data-testid="motw-preview"]').text()).toBe(
        'View match'
      );
    });
  });
});
