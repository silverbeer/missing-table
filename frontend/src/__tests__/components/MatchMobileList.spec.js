/**
 * The phone match list: sticky headers, day groups, and the sheet the rows
 * open (SB-1101).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount } from '@vue/test-utils';
import MatchMobileList from '@/components/matches/MatchMobileList.vue';
import {
  createMockMatch,
  createCompletedMatch,
} from '../helpers/matchFactories';

vi.mock('@/components/shared/ClubLogo.vue', () => ({
  default: {
    name: 'ClubLogo',
    props: ['logoUrl', 'name', 'size'],
    template: '<span data-testid="club-logo" />',
  },
}));

const NOW = new Date('2026-09-20T12:00:00');

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = '';
});

const mountList = (props = {}) =>
  mount(MatchMobileList, {
    props: { matches: [createCompletedMatch()], ...props },
    attachTo: document.body,
  });

describe('MatchMobileList — headers stay put while their group scrolls', () => {
  it('pins the league band to the top of the viewport', () => {
    const header = mountList({ sectionLabel: 'HOMEGROWN LEAGUE' }).find(
      '[data-testid="match-section-header"]'
    );

    expect(header.text()).toBe('HOMEGROWN LEAGUE');
    expect(header.classes()).toContain('sticky');
    expect(header.classes()).toContain('top-0');
  });

  it('parks the day header under the league band rather than over it', () => {
    const day = mountList({ sectionLabel: 'HOMEGROWN LEAGUE' }).find(
      '[data-testid="match-day-header"]'
    );

    expect(day.classes()).toContain('sticky');
    expect(day.attributes('style')).toContain('top: 2.25rem');
  });

  it('puts the day header at the top when there is no league band', () => {
    const wrapper = mountList();
    expect(wrapper.find('[data-testid="match-section-header"]').exists()).toBe(
      false
    );
    expect(
      wrapper.find('[data-testid="match-day-header"]').attributes('style')
    ).toContain('top: 0px');
  });
});

describe('MatchMobileList — the date comes off the rows', () => {
  it('heads each day once instead of dating every match', () => {
    const wrapper = mountList({
      matches: [
        createCompletedMatch({ id: 1, match_date: '2026-09-19' }),
        createCompletedMatch({ id: 2, match_date: '2026-09-19' }),
        createCompletedMatch({ id: 3, match_date: '2026-09-20' }),
      ],
    });

    const headers = wrapper.findAll('[data-testid="match-day-header"]');
    expect(headers).toHaveLength(2);
    expect(headers[0].text()).toBe('Yesterday · Sat, Sep 19');
    expect(headers[1].text()).toBe('Today · Sun, Sep 20');
    expect(wrapper.findAll('[data-testid="match-list-row"]')).toHaveLength(3);
  });
});

describe('MatchMobileList — the sheet', () => {
  const openSheet = async wrapper => {
    await wrapper.find('[data-testid="match-row-more"]').trigger('click');
    return wrapper;
  };

  it('opens with Edit and the forensics for an admin', async () => {
    const wrapper = mountList({
      matches: [
        createCompletedMatch({ match_id: 'EXT-99', source: 'match-scraper' }),
      ],
      isAdmin: true,
      canEdit: () => true,
    });

    await openSheet(wrapper);

    const sheet = document.querySelector('[data-testid="match-actions-sheet"]');
    expect(sheet).not.toBeNull();
    expect(
      sheet.querySelector('[data-testid="sheet-edit-match"]')
    ).not.toBeNull();
    expect(
      sheet.querySelector('[data-testid="sheet-match-id"]').textContent.trim()
    ).toBe('EXT-99');
    expect(
      sheet.querySelector('[data-testid="sheet-source"]').textContent
    ).toContain('Scraped');
  });

  it('never shows Edit to someone who may not edit the match', async () => {
    const wrapper = mountList({ isAdmin: true, canEdit: () => false });
    await openSheet(wrapper);

    const sheet = document.querySelector('[data-testid="match-actions-sheet"]');
    expect(sheet.querySelector('[data-testid="sheet-edit-match"]')).toBeNull();
    expect(sheet.textContent).not.toContain('Edit match');
  });

  it('keeps the forensics away from a non-admin who may still edit', async () => {
    const wrapper = mountList({ isAdmin: false, canEdit: () => true });
    await openSheet(wrapper);

    const sheet = document.querySelector('[data-testid="match-actions-sheet"]');
    expect(
      sheet.querySelector('[data-testid="sheet-edit-match"]')
    ).not.toBeNull();
    expect(sheet.querySelector('[data-testid="sheet-forensics"]')).toBeNull();
  });

  it('offers no way in at all to a viewer with neither', () => {
    const wrapper = mountList({ isAdmin: false, canEdit: () => false });
    expect(wrapper.find('[data-testid="match-row-more"]').exists()).toBe(false);
  });

  it('bubbles view and edit up to the parent, and closes behind itself', async () => {
    const match = createCompletedMatch({ id: 7 });
    const wrapper = mountList({
      matches: [match],
      isAdmin: true,
      canEdit: () => true,
    });

    await openSheet(wrapper);
    document.querySelector('[data-testid="sheet-edit-match"]').click();
    await wrapper.vm.$nextTick();

    expect(wrapper.emitted('edit')[0][0].id).toBe(7);
    expect(
      document.querySelector('[data-testid="match-actions-sheet"]')
    ).toBeNull();
  });
});

describe('MatchMobileList — the viewer’s own team', () => {
  it('marks matches their team is in', () => {
    const wrapper = mountList({
      matches: [
        createMockMatch({ id: 1, home_team_id: 1, away_team_id: 2 }),
        createMockMatch({ id: 2, home_team_id: 3, away_team_id: 4 }),
      ],
      // A select binds a string; the highlight must survive that.
      highlightTeamId: '1',
    });

    const rows = wrapper.findAll('[data-testid="match-list-row"]');
    expect(rows[0].classes()).toContain('border-l-accent-400');
    expect(rows[1].classes()).not.toContain('border-l-accent-400');
  });

  it('marks nothing when no team is selected', () => {
    const wrapper = mountList({ highlightTeamId: '' });
    expect(
      wrapper.find('[data-testid="match-list-row"]').classes()
    ).not.toContain('border-l-accent-400');
  });
});
