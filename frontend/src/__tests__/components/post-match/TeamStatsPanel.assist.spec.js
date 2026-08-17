/**
 * TeamStatsPanel.vue — assist picker on the post-match goal form (SB-432).
 *
 * The post-match endpoint has accepted `assist_player_id` all along; this form
 * never sent it. Same rules as the live modal: optional, roster-only, and never
 * the scorer.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import TeamStatsPanel from '@/components/post-match/TeamStatsPanel.vue';

const ROSTER = [
  { id: 10, jersey_number: 9, display_name: 'Scorer Nine' },
  { id: 11, jersey_number: 8, display_name: 'Assister Eight' },
  { id: 12, jersey_number: 14, display_name: 'Other Fourteen' },
];

const mountPanel = (roster = ROSTER) =>
  mount(TeamStatsPanel, {
    props: {
      teamId: 1,
      teamName: 'Home FC',
      roster,
      events: [],
      playerStats: [],
      canEdit: true,
    },
  });

const assistSelect = wrapper =>
  wrapper.findAll('select').find(s => {
    const label = s.element.closest('div')?.querySelector('label');
    return label?.textContent?.trim() === 'Assist';
  });

describe('TeamStatsPanel assist picker (SB-432)', () => {
  it('offers no assist until a scorer is selected', async () => {
    const wrapper = mountPanel();

    expect(assistSelect(wrapper)).toBeUndefined();
  });

  it('excludes the scorer from their own assist options', async () => {
    const wrapper = mountPanel();
    wrapper.vm.goalForm.player_id = 10;
    await wrapper.vm.$nextTick();

    const select = assistSelect(wrapper);
    expect(select).toBeDefined();
    const optionText = select.findAll('option').map(o => o.text());
    // "No assist" plus the two teammates — never the scorer.
    expect(optionText).toHaveLength(3);
    expect(optionText.join(' ')).not.toContain('Scorer Nine');
  });

  it('includes assist_player_id in the emitted goal', async () => {
    const wrapper = mountPanel();
    wrapper.vm.goalForm.player_id = 10;
    await wrapper.vm.$nextTick();
    wrapper.vm.goalForm.assist_player_id = 11;
    wrapper.vm.goalForm.match_minute = 34;
    await wrapper.vm.$nextTick();

    wrapper.vm.submitGoal();

    const [payload] = wrapper.emitted('add-goal')[0];
    expect(payload.player_id).toBe(10);
    expect(payload.assist_player_id).toBe(11);
  });

  it('omits assist_player_id when no assist is chosen', async () => {
    const wrapper = mountPanel();
    wrapper.vm.goalForm.player_id = 10;
    wrapper.vm.goalForm.match_minute = 34;
    await wrapper.vm.$nextTick();

    wrapper.vm.submitGoal();

    const [payload] = wrapper.emitted('add-goal')[0];
    // Absent, not null — most goals have no assist and the API treats the
    // field as optional.
    expect('assist_player_id' in payload).toBe(false);
  });

  it('drops a stale assist when the scorer changes to the assister', async () => {
    const wrapper = mountPanel();
    wrapper.vm.goalForm.player_id = 10;
    await wrapper.vm.$nextTick();
    wrapper.vm.goalForm.assist_player_id = 11;
    await wrapper.vm.$nextTick();

    wrapper.vm.goalForm.player_id = 11;
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.goalForm.assist_player_id).toBe('');
  });

  it('resets the assist after a goal is submitted', async () => {
    const wrapper = mountPanel();
    wrapper.vm.goalForm.player_id = 10;
    await wrapper.vm.$nextTick();
    wrapper.vm.goalForm.assist_player_id = 11;
    wrapper.vm.goalForm.match_minute = 34;
    await wrapper.vm.$nextTick();

    wrapper.vm.submitGoal();
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.goalForm.assist_player_id).toBe('');
  });

  it('offers no assist picker with a free-text scorer and no roster', async () => {
    const wrapper = mountPanel([]);
    wrapper.vm.goalForm.player_name = 'Trialist 99';
    await wrapper.vm.$nextTick();

    expect(assistSelect(wrapper)).toBeUndefined();
  });
});
