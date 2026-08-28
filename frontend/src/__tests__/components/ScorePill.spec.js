/**
 * ScorePill.vue tests.
 *
 * The pill was three byte-identical copies inside TournamentMatchCenter, set in
 * a monospace face that read as terminal output. Now one component with the UI
 * font and tabular figures.
 *
 * The behaviour that matters beyond looks: absent is not zero. A match nobody
 * has scored shows "vs", never "0 – 0" (CLAUDE.md).
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';

import ScorePill from '@/components/ui/ScorePill.vue';

const mountPill = (props = {}) => mount(ScorePill, { props });

// Thin space (U+2009) and nbsp are invisible in assertions; strip them.
const text = wrapper => wrapper.text().replace(/[\u2009\u00a0]/g, ' ');

describe('ScorePill played state', () => {
  it('renders both scores', () => {
    const wrapper = mountPill({ homeScore: 2, awayScore: 1 });

    expect(text(wrapper)).toBe('2 – 1');
  });

  it('renders a goalless draw as a real score, not as absent', () => {
    const wrapper = mountPill({ homeScore: 0, awayScore: 0 });

    expect(text(wrapper)).toBe('0 – 0');
    expect(wrapper.classes()).toContain('bg-surface-alt');
  });

  it('uses tabular figures rather than a monospace face', () => {
    const wrapper = mountPill({ homeScore: 2, awayScore: 1 });

    expect(wrapper.classes()).toContain('tabular-nums');
    expect(wrapper.classes()).not.toContain('font-mono');
  });

  it('colours the chip from theme tokens, not a fixed shade', () => {
    // A hard-coded near-black sat heavily on the light table and vanished
    // against the dark one.
    const wrapper = mountPill({ homeScore: 2, awayScore: 1 });

    expect(wrapper.classes()).toEqual(
      expect.arrayContaining(['bg-surface-alt', 'text-fg', 'border-line'])
    );
    expect(wrapper.classes().join(' ')).not.toMatch(
      /bg-(gray|black|white)-?\d*/
    );
  });
});

describe('ScorePill unplayed state', () => {
  it('shows vs when no score is recorded', () => {
    const wrapper = mountPill();

    expect(text(wrapper)).toBe('vs');
  });

  it('does not paint the dark pill when there is no score', () => {
    const wrapper = mountPill();

    expect(wrapper.classes()).not.toContain('bg-surface-alt');
    expect(wrapper.classes()).toContain('text-fg-muted');
  });

  it('shows vs when only one side has a score', () => {
    // Half a score is not a result — rendering "3 – " or a dark pill reading
    // "vs" (the old behaviour) claims more than we know.
    const wrapper = mountPill({ homeScore: 3 });

    expect(text(wrapper)).toBe('vs');
    expect(wrapper.classes()).not.toContain('bg-surface-alt');
  });
});

describe('ScorePill penalties', () => {
  it('appends the shootout score', () => {
    const wrapper = mountPill({
      homeScore: 1,
      awayScore: 1,
      homePenaltyScore: 5,
      awayPenaltyScore: 4,
    });

    expect(text(wrapper)).toBe('1 – 1(5 – 4 pk)');
  });

  it('renders the shootout smaller than the result', () => {
    const wrapper = mountPill({
      homeScore: 1,
      awayScore: 1,
      homePenaltyScore: 5,
      awayPenaltyScore: 4,
    });

    expect(
      wrapper.find('[data-testid="score-pill-penalties"]').classes()
    ).toContain('text-xs');
  });

  it('ignores a half-recorded shootout', () => {
    const wrapper = mountPill({
      homeScore: 1,
      awayScore: 1,
      homePenaltyScore: 5,
    });

    expect(wrapper.find('[data-testid="score-pill-penalties"]').exists()).toBe(
      false
    );
    expect(text(wrapper)).toBe('1 – 1');
  });
});

describe('ScorePill status guard (SB-886)', () => {
  // Production stored `home_score = 0, away_score = 0` on scheduled matches --
  // the columns carried `DEFAULT 0` -- so the Tournaments tab announced a
  // nil-nil draw for fixtures kicking off the next morning. The migration nulls
  // those rows; `status` makes sure the component cannot render a result from
  // bad data even if any comes back.

  it('shows vs for a scheduled match carrying placeholder zeros', () => {
    // The exact shape of prod rows 3853-3855 before the backfill.
    const wrapper = mountPill({
      homeScore: 0,
      awayScore: 0,
      status: 'scheduled',
    });

    expect(text(wrapper)).toBe('vs');
    expect(wrapper.classes()).not.toContain('bg-surface-alt');
  });

  it('shows vs for cancelled and tbd matches carrying placeholder zeros', () => {
    for (const status of ['cancelled', 'tbd']) {
      expect(text(mountPill({ homeScore: 0, awayScore: 0, status }))).toBe(
        'vs'
      );
    }
  });

  it('still renders a genuine goalless draw once the match is complete', () => {
    // Why the backfill is scoped to unplayed statuses: prod holds 42 real
    // nil-nil results, and they must survive.
    const wrapper = mountPill({
      homeScore: 0,
      awayScore: 0,
      status: 'completed',
    });

    expect(text(wrapper)).toBe('0 – 0');
  });

  it('renders a live match at 0-0 -- that is a real scoreline', () => {
    const wrapper = mountPill({
      homeScore: 0,
      awayScore: 0,
      status: 'in_progress',
    });

    expect(text(wrapper)).toBe('0 – 0');
  });

  it('renders a forfeit result', () => {
    const wrapper = mountPill({
      homeScore: 3,
      awayScore: 0,
      status: 'forfeit',
    });

    expect(text(wrapper)).toBe('3 – 0');
  });

  it('suppresses penalties on an unplayed match', () => {
    const wrapper = mountPill({
      homeScore: 0,
      awayScore: 0,
      homePenaltyScore: 5,
      awayPenaltyScore: 4,
      status: 'scheduled',
    });

    expect(text(wrapper)).toBe('vs');
    expect(wrapper.find('[data-testid="score-pill-penalties"]').exists()).toBe(
      false
    );
  });

  it('keeps the old behaviour when no status is passed', () => {
    // Back-compat: the prop is optional, so existing callers are unaffected.
    expect(text(mountPill({ homeScore: 2, awayScore: 1 }))).toBe('2 – 1');
    expect(text(mountPill({ homeScore: 0, awayScore: 0 }))).toBe('0 – 0');
  });
});
