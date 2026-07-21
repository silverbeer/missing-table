-- Lock down PostgREST-exposed functions (SB-293)
--
-- PostgreSQL grants EXECUTE on functions to PUBLIC by default, and PostgREST
-- exposes every function in the public schema at /rest/v1/rpc/<name>. Four
-- functions were therefore callable by any anon/authenticated client:
--
--   promote_to_admin(email)         SECURITY DEFINER - one HTTP call sets
--                                   role='admin' for any account. Critical
--                                   privilege escalation (prod-only legacy
--                                   function).
--   create_player_history_entry()   SECURITY DEFINER - writes arbitrary
--                                   position codes / roster history rows,
--                                   bypassing all backend validation
--                                   (live-verified during the SB-284 review).
--   add_schema_version()            SECURITY DEFINER - writes migration
--                                   bookkeeping.
--   reset_all_sequences()           maintenance helper; no client caller.
--
-- Read-only helpers (is_admin, manages_team, get_club_teams, ...) and
-- trigger functions keep their grants - RLS policies and PostgREST reads
-- depend on them. The backend talks to the DB with the service role, which
-- keeps EXECUTE on everything.
--
-- Signatures are resolved from pg_proc (they differ between environments -
-- schema drift), so the lockdown covers every overload present.

DO $$
DECLARE
    fn regprocedure;
BEGIN
    FOR fn IN
        SELECT p.oid::regprocedure
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proname IN (
              'promote_to_admin',
              'create_player_history_entry',
              'add_schema_version',
              'reset_all_sequences'
          )
    LOOP
        EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC, anon, authenticated', fn);
        EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role', fn);
        RAISE NOTICE 'Locked down %', fn;
    END LOOP;
END $$;

-- promote_to_admin has no legitimate caller anywhere in the codebase
-- (admin promotion goes through manage_users.py with the service role).
-- Drop it entirely rather than leaving a locked footgun.
DROP FUNCTION IF EXISTS public.promote_to_admin(text);
