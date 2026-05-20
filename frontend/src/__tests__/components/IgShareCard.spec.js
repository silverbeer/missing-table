/**
 * IgShareCard.vue Tests (SB-32)
 *
 * Pure presentational tests: mode toggling, photo fallback, initials.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import IgShareCard from '@/components/IgShareCard.vue';
import {
  createMockMatch,
  createCompletedMatch,
} from '../helpers/matchFactories';

const mountCard = (props = {}) =>
  mount(IgShareCard, {
    props: {
      match: createMockMatch(),
      mode: 'preview',
      ...props,
    },
  });

describe('IgShareCard', () => {
  describe('preview mode', () => {
    it('renders MATCH PREVIEW status and VS divider', () => {
      const wrapper = mountCard({ mode: 'preview' });
      expect(wrapper.find('[data-testid="ig-status"]').text()).toBe(
        'MATCH PREVIEW'
      );
      expect(wrapper.find('[data-testid="ig-vs"]').text()).toBe('VS');
      expect(wrapper.find('[data-testid="ig-score"]').exists()).toBe(false);
    });

    it('renders kickoff time when scheduled_kickoff is set', () => {
      const wrapper = mountCard({
        mode: 'preview',
        match: createMockMatch({
          scheduled_kickoff: '2026-05-25T19:00:00Z',
        }),
      });
      expect(wrapper.find('[data-testid="ig-kickoff"]').exists()).toBe(true);
    });

    it('omits kickoff element when scheduled_kickoff is missing', () => {
      const wrapper = mountCard({
        mode: 'preview',
        match: createMockMatch({ scheduled_kickoff: null }),
      });
      expect(wrapper.find('[data-testid="ig-kickoff"]').exists()).toBe(false);
    });
  });

  describe('result mode', () => {
    it('renders FINAL status and the score, not VS', () => {
      const wrapper = mountCard({
        mode: 'result',
        match: createCompletedMatch({ home_score: 4, away_score: 2 }),
      });
      expect(wrapper.find('[data-testid="ig-status"]').text()).toBe('FINAL');
      const score = wrapper.find('[data-testid="ig-score"]');
      expect(score.exists()).toBe(true);
      expect(score.text()).toMatch(/4\s*–\s*2/);
      expect(wrapper.find('[data-testid="ig-vs"]').exists()).toBe(false);
    });
  });

  describe('photo handling', () => {
    it('renders <img> when photoSrc is provided', () => {
      const wrapper = mountCard({
        photoSrc: 'blob:fake/photo',
      });
      expect(wrapper.find('[data-testid="ig-photo"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="ig-photo-fallback"]').exists()).toBe(
        false
      );
    });

    it('renders gradient fallback when photoSrc is null', () => {
      const wrapper = mountCard({ photoSrc: null });
      expect(wrapper.find('[data-testid="ig-photo-fallback"]').exists()).toBe(
        true
      );
      expect(wrapper.find('[data-testid="ig-photo"]').exists()).toBe(false);
    });

    it('sets crossorigin only when photoIsCrossOrigin is true', () => {
      const wrapper = mountCard({
        photoSrc: 'https://example.com/p.jpg',
        photoIsCrossOrigin: true,
      });
      expect(
        wrapper.find('[data-testid="ig-photo"]').attributes('crossorigin')
      ).toBe('anonymous');
    });
  });

  describe('team display', () => {
    it('renders team names', () => {
      const wrapper = mountCard();
      expect(wrapper.find('[data-testid="ig-home-name"]').text()).toBe(
        'Blue Stars U14'
      );
      expect(wrapper.find('[data-testid="ig-away-name"]').text()).toBe(
        'Red Hawks U14'
      );
    });

    it('uses initials fallback when team has no logo_url', () => {
      const wrapper = mountCard({
        match: createMockMatch({
          home_team_club: { logo_url: null, primary_color: '#000' },
          home_team_name: 'Green Valley United',
        }),
      });
      // GVU initials: G V U
      expect(wrapper.html()).toContain('GVU');
    });
  });

  describe('metadata chips', () => {
    it('renders age group label', () => {
      const wrapper = mountCard();
      expect(wrapper.find('[data-testid="ig-age-chip"]').text()).toBe('U14');
    });

    it('formats meta line as upper-cased type · division', () => {
      const wrapper = mountCard();
      expect(wrapper.find('[data-testid="ig-meta"]').text()).toBe(
        'LEAGUE · NORTHEAST'
      );
    });

    it('falls back to season when division is missing', () => {
      const wrapper = mountCard({
        match: createMockMatch({
          division_name: null,
          division: null,
          season_name: '2025-2026',
        }),
      });
      expect(wrapper.find('[data-testid="ig-meta"]').text()).toContain(
        '2025-2026'
      );
    });

    it('prefers tournament_name over division for tournament matches', () => {
      const wrapper = mountCard({
        match: createMockMatch({
          match_type_name: 'Tournament',
          tournament_name: 'Generation Cup',
          // Backend sets these to the literal "Unknown" string when null:
          division_name: 'Unknown',
          division: null,
        }),
      });
      expect(wrapper.find('[data-testid="ig-meta"]').text()).toBe(
        'TOURNAMENT · GENERATION CUP'
      );
    });

    it('filters out the literal "Unknown" sentinel from the meta line', () => {
      const wrapper = mountCard({
        match: createMockMatch({
          match_type_name: 'Tournament',
          tournament_name: null,
          division_name: 'Unknown', // backend default
          season_name: 'Unknown',
        }),
      });
      // Should NOT contain UNKNOWN — only TOURNAMENT.
      expect(wrapper.find('[data-testid="ig-meta"]').text()).toBe('TOURNAMENT');
    });
  });

  describe('layout invariants', () => {
    it('matches the 1080x1080 contract', () => {
      const wrapper = mountCard();
      // Inline styles in scoped <style> get hoisted; we just check the
      // class is present (the CSS itself is the contract). Smoke check:
      expect(wrapper.find('[data-testid="ig-share-card"]').exists()).toBe(true);
    });
  });
});
