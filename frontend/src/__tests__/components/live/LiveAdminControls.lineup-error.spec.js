/**
 * LiveAdminControls.vue — SB-118 error/retry surface
 *
 * Covers the three SB-118 behaviors:
 *  (a) a failed fetchRosters prop renders the error div + Retry button
 *      and leaves lineupsLoaded false (LineupManager not rendered)
 *  (b) clicking Retry re-invokes the loaders; on success the error clears
 *      and LineupManager is rendered
 *  (c) handleSaveLineup with {success:false, error:'boom'} calls alert and
 *      leaves savingLineup false after the call
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import LiveAdminControls from '@/components/live/LiveAdminControls.vue';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const baseMatchState = {
  home_team_id: 10,
  away_team_id: 20,
  home_team_name: 'Home FC',
  away_team_name: 'Away FC',
  home_score: 0,
  away_score: 0,
  age_group_name: 'U15',
  half_duration: 45,
};

/**
 * Mount the component with the lineup section already open so we don't need
 * to click the toggle in every test. We open it by calling toggleLineupSection
 * after mount (since Vue Test Utils can trigger the button click).
 *
 * Stubs LineupManager to keep the test lightweight and avoid its own
 * internal setup (Supabase, formations config, etc.).
 */
const mountControls = async (propsOverrides = {}) => {
  const wrapper = mount(LiveAdminControls, {
    props: {
      matchState: baseMatchState,
      matchPeriod: 'Not Started',
      ...propsOverrides,
    },
    global: {
      stubs: {
        LineupManager: {
          name: 'LineupManager',
          props: [
            'teamId',
            'teamName',
            'ageGroupName',
            'roster',
            'initialLineup',
            'saving',
            'sportType',
          ],
          emits: ['save'],
          template:
            '<div class="lineup-manager-stub" data-testid="lineup-manager-stub" />',
        },
      },
    },
  });

  // Open the lineup section so the conditional content is visible
  await wrapper.find('.section-toggle').trigger('click');

  return wrapper;
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('LiveAdminControls — SB-118 lineup error/retry', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  // ── (a) failed load ──────────────────────────────────────────────────────
  describe('when fetchRosters rejects on initial load', () => {
    it('shows the lineup-error div with a Retry button', async () => {
      const failingFetchRosters = vi
        .fn()
        .mockRejectedValue(new Error('Network error'));

      const wrapper = await mountControls({
        fetchRosters: failingFetchRosters,
      });

      // Wait for the async loadLineupsAndRosters triggered by toggle
      await vi.waitFor(() => wrapper.find('.lineup-error').exists());

      expect(wrapper.find('.lineup-error').exists()).toBe(true);
      expect(wrapper.find('.lineup-error').text()).toContain(
        'Could not load lineups'
      );
      expect(wrapper.find('.retry-button').exists()).toBe(true);
    });

    it('does not render LineupManager when the load failed', async () => {
      const failingFetchRosters = vi
        .fn()
        .mockRejectedValue(new Error('Network error'));

      const wrapper = await mountControls({
        fetchRosters: failingFetchRosters,
      });

      await vi.waitFor(() => wrapper.find('.lineup-error').exists());

      expect(wrapper.find('[data-testid="lineup-manager-stub"]').exists()).toBe(
        false
      );
    });
  });

  // ── (b) retry succeeds ───────────────────────────────────────────────────
  describe('when Retry is clicked and the second load succeeds', () => {
    it('clears the error and renders LineupManager', async () => {
      let callCount = 0;
      const flakyFetchRosters = vi.fn().mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.reject(new Error('blip'));
        }
        return Promise.resolve({ home: [], away: [] });
      });

      const fetchLineups = vi.fn().mockResolvedValue(undefined);

      const wrapper = await mountControls({
        fetchRosters: flakyFetchRosters,
        fetchLineups,
      });

      // Wait for initial failure to surface
      await vi.waitFor(() => wrapper.find('.lineup-error').exists());

      // Click Retry
      await wrapper.find('.retry-button').trigger('click');

      // Wait for the error to clear
      await vi.waitFor(() => !wrapper.find('.lineup-error').exists());

      expect(wrapper.find('.lineup-error').exists()).toBe(false);
      expect(wrapper.find('[data-testid="lineup-manager-stub"]').exists()).toBe(
        true
      );
    });

    it('calls fetchRosters a second time when Retry is clicked', async () => {
      let callCount = 0;
      const flakyFetchRosters = vi.fn().mockImplementation(() => {
        callCount++;
        if (callCount === 1) return Promise.reject(new Error('blip'));
        return Promise.resolve({ home: [], away: [] });
      });

      const fetchLineups = vi.fn().mockResolvedValue(undefined);

      const wrapper = await mountControls({
        fetchRosters: flakyFetchRosters,
        fetchLineups,
      });

      await vi.waitFor(() => wrapper.find('.lineup-error').exists());
      await wrapper.find('.retry-button').trigger('click');
      await vi.waitFor(() => !wrapper.find('.lineup-error').exists());

      expect(flakyFetchRosters).toHaveBeenCalledTimes(2);
    });
  });

  // ── (c) save failure calls alert ─────────────────────────────────────────
  describe('handleSaveLineup with {success:false}', () => {
    it('calls window.alert with the error message', async () => {
      const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

      const saveLineup = vi.fn().mockResolvedValue({
        success: false,
        error: 'boom',
      });

      // Mount with a working load path so we reach LineupManager
      const fetchRosters = vi.fn().mockResolvedValue({ home: [], away: [] });
      const fetchLineups = vi.fn().mockResolvedValue(undefined);

      const wrapper = await mountControls({
        fetchRosters,
        fetchLineups,
        saveLineup,
      });

      // Wait for lineup section to fully load (no error, LineupManager rendered)
      await vi.waitFor(() =>
        wrapper.find('[data-testid="lineup-manager-stub"]').exists()
      );

      // Trigger handleSaveLineup by emitting 'save' from the LineupManager stub.
      // The template binds @save="handleSaveLineup(matchState.home_team_id, $event)".
      const stub = wrapper.findComponent({ name: 'LineupManager' });
      await stub.vm.$emit('save', {
        formation_name: '4-3-3',
        positions: [],
      });

      await vi.waitFor(() => alertSpy.mock.calls.length > 0);

      expect(alertSpy).toHaveBeenCalledWith('boom');
    });

    it('resets savingLineup to false after a failed save', async () => {
      vi.spyOn(window, 'alert').mockImplementation(() => {});

      const saveLineup = vi.fn().mockResolvedValue({
        success: false,
        error: 'boom',
      });

      const fetchRosters = vi.fn().mockResolvedValue({ home: [], away: [] });
      const fetchLineups = vi.fn().mockResolvedValue(undefined);

      const wrapper = await mountControls({
        fetchRosters,
        fetchLineups,
        saveLineup,
      });

      await vi.waitFor(() =>
        wrapper.find('[data-testid="lineup-manager-stub"]').exists()
      );

      const stub = wrapper.findComponent({ name: 'LineupManager' });
      await stub.vm.$emit('save', {
        formation_name: '4-3-3',
        positions: [],
      });

      // After the async chain resolves, savingLineup must be false.
      // We verify indirectly: the LineupManager stub must still exist
      // (not in a loading / error state) and alert must have been called.
      await vi.waitFor(() => expect(saveLineup).toHaveBeenCalled());

      // savingLineup is an internal ref — confirm via prop that was passed to stub.
      // Vue Test Utils exposes props on the stub component.
      // After the finally block runs, saving prop should be false.
      // Give the event loop one more tick.
      await new Promise(r => setTimeout(r, 0));

      const stubEl = wrapper.findComponent({ name: 'LineupManager' });
      expect(stubEl.props('saving')).toBe(false);
    });
  });
});
