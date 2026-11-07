/**
 * TournamentMotdBanner.vue (SB-1560)
 *
 * The three states: no reasons recorded (null), reasons recorded but empty
 * ([]), and populated. Plus: an unplayed match never renders as 0–0.
 */
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import TournamentMotdBanner from '@/components/TournamentMotdBanner.vue';

const match = (over = {}) => ({
  id: 501,
  home_team: { id: 1, name: 'IFA' },
  away_team: { id: 2, name: 'Cedar Stars' },
  age_group: { id: 3, name: 'U15' },
  home_score: null,
  away_score: null,
  ...over,
});

const pick = (over = {}) => ({
  match_date: '2026-12-03',
  blurb: null,
  reasons: null,
  match: match(),
  ...over,
});

const mountWith = props => mount(TournamentMotdBanner, { props });

describe('TournamentMotdBanner', () => {
  it('shows the fixture and no Why list when reasons are null', () => {
    const w = mountWith({ pick: pick() });
    expect(w.find('[data-testid="motd-fixture"]').text()).toContain('IFA');
    expect(w.find('[data-testid="motd-fixture"]').text()).toContain(
      'Cedar Stars'
    );
    expect(w.find('[data-testid="motd-reasons"]').exists()).toBe(false);
    expect(w.find('[data-testid="motd-blurb"]').exists()).toBe(false);
    expect(w.attributes('data-has-reasons')).toBe('false');
  });

  it('shows no Why list when reasons are an empty array', () => {
    const w = mountWith({
      pick: pick({ reasons: [], blurb: 'Group decider' }),
    });
    expect(w.find('[data-testid="motd-reasons"]').exists()).toBe(false);
    expect(w.find('[data-testid="motd-blurb"]').text()).toBe('Group decider');
  });

  it('lists every reason when populated', () => {
    const w = mountWith({
      pick: pick({
        reasons: [{ text: 'Top two in Group A' }, { text: 'Both unbeaten' }],
      }),
    });
    const items = w.findAll('[data-testid="motd-reason"]');
    expect(items).toHaveLength(2);
    expect(items[0].text()).toContain('Top two in Group A');
    expect(items[1].text()).toContain('Both unbeaten');
    expect(w.attributes('data-has-reasons')).toBe('true');
  });

  it('renders an unplayed match as "vs", never 0–0', () => {
    const w = mountWith({ pick: pick() });
    expect(w.find('[data-testid="motd-score"]').exists()).toBe(false);
    expect(w.find('[data-testid="motd-fixture"]').text()).not.toContain('0');
  });

  it('prefers the live copy of the match for the score', () => {
    const w = mountWith({
      pick: pick(),
      liveMatch: match({ home_score: 2, away_score: 1 }),
    });
    expect(w.find('[data-testid="motd-score"]').text()).toBe('2–1');
  });

  it('shows the day label and age group', () => {
    const w = mountWith({ pick: pick(), dayLabel: 'Today' });
    expect(w.find('[data-testid="motd-day"]').text()).toContain('Today');
    expect(w.find('[data-testid="motd-age"]').text()).toBe('U15');
  });

  it('emits select-match with the match when the fixture is clicked', async () => {
    const w = mountWith({ pick: pick() });
    await w.find('[data-testid="motd-fixture"]').trigger('click');
    expect(w.emitted('select-match')[0][0].id).toBe(501);
  });
});
