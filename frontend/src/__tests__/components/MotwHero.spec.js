/**
 * MotwHero.vue tests (SB-1010).
 *
 * The hero is the one place in the app that announces a match as special, so
 * the states it can get wrong are expensive: a countdown on a match played
 * last week, or a 0–0 printed under a fixture nobody has played.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import MotwHero from '@/components/MotwHero.vue';

const HOUR = 60 * 60 * 1000;
const DAY = 24 * HOUR;

const makeMatch = (overrides = {}) => ({
  id: 1,
  match_date: '2026-09-05',
  scheduled_kickoff: new Date(Date.now() + 2 * DAY).toISOString(),
  home_team_name: 'NEFC',
  away_team_name: 'IFA',
  home_team_club: { logo_url: '/logos/nefc.png' },
  away_team_club: { logo_url: '/logos/ifa.png' },
  home_score: null,
  away_score: null,
  match_status: 'scheduled',
  age_group_name: 'U15',
  division_name: 'Northeast',
  ...overrides,
});

const mountHero = (props = {}) =>
  mount(MotwHero, {
    props: { match: makeMatch(), ...props },
    global: { stubs: { ClubLogo: true } },
  });

// The strip opens on click, so anything asserting on the fixture has to
// reveal it first — which is itself the behaviour worth guarding.
const mountOpen = async (props = {}) => {
  const wrapper = mountHero(props);
  await wrapper.find('[data-testid="motw-disclosure"]').trigger('click');
  return wrapper;
};

describe('MotwHero', () => {
  describe('the closed strip', () => {
    it('starts closed, withholding the fixture', () => {
      // The reveal is the point: one pick a week is small enough to be worth
      // discovering rather than announcing.
      const wrapper = mountHero();

      expect(wrapper.find('[data-testid="motw-panel"]').exists()).toBe(false);
      expect(wrapper.find('[data-testid="motw-home"]').exists()).toBe(false);
      expect(wrapper.text()).not.toContain('NEFC');
    });

    it('still says a pick exists, so it is worth clicking', () => {
      const wrapper = mountHero();

      expect(wrapper.text()).toContain('Match of the Week');
      expect(wrapper.find('[data-testid="motw-disclosure"]').text()).toContain(
        'Reveal'
      );
    });

    it('teases a played match as a result, not as an upcoming fixture', () => {
      const wrapper = mountHero({
        match: makeMatch({
          match_status: 'completed',
          home_score: 2,
          away_score: 0,
        }),
      });

      expect(wrapper.find('[data-testid="motw-disclosure"]').text()).toContain(
        'Played'
      );
    });

    it('opens and closes again on click', async () => {
      const wrapper = mountHero();
      const toggle = wrapper.find('[data-testid="motw-disclosure"]');

      await toggle.trigger('click');
      expect(wrapper.find('[data-testid="motw-panel"]').exists()).toBe(true);
      expect(toggle.attributes('aria-expanded')).toBe('true');

      await toggle.trigger('click');
      expect(wrapper.find('[data-testid="motw-panel"]').exists()).toBe(false);
      expect(toggle.attributes('aria-expanded')).toBe('false');
    });
  });

  describe('the fixture', () => {
    it('names both teams', async () => {
      const wrapper = await mountOpen();

      expect(wrapper.find('[data-testid="motw-home"]').text()).toBe('NEFC');
      expect(wrapper.find('[data-testid="motw-away"]').text()).toBe('IFA');
    });

    it('shows "vs" and no score before the match is played', async () => {
      const wrapper = await mountOpen();

      expect(wrapper.find('[data-testid="motw-vs"]').exists()).toBe(true);
      expect(wrapper.find('[data-testid="motw-score"]').exists()).toBe(false);
    });

    it('shows the score once the match is complete', async () => {
      const wrapper = await mountOpen({
        match: makeMatch({
          match_status: 'completed',
          home_score: 3,
          away_score: 1,
        }),
      });

      expect(wrapper.find('[data-testid="motw-score"]').text()).toContain('3');
      expect(wrapper.find('[data-testid="motw-score"]').text()).toContain('1');
      expect(wrapper.find('[data-testid="motw-vs"]').exists()).toBe(false);
    });

    it('never renders 0–0 for a scheduled match carrying stored zeros', async () => {
      // A scheduled match with zeros on it is not a goalless draw — it is a
      // result nobody recorded (CLAUDE.md rule 2, SB-886).
      const wrapper = await mountOpen({
        match: makeMatch({ home_score: 0, away_score: 0 }),
      });

      expect(wrapper.find('[data-testid="motw-score"]').exists()).toBe(false);
      expect(wrapper.find('[data-testid="motw-vs"]').exists()).toBe(true);
    });

    it('treats a half-entered result as no result', async () => {
      const wrapper = await mountOpen({
        match: makeMatch({
          match_status: 'completed',
          home_score: 2,
          away_score: null,
        }),
      });

      expect(wrapper.find('[data-testid="motw-score"]').exists()).toBe(false);
    });
  });

  describe('the status line', () => {
    it('counts down in days for a match days away', async () => {
      const wrapper = await mountOpen();

      expect(wrapper.find('[data-testid="motw-status"]').text()).toBe(
        'Kicks off in 2 days'
      );
    });

    it('counts down in hours inside a day', async () => {
      const wrapper = await mountOpen({
        match: makeMatch({
          scheduled_kickoff: new Date(Date.now() + 3 * HOUR).toISOString(),
        }),
      });

      expect(wrapper.find('[data-testid="motw-status"]').text()).toBe(
        'Kicks off in 3 hours'
      );
    });

    it('says full time instead of counting down to a played match', async () => {
      // The countdown running on a finished match is what makes a featured
      // card look abandoned by Monday.
      const wrapper = await mountOpen({
        match: makeMatch({
          match_status: 'completed',
          home_score: 1,
          away_score: 0,
          scheduled_kickoff: new Date(Date.now() - 3 * DAY).toISOString(),
        }),
      });

      expect(wrapper.find('[data-testid="motw-status"]').text()).toBe(
        'Full time'
      );
    });

    it('says live while the match is under way', async () => {
      const wrapper = await mountOpen({
        match: makeMatch({
          match_status: 'live',
          home_score: 1,
          away_score: 1,
        }),
      });

      expect(wrapper.find('[data-testid="motw-status"]').text()).toBe(
        'Live now'
      );
    });

    it('admits an unknown kick-off rather than inventing one', async () => {
      const wrapper = await mountOpen({
        match: makeMatch({ scheduled_kickoff: null }),
      });

      expect(wrapper.find('[data-testid="motw-status"]').text()).toBe(
        'Time TBC'
      );
    });
  });

  describe('the meta line', () => {
    it('lists age group and division', async () => {
      const text = (await mountOpen()).find('[data-testid="motw-meta"]').text();

      expect(text).toContain('U15');
      expect(text).toContain('Northeast');
    });

    it('omits a division the API could not name, rather than printing Unknown', async () => {
      // "Unknown" on the one card the site is showing off is worse than a
      // shorter line.
      const wrapper = await mountOpen({
        match: makeMatch({ division_name: 'Unknown' }),
      });

      expect(wrapper.find('[data-testid="motw-meta"]').text()).not.toContain(
        'Unknown'
      );
    });

    it('falls back to the match date when there is no kick-off time', async () => {
      const wrapper = await mountOpen({
        match: makeMatch({ scheduled_kickoff: null }),
      });

      expect(wrapper.find('[data-testid="motw-meta"]').text()).toContain(
        '2026-09-05'
      );
    });
  });

  describe('the editorial line (SB-1010)', () => {
    it('offers nothing to write with when the viewer is not an admin', () => {
      const wrapper = mountHero();

      expect(wrapper.find('[data-testid="motw-blurb-add"]').exists()).toBe(
        false
      );
      expect(wrapper.find('[data-testid="motw-blurb-edit"]').exists()).toBe(
        false
      );
    });

    it('invites an admin to write one when the pick has no line yet', async () => {
      const wrapper = await mountOpen({ canEdit: true });

      expect(wrapper.find('[data-testid="motw-blurb-add"]').exists()).toBe(
        true
      );
    });

    it('opens the editor primed with the existing line', async () => {
      const wrapper = await mountOpen({
        canEdit: true,
        blurb: 'Two unbeaten records.',
      });

      await wrapper.find('[data-testid="motw-blurb-edit"]').trigger('click');

      expect(
        wrapper.find('[data-testid="motw-blurb-input"]').element.value
      ).toBe('Two unbeaten records.');
    });

    it('emits the trimmed line on save', async () => {
      const wrapper = await mountOpen({ canEdit: true });

      await wrapper.find('[data-testid="motw-blurb-add"]').trigger('click');
      await wrapper
        .find('[data-testid="motw-blurb-input"]')
        .setValue('  Two unbeaten records.  ');
      await wrapper.find('[data-testid="motw-blurb-save"]').trigger('click');

      expect(wrapper.emitted('save-blurb')[0][0]).toBe('Two unbeaten records.');
    });

    it('saves an emptied line as absent, not as an empty one', async () => {
      // The share card renders its "why" panel on presence. A blank string
      // would frame nothing.
      const wrapper = await mountOpen({ canEdit: true, blurb: 'Old line.' });

      await wrapper.find('[data-testid="motw-blurb-edit"]').trigger('click');
      await wrapper.find('[data-testid="motw-blurb-input"]').setValue('   ');
      await wrapper.find('[data-testid="motw-blurb-save"]').trigger('click');

      expect(wrapper.emitted('save-blurb')[0][0]).toBe(null);
    });

    it('caps the line where the API does', async () => {
      const wrapper = await mountOpen({ canEdit: true });

      await wrapper.find('[data-testid="motw-blurb-add"]').trigger('click');

      expect(
        wrapper.find('[data-testid="motw-blurb-input"]').attributes('maxlength')
      ).toBe('280');
    });

    it('keeps quiet about the count until it is nearly spent', async () => {
      const wrapper = await mountOpen({ canEdit: true });
      await wrapper.find('[data-testid="motw-blurb-add"]').trigger('click');

      const count = () => wrapper.find('[data-testid="motw-blurb-count"]');
      expect(count().classes()).not.toContain('motw-editor-count--near');

      await wrapper
        .find('[data-testid="motw-blurb-input"]')
        .setValue('x'.repeat(250));

      expect(count().classes()).toContain('motw-editor-count--near');
    });

    it('cancel abandons the draft and leaves the line alone', async () => {
      const wrapper = await mountOpen({
        canEdit: true,
        blurb: 'Two unbeaten records.',
      });

      await wrapper.find('[data-testid="motw-blurb-edit"]').trigger('click');
      await wrapper.find('[data-testid="motw-blurb-input"]').setValue('junk');
      await wrapper.find('[data-testid="motw-blurb-cancel"]').trigger('click');

      expect(wrapper.emitted('save-blurb')).toBeUndefined();
      expect(wrapper.find('[data-testid="motw-blurb"]').text()).toContain(
        'Two unbeaten records.'
      );
    });

    it('holds the editor open while the save is in flight', async () => {
      // A failed save must not throw away what someone just wrote.
      const wrapper = await mountOpen({ canEdit: true, saving: true });

      await wrapper.find('[data-testid="motw-blurb-add"]').trigger('click');

      expect(
        wrapper.find('[data-testid="motw-blurb-save"]').attributes('disabled')
      ).toBeDefined();
      expect(wrapper.find('[data-testid="motw-blurb-editor"]').exists()).toBe(
        true
      );
    });
  });

  describe('blurb and actions', () => {
    it('renders the blurb when there is one', async () => {
      const wrapper = await mountOpen({ blurb: 'Two unbeaten records.' });

      expect(wrapper.find('[data-testid="motw-blurb"]').text()).toBe(
        'Two unbeaten records.'
      );
    });

    it('renders no blurb element at all when none was written', async () => {
      // Absent renders as absent, not as an empty line holding space.
      const wrapper = await mountOpen();
      expect(wrapper.find('[data-testid="motw-blurb"]').exists()).toBe(false);
    });

    it('hides the share button from logged-out viewers', async () => {
      const wrapper = await mountOpen();
      expect(wrapper.find('[data-testid="motw-share"]').exists()).toBe(false);
    });

    it('offers sharing to a signed-in viewer', async () => {
      const wrapper = await mountOpen({ canShare: true });

      expect(wrapper.find('[data-testid="motw-share"]').exists()).toBe(true);
    });

    it('emits the match on preview and share', async () => {
      const wrapper = await mountOpen({ canShare: true });

      await wrapper.find('[data-testid="motw-preview"]').trigger('click');
      await wrapper.find('[data-testid="motw-share"]').trigger('click');

      expect(wrapper.emitted('preview')[0][0].id).toBe(1);
      expect(wrapper.emitted('share')[0][0].id).toBe(1);
    });

    it('calls the primary action "View match" once there is a result', async () => {
      const wrapper = await mountOpen({
        match: makeMatch({
          match_status: 'completed',
          home_score: 2,
          away_score: 2,
        }),
      });

      expect(wrapper.find('[data-testid="motw-preview"]').text()).toBe(
        'View match'
      );
    });
  });
});
