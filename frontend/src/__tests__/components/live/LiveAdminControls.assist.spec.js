/**
 * LiveAdminControls.vue — assist picker on the goal modal (SB-432).
 *
 * The backend has accepted and validated `assist_player_id` since the Android
 * live-scoring work; the web UI never sent it. These pin the picker's rules:
 *
 *  (a) no assist offered until a roster scorer is chosen
 *  (b) the scorer is excluded from their own assist options
 *  (c) submitting with an assist emits assistPlayerId
 *  (d) submitting without one emits null — most goals have no assist
 *  (e) changing the scorer to the current assister drops the stale assist
 *  (f) a free-text ("Other") scorer gets no assist picker at all
 *
 * Refs are set directly rather than driven through the selects, matching
 * LiveAdminControls.spec.js.
 */

import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import LiveAdminControls from '@/components/live/LiveAdminControls.vue';

vi.mock('@/components/live/LineupManager.vue', () => ({
  default: { template: '<div />' },
}));

const baseMatchState = {
  home_team_id: 1,
  away_team_id: 2,
  home_team_name: 'Home FC',
  away_team_name: 'Away FC',
  home_score: 0,
  away_score: 0,
  age_group_name: 'U15',
  half_duration: 45,
};

const mockRoster = [
  { id: 10, jersey_number: 9, display_name: 'Scorer Nine' },
  { id: 11, jersey_number: 8, display_name: 'Assister Eight' },
  { id: 12, jersey_number: 14, display_name: 'Other Fourteen' },
];

const mountControls = () =>
  mount(LiveAdminControls, {
    props: {
      matchState: baseMatchState,
      matchPeriod: '1st Half',
      fetchRosters: vi.fn().mockResolvedValue({ home: [], away: [] }),
      fetchLineups: vi.fn().mockResolvedValue(undefined),
      saveLineup: vi.fn().mockResolvedValue({ success: true }),
      homeLineup: null,
      awayLineup: null,
      sportType: 'soccer',
    },
  });

/** Goal modal open on the home team, with a roster loaded. */
async function openGoalModal(wrapper, { roster = mockRoster } = {}) {
  wrapper.vm.homeRoster = roster;
  wrapper.vm.rostersLoaded = true;
  wrapper.vm.showGoalModal = true;
  wrapper.vm.goalTeamId = baseMatchState.home_team_id;
  await wrapper.vm.$nextTick();
}

const assistSelect = wrapper => wrapper.find('#assist-select');

describe('LiveAdminControls assist picker (SB-432)', () => {
  it('offers no assist until a roster scorer is selected', async () => {
    const wrapper = mountControls();
    await openGoalModal(wrapper);

    expect(assistSelect(wrapper).exists()).toBe(false);
  });

  it('excludes the scorer from their own assist options', async () => {
    const wrapper = mountControls();
    await openGoalModal(wrapper);
    wrapper.vm.selectedPlayerId = 10;
    await wrapper.vm.$nextTick();

    expect(assistSelect(wrapper).exists()).toBe(true);
    const optionText = assistSelect(wrapper)
      .findAll('option')
      .map(o => o.text());
    // "No assist" plus the two teammates — never the scorer.
    expect(optionText).toHaveLength(3);
    expect(optionText.join(' ')).not.toContain('Scorer Nine');
    expect(optionText.join(' ')).toContain('Assister Eight');
  });

  it('emits assistPlayerId when an assist is chosen', async () => {
    const wrapper = mountControls();
    await openGoalModal(wrapper);
    wrapper.vm.selectedPlayerId = 10;
    await wrapper.vm.$nextTick();
    wrapper.vm.selectedAssistPlayerId = 11;
    await wrapper.vm.$nextTick();

    await wrapper.find('.submit-button').trigger('click');

    const [payload] = wrapper.emitted('post-goal')[0];
    expect(payload.playerId).toBe(10);
    expect(payload.assistPlayerId).toBe(11);
  });

  it('emits a null assist when none is chosen', async () => {
    const wrapper = mountControls();
    await openGoalModal(wrapper);
    wrapper.vm.selectedPlayerId = 10;
    await wrapper.vm.$nextTick();

    await wrapper.find('.submit-button').trigger('click');

    const [payload] = wrapper.emitted('post-goal')[0];
    expect(payload.playerId).toBe(10);
    expect(payload.assistPlayerId).toBeNull();
  });

  it('drops a stale assist when the scorer changes to the assister', async () => {
    const wrapper = mountControls();
    await openGoalModal(wrapper);
    wrapper.vm.selectedPlayerId = 10;
    await wrapper.vm.$nextTick();
    wrapper.vm.selectedAssistPlayerId = 11;
    await wrapper.vm.$nextTick();

    // The assister scored after all — their own assist must not survive.
    wrapper.vm.selectedPlayerId = 11;
    await wrapper.vm.$nextTick();
    await wrapper.find('.submit-button').trigger('click');

    const [payload] = wrapper.emitted('post-goal')[0];
    expect(payload.playerId).toBe(11);
    expect(payload.assistPlayerId).toBeNull();
  });

  it('offers no assist picker for a free-text scorer', async () => {
    const wrapper = mountControls();
    await openGoalModal(wrapper);
    wrapper.vm.selectedPlayerId = 'other';
    await wrapper.vm.$nextTick();

    // The API only accepts a roster player as assister, so there is nothing
    // sensible to offer alongside a typed-in name.
    expect(assistSelect(wrapper).exists()).toBe(false);
  });

  it('sends no assist for a free-text scorer even if one was picked first', async () => {
    const wrapper = mountControls();
    await openGoalModal(wrapper);
    wrapper.vm.selectedPlayerId = 10;
    await wrapper.vm.$nextTick();
    wrapper.vm.selectedAssistPlayerId = 11;
    await wrapper.vm.$nextTick();

    wrapper.vm.selectedPlayerId = 'other';
    wrapper.vm.goalPlayerName = 'Trialist 99';
    await wrapper.vm.$nextTick();
    await wrapper.find('.submit-button').trigger('click');

    const [payload] = wrapper.emitted('post-goal')[0];
    expect(payload.playerId).toBeNull();
    expect(payload.assistPlayerId).toBeNull();
  });

  it('offers no assist picker when the team has no roster', async () => {
    const wrapper = mountControls();
    await openGoalModal(wrapper, { roster: [] });

    expect(assistSelect(wrapper).exists()).toBe(false);
  });
});
