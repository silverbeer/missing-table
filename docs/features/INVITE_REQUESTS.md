# Invite Requests

Anyone can ask to join from the public "Request an invite" form
(`POST /api/invite-requests`). Admins review them under **Admin → Requests →
Invite Requests** (`AdminInviteRequests.vue`).

## Reviewing a request

A pending request has three actions.

| Action | What happens | Email the requester gets |
|--------|--------------|--------------------------|
| **Approve** | Opens **Invites** with the form pre-filled from the request (email, name as the note, iPhone beta if they asked). The admin picks the invite type and club/team and creates the invite. Creating it sends `invite_request_id`, which marks the request `approved` and links it (`invitation_id`). | The invitation, with its code (plus TestFlight steps for iPhone beta) |
| **Reject** | `PUT /api/invite-requests/{id}/status` → `rejected` | A short "not approved right now" note — once; rejecting an already-rejected request sends nothing |
| **Already a user** | `PUT /api/invite-requests/{id}/status` → `existing_user` (SB-1408). For a requester who already has an account — e.g. asking again to get the iPhone beta. Closes the request; no invite. Add them to TestFlight by hand. | None |

**There is no approval without an invitation** (SB-1392). The status endpoint
accepts only `pending`, `rejected` and `existing_user`; `approved` is set solely by creating the
invite. Before SB-1392, Approve only flipped the status and sent a "you're
approved" email with no code, which left the requester with no way in.

Approve still needs the admin: a request carries only free-text team ("IFA"),
and an invitation needs a real invite type and club/team.

**Don't link** on the pre-filled form creates the invite without approving the
request — it stays pending.

## After review

| Row | Actions |
|-----|---------|
| Approved, linked invite still pending | **Resend invite** — `POST /api/invites/admin/{invite_id}/resend-email` re-sends the same code |
| Approved, linked invite used/expired | none |
| Rejected or already a user | **Reset** to pending (no email) |

Rows approved before SB-1392 with no invite were repaired by migration
`20261023120000_invite_requests_backfill_approved.sql` (SB-1407): linked to the
hand-made invite for the same email if one existed, removed if a newer pending
request from the same email superseded it, otherwise reset to pending.

A linked request cannot be reset or rejected (`409`): its invitation exists.
Cancel the invitation from **Invites** instead.

**Send test rejection email** (header button,
`POST /api/invite-requests/test-rejection-email`) sends the rejection template
to any address, touching no request — preview it before a real Reject.

Email failures are logged and never fail the action; the row shows the linked
invite's code, status and TestFlight state.

## Code

- `backend/api/invite_requests.py` — submit, list, stats, reject/reset, test rejection email
- `backend/api/invites.py` — `_require_linkable_invite_request`, `_link_invite_request`, `resend-email`
- `backend/services/email_service.py` — `send_invitation`, `send_invite_request_rejection`
- `frontend/src/utils/inviteRequests.js` — request → invite-form prefill
- Tests: `backend/tests/unit/test_invite_request_review.py`, `test_invite_request_link.py`,
  `frontend/src/__tests__/components/InviteFromRequest.spec.js`
