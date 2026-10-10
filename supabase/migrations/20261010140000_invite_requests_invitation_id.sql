-- SB-1312: link an invite request to the invitation created from it.
--
-- Purely additive. An admin can create an invitation straight from a request;
-- the request then records which invitation answered it. Existing rows were
-- answered (if at all) by an invitation nobody linked, so they stay NULL.
-- Deleting the invitation keeps the request and just drops the link.

ALTER TABLE public.invite_requests
    ADD COLUMN IF NOT EXISTS invitation_id uuid
        REFERENCES public.invitations(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_invite_requests_invitation_id
    ON public.invite_requests (invitation_id);

COMMENT ON COLUMN public.invite_requests.invitation_id IS
    'Invitation an admin created from this request (SB-1312). NULL = not linked.';
