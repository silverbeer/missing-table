/**
 * LiveScoreboard.vue — stoppage badge (SB-67).
 *
 * Just covers the new isInStoppage display surface. The rest of the
 * scoreboard (score, goals list, team names, period text) is exercised
 * via manual + e2e checks and isn't under test here.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import LiveScoreboard from '@/components/live/LiveScoreboard.vue';

const baseMatchState = {
  home_team_id: 1,
  away_team_id: 2,
  home_team_name: 'Home FC',
  away_team_name: 'Away FC',
  home_score: 0,
  away_score: 0,
  age_group_name: 'U15',
  division_name: 'Northeast',
};

const mountBoard = (overrides = {}) =>
  mount(LiveScoreboard, {
    props: {
      matchState: baseMatchState,
      elapsedTime: '45:00',
      matchPeriod: '1st Half',
      events: [],
      ...overrides,
    },
  });

describe('LiveScoreboard stoppage badge (SB-67)', () => {
  it('does not render the badge during regulation', () => {
    const wrapper = mountBoard({ isInStoppage: false });
    expect(wrapper.find('[data-testid="stoppage-badge"]').exists()).toBe(false);
  });

  it('renders the badge when isInStoppage is true', () => {
    const wrapper = mountBoard({
      isInStoppage: true,
      elapsedTime: '45+2:45',
    });
    const badge = wrapper.find('[data-testid="stoppage-badge"]');
    expect(badge.exists()).toBe(true);
    expect(badge.text()).toBe('STOPPAGE TIME');
  });

  it('applies the clock-stoppage class to the clock when in stoppage', () => {
    const wrapper = mountBoard({
      isInStoppage: true,
      elapsedTime: '45+1:00',
    });
    expect(wrapper.find('.clock').classes()).toContain('clock-stoppage');
  });

  it('renders whatever elapsedTime string the parent provides', () => {
    // The composable formats `45+M:SS` for us; the scoreboard just
    // displays whatever string lands in the prop.
    const wrapper = mountBoard({
      isInStoppage: true,
      elapsedTime: '90+3:20',
    });
    expect(wrapper.find('.clock').text()).toBe('90+3:20');
  });
});
