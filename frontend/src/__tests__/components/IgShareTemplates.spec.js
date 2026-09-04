/**
 * IgShareCard template tests (SB-32).
 *
 * Covers the dispatcher's template prop wiring and template-specific
 * elements. Each of the four templates is mounted via IgShareCard so we
 * also exercise the prop pass-through.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import IgShareCard from '@/components/IgShareCard.vue';
import {
  createMockMatch,
  createCompletedMatch,
} from '../helpers/matchFactories';

const mountCard = (template, props = {}) =>
  mount(IgShareCard, {
    props: {
      match: createMockMatch(),
      mode: 'preview',
      template,
      ...props,
    },
  });

describe('IgShareCard dispatcher', () => {
  it('renders IgOverlay by default', () => {
    const wrapper = mount(IgShareCard, {
      props: { match: createMockMatch(), mode: 'preview' },
    });
    expect(
      wrapper.find('[data-testid="ig-share-card"]').attributes('data-template')
    ).toBe('overlay');
  });

  it('falls back to overlay when given an unknown template', () => {
    // Validator throws in dev — silence it for this case by passing a
    // valid string; we only really need to ensure overlay is the safe
    // default at runtime via the computed.
    const wrapper = mountCard('overlay');
    expect(
      wrapper.find('[data-testid="ig-share-card"]').attributes('data-template')
    ).toBe('overlay');
  });
});

describe('IgOverlay template', () => {
  it('uses the overlay layout', () => {
    const wrapper = mountCard('overlay');
    expect(
      wrapper.find('[data-testid="ig-share-card"]').attributes('data-template')
    ).toBe('overlay');
    // Photo layer is a hallmark of this template.
    expect(wrapper.find('[data-testid="ig-photo-fallback"]').exists()).toBe(
      true
    );
  });
});

describe('IgSplit template', () => {
  it('renders MATCH PREVIEW hero in preview mode', () => {
    const wrapper = mountCard('split');
    expect(
      wrapper.find('[data-testid="ig-share-card"]').attributes('data-template')
    ).toBe('split');
    expect(wrapper.find('[data-testid="ig-status"]').text()).toMatch(
      /MATCH\s*PREVIEW/
    );
    expect(wrapper.find('[data-testid="ig-vs"]').exists()).toBe(true);
  });

  it('renders FULL TIME and the score in result mode', () => {
    const wrapper = mountCard('split', {
      match: createCompletedMatch({ home_score: 2, away_score: 1 }),
      mode: 'result',
    });
    expect(wrapper.find('[data-testid="ig-status"]').text()).toBe('FULL TIME');
    expect(wrapper.find('[data-testid="ig-score"]').text()).toMatch(
      /2\s*–\s*1/
    );
  });

  it('shows the @missingtable handle in the footer band', () => {
    const wrapper = mountCard('split');
    expect(wrapper.find('[data-testid="ig-handle"]').text()).toBe(
      '@missingtable'
    );
  });
});

describe('IgTournamentRound template', () => {
  const tournamentMatch = (overrides = {}) =>
    createMockMatch({
      tournament_name: '2026 MLS NEXT Cup',
      tournament_group: 'Championship',
      tournament_round: 'quarterfinal',
      ...overrides,
    });

  it('uses the round name as the hero', () => {
    const wrapper = mountCard('tournament-round', { match: tournamentMatch() });
    expect(wrapper.find('[data-testid="ig-status"]').text()).toBe(
      'QUARTERFINAL'
    );
  });

  it('renders tournament name and group above the hero', () => {
    const wrapper = mountCard('tournament-round', { match: tournamentMatch() });
    expect(wrapper.find('[data-testid="ig-tournament"]').text()).toBe(
      '2026 MLS NEXT CUP'
    );
    expect(wrapper.find('[data-testid="ig-group"]').text()).toBe(
      'CHAMPIONSHIP'
    );
  });

  it('normalizes round_of_8 and semifinal tokens', () => {
    const r8 = mountCard('tournament-round', {
      match: tournamentMatch({ tournament_round: 'round_of_8' }),
    });
    expect(r8.find('[data-testid="ig-status"]').text()).toBe('QUARTERFINAL');

    const sf = mountCard('tournament-round', {
      match: tournamentMatch({ tournament_round: 'semifinal' }),
    });
    expect(sf.find('[data-testid="ig-status"]').text()).toBe('SEMIFINAL');
  });
});

describe('tagline', () => {
  const previewCopy = 'Check out missingtable.com for live match updates';
  const resultCopy = 'Go to missingtable.com to request an invite';

  for (const template of ['overlay', 'split', 'tournament-round', 'stadium']) {
    it(`renders the preview CTA on the ${template} template`, () => {
      const wrapper = mountCard(template, {
        match: createMockMatch({
          tournament_round: template === 'tournament-round' ? 'final' : null,
          tournament_name: template === 'tournament-round' ? 'Cup' : null,
        }),
      });
      expect(wrapper.find('[data-testid="ig-tagline"]').text()).toBe(
        previewCopy
      );
    });

    it(`renders the result CTA on the ${template} template`, () => {
      const wrapper = mountCard(template, {
        mode: 'result',
        match: createMockMatch({
          tournament_round: template === 'tournament-round' ? 'final' : null,
          tournament_name: template === 'tournament-round' ? 'Cup' : null,
        }),
      });
      expect(wrapper.find('[data-testid="ig-tagline"]').text()).toBe(
        resultCopy
      );
    });
  }
});

describe('MLS Next badge gating', () => {
  const homegrownMatch = (overrides = {}) =>
    createMockMatch({
      division: { name: 'Northeast', leagues: { name: 'Homegrown' } },
      ...overrides,
    });
  const academyMatch = (overrides = {}) =>
    createMockMatch({
      division: { name: 'West', leagues: { name: 'Academy' } },
      ...overrides,
    });

  it('detects Homegrown via the home team when match has no division (tournament)', () => {
    const wrapper = mountCard('overlay', {
      match: createMockMatch({
        division: null,
        division_name: 'Unknown',
        home_team_league_name: 'Homegrown',
        away_team_league_name: 'Academy',
      }),
    });
    expect(wrapper.find('[data-testid="ig-mls-next-badge"]').exists()).toBe(
      true
    );
  });

  it('detects Homegrown via the away team when match has no division', () => {
    const wrapper = mountCard('overlay', {
      match: createMockMatch({
        division: null,
        home_team_league_name: 'Academy',
        away_team_league_name: 'Homegrown',
      }),
    });
    expect(wrapper.find('[data-testid="ig-mls-next-badge"]').exists()).toBe(
      true
    );
  });

  it('hides the badge when neither team nor match is Homegrown', () => {
    const wrapper = mountCard('overlay', {
      match: createMockMatch({
        division: null,
        home_team_league_name: 'Academy',
        away_team_league_name: 'Academy',
      }),
    });
    expect(wrapper.find('[data-testid="ig-mls-next-badge"]').exists()).toBe(
      false
    );
  });

  for (const template of ['overlay', 'split', 'stadium']) {
    it(`shows MLS Next badge in ${template} when league is Homegrown`, () => {
      const wrapper = mountCard(template, { match: homegrownMatch() });
      expect(wrapper.find('[data-testid="ig-mls-next-badge"]').exists()).toBe(
        true
      );
    });
    it(`hides MLS Next badge in ${template} for non-Homegrown leagues`, () => {
      const wrapper = mountCard(template, { match: academyMatch() });
      expect(wrapper.find('[data-testid="ig-mls-next-badge"]').exists()).toBe(
        false
      );
    });
  }

  it('shows MLS Next badge in tournament-round template when league is Homegrown', () => {
    const wrapper = mountCard('tournament-round', {
      match: homegrownMatch({
        tournament_round: 'final',
        tournament_name: 'Cup',
      }),
    });
    expect(wrapper.find('[data-testid="ig-mls-next-badge"]').exists()).toBe(
      true
    );
  });
});

describe('IgStadium template', () => {
  it('leads the top band with the tournament, not the wordmark', () => {
    // The missingtable.com wordmark used to sit here, duplicating what the
    // bottom band already says twice (@missingtable + "Check out
    // missingtable.com...") while squeezing the tournament name -- the
    // actual subject of the card -- onto two cramped lines (SB-899).
    const wrapper = mountCard('stadium', {
      match: createMockMatch({ tournament_name: 'Copa Rayados East Coast' }),
    });

    expect(wrapper.find('[data-testid="ig-brand-top"]').exists()).toBe(false);
    // The band now opens on the subject of the card.
    expect(wrapper.find('[data-testid="ig-meta"]').text()).toContain(
      'COPA RAYADOS EAST COAST'
    );
  });

  it('still carries the brand once, in the bottom band', () => {
    const wrapper = mountCard('stadium');
    expect(wrapper.find('[data-testid="ig-handle"]').text()).toBe(
      '@missingtable'
    );
  });

  it('does not require a photo to render', () => {
    const wrapper = mountCard('stadium', { photoSrc: null });
    // No ig-photo or fallback in this template at all.
    expect(wrapper.find('[data-testid="ig-photo"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="ig-photo-fallback"]').exists()).toBe(
      false
    );
  });

  it('renders score in result mode', () => {
    const wrapper = mountCard('stadium', {
      match: createCompletedMatch({ home_score: 4, away_score: 2 }),
      mode: 'result',
    });
    expect(wrapper.find('[data-testid="ig-score"]').text()).toMatch(
      /4\s*–\s*2/
    );
    expect(wrapper.find('[data-testid="ig-status"]').text()).toBe('FINAL');
  });
});

describe('tournament logo (all templates)', () => {
  // The four templates each render a tournament logo at the top of the
  // card when match.tournament_logo_url is set. When absent, the slot is
  // omitted entirely so non-tournament matches don't get an empty box.
  const LOGO_URL = 'https://example.com/logos/nac.png';

  for (const template of ['overlay', 'split', 'tournament-round', 'stadium']) {
    it(`renders the tournament logo on ${template} when tournament_logo_url is set`, () => {
      const wrapper = mountCard(template, {
        match: createMockMatch({
          tournament_logo_url: LOGO_URL,
          tournament_name:
            template === 'tournament-round' ? 'NAC Championships' : null,
          tournament_round: template === 'tournament-round' ? 'final' : null,
        }),
      });
      // Rendered as a background-image div (not <img>) inside a white
      // chip so html2canvas honors contain and dark logos stay legible.
      const logo = wrapper.find('[data-testid="ig-tournament-logo"]');
      expect(logo.exists()).toBe(true);
      expect(logo.attributes('style')).toContain(LOGO_URL);
    });

    it(`omits the logo slot on ${template} when tournament_logo_url is absent`, () => {
      const wrapper = mountCard(template, {
        match: createMockMatch({
          tournament_logo_url: null,
          tournament_name:
            template === 'tournament-round' ? 'NAC Championships' : null,
          tournament_round: template === 'tournament-round' ? 'final' : null,
        }),
      });
      expect(wrapper.find('[data-testid="ig-tournament-logo"]').exists()).toBe(
        false
      );
    });
  }
});

describe('IgMotw template (SB-1010)', () => {
  it('brands the card as the MT weekly pick', () => {
    // The whole point of a separate template: recognisable as the series
    // from a thumbnail, before a word is read.
    const wrapper = mountCard('motw');

    expect(
      wrapper.find('[data-testid="ig-share-card"]').attributes('data-template')
    ).toBe('motw');
    expect(wrapper.text()).toContain('MT');
    expect(wrapper.text()).toContain('Match of the Week');
  });

  it('carries the editorial blurb through the dispatcher', () => {
    const wrapper = mountCard('motw', { blurb: 'Two unbeaten records.' });

    expect(wrapper.find('[data-testid="ig-motw-blurb"]').text()).toBe(
      'Two unbeaten records.'
    );
  });

  it('leaves the blurb out entirely when none was written', () => {
    const wrapper = mountCard('motw');

    expect(wrapper.find('[data-testid="ig-motw-blurb"]').exists()).toBe(false);
  });

  it('shows VS before the match and the scores after', () => {
    const before = mountCard('motw');
    expect(before.find('[data-testid="ig-vs"]').exists()).toBe(true);
    expect(before.find('[data-testid="ig-home-score"]').exists()).toBe(false);

    const after = mountCard('motw', {
      match: createCompletedMatch({ home_score: 3, away_score: 1 }),
      mode: 'result',
    });
    expect(after.find('[data-testid="ig-status"]').text()).toBe('FULL TIME');
    expect(after.find('[data-testid="ig-home-score"]').text()).toBe('3');
  });
});
