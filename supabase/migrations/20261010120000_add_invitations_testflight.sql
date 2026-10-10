-- TestFlight beta on invitations (SB-1314)
--
-- An admin can mark an invite "iPhone beta": the backend adds the invitee to
-- the external TestFlight group through the App Store Connect API. The
-- outcome is recorded here, never on the invite's own status — a TestFlight
-- failure must not fail the invite, and the admin UI offers a retry.
--
-- testflight_status NULL means TestFlight was not requested.

ALTER TABLE public.invitations
    ADD COLUMN IF NOT EXISTS testflight_email character varying(255),
    ADD COLUMN IF NOT EXISTS testflight_status character varying(20),
    ADD COLUMN IF NOT EXISTS testflight_error text,
    ADD COLUMN IF NOT EXISTS testflight_tester_id character varying(64);

ALTER TABLE public.invitations
    DROP CONSTRAINT IF EXISTS invitations_testflight_status_check;

ALTER TABLE public.invitations
    ADD CONSTRAINT invitations_testflight_status_check CHECK (
        testflight_status IS NULL
        OR testflight_status IN ('pending', 'added', 'failed', 'removed')
    );

COMMENT ON COLUMN public.invitations.testflight_email IS
    'Apple Account email to add as a TestFlight external tester; often differs from the invite email.';
COMMENT ON COLUMN public.invitations.testflight_status IS
    'TestFlight beta outcome: pending|added|failed|removed. NULL = not requested.';
COMMENT ON COLUMN public.invitations.testflight_error IS
    'Last App Store Connect error for this invite, for the admin retry.';
COMMENT ON COLUMN public.invitations.testflight_tester_id IS
    'App Store Connect betaTesters id, used to remove the tester when the user is deleted.';
