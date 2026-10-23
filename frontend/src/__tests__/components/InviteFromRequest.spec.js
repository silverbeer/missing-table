/**
 * Create an invite from an invite request (SB-1312).
 *
 * "Approve" on a pending request opens the Invites section with the form
 * pre-filled (email, name in the note, iPhone beta); the created invite
 * carries invite_request_id so the backend links and approves the request.
 * Approving has no other path (SB-1392); Reject emails the requester.
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
let put;
const installFetch = (requests = [REQUEST]) => {
  posted = [];
  put = [];
  global.fetch = vi.fn((url, opts = {}) => {
    if (opts.method === 'PUT') {
      put.push({ url, body: JSON.parse(opts.body) });
      return jsonResponse({ success: true });
    }
    if (opts.method === 'POST' && url.includes('/resend-email')) {
      posted.push({ url });
      return jsonResponse({ success: true });
    }
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

const LINKED = {
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
};

const mountRequests = async requests => {
  installFetch(requests);
  const wrapper = mount(AdminInviteRequests);
  await flushPromises();
  return wrapper;
};

const has = (wrapper, testid) =>
  wrapper.find(`[data-testid="${testid}"]`).exists();

describe('AdminInviteRequests', () => {
  beforeEach(() => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.spyOn(window, 'alert').mockImplementation(() => {});
  });

  it('offers only Approve and Reject on a pending request', async () => {
    const wrapper = await mountRequests([REQUEST]);

    const actions = wrapper.findAll('tbody button').map(b => b.text());
    expect(actions).toEqual(['Approve', 'Reject']);
    expect(wrapper.text()).not.toContain('test approval email');
  });

  it('Approve emits the request without changing its status', async () => {
    const wrapper = await mountRequests([REQUEST]);

    await wrapper.find('[data-testid="approve-request"]').trigger('click');
    expect(wrapper.emitted('approve')[0][0].id).toBe('req-1');
    expect(put).toHaveLength(0);
  });

  it('Reject sets the request rejected', async () => {
    const wrapper = await mountRequests([REQUEST]);

    await wrapper.find('[data-testid="reject-request"]').trigger('click');
    await flushPromises();
    expect(window.confirm.mock.calls[0][0]).toContain('pat@example.com');
    expect(put).toEqual([
      {
        url: 'http://localhost:8000/api/invite-requests/req-1/status',
        body: { status: 'rejected' },
      },
    ]);
  });

  it('an approved request resends its invite, and cannot be reset', async () => {
    const wrapper = await mountRequests([LINKED]);

    expect(has(wrapper, 'reset-request')).toBe(false);
    await wrapper.find('[data-testid="resend-invite"]').trigger('click');
    await flushPromises();
    expect(posted).toEqual([
      { url: 'http://localhost:8000/api/invites/admin/inv-1/resend-email' },
    ]);
  });

  it('no resend once the invite is used', async () => {
    const wrapper = await mountRequests([
      { ...LINKED, invitation: { ...LINKED.invitation, status: 'used' } },
    ]);

    expect(has(wrapper, 'resend-invite')).toBe(false);
  });

  it('a rejected request, or one approved before invites were required, can be reset', async () => {
    for (const status of ['rejected', 'approved']) {
      const wrapper = await mountRequests([{ ...REQUEST, status }]);

      expect(has(wrapper, 'reset-request')).toBe(true);
      expect(has(wrapper, 'resend-invite')).toBe(false);
      expect(has(wrapper, 'approve-request')).toBe(false);
    }
  });

  it('shows the linked invite and its TestFlight status', async () => {
    const wrapper = await mountRequests([LINKED]);

    const linked = wrapper.find('[data-testid="linked-invite"]');
    expect(linked.text()).toContain('ABCDEFGHJKLM · Club Fan · pending');
    expect(linked.text()).toContain('TestFlight: failed');
    expect(has(wrapper, 'approve-request')).toBe(false);
  });
});

describe('AdminPanel', () => {
  it('switches to Invites with the prefill, and drops it on leaving', async () => {
    const wrapper = shallowMount(AdminPanel);
    wrapper.findComponent(AdminInviteRequests).vm.$emit('approve', REQUEST);
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
