/**
 * Manager roles page (SB-1799): explains both roles, never offers a way to
 * request one, closes on ✕ and backdrop, and is opened through the shared
 * composable that the user menu and the live-scoring hint use.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import ManagerRolesView from '@/components/ManagerRolesView.vue';
import { useManagerRolesPage } from '@/composables/useManagerRolesPage';

describe('ManagerRolesView', () => {
  it('describes the team manager and club manager roles', () => {
    const w = mount(ManagerRolesView);
    const team = w.get('[data-testid="role-team-manager"]').text();
    const club = w.get('[data-testid="role-club-manager"]').text();
    expect(team).toContain('Live score matches');
    expect(team).toContain('For one team');
    expect(club).toContain('For every team in one club');
    expect(w.get('[data-testid="role-how"]').text()).toContain('by invitation');
  });

  it('offers no request, apply or claim action', () => {
    const w = mount(ManagerRolesView);
    const buttons = w.findAll('button').map(b => b.text());
    expect(buttons).toEqual(['✕']);
    expect(w.findAll('a')).toHaveLength(0);
    expect(w.text()).not.toMatch(/request (a|the|to)|apply|claim/i);
  });

  it('says matches, never games', () => {
    expect(mount(ManagerRolesView).text()).not.toMatch(/\bgames?\b/i);
  });

  it('closes from the ✕ and from the backdrop', async () => {
    const w = mount(ManagerRolesView);
    await w.get('[data-testid="manager-roles-close"]').trigger('click');
    await w.get('[data-testid="manager-roles-overlay"]').trigger('click');
    expect(w.emitted('close')).toHaveLength(2);
  });
});

describe('useManagerRolesPage', () => {
  beforeEach(() => useManagerRolesPage().close());

  it('is one shared flag across callers', () => {
    const a = useManagerRolesPage();
    const b = useManagerRolesPage();
    a.open();
    expect(b.isOpen.value).toBe(true);
    b.close();
    expect(a.isOpen.value).toBe(false);
  });
});
