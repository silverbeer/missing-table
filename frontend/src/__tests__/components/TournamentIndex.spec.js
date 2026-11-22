/**
 * TournamentIndex.vue (SB-1767): the season index of the Tournaments tab.
 *
 * One card per tournament, in the order given. A count the server could not
 * load is absent — no number, never "0". No logo is a neutral placeholder.
 * Live stands out, and says so in words, not only in colour.
 *
 * The default fixture is a scraped tournament: no logo, a location, dates.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import TournamentIndex from '@/components/TournamentIndex.vue';
import { compareByStatus } from '@/utils/tournamentStatus';

// Clock pinned: Wednesday 2026-11-18, midday local.
const NOW = new Date(2026, 10, 18, 12, 0, 0);

const LIVE = {
  id: 11,
  name: 'Thanksgiving Cup',
  start_date: '2026-11-17',
  end_date: '2026-11-20',
  location: 'Bradenton, FL',
  logo_url: 'https://example.test/cup.png',
  match_count: 40,
};
const SOON = {
  id: 12,
  name: 'Winter Showcase',
  start_date: '2026-11-21',
  end_date: '2026-11-22',
  location: 'Lakewood Ranch, FL',
  logo_url: null,
  match_count: null,
};
const LATER = {
  id: 14,
  name: 'Spring Classic',
  start_date: '2027-03-06',
  end_date: '2027-03-06',
  location: null,
  logo_url: null,
  match_count: 1,
};
const DONE = {
  id: 13,
  name: 'Fall Festival',
  start_date: '2026-10-03',
  end_date: '2026-10-05',
  location: 'Richmond, VA',
  logo_url: null,
  match_count: 0,
};

const sorted = list => list.slice().sort((a, b) => compareByStatus(a, b, NOW));

const mountIndex = (tournaments, props = {}) =>
  mount(TournamentIndex, { props: { tournaments, now: NOW, ...props } });

const cards = w => w.findAll('[data-testid="tournament-card"]');
const card = (w, id) =>
  w.find(`[data-testid="tournament-card"][data-id="${id}"]`);

describe('TournamentIndex', () => {
  it('renders one card per tournament, in status order', () => {
    const w = mountIndex(sorted([DONE, LATER, SOON, LIVE]));
    expect(cards(w).map(c => c.attributes('data-id'))).toEqual([
      '11',
      '12',
      '14',
      '13',
    ]);
    expect(cards(w).map(c => c.attributes('data-state'))).toEqual([
      'live',
      'soon',
      'upcoming',
      'completed',
    ]);
  });

  it('labels each status in words', () => {
    const w = mountIndex(sorted([DONE, LATER, SOON, LIVE]));
    const status = id =>
      card(w, id).find('[data-testid="tournament-card-status"]').text();
    expect(status(11)).toBe('Happening today');
    expect(status(12)).toBe('Upcoming');
    expect(status(14)).toBe('Upcoming');
    expect(status(13)).toBe('Completed');
  });

  it('shows no status chip for a tournament with no dates', () => {
    const w = mountIndex([{ ...SOON, start_date: null, end_date: null }]);
    expect(card(w, 12).attributes('data-state')).toBe('unknown');
    expect(
      card(w, 12).find('[data-testid="tournament-card-status"]').exists()
    ).toBe(false);
  });

  it('shows the logo when there is one, and a neutral placeholder when not', () => {
    const w = mountIndex([LIVE, SOON]);
    const logo = card(w, 11).find('[data-testid="tournament-card-logo"]');
    expect(logo.exists()).toBe(true);
    expect(logo.attributes('src')).toBe(LIVE.logo_url);
    expect(
      card(w, 11).find('[data-testid="tournament-logo-placeholder"]').exists()
    ).toBe(false);

    expect(card(w, 12).find('img').exists()).toBe(false);
    const placeholder = card(w, 12).find(
      '[data-testid="tournament-logo-placeholder"]'
    );
    expect(placeholder.exists()).toBe(true);
    expect(placeholder.attributes('aria-hidden')).toBe('true');
  });

  it('shows no number for a count that could not be loaded — never 0', () => {
    const w = mountIndex([SOON]);
    expect(
      card(w, 12).find('[data-testid="tournament-card-count"]').exists()
    ).toBe(false);
    expect(card(w, 12).text()).not.toMatch(/\b0\b/);
    expect(card(w, 12).text()).not.toContain('match');
  });

  it('shows no number when the count is missing altogether', () => {
    const noCount = { ...LIVE };
    delete noCount.match_count;
    const w = mountIndex([noCount]);
    expect(
      card(w, 11).find('[data-testid="tournament-card-count"]').exists()
    ).toBe(false);
  });

  it('shows a real count, including a real zero', () => {
    const w = mountIndex([LIVE, LATER, DONE]);
    const count = id =>
      card(w, id).find('[data-testid="tournament-card-count"]').text();
    expect(count(11)).toBe('40 matches');
    expect(count(14)).toBe('1 match');
    expect(count(13)).toBe('0 matches');
  });

  it('makes a live tournament stand out, with a static dot — not a pulse', () => {
    // "Live" on the index is the dates alone: on today, not necessarily
    // mid-match. A pulse would claim a match in progress on a rest day.
    const w = mountIndex([LIVE, SOON]);
    const status = card(w, 11).find('[data-testid="tournament-card-status"]');
    expect(card(w, 11).classes()).toContain('ring-1');
    expect(status.find('span[aria-hidden="true"]').exists()).toBe(true);
    expect(card(w, 11).find('.animate-pulse').exists()).toBe(false);
    expect(card(w, 12).classes()).not.toContain('ring-1');
  });

  it('wraps a long unbroken name instead of overflowing', () => {
    // Layout is not measured in happy-dom; this pins the wrapping classes.
    const long = { ...SOON, name: 'U'.repeat(120) };
    const w = mountIndex([long]);
    const name = card(w, 12).find('[data-testid="tournament-card-name"]');
    expect(name.text()).toBe('U'.repeat(120));
    expect(name.classes()).toEqual(
      expect.arrayContaining(['break-words', 'min-w-0'])
    );
  });

  it('shows the dates and location', () => {
    const w = mountIndex([LIVE, LATER]);
    expect(
      card(w, 11).find('[data-testid="tournament-card-dates"]').text()
    ).toBe('Nov 17, 2026 – Nov 20, 2026');
    expect(
      card(w, 11).find('[data-testid="tournament-card-location"]').text()
    ).toBe('Bradenton, FL');
    // One-day tournament: the date once. No location: nothing in its place.
    expect(
      card(w, 14).find('[data-testid="tournament-card-dates"]').text()
    ).toBe('Mar 6, 2027');
    expect(
      card(w, 14).find('[data-testid="tournament-card-location"]').exists()
    ).toBe(false);
  });

  it('cards are real buttons that emit the tournament id', async () => {
    const w = mountIndex([LIVE, SOON]);
    expect(card(w, 12).element.tagName).toBe('BUTTON');
    expect(card(w, 12).attributes('type')).toBe('button');
    await card(w, 12).trigger('click');
    expect(w.emitted('open')).toEqual([[12]]);
  });

  it('shows a notice only when given one', () => {
    expect(
      mountIndex([LIVE])
        .find('[data-testid="tournament-index-notice"]')
        .exists()
    ).toBe(false);
    const w = mountIndex([LIVE], {
      notice: "That tournament isn't available.",
    });
    expect(w.find('[data-testid="tournament-index-notice"]').text()).toBe(
      "That tournament isn't available."
    );
  });
});
