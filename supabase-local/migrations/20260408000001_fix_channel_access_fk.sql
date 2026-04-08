-- Fix: change channel_access_requests.user_id FK from auth.users → user_profiles
--
-- PostgREST cannot resolve the user_profiles join when the FK points to
-- the auth schema. This enables the admin endpoint join:
--   user_profiles!channel_access_requests_user_id_fkey(display_name, email)
--
-- Safe to run whether the original migration used auth.users or user_profiles —
-- it drops the old constraint and re-adds with the correct target.
-- Cascade delete still works: auth.users deletion → user_profiles → channel_access_requests.

ALTER TABLE public.channel_access_requests
    DROP CONSTRAINT IF EXISTS channel_access_requests_user_id_fkey;

ALTER TABLE public.channel_access_requests
    ADD CONSTRAINT channel_access_requests_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES public.user_profiles(id) ON DELETE CASCADE;
