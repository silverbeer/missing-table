-- SB-1715: remembered Table/Matches filters follow the user across devices.
--
-- Until now the filters lived only in the browser's localStorage
-- (useFilterMemory, SB-1112). This stores the same thing per account:
--
--   { "<view>": { "filters": {...} | null, "panel_open": bool, "saved_at": <ms> } }
--
-- A column of its own, not a key inside `preferences`: preferences are
-- explicit choices saved from the Profile page; this is remembered UI state
-- written every few seconds. Keeping them apart means neither write can
-- clobber the other.

ALTER TABLE public.user_profiles
    ADD COLUMN IF NOT EXISTS filter_memory jsonb;

COMMENT ON COLUMN public.user_profiles.filter_memory IS
    'Remembered Table/Matches filter state per view (SB-1715). NULL = nothing remembered.';

-- Merge one view's patch atomically. Table and Matches save independently,
-- and a read-modify-write in Python would let one drop the other.
CREATE OR REPLACE FUNCTION public.set_filter_memory(p_user_id uuid, p_view text, p_patch jsonb)
RETURNS void
LANGUAGE sql
SET search_path = public
AS $$
    UPDATE public.user_profiles
       SET filter_memory = COALESCE(filter_memory, '{}'::jsonb)
           || jsonb_build_object(
                p_view,
                COALESCE(filter_memory -> p_view, '{}'::jsonb) || p_patch
              )
     WHERE id = p_user_id;
$$;

REVOKE ALL ON FUNCTION public.set_filter_memory(uuid, text, jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.set_filter_memory(uuid, text, jsonb) TO service_role;
