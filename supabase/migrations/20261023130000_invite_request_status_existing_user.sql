-- SB-1408: close an invite request from someone who already has an account.
--
-- Repeat requests (an existing user asking for the iPhone beta, say) had no
-- correct exit: Reject emails a "can't approve right now" note and Approve
-- mints a second invite. 'existing_user' closes the request with no email and
-- no invitation, and keeps the row. Additive.

ALTER TYPE public.invite_request_status ADD VALUE IF NOT EXISTS 'existing_user';

COMMENT ON COLUMN public.invite_requests.status IS
    'Request status: pending, approved (has invitation_id), rejected, or existing_user (requester already has an account; closed without email)';
