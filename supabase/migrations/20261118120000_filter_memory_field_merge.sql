-- SB-1722: merge remembered filters key by key, so each platform sends only
-- its own fields (docs/03-architecture/filter-memory-format.md).
--
-- Before: a patch's `filters` replaced the stored object whole. With web,
-- Android and iOS each owning different fields, that made every write drop
-- the others' — and a client copying fields from its last /me read would
-- overwrite a newer value set on another device with a stale one.
--
-- Now: when the patch's `filters` is an object it is merged into the stored
-- `filters` object; `filters: null` still clears it.

CREATE OR REPLACE FUNCTION public.set_filter_memory(p_user_id uuid, p_view text, p_patch jsonb)
RETURNS void
LANGUAGE sql
SET search_path = public
AS $$
    UPDATE public.user_profiles
       SET filter_memory = COALESCE(filter_memory, '{}'::jsonb)
           || jsonb_build_object(
                p_view,
                COALESCE(filter_memory -> p_view, '{}'::jsonb)
                || p_patch
                || CASE
                     WHEN jsonb_typeof(p_patch -> 'filters') = 'object' THEN
                       jsonb_build_object(
                         'filters',
                         CASE
                           WHEN jsonb_typeof(filter_memory -> p_view -> 'filters') = 'object'
                             THEN filter_memory -> p_view -> 'filters'
                           ELSE '{}'::jsonb
                         END
                         || (p_patch -> 'filters')
                       )
                     ELSE '{}'::jsonb
                   END
              )
     WHERE id = p_user_id;
$$;

REVOKE ALL ON FUNCTION public.set_filter_memory(uuid, text, jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.set_filter_memory(uuid, text, jsonb) TO service_role;
