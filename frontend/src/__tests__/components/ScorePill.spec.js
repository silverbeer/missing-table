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
