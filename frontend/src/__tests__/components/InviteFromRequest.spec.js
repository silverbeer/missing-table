/**
 * Create an invite from an invite request (SB-1312).
 *
 * "Create invite" on a pending request opens the Invites section with the
 * form pre-filled (email, name in the note, iPhone beta); the created invite
 * carries invite_request_id so the backend links and approves the request.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ref } from 'vue';
import { mount, shallowMount, flushPromises } from '@vue/test-utils';
import AdminInvites from '@/components/admin/AdminInvites.vue';
import AdminInviteRequests from '@/components/admin/AdminInviteRequests.vue';
import AdminPanel from '@/components/AdminPanel.vue';
import {
  invitePrefillFromRequest,
  linkedInviteSummary,
} from '@/utils/inviteRequests';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

const REQUEST = {
  id: 'req-1',
  email: 'pat@example.com',
  name: 'Pat Fan',
  team: 'IFA U14',
  reason: null,
  wants_ios_beta: true,
  status: 'pending',
  invitation_id: null,
  invitation: null,
  created_at: '2026-10-10T00:00:00Z',
};

const jsonResponse = (body, ok = true) =>
  Promise.resolve({ ok, json: () => Promise.resolve(body) });

let posted;
const installFetch = (requests = [REQUEST]) => {
  posted = [];
  global.fetch = vi.fn((url, opts = {}) => {
    if (opts.method === 'POST') {
      posted.push({ url, body: JSON.parse(opts.body) });
      return jsonResponse({
        id: 'inv-1',
        invite_code: 'ABCDEFGHJKLM',
        invite_type: 'club_fan',
        club_id: 10,
        expires_at: '2026-10-17T00:00:00Z',
      });
    }
    if (url.endsWith('/api/clubs'))
      return jsonResponse([{ id: 10, name: 'IFA' }]);
    if (url.includes('/api/invite-requests/stats'))
      return jsonResponse({ total: 1, pending: 1 });
    if (url.includes('/api/invite-requests')) return jsonResponse(requests);
    return jsonResponse([]);
  });
};

beforeEach(() => {
  mockAuthStore = {
    userRole: ref('admin'),
    isAdmin: ref(true),
    isClubManager: ref(false),
    getAuthHeaders: () => ({ Authorization: 'Bearer t' }),
  };
  installFetch();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('invitePrefillFromRequest', () => {
  it('puts the email, the name (as the note) and the beta opt-in in the form', () => {
    expect(invitePrefillFromRequest(REQUEST)).toEqual({
      request: { id: 'req-1', name: 'Pat Fan', email: 'pat@example.com' },
      form: { email: 'pat@example.com', note: 'Pat Fan', iosBeta: true },
    });
  });

  it('leaves iPhone beta off when the requester did not ask', () => {
    const prefill = invitePrefillFromRequest({
      ...REQUEST,
      wants_ios_beta: false,
    });
    expect(prefill.form.iosBeta).toBe(false);
  });

  it('summarises a linked invite', () => {
    expect(
      linkedInviteSummary({
        invite_code: 'ABCDEFGHJKLM',
        invite_type: 'club_fan',
        status: 'pending',
      })
    ).toBe('ABCDEFGHJKLM · Club Fan · pending');
  });
});

describe('AdminInvites with a request prefill', () => {
  const mountPrefilled = async () => {
    const wrapper = mount(AdminInvites, {
      props: { prefill: invitePrefillFromRequest(REQUEST) },
    });
    await flushPromises();
    return wrapper;
  };

  it('opens the form pre-filled and says which request it answers', async () => {
    const wrapper = await mountPrefilled();

    expect(
      wrapper.find('[data-testid="invite-email-input"]').element.value
    ).toBe('pat@example.com');
    expect(
      wrapper.find('[data-testid="invite-note-input"]').element.value
    ).toBe('Pat Fan');
    expect(
      wrapper.find('[data-testid="invite-ios-beta-checkbox"]').element.checked
    ).toBe(true);
    expect(
      wrapper.find('[data-testid="invite-from-request-banner"]').text()
    ).toContain('Pat Fan');
    // The admin still picks the type and club/team.
    expect(
      wrapper.find('[data-testid="invite-type-select"]').element.value
    ).toBe('');
  });

  it('sends invite_request_id with the invite, then drops the link', async () => {
    const wrapper = await mountPrefilled();
    await wrapper
      .find('[data-testid="invite-type-select"]')
      .setValue('club_fan');
    await wrapper
      .findAll('[data-testid="invite-club-select"] option')[1]
      .setSelected();
    await wrapper.find('[data-testid="create-invite-form"]').trigger('submit');
    await flushPromises();

    expect(posted).toHaveLength(1);
    expect(posted[0].url).toContain('/api/invites/admin/club-fan');
    expect(posted[0].body).toMatchObject({
      club_id: 10,
      email: 'pat@example.com',
      note: 'Pat Fan',
      ios_beta: true,
      invite_request_id: 'req-1',
    });
    expect(wrapper.emitted('prefill-done')).toHaveLength(1);
    expect(
      wrapper.find('[data-testid="invite-from-request-banner"]').exists()
    ).toBe(false);
  });

  it("Don't link keeps the fields but sends no invite_request_id", async () => {
    const wrapper = await mountPrefilled();
    await wrapper
      .find('[data-testid="invite-from-request-unlink"]')
      .trigger('click');
    await wrapper
      .find('[data-testid="invite-type-select"]')
      .setValue('club_fan');
    await wrapper
      .findAll('[data-testid="invite-club-select"] option')[1]
      .setSelected();
    await wrapper.find('[data-testid="create-invite-form"]').trigger('submit');
    await flushPromises();

    expect(posted[0].body.email).toBe('pat@example.com');
    expect(posted[0].body).not.toHaveProperty('invite_request_id');
  });

  it('without a prefill the form is empty and nothing is linked', async () => {
    const wrapper = mount(AdminInvites);
    await flushPromises();

    expect(
      wrapper.find('[data-testid="invite-from-request-banner"]').exists()
    ).toBe(false);
    expect(
      wrapper.find('[data-testid="invite-email-input"]').element.value
    ).toBe('');
  });
});

describe('AdminInviteRequests', () => {
  it('offers Create invite on a pending request and emits it', async () => {
    const wrapper = mount(AdminInviteRequests);
    await flushPromises();

    await wrapper
      .find('[data-testid="create-invite-from-request"]')
      .trigger('click');
    expect(wrapper.emitted('create-invite')[0][0].id).toBe('req-1');
  });

  it('shows the linked invite and its TestFlight status', async () => {
    installFetch([
      {
        ...REQUEST,
        status: 'approved',
        invitation_id: 'inv-1',
        invitation: {
          id: 'inv-1',
          invite_code: 'ABCDEFGHJKLM',
          invite_type: 'club_fan',
          status: 'pending',
          testflight_status: 'failed',
          testflight_error: 'HTTP 403',
        },
      },
    ]);
    const wrapper = mount(AdminInviteRequests);
    await flushPromises();

    const linked = wrapper.find('[data-testid="linked-invite"]');
    expect(linked.text()).toContain('ABCDEFGHJKLM · Club Fan · pending');
    expect(linked.text()).toContain('TestFlight: failed');
    expect(
      wrapper.find('[data-testid="create-invite-from-request"]').exists()
    ).toBe(false);
  });
});

describe('AdminPanel', () => {
  it('switches to Invites with the prefill, and drops it on leaving', async () => {
    const wrapper = shallowMount(AdminPanel);
    wrapper
      .findComponent(AdminInviteRequests)
      .vm.$emit('create-invite', REQUEST);
    await flushPromises();

    const invites = wrapper.findComponent(AdminInvites);
    expect(invites.exists()).toBe(true);
    expect(invites.props('prefill')).toEqual(invitePrefillFromRequest(REQUEST));

    await wrapper
      .find('[data-testid="admin-section-select"]')
      .setValue('invite-requests');
    await wrapper
      .find('[data-testid="admin-section-select"]')
      .setValue('invites');
    expect(wrapper.findComponent(AdminInvites).props('prefill')).toBeNull();
  });
});
