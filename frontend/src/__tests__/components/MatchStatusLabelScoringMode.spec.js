/**
 * MatchStatusLabel — under way vs live-scored (SB-910).
 *
 * Marking a match live meant two things at once: the ball is rolling, and
 * someone is driving the clock with an event feed. Most matches are the first
 * without the second — a parent marks it in progress and types in the score a
 * partner texts from the touchline. A pulsing "Live" on those promises a feed
 * nobody is producing.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import MatchStatusLabel from '@/components/ui/MatchStatusLabel.vue';

const label = props => mount(MatchStatusLabel, { props });

describe('a match under way', () => {
  it('reads Live and pulses when it is being live-scored', () => {
    const w = label({ status: 'live', scoringMode: 'live' });
    expect(w.text()).toBe('Live');
    expect(w.classes()).toContain('animate-pulse');
  });

  it('reads In Progress, without a pulse, when it is not', () => {
    const w = label({ status: 'live', scoringMode: 'manual' });
    expect(w.text()).toBe('In Progress');
    expect(w.classes()).not.toContain('animate-pulse');
  });

  it('defaults to In Progress when the mode is absent', () => {
    // An older payload, or a caller that does not pass the prop. Claiming a
    // live feed we cannot confirm is the worse failure.
    expect(label({ status: 'live' }).text()).toBe('In Progress');
  });

  it('treats in_progress as an alias for live', () => {
    expect(label({ status: 'in_progress', scoringMode: 'live' }).text()).toBe(
      'Live'
    );
  });
});

describe('every other status is unchanged', () => {
  it.each([
    ['completed', 'Final'],
    ['forfeit', 'Forfeit'],
    ['cancelled', 'Cancelled'],
    ['postponed', 'Postponed'],
    ['tbd', 'TBD'],
  ])('%s reads %s', (status, text) => {
    expect(label({ status }).text()).toBe(text);
  });

  it('renders nothing for an unknown status rather than guessing', () => {
    expect(label({ status: 'banana' }).find('span').exists()).toBe(false);
  });

  it('ignores the scoring mode on a finished match', () => {
    // scoring_mode stays 'live' after the whistle — it is provenance, not
    // state. It must not turn "Final" into "Live".
    const w = label({ status: 'completed', scoringMode: 'live' });
    expect(w.text()).toBe('Final');
    expect(w.classes()).not.toContain('animate-pulse');
  });
});
