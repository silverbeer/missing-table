/**
 * Tournament logo light/dark variants (SB-1770).
 *
 * The dark logo is optional and rare. Default fixture: a tournament with a
 * regular logo and no dark one, which must look the same in both themes. A
 * dark logo shows only in dark mode, and on the share cards, whose ground is
 * always near-black. No logo at all stays no logo.
 */

import { describe, it, expect, afterEach } from 'vitest';
import { ref, nextTick } from 'vue';
import { mount } from '@vue/test-utils';

import TournamentHeroCard from '@/components/TournamentHeroCard.vue';
import TournamentIndex from '@/components/TournamentIndex.vue';
import { useTheme } from '@/composables/useTheme';
import { useIgShareData } from '@/composables/useIgShareData';
import { tournamentLogoSrc } from '@/utils/tournamentLogo';

const LIGHT = 'https://example.test/flex.png';
const DARK = 'https://example.test/flex-dark.png';

const tournament = (over = {}) => ({
  id: 9,
  name: 'MLS NEXT Flex',
  start_date: '2026-12-05',
  end_date: '2026-12-07',
  location: null,
  description: null,
  logo_url: LIGHT,
  logo_dark_url: null,
  age_groups: [],
  ...over,
});

const theme = useTheme();
afterEach(() => {
  theme.setTheme('light');
  localStorage.clear();
});

describe('tournamentLogoSrc', () => {
  it('uses the regular logo in light mode, even when a dark one exists', () => {
    expect(tournamentLogoSrc(tournament({ logo_dark_url: DARK }), false)).toBe(
      LIGHT
    );
  });

  it('uses the dark logo in dark mode when there is one', () => {
    expect(tournamentLogoSrc(tournament({ logo_dark_url: DARK }), true)).toBe(
      DARK
    );
  });

  it('falls back to the regular logo in dark mode without a dark one', () => {
    expect(tournamentLogoSrc(tournament(), true)).toBe(LIGHT);
  });

  it('is null for no logo, or no tournament', () => {
    expect(tournamentLogoSrc(tournament({ logo_url: null }), true)).toBeNull();
    expect(tournamentLogoSrc(null, false)).toBeNull();
  });
});

describe('TournamentHeroCard logo', () => {
  const logo = w => w.find('[data-testid="tournament-logo"]');
  const mountHero = t =>
    mount(TournamentHeroCard, { props: { tournament: t, matches: [] } });

  it('follows the theme when a dark logo is set', async () => {
    const w = mountHero(tournament({ logo_dark_url: DARK }));
    expect(logo(w).attributes('src')).toBe(LIGHT);
    theme.setTheme('dark');
    await nextTick();
    expect(logo(w).attributes('src')).toBe(DARK);
  });

  it('keeps the regular logo in dark mode without a dark one', () => {
    theme.setTheme('dark');
    const w = mountHero(tournament());
    expect(logo(w).attributes('src')).toBe(LIGHT);
  });

  it('shows no logo when neither is set', () => {
    theme.setTheme('dark');
    const w = mountHero(tournament({ logo_url: null }));
    expect(logo(w).exists()).toBe(false);
  });
});

describe('TournamentIndex logo', () => {
  const logo = w => w.find('[data-testid="tournament-card-logo"]');
  const mountIndex = t =>
    mount(TournamentIndex, { props: { tournaments: [t] } });

  it('uses the dark logo in dark mode', () => {
    theme.setTheme('dark');
    const w = mountIndex(tournament({ logo_dark_url: DARK }));
    expect(logo(w).attributes('src')).toBe(DARK);
  });

  it('uses the regular logo in light mode', () => {
    const w = mountIndex(tournament({ logo_dark_url: DARK }));
    expect(logo(w).attributes('src')).toBe(LIGHT);
  });
});

describe('share cards', () => {
  const urlFor = match =>
    useIgShareData(ref(match), ref('preview'), ref([])).tournamentLogoUrl.value;

  it('prefer the dark logo, since the card ground is dark', () => {
    expect(
      urlFor({
        tournament_logo_url: LIGHT,
        tournament_logo_dark_url: DARK,
      })
    ).toBe(DARK);
  });

  it('fall back to the regular logo', () => {
    expect(
      urlFor({ tournament_logo_url: LIGHT, tournament_logo_dark_url: null })
    ).toBe(LIGHT);
  });

  it('have no logo when neither is set', () => {
    expect(urlFor({})).toBeNull();
  });
});
