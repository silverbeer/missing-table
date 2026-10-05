-- SB-1247: match_events and match_lineups were writable by any signed-in user.
--
-- Their INSERT/UPDATE policies were `WITH CHECK (true)` / `USING (true)` for all
-- roles, and `authenticated` held INSERT/UPDATE/DELETE/TRUNCATE grants. Because the
-- API login token is the user's Supabase JWT, any MT account (fans included) could
-- call PostgREST directly and insert fake goals/cards/chat or edit any event or
-- lineup, bypassing the API's permission checks.
--
-- The backend writes these tables with the service key (bypasses RLS) and no client
-- writes them directly, so clients need read access only. SELECT policies and the
-- supabase_realtime publication are untouched, so web Realtime keeps working.

DROP POLICY IF EXISTS match_events_insert_policy ON public.match_events;
DROP POLICY IF EXISTS match_events_update_policy ON public.match_events;
DROP POLICY IF EXISTS match_lineups_insert_policy ON public.match_lineups;
DROP POLICY IF EXISTS match_lineups_update_policy ON public.match_lineups;

REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.match_events FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.match_lineups FROM anon, authenticated;
