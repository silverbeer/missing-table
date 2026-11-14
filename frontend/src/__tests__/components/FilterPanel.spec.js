import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import FilterPanel from '@/components/ui/FilterPanel.vue';

const isOpen = w =>
  !(
    w.get('[data-testid="filter-panel-table-body"]').attributes('style') || ''
  ).includes('display: none');

const mountPanel = (props = {}) =>
  mount(FilterPanel, {
    props: { view: 'table', summary: '2026-2027 · U15 · Northeast', ...props },
    slots: { default: '<div data-testid="row">Age Groups</div>' },
  });

describe('FilterPanel (SB-1714)', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it('opens by default, showing the rows and not the summary', () => {
    const w = mountPanel();
    const toggle = w.get('[data-testid="filter-panel-table-toggle"]');
    expect(toggle.attributes('aria-expanded')).toBe('true');
    expect(isOpen(w)).toBe(true);
    expect(w.find('[data-testid="filter-panel-table-summary"]').exists()).toBe(
      false
    );
  });

  it('collapses to the summary line and back', async () => {
    const w = mountPanel();
    const toggle = w.get('[data-testid="filter-panel-table-toggle"]');
    await toggle.trigger('click');
    expect(toggle.attributes('aria-expanded')).toBe('false');
    expect(isOpen(w)).toBe(false);
    expect(w.get('[data-testid="filter-panel-table-summary"]').text()).toBe(
      '2026-2027 · U15 · Northeast'
    );
    await toggle.trigger('click');
    expect(toggle.attributes('aria-expanded')).toBe('true');
  });

  it('remembers closed per view across mounts', async () => {
    const w = mountPanel();
    await w.get('[data-testid="filter-panel-table-toggle"]').trigger('click');
    w.unmount();

    const again = mountPanel();
    expect(
      again
        .get('[data-testid="filter-panel-table-toggle"]')
        .attributes('aria-expanded')
    ).toBe('false');

    const other = mountPanel({ view: 'matches' });
    expect(
      other
        .get('[data-testid="filter-panel-matches-toggle"]')
        .attributes('aria-expanded')
    ).toBe('true');
  });

  it('closed with nothing to summarise still says "Filters"', async () => {
    const w = mountPanel({ summary: '' });
    await w.get('[data-testid="filter-panel-table-toggle"]').trigger('click');
    expect(w.get('[data-testid="filter-panel-table-toggle"]').text()).toContain(
      'Filters'
    );
  });

  it('works when localStorage throws', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('private mode');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('private mode');
    });
    const w = mountPanel();
    const toggle = w.get('[data-testid="filter-panel-table-toggle"]');
    expect(toggle.attributes('aria-expanded')).toBe('true');
    await toggle.trigger('click');
    expect(toggle.attributes('aria-expanded')).toBe('false');
  });
});
