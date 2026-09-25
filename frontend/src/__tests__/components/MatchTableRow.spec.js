/**
 * The shared desktop match row (SB-1121).
 *
 * The point of this component is that All Matches and My Club render the same
 * row, so the tests that matter most are the ones asserting what a row no
 * longer says, and that both modes say it the same way.
 */

import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import MatchTableRow from '@/components/matches/MatchTableRow.vue';

vi.mock('@/components/shared/ClubLogo.vue', () => ({
  default: {
    name: 'ClubLogo',
    props: ['logoUrl', 'name', 'size'],
    template: '<span data-testid="club-logo" />',
  },
}));

const MATCH = {
  id: 27168,
  match_date: '2026-09-06T04:00:00.000Z',
  match_status: 'completed',
  home_score: 7,
  away_score: 1,
  match_type_name: 'League',
  age_group_name: 'U15',
  match_id: 'EXT-26285',
  source: 'match-scraper',
};

const TEAMS_MYCLUB = {
  mode: 'myclub',
  prefix: 'vs',
  opponent: { name: 'Downtown United Soccer Club', logoUrl: '' },
};

const TEAMS_ALL = {
  mode: 'all',
  away: { name: 'IFA', logoUrl: '', icon: '', bold: false },
  home: { name: 'Metropolitan Oval', logoUrl: '', icon: '', bold: true },
};

// A <tr> needs a table parent or Vue Test Utils hoists it out of the DOM.
const mountRow = (props = {}) =>
  mount(
    {
      components: { MatchTableRow },
      template:
        '<table><tbody><MatchTableRow v-bind="$attrs" /></tbody></table>',
      inheritAttrs: false,
    },
    {
      attrs: {
        match: MATCH,
        teams: TEAMS_MYCLUB,
        status: { label: 'completed', live: false, inProgress: false },
        ...props,
      },
    }
  );

describe('MatchTableRow — what the row stopped saying', () => {
  it('shows no Match ID and no Source, even for an admin', () => {
    const wrapper = mountRow({ isAdmin: true, isAuthenticated: true });
    expect(wrapper.text()).not.toContain('EXT-26285');
    expect(wrapper.text()).not.toContain('match-scraper');
  });

  it('shows no per-row age group — the filter above already says U15', () => {
    expect(mountRow().find('[data-testid="row-age-group"]').exists()).toBe(
      false
    );
    expect(mountRow().text()).not.toContain('U15');
  });

  it('shows no Match Type column text — the competition is a chip now', () => {
    const wrapper = mountRow();
    const chip = wrapper.find('[data-testid="row-competition"]');
    expect(chip.exists()).toBe(true);
    // The word appears once, in the chip, not also in a column of its own.
    expect(wrapper.text().match(/League/g)).toHaveLength(1);
  });
});

describe('MatchTableRow — competition', () => {
  it('names the competition on the row', () => {
    expect(mountRow().find('[data-testid="row-competition"]').text()).toBe(
      'League'
    );
  });

  it('tints Flex differently from League', () => {
    const league = mountRow().find('[data-testid="row-competition"]').classes();
    const flex = mountRow({
      match: { ...MATCH, match_type_name: 'Flex' },
    })
      .find('[data-testid="row-competition"]')
      .classes();
    expect(league.join(' ')).not.toBe(flex.join(' '));
  });

  it('shows no chip when the match does not say, and never calls it League', () => {
    const wrapper = mountRow({ match: { ...MATCH, match_type_name: null } });
    expect(wrapper.find('[data-testid="row-competition"]').exists()).toBe(
      false
    );
    expect(wrapper.text()).not.toContain('League');
  });
});

describe('MatchTableRow — the date and the score', () => {
  it('reads the date as a weekday, not an ISO string', () => {
    const text = mountRow().text();
    expect(text).toContain('Sun 6');
    expect(text).toContain('Sep');
    expect(text).not.toContain('2026-09-06');
  });

  it('reads home first on My Club and away first on All Matches', () => {
    expect(mountRow().find('[data-testid="row-score"]').text()).toBe('7 - 1');
    expect(
      mountRow({ mode: 'all', teams: TEAMS_ALL })
        .find('[data-testid="row-score"]')
        .text()
    ).toBe('1 - 7');
  });

  it('separates a fixture to come from one nobody scored', () => {
    const upcoming = mountRow({
      match: {
        ...MATCH,
        match_status: 'scheduled',
        home_score: null,
        away_score: null,
      },
    })
      .find('[data-testid="row-score"]')
      .text();
    const unreported = mountRow({
      match: { ...MATCH, home_score: null, away_score: null },
    })
      .find('[data-testid="row-score"]')
      .text();

    expect(upcoming).not.toBe(unreported);
    expect(upcoming).not.toContain('0');
  });
});

describe('MatchTableRow — modes', () => {
  it('numbers the rows and shows a result on My Club', () => {
    const wrapper = mountRow({ index: 3, result: 'W' });
    expect(wrapper.find('[data-testid="row-result"]').text()).toBe('W');
    expect(wrapper.text()).toContain('4');
  });

  it('shows neither on All Matches, where no team is yours', () => {
    const wrapper = mountRow({
      mode: 'all',
      teams: TEAMS_ALL,
      index: 3,
      result: '-',
    });
    expect(wrapper.find('[data-testid="row-result"]').exists()).toBe(false);
  });
});

describe('MatchTableRow — actions', () => {
  it('opens the match when the row is clicked', async () => {
    const wrapper = mountRow();
    await wrapper.find('[data-testid="match-table-row"]').trigger('click');
    expect(wrapper.findComponent(MatchTableRow).emitted('view')).toHaveLength(
      1
    );
  });

  it('offers Edit only to someone who may edit this match', () => {
    expect(mountRow({ isAuthenticated: true, canEdit: true }).text()).toContain(
      'Edit'
    );
    expect(
      mountRow({ isAuthenticated: true, canEdit: false }).text()
    ).not.toContain('Edit');
  });

  it('offers the Match of the Week toggle only to an admin', () => {
    expect(
      mountRow({ isAuthenticated: true, isAdmin: true })
        .find(`[data-testid="motw-toggle-${MATCH.id}"]`)
        .exists()
    ).toBe(true);
    expect(
      mountRow({ isAuthenticated: true, isAdmin: false })
        .find(`[data-testid="motw-toggle-${MATCH.id}"]`)
        .exists()
    ).toBe(false);
  });

  it('does not open the match when an action button is used', async () => {
    const wrapper = mountRow({ isAuthenticated: true, canEdit: true });
    const buttons = wrapper.findAll('button');
    await buttons[buttons.length - 1].trigger('click');
    const row = wrapper.findComponent(MatchTableRow);
    expect(row.emitted('edit')).toHaveLength(1);
    expect(row.emitted('view')).toBeUndefined();
  });
});
