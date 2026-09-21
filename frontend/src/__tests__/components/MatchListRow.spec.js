/**
 * The compact phone match row (SB-1101).
 *
 * The acceptance criteria are all about what a row no longer says and what it
 * still must: Type / Status / Match ID / Source are gone, tap opens the match,
 * a long press opens the sheet, and the three states a match can be in stay
 * distinguishable from each other.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount } from '@vue/test-utils';
import MatchListRow from '@/components/matches/MatchListRow.vue';
import {
  createMockMatch,
  createCompletedMatch,
  createLiveMatch,
  createPostponedMatch,
} from '../helpers/matchFactories';

// Stub ClubLogo: it fetches nothing, but stubbing keeps the rendered text to
// what this row itself writes.
vi.mock('@/components/shared/ClubLogo.vue', () => ({
  default: {
    name: 'ClubLogo',
    props: ['logoUrl', 'name', 'size'],
    template: '<span data-testid="club-logo" />',
  },
}));

const mountRow = (match, props = {}) =>
  mount(MatchListRow, { props: { match, ...props } });

// A future fixture and a past one, relative to a frozen clock.
const NOW = new Date('2026-09-20T12:00:00');

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('MatchListRow — what the row stopped saying', () => {
  it('drops Type, Status, Match ID and Source labels from the row', () => {
    const wrapper = mountRow(
      createCompletedMatch({
        match_id: 'EXT-123',
        source: 'match-scraper',
        match_type_name: 'League',
      }),
      { isAdmin: true }
    );

    const text = wrapper.text();
    expect(text).not.toContain('Type:');
    expect(text).not.toContain('Status:');
    expect(text).not.toContain('Match ID:');
    expect(text).not.toContain('Source:');
    expect(text).not.toContain('EXT-123');
  });

  it('drops the two full-width action buttons', () => {
    const wrapper = mountRow(createCompletedMatch(), { isAdmin: true });
    expect(wrapper.text()).not.toContain('View Match');
    expect(wrapper.text()).not.toContain('Edit Match');
  });

  it('says nothing about status on a completed match — the score says it', () => {
    const wrapper = mountRow(createCompletedMatch());
    expect(wrapper.find('[data-testid="match-status-label"]').exists()).toBe(
      false
    );
  });
});

describe('MatchListRow — the fixture', () => {
  it('gives each team its own line with its own score', () => {
    const wrapper = mountRow(
      createCompletedMatch({ home_score: 3, away_score: 1 })
    );

    expect(wrapper.find('[data-testid="match-row-home-score"]').text()).toBe(
      '3'
    );
    expect(wrapper.find('[data-testid="match-row-away-score"]').text()).toBe(
      '1'
    );
  });

  it('marks and bolds the winner, and marks the loser with nothing', () => {
    const wrapper = mountRow(
      createCompletedMatch({ home_score: 3, away_score: 1 })
    );

    const home = wrapper.find('[data-testid="match-row-home"]');
    const away = wrapper.find('[data-testid="match-row-away"]');
    expect(home.text()).toContain('✓');
    expect(away.text()).not.toContain('✓');
    expect(away.text()).not.toContain('✗');
    expect(home.html()).toContain('font-bold');
  });

  it('marks both sides of a draw and bolds neither', () => {
    const wrapper = mountRow(
      createCompletedMatch({ home_score: 2, away_score: 2 })
    );

    expect(wrapper.find('[data-testid="match-row-home"]').text()).toContain(
      '='
    );
    expect(wrapper.find('[data-testid="match-row-away"]').text()).toContain(
      '='
    );
  });

  it('shows a red card per card, on the team that got it', () => {
    const wrapper = mountRow(
      createCompletedMatch({
        home_team_id: 1,
        away_team_id: 2,
        red_cards: [{ team_id: 1 }, { team_id: 1 }, { team_id: 2 }],
      })
    );

    expect(
      wrapper.findAll('[data-testid="match-row-home-red-card"]')
    ).toHaveLength(2);
    expect(
      wrapper.findAll('[data-testid="match-row-away-red-card"]')
    ).toHaveLength(1);
  });
});

describe('MatchListRow — the three states of a scoreline', () => {
  it('an upcoming fixture shows its kickoff time, not the word Scheduled', () => {
    const wrapper = mountRow(
      createMockMatch({
        match_date: '2026-09-27',
        match_status: 'scheduled',
        scheduled_kickoff: '2026-09-27T14:30:00Z',
      })
    );

    const kickoff = wrapper.find('[data-testid="match-row-kickoff"]');
    expect(kickoff.exists()).toBe(true);
    expect(kickoff.text()).toMatch(/\d{1,2}:\d{2}\s?(AM|PM)/);
    expect(wrapper.text()).not.toContain('Scheduled');
  });

  it('a played match with no score reads Not reported, not a kickoff time', () => {
    const wrapper = mountRow(
      createMockMatch({
        match_date: '2026-09-13',
        match_status: 'scheduled',
        scheduled_kickoff: '2026-09-13T14:30:00Z',
      })
    );

    expect(wrapper.find('[data-testid="match-row-kickoff"]').exists()).toBe(
      false
    );
    expect(wrapper.find('[data-testid="match-status-label"]').text()).toBe(
      'Not reported'
    );
  });

  it('never puns an absent score into a zero', () => {
    const wrapper = mountRow(
      createMockMatch({ match_date: '2026-09-27', match_status: 'scheduled' })
    );

    expect(wrapper.find('[data-testid="match-row-home-score"]').text()).toBe(
      '—'
    );
    expect(wrapper.find('[data-testid="match-row-away-score"]').text()).toBe(
      '—'
    );
  });

  it('keeps a status that the scoreline cannot convey', () => {
    for (const match of [
      createPostponedMatch({ match_date: '2026-09-27' }),
      createLiveMatch({ match_date: '2026-09-20' }),
      createCompletedMatch({ match_status: 'forfeit' }),
    ]) {
      const wrapper = mountRow(match);
      expect(wrapper.find('[data-testid="match-status-label"]').exists()).toBe(
        true
      );
    }
  });
});

describe('MatchListRow — tap is the common act', () => {
  it('emits view on a click', async () => {
    const match = createCompletedMatch();
    const wrapper = mountRow(match);

    await wrapper.find('[data-testid="match-list-row"]').trigger('click');
    expect(wrapper.emitted('view')).toHaveLength(1);
    // The payload arrives as Vue's reactive proxy of the prop, so identity is
    // not preserved; the id is what the parent routes on.
    expect(wrapper.emitted('view')[0][0].id).toBe(match.id);
  });

  it('is reachable and operable from the keyboard', async () => {
    const row = mountRow(createCompletedMatch()).find(
      '[data-testid="match-list-row"]'
    );

    expect(row.attributes('tabindex')).toBe('0');
    expect(row.attributes('role')).toBe('button');
    expect(row.attributes('aria-label')).toBeTruthy();

    await row.trigger('keydown.enter');
    expect(row.exists()).toBe(true);
  });

  it('names the fixture and the result for a screen reader', () => {
    const wrapper = mountRow(
      createCompletedMatch({
        home_team_name: 'Blue Stars U14',
        away_team_name: 'Red Hawks U14',
        home_score: 3,
        away_score: 1,
      })
    );

    expect(
      wrapper.find('[data-testid="match-list-row"]').attributes('aria-label')
    ).toBe('Red Hawks U14 at Blue Stars U14, 1 to 3');
  });
});

describe('MatchListRow — long press opens the sheet', () => {
  const press = async (wrapper, { hold = 600, move = 0 } = {}) => {
    const row = wrapper.find('[data-testid="match-list-row"]');
    await row.trigger('pointerdown', {
      pointerType: 'touch',
      clientX: 10,
      clientY: 10,
    });
    if (move) {
      await row.trigger('pointermove', {
        clientX: 10 + move,
        clientY: 10,
      });
    }
    vi.advanceTimersByTime(hold);
    return row;
  };

  it('emits more once the press holds', async () => {
    const match = createCompletedMatch();
    const wrapper = mountRow(match, { isAdmin: true });

    await press(wrapper);
    expect(wrapper.emitted('more')).toHaveLength(1);
    expect(wrapper.emitted('more')[0][0].id).toBe(match.id);
  });

  it('does not also open the match — a press must not fire the tap', async () => {
    const wrapper = mountRow(createCompletedMatch(), { isAdmin: true });

    const row = await press(wrapper);
    await row.trigger('click');

    expect(wrapper.emitted('more')).toHaveLength(1);
    expect(wrapper.emitted('view')).toBeUndefined();
  });

  it('cancels when the finger travels — that is a scroll, not a press', async () => {
    const wrapper = mountRow(createCompletedMatch(), { isAdmin: true });

    await press(wrapper, { move: 40 });
    expect(wrapper.emitted('more')).toBeUndefined();
  });

  it('cancels when the finger lifts early', async () => {
    const wrapper = mountRow(createCompletedMatch(), { isAdmin: true });
    const row = wrapper.find('[data-testid="match-list-row"]');

    await row.trigger('pointerdown', { pointerType: 'touch' });
    vi.advanceTimersByTime(200);
    await row.trigger('pointerup');
    vi.advanceTimersByTime(600);

    expect(wrapper.emitted('more')).toBeUndefined();
  });

  it('lets the tap through again on the press that follows a long press', async () => {
    const wrapper = mountRow(createCompletedMatch(), { isAdmin: true });

    const row = await press(wrapper);
    await row.trigger('click');

    await row.trigger('pointerdown', { pointerType: 'touch' });
    await row.trigger('pointerup');
    await row.trigger('click');

    expect(wrapper.emitted('view')).toHaveLength(1);
  });

  it('does nothing on a press when there is no sheet to open', async () => {
    const wrapper = mountRow(createCompletedMatch(), {
      isAdmin: false,
      canEdit: false,
    });

    await press(wrapper);
    expect(wrapper.emitted('more')).toBeUndefined();
  });
});

describe('MatchListRow — the sheet stays reachable without a gesture', () => {
  it('offers a named button to an admin', async () => {
    const wrapper = mountRow(createCompletedMatch(), { isAdmin: true });
    const more = wrapper.find('[data-testid="match-row-more"]');

    expect(more.exists()).toBe(true);
    expect(more.attributes('aria-label')).toContain('More options');

    await more.trigger('click');
    expect(wrapper.emitted('more')).toHaveLength(1);
  });

  it('offers it to anyone who may edit the match', () => {
    const wrapper = mountRow(createCompletedMatch(), {
      isAdmin: false,
      canEdit: true,
    });
    expect(wrapper.find('[data-testid="match-row-more"]').exists()).toBe(true);
  });

  it('hides it from a viewer with nothing behind it', () => {
    const wrapper = mountRow(createCompletedMatch(), {
      isAdmin: false,
      canEdit: false,
    });
    expect(wrapper.find('[data-testid="match-row-more"]').exists()).toBe(false);
  });

  it('does not open the match when the button is used', async () => {
    const wrapper = mountRow(createCompletedMatch(), { isAdmin: true });
    await wrapper.find('[data-testid="match-row-more"]').trigger('click');
    expect(wrapper.emitted('view')).toBeUndefined();
  });
});

describe('MatchListRow — which competition (SB-1105)', () => {
  const chipOf = wrapper => wrapper.find('[data-testid="row-competition"]');

  it('names the competition on a League match', () => {
    const chip = chipOf(
      mountRow(createCompletedMatch({ match_type_name: 'League' }))
    );
    expect(chip.exists()).toBe(true);
    expect(chip.text()).toBe('League');
  });

  it('names the competition on a Flex match', () => {
    const chip = chipOf(
      mountRow(createCompletedMatch({ match_type_name: 'Flex' }))
    );
    expect(chip.exists()).toBe(true);
    expect(chip.text()).toBe('Flex');
  });

  it('tints League and Flex differently, so the two are not read letter by letter', () => {
    const league = chipOf(
      mountRow(createCompletedMatch({ match_type_name: 'League' }))
    ).attributes('class');
    const flex = chipOf(
      mountRow(createCompletedMatch({ match_type_name: 'Flex' }))
    ).attributes('class');
    expect(league).not.toBe(flex);
  });

  it('shows no chip when the match does not say, and never calls it League', () => {
    const wrapper = mountRow(createCompletedMatch({ match_type_name: null }));
    expect(chipOf(wrapper).exists()).toBe(false);
    expect(wrapper.text()).not.toContain('League');
  });

  it('shows the competition on a finished match, which has no other meta', () => {
    // The archive is mostly completed matches, whose meta line SB-1101 removed
    // entirely. The chip has to bring it back or the common case says nothing.
    const wrapper = mountRow(
      createCompletedMatch({ match_type_name: 'Flex', age_group_name: null }),
      { isAdmin: false, canEdit: false }
    );
    expect(wrapper.find('[data-testid="match-row-meta"]').exists()).toBe(true);
    expect(chipOf(wrapper).text()).toBe('Flex');
  });
});
