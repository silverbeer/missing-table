/**
 * LiveAdminControls — half-time countdown + backdated 2nd-half start (SB-1353).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount } from '@vue/test-utils';
import LiveAdminControls from '@/components/live/LiveAdminControls.vue';

vi.mock('@/components/live/LineupManager.vue', () => ({
  default: { template: '<div />' },
}));

const HT = '2026-10-19T15:00:00.000Z';
const at = (min, sec = 0) => Date.parse(HT) + (min * 60 + sec) * 1000;

const mountAt = (minutes, seconds = 0, halftimeStart = HT) => {
  vi.setSystemTime(at(minutes, seconds));
  return mount(LiveAdminControls, {
    props: {
      matchState: {
        home_team_id: 1,
        away_team_id: 2,
        home_team_name: 'Home FC',
        away_team_name: 'Away FC',
        half_duration: 45,
        halftime_start: halftimeStart,
      },
      matchPeriod: 'Halftime',
    },
  });
};

const countdown = w => w.find('[data-testid="halftime-countdown"]');
const startBtn = w => w.find('[data-testid="start-second-half"]');

describe('LiveAdminControls half-time countdown (SB-1353)', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('shows time left in the break and ticks every second', async () => {
    const w = mountAt(2, 18);
    expect(countdown(w).text()).toBe('Half time · 7:42 left');
    expect(countdown(w).classes()).not.toContain('overdue');
    expect(startBtn(w).classes()).toContain('start');

    await vi.advanceTimersByTimeAsync(1000);
    expect(countdown(w).text()).toBe('Half time · 7:41 left');
  });

  it('turns red once the break is overdue', () => {
    const w = mountAt(12, 15);
    expect(countdown(w).text()).toBe('2nd half overdue · +2:15');
    expect(countdown(w).classes()).toContain('overdue');
    expect(startBtn(w).classes()).toContain('overdue');
  });

  it('shows no countdown without a halftime_start', () => {
    const w = mountAt(3, 0, null);
    expect(countdown(w).exists()).toBe(false);
  });

  it('starts the 2nd half immediately when not overdue', async () => {
    const w = mountAt(5);
    await startBtn(w).trigger('click');
    expect(w.find('[data-testid="second-half-modal"]').exists()).toBe(false);
    expect(w.emitted('update-clock')[0]).toEqual(['start_second_half']);
  });

  it('starts immediately when overdue by under a minute', async () => {
    const w = mountAt(10, 30);
    await startBtn(w).trigger('click');
    expect(w.find('[data-testid="second-half-modal"]').exists()).toBe(false);
    expect(w.emitted('update-clock')[0]).toEqual(['start_second_half']);
  });

  it('offers a backdated start when overdue', async () => {
    const w = mountAt(14);
    await startBtn(w).trigger('click');
    const modal = w.find('[data-testid="second-half-modal"]');
    expect(modal.exists()).toBe(true);
    expect(modal.text()).toContain('Start the 2nd half');
    expect(modal.text()).toContain('The 10-minute break ended at');
    expect(w.emitted('update-clock')).toBeUndefined();

    await w.find('[data-testid="second-half-at-break-end"]').trigger('click');
    expect(w.emitted('update-clock')[0]).toEqual([
      { action: 'start_second_half', occurred_at: '2026-10-19T15:10:00.000Z' },
    ]);
    expect(w.find('[data-testid="second-half-modal"]').exists()).toBe(false);
  });

  it('"Just now" sends a plain start', async () => {
    const w = mountAt(14);
    await startBtn(w).trigger('click');
    await w.find('[data-testid="second-half-now"]').trigger('click');
    expect(w.emitted('update-clock')[0]).toEqual(['start_second_half']);
  });

  it('Cancel closes the modal without emitting', async () => {
    const w = mountAt(14);
    await startBtn(w).trigger('click');
    await w
      .find('[data-testid="second-half-modal"] .cancel-button')
      .trigger('click');
    expect(w.find('[data-testid="second-half-modal"]').exists()).toBe(false);
    expect(w.emitted('update-clock')).toBeUndefined();
  });
});
