-- SB-1131: make user_profiles.email unique, case-insensitively.
--
-- The baseline schema has always declared `user_profiles_email_key UNIQUE
-- (email)`, but production does not have it — verified against pg_constraint
-- and pg_indexes, which show only user_profiles_username_unique. So the
-- baseline and production disagreed about what is legal, and anything tested
-- against that constraint locally passed and then did not hold in prod.
--
-- Two accounts had already ended up sharing pytom13@gmail.com as a result. A
-- password reset for either one went to that single inbox, and
-- get_user_for_password_reset returns data[0], so which account a reset link
-- belonged to was decided by row order rather than by anything the person
-- asking had chosen. Both were test accounts and have been deleted.
--
-- lower(email) rather than email: addresses are case-insensitive in practice,
-- and SB-1130 normalises on write precisely so a reset can find an account
-- typed in any case. A plain UNIQUE(email) would still admit
-- 'Parent@example.com' alongside 'parent@example.com' — two rows the
-- application considers the same address. The functional index makes the
-- guarantee hold in the database, independent of every writer remembering to
-- normalise first.
--
-- Partial on email IS NOT NULL: most accounts have no address (MT keys on
-- username and synthesises one for Supabase Auth), and there is no reason to
-- index twenty-three nulls.

BEGIN;

-- Idempotent, and it removes the case-sensitive constraint wherever it does
-- exist — a local database built from the baseline has it, production never
-- did. Without this, local would carry both and diverge again.
ALTER TABLE public.user_profiles
    DROP CONSTRAINT IF EXISTS user_profiles_email_key;

CREATE UNIQUE INDEX IF NOT EXISTS user_profiles_email_lower_key
    ON public.user_profiles (lower(email))
    WHERE email IS NOT NULL;

COMMIT;
