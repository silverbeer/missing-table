-- SB-1311: "Get the iPhone beta" opt-in on the public Request Invite form.
--
-- Purely additive. Existing rows predate the checkbox, so they default to
-- false: nobody who asked before it existed asked for the beta.

ALTER TABLE public.invite_requests
    ADD COLUMN IF NOT EXISTS wants_ios_beta boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.invite_requests.wants_ios_beta IS
    'Requester ticked "Get the iPhone beta" on the Request Invite form (SB-1311).';
