/**
 * Goal-scorers tests (SB-33).
 *
 * Two layers:
 *  1. IgScorers presentational component — props in, markup out.
 *  2. End-to-end through IgShareCard — verifies useIgShareData derives
 *     scorers from raw events, gates them to result mode, orders by
 *     minute, splits by team, and flags braces / hat-tricks. Exercised on
 *     all four templates.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import IgScorers from '@/components/ig/IgScorers.vue';
import IgShareCard from '@/components/IgShareCard.vue';
import {
  createCompletedMatch,
  createGoalEvent,
} from '../helpers/matchFactories';

const TEMPLATES = ['overlay', 'split', 'tournament-round', 'stadium'];

// Completed tournament match so every template (incl. tournament-round)
// renders cleanly in result mode.
const resultMatch = (overrides = {}) =>
  createCompletedMatch({
    home_score: 3,
    away_score: 1,
    tournament_name: 'Spring Cup',
    tournament_round: 'final',
    ...overrides,
  });

const mountResult = (template, { events = [], match } = {}) =>
  mount(IgShareCard, {
    props: {
      match: match || resultMatch(),
      mode: 'result',
      template,
      events,
    },
  });

describe('IgScorers (presentational)', () => {
  const mountScorers = (props = {}) =>
    mount(IgScorers, {
      props: {
        home: [{ id: 1, name: '#10', minute: "22'", goalCount: 1 }],
        away: [{ id: 2, name: '#7', minute: "55'", goalCount: 1 }],
        ...props,
      },
    });

  it('renders one line per goal with name and minute', () => {
    const wrapper = mountScorers();
    const home = wrapper.findAll('[data-testid="ig-scorer-home"]');
    const away = wrapper.findAll('[data-testid="ig-scorer-away"]');
    expect(home).toHaveLength(1);
    expect(away).toHaveLength(1);
    expect(home[0].text()).toContain('#10');
    expect(home[0].text()).toContain("22'");
    expect(away[0].text()).toContain('#7');
  });

  it('flags multi-goal lines with the gold accent class', () => {
    const wrapper = mountScorers({
      home: [
        { id: 1, name: '#9', minute: "10'", goalCount: 2, isMultiGoal: true },
        { id: 2, name: '#9', minute: "40'", goalCount: 2, isMultiGoal: true },
      ],
    });
    const home = wrapper.findAll('[data-testid="ig-scorer-home"]');
    expect(home.every(l => l.classes().includes('ig-scorer-multi'))).toBe(true);
  });

  it('flags hat-trick lines and renders the celebration banner', () => {
    const wrapper = mountScorers({
      home: [
        { id: 1, name: '#9', minute: "10'", goalCount: 3, isHatTrick: true },
      ],
      hatTricks: [{ name: '#9', count: 3 }],
    });
    expect(wrapper.find('[data-testid="ig-scorer-home"]').classes()).toContain(
      'ig-scorer-hat'
    );
    const banner = wrapper.find('[data-testid="ig-hat-banner"]');
    expect(banner.exists()).toBe(true);
    expect(banner.text()).toContain('HAT-TRICK');
    expect(banner.text()).toContain('#9');
  });

  it('shows the tally instead of HAT-TRICK for 4+ goals', () => {
    const wrapper = mountScorers({
      home: [],
      away: [],
      hatTricks: [{ name: 'Ronaldo', count: 4 }],
    });
    const banner = wrapper.find('[data-testid="ig-hat-banner"]');
    expect(banner.text()).toContain('4 GOALS');
    expect(banner.text()).not.toContain('HAT-TRICK');
  });

  it('omits the banner when there are no hat-tricks', () => {
    const wrapper = mountScorers();
    expect(wrapper.find('[data-testid="ig-hat-banner"]').exists()).toBe(false);
  });

  it('applies the size variant class', () => {
    const wrapper = mountScorers({ size: 'sm' });
    expect(wrapper.find('[data-testid="ig-scorers"]').classes()).toContain(
      'ig-scorers-sm'
    );
  });
});

describe('goal scorers on result cards (SB-33)', () => {
  // #10 home @22', #7 away @55'.
  const oneEach = () => [
    createGoalEvent({
      id: 1,
      team_id: 1,
      player_name: '#10',
      match_minute: 22,
    }),
    createGoalEvent({ id: 2, team_id: 2, player_name: '#7', match_minute: 55 }),
  ];

  for (const template of TEMPLATES) {
    it(`renders the scorers block in result mode on the ${template} card`, () => {
      const wrapper = mountResult(template, { events: oneEach() });
      expect(wrapper.find('[data-testid="ig-scorers"]').exists()).toBe(true);
      expect(wrapper.findAll('[data-testid="ig-scorer-home"]')).toHaveLength(1);
      expect(wrapper.findAll('[data-testid="ig-scorer-away"]')).toHaveLength(1);
    });
  }

  it('hides scorers in preview mode even when events exist', () => {
    const wrapper = mount(IgShareCard, {
      props: {
        match: resultMatch(),
        mode: 'preview',
        template: 'stadium',
        events: oneEach(),
      },
    });
    expect(wrapper.find('[data-testid="ig-scorers"]').exists()).toBe(false);
  });

  it('hides scorers when the match has no goal events', () => {
    const wrapper = mountResult('stadium', { events: [] });
    expect(wrapper.find('[data-testid="ig-scorers"]').exists()).toBe(false);
  });

  it('ignores non-goal events (cards do not appear as scorers)', () => {
    const wrapper = mountResult('stadium', {
      events: [
        createGoalEvent({ id: 1, team_id: 1, player_name: '#10' }),
        createGoalEvent({
          id: 2,
          team_id: 1,
          event_type: 'yellow_card',
          player_name: '#4',
          match_minute: 70,
        }),
      ],
    });
    const home = wrapper.findAll('[data-testid="ig-scorer-home"]');
    expect(home).toHaveLength(1);
    expect(home[0].text()).toContain('#10');
    expect(wrapper.text()).not.toContain('#4');
  });

  it('orders scorers by match minute', () => {
    const wrapper = mountResult('stadium', {
      events: [
        createGoalEvent({
          id: 1,
          team_id: 1,
          player_name: 'Late',
          match_minute: 60,
        }),
        createGoalEvent({
          id: 2,
          team_id: 1,
          player_name: 'Early',
          match_minute: 8,
        }),
        createGoalEvent({
          id: 3,
          team_id: 1,
          player_name: 'Mid',
          match_minute: 33,
        }),
      ],
    });
    const names = wrapper
      .findAll('[data-testid="ig-scorer-home"]')
      .map(l => l.find('.ig-scorer-name').text());
    expect(names).toEqual(['Early', 'Mid', 'Late']);
  });

  it('formats stoppage-time minutes as "90+5\'"', () => {
    const wrapper = mountResult('stadium', {
      events: [
        createGoalEvent({
          id: 1,
          team_id: 1,
          player_name: '#11',
          match_minute: 90,
          extra_time: 5,
        }),
      ],
    });
    expect(wrapper.find('[data-testid="ig-scorer-home"]').text()).toContain(
      "90+5'"
    );
  });

  it('splits goals to the correct team column', () => {
    const wrapper = mountResult('stadium', {
      events: [
        createGoalEvent({ id: 1, team_id: 1, player_name: 'HomeGuy' }),
        createGoalEvent({
          id: 2,
          team_id: 2,
          player_name: 'AwayGuy',
          match_minute: 30,
        }),
      ],
    });
    expect(wrapper.find('[data-testid="ig-scorer-home"]').text()).toContain(
      'HomeGuy'
    );
    expect(wrapper.find('[data-testid="ig-scorer-away"]').text()).toContain(
      'AwayGuy'
    );
  });

  it('highlights a brace (2 goals) without a hat-trick banner', () => {
    const wrapper = mountResult('stadium', {
      events: [
        createGoalEvent({
          id: 1,
          team_id: 1,
          player_name: '#37',
          match_minute: 56,
        }),
        createGoalEvent({
          id: 2,
          team_id: 1,
          player_name: '#37',
          match_minute: 62,
        }),
      ],
    });
    const home = wrapper.findAll('[data-testid="ig-scorer-home"]');
    expect(home).toHaveLength(2);
    expect(home.every(l => l.classes().includes('ig-scorer-multi'))).toBe(true);
    expect(wrapper.find('[data-testid="ig-hat-banner"]').exists()).toBe(false);
  });

  it('celebrates a hat-trick (3 goals by one player)', () => {
    const wrapper = mountResult('stadium', {
      events: [
        createGoalEvent({
          id: 1,
          team_id: 1,
          player_name: 'Messi',
          match_minute: 12,
        }),
        createGoalEvent({
          id: 2,
          team_id: 1,
          player_name: 'Messi',
          match_minute: 44,
        }),
        createGoalEvent({
          id: 3,
          team_id: 1,
          player_name: 'Messi',
          match_minute: 77,
        }),
      ],
    });
    const banner = wrapper.find('[data-testid="ig-hat-banner"]');
    expect(banner.exists()).toBe(true);
    expect(banner.text()).toContain('HAT-TRICK');
    expect(banner.text()).toContain('Messi');
    const home = wrapper.findAll('[data-testid="ig-scorer-home"]');
    expect(home.every(l => l.classes().includes('ig-scorer-hat'))).toBe(true);
  });

  it('does not group distinct players who share no id/name into a brace', () => {
    const wrapper = mountResult('stadium', {
      events: [
        createGoalEvent({
          id: 1,
          team_id: 1,
          player_name: '#5',
          match_minute: 10,
        }),
        createGoalEvent({
          id: 2,
          team_id: 1,
          player_name: '#6',
          match_minute: 20,
        }),
      ],
    });
    const home = wrapper.findAll('[data-testid="ig-scorer-home"]');
    expect(home.some(l => l.classes().includes('ig-scorer-multi'))).toBe(false);
  });

  it('does not merge the same jersey number across opposing teams', () => {
    // Both teams field a #9 with no player_id — different players, so
    // neither line should be flagged multi-goal and there is no banner.
    const wrapper = mountResult('stadium', {
      events: [
        createGoalEvent({
          id: 1,
          team_id: 1,
          player_name: '#9',
          match_minute: 15,
        }),
        createGoalEvent({
          id: 2,
          team_id: 2,
          player_name: '#9',
          match_minute: 40,
        }),
      ],
    });
    expect(
      wrapper.find('[data-testid="ig-scorer-home"]').classes()
    ).not.toContain('ig-scorer-multi');
    expect(
      wrapper.find('[data-testid="ig-scorer-away"]').classes()
    ).not.toContain('ig-scorer-multi');
    expect(wrapper.find('[data-testid="ig-hat-banner"]').exists()).toBe(false);
  });
});
