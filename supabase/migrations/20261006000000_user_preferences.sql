-- SB-1286: per-account user preferences.
--
-- One jsonb object rather than a column per preference: the backend
-- validates its shape (backend/user_preferences.py), so a new preference
-- is a model field and a UI control, not a migration. The trade-off is no
-- FK on ids inside it - readers must skip an id that no longer exists.
--
-- First key: default_age_group_id (int) - the age group Table and Matches
-- open on when this browser has no remembered pick.

ALTER TABLE public.user_profiles
    ADD COLUMN IF NOT EXISTS preferences jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.user_profiles
    ADD CONSTRAINT user_profiles_preferences_is_object
    CHECK (jsonb_typeof(preferences) = 'object');

COMMENT ON COLUMN public.user_profiles.preferences IS
    'Per-account UI preferences, shape validated by backend/user_preferences.py (SB-1286). Absent key = no preference.';
