/**
 * LiveAdminControls.vue — card modal free-text player entry (SB-117).
 *
 * Covers:
 *  (a) empty roster → free-text input visible, Record Card disabled until
 *      name typed, enabled after
 *  (b) submit with empty roster emits post-card with playerName set + playerId null
 *  (c) roster present → selecting player enables submit, emits playerId with
 *      playerName null
 *  (d) "Other (type name)" option in roster select shows free-text input
 */

import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import LiveAdminControls from '@/components/live/LiveAdminControls.vue';

// LineupManager imports nothing that needs mocking for these tests, but we
// stub it to avoid pulling in its own dependencies (roster-heavy UI not under
// test here).
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

/**
 * Mounts the component with the clock running (1st Half) so the card button
 * is visible. Extra props/overrides can be provided.
 */
const mountControls = (overrides = {}) =>
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
      ...overrides,
    },
  });

// ---------------------------------------------------------------------------
// Helpers to drive the card modal through common steps
// ---------------------------------------------------------------------------

/** Open the card modal via the "+ Card" button. */
async function openCardModal(wrapper) {
  await wrapper.find('.control-button.card').trigger('click');
}

// ---------------------------------------------------------------------------
// Scenario (a) — empty roster
// ---------------------------------------------------------------------------

describe('LiveAdminControls card modal — empty roster (SB-117)', () => {
  it('shows free-text input when the card team has no roster', async () => {
    const wrapper = mountControls({
      fetchRosters: vi.fn().mockResolvedValue({ home: [], away: [] }),
    });

    await openCardModal(wrapper);

    // Trigger the watcher that loads rosters on modal open (flush promises)
    await wrapper.vm.$nextTick();

    // Set the cardTeamId directly through the internal ref so we can inspect
    // the roster-dependent UI without needing an async roster load in tests.
    wrapper.vm.showCardModal = true;
    // Simulate home team selection; cardTeamRoster will be [] because homeRoster is []
    wrapper.vm.cardTeamId = baseMatchState.home_team_id;
    await wrapper.vm.$nextTick();

    // No roster → no <select>, only "No roster available" and a free-text input
    expect(wrapper.find('#card-player-select').exists()).toBe(false);
    expect(
      wrapper.find('input[placeholder="Enter player name or number"]').exists()
    ).toBe(true);
  });

  it('Record Card button is disabled with empty roster and no name typed', async () => {
    const wrapper = mountControls();
    wrapper.vm.showCardModal = true;
    wrapper.vm.cardTeamId = baseMatchState.home_team_id;
    wrapper.vm.selectedCardType = 'yellow_card';
    // cardPlayerName is '' by default → canSubmitCard false
    await wrapper.vm.$nextTick();

    const submitBtn = wrapper.find('.submit-button');
    expect(submitBtn.attributes('disabled')).toBeDefined();
  });

  it('Record Card button becomes enabled once a name is typed (empty roster)', async () => {
    const wrapper = mountControls();
    wrapper.vm.showCardModal = true;
    wrapper.vm.cardTeamId = baseMatchState.home_team_id;
    wrapper.vm.selectedCardType = 'yellow_card';
    await wrapper.vm.$nextTick();

    const input = wrapper.find(
      'input[placeholder="Enter player name or number"]'
    );
    await input.setValue('Player 7');
    await wrapper.vm.$nextTick();

    const submitBtn = wrapper.find('.submit-button');
    expect(submitBtn.attributes('disabled')).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Scenario (b) — submit with empty roster emits correct payload
// ---------------------------------------------------------------------------

describe('LiveAdminControls card modal — post-card emit with free-text player (SB-117)', () => {
  it('emits post-card with playerName and playerId null when using free-text entry', async () => {
    const wrapper = mountControls();
    wrapper.vm.showCardModal = true;
    wrapper.vm.cardTeamId = baseMatchState.away_team_id;
    wrapper.vm.selectedCardType = 'red_card';
    wrapper.vm.cardPlayerName = 'Keeper 1';
    wrapper.vm.cardMessage = 'Dangerous foul';
    await wrapper.vm.$nextTick();

    await wrapper.find('.submit-button').trigger('click');

    expect(wrapper.emitted('post-card')).toBeTruthy();
    const [payload] = wrapper.emitted('post-card')[0];
    expect(payload.playerId).toBeNull();
    expect(payload.playerName).toBe('Keeper 1');
    expect(payload.teamId).toBe(baseMatchState.away_team_id);
    expect(payload.cardType).toBe('red_card');
    expect(payload.message).toBe('Dangerous foul');
  });

  it('modal resets and closes after submit', async () => {
    const wrapper = mountControls();
    wrapper.vm.showCardModal = true;
    wrapper.vm.cardTeamId = baseMatchState.home_team_id;
    wrapper.vm.selectedCardType = 'yellow_card';
    wrapper.vm.cardPlayerName = 'Sub 15';
    await wrapper.vm.$nextTick();

    await wrapper.find('.submit-button').trigger('click');
    await wrapper.vm.$nextTick();

    expect(wrapper.vm.showCardModal).toBe(false);
    expect(wrapper.vm.cardTeamId).toBeNull();
    expect(wrapper.vm.cardPlayerName).toBe('');
  });
});

// ---------------------------------------------------------------------------
// Scenario (c) — roster present: selecting player enables submit, emits
//               playerId with playerName null
// ---------------------------------------------------------------------------

describe('LiveAdminControls card modal — roster present (SB-117)', () => {
  const mockRoster = [
    { id: 10, jersey_number: 10, display_name: 'Alice' },
    { id: 11, jersey_number: 11, display_name: 'Bob' },
  ];

  it('shows the player select when a roster is available', async () => {
    const wrapper = mountControls();
    // Pre-load homeRoster as if fetchRosters resolved
    wrapper.vm.homeRoster = mockRoster;
    wrapper.vm.rostersLoaded = true;
    wrapper.vm.showCardModal = true;
    wrapper.vm.cardTeamId = baseMatchState.home_team_id;
    await wrapper.vm.$nextTick();

    expect(wrapper.find('#card-player-select').exists()).toBe(true);
  });

  it('submit is disabled when no player is selected from roster', async () => {
    const wrapper = mountControls();
    wrapper.vm.homeRoster = mockRoster;
    wrapper.vm.rostersLoaded = true;
    wrapper.vm.showCardModal = true;
    wrapper.vm.cardTeamId = baseMatchState.home_team_id;
    wrapper.vm.selectedCardType = 'yellow_card';
    // cardPlayerId defaults to null → canSubmitCard false
    await wrapper.vm.$nextTick();

    const submitBtn = wrapper.find('.submit-button');
    expect(submitBtn.attributes('disabled')).toBeDefined();
  });

  it('submit is enabled once a roster player is selected', async () => {
    const wrapper = mountControls();
    wrapper.vm.homeRoster = mockRoster;
    wrapper.vm.rostersLoaded = true;
    wrapper.vm.showCardModal = true;
    wrapper.vm.cardTeamId = baseMatchState.home_team_id;
    wrapper.vm.selectedCardType = 'yellow_card';
    wrapper.vm.cardPlayerId = 10; // select Alice
    await wrapper.vm.$nextTick();

    const submitBtn = wrapper.find('.submit-button');
    expect(submitBtn.attributes('disabled')).toBeUndefined();
  });

  it('emits post-card with playerId set and playerName null when roster player chosen', async () => {
    const wrapper = mountControls();
    wrapper.vm.homeRoster = mockRoster;
    wrapper.vm.rostersLoaded = true;
    wrapper.vm.showCardModal = true;
    wrapper.vm.cardTeamId = baseMatchState.home_team_id;
    wrapper.vm.selectedCardType = 'yellow_card';
    wrapper.vm.cardPlayerId = 10;
    await wrapper.vm.$nextTick();

    await wrapper.find('.submit-button').trigger('click');

    expect(wrapper.emitted('post-card')).toBeTruthy();
    const [payload] = wrapper.emitted('post-card')[0];
    expect(payload.playerId).toBe(10);
    expect(payload.playerName).toBeNull();
    expect(payload.teamId).toBe(baseMatchState.home_team_id);
    expect(payload.cardType).toBe('yellow_card');
  });
});

// ---------------------------------------------------------------------------
// Scenario (d) — "Other (type name)" option shows free-text input
// ---------------------------------------------------------------------------

describe('LiveAdminControls card modal — Other option (SB-117)', () => {
  const mockRoster = [{ id: 5, jersey_number: 5, display_name: 'Dave' }];

  it('shows free-text input when "Other" is selected', async () => {
    const wrapper = mountControls();
    wrapper.vm.homeRoster = mockRoster;
    wrapper.vm.rostersLoaded = true;
    wrapper.vm.showCardModal = true;
    wrapper.vm.cardTeamId = baseMatchState.home_team_id;
    wrapper.vm.cardPlayerId = 'other';
    await wrapper.vm.$nextTick();

    // The free-text input should now be visible alongside the select
    expect(
      wrapper.find('input[placeholder="Enter player name or number"]').exists()
    ).toBe(true);
    // The select is also present (roster exists)
    expect(wrapper.find('#card-player-select').exists()).toBe(true);
  });

  it('submit is disabled when Other is selected but name is empty', async () => {
    const wrapper = mountControls();
    wrapper.vm.homeRoster = mockRoster;
    wrapper.vm.rostersLoaded = true;
    wrapper.vm.showCardModal = true;
    wrapper.vm.cardTeamId = baseMatchState.home_team_id;
    wrapper.vm.selectedCardType = 'yellow_card';
    wrapper.vm.cardPlayerId = 'other';
    wrapper.vm.cardPlayerName = '';
    await wrapper.vm.$nextTick();

    expect(wrapper.find('.submit-button').attributes('disabled')).toBeDefined();
  });

  it('submit is enabled when Other is selected and name is provided', async () => {
    const wrapper = mountControls();
    wrapper.vm.homeRoster = mockRoster;
    wrapper.vm.rostersLoaded = true;
    wrapper.vm.showCardModal = true;
    wrapper.vm.cardTeamId = baseMatchState.home_team_id;
    wrapper.vm.selectedCardType = 'yellow_card';
    wrapper.vm.cardPlayerId = 'other';
    wrapper.vm.cardPlayerName = 'Coach pick';
    await wrapper.vm.$nextTick();

    expect(
      wrapper.find('.submit-button').attributes('disabled')
    ).toBeUndefined();
  });

  it('emits post-card with playerName and playerId null when Other name typed', async () => {
    const wrapper = mountControls();
    wrapper.vm.homeRoster = mockRoster;
    wrapper.vm.rostersLoaded = true;
    wrapper.vm.showCardModal = true;
    wrapper.vm.cardTeamId = baseMatchState.home_team_id;
    wrapper.vm.selectedCardType = 'yellow_card';
    wrapper.vm.cardPlayerId = 'other';
    wrapper.vm.cardPlayerName = 'Sub 99';
    await wrapper.vm.$nextTick();

    await wrapper.find('.submit-button').trigger('click');

    expect(wrapper.emitted('post-card')).toBeTruthy();
    const [payload] = wrapper.emitted('post-card')[0];
    expect(payload.playerId).toBeNull();
    expect(payload.playerName).toBe('Sub 99');
    expect(payload.cardType).toBe('yellow_card');
  });
});
