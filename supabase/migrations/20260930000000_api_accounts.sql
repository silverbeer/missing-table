-- API-only accounts (SB-1145).
--
-- An API account is a user_profiles row with no auth.users row behind it: it
-- has no password and can never log in to the web app. Its only credential is
-- a short-lived token minted by an admin script (backend/scripts/
-- manage_ai_users.py) whose audience is accepted on /api/ai/* and nowhere else.
--
-- The first two are the MT AI eval principals, ai-eval-real (is_test=false) and
-- ai-eval-test (is_test=true), so an eval run in prod can prove the test
-- partition is hidden without borrowing a human's (admin) session.
--
-- The flag is also how eval traffic is attributed and excluded from real-usage
-- numbers: ai_conversations.user_id → user_profiles.is_api_account.

ALTER TABLE public.user_profiles ADD COLUMN is_api_account boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.user_profiles.is_api_account IS
    'API-only principal: no login, token accepted on /api/ai/* only; excluded from real-usage numbers (SB-1145).';
