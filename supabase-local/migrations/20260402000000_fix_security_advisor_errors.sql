-- Fix 8 Supabase Security Advisor errors
--
-- 1. teams_with_league_badges view: set security_invoker=true so the view
--    respects the querying user's RLS policies, not the view creator's.
--
-- 2. FreeRADIUS tables (radcheck, radreply, radusergroup, radgroupcheck,
--    radgroupreply, radacct, radpostauth): enable RLS with no policies, so
--    PostgREST (anon/authenticated roles) cannot access them. FreeRADIUS
--    connects directly as the DB owner and bypasses RLS via service_role.

-- ============================================================================
-- Fix 1: teams_with_league_badges view — use SECURITY INVOKER
-- ============================================================================
ALTER VIEW public.teams_with_league_badges SET (security_invoker = true);


-- ============================================================================
-- Fix 2: Enable RLS on FreeRADIUS tables (deny PostgREST access)
-- ============================================================================
ALTER TABLE public.radcheck      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.radreply      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.radusergroup  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.radgroupcheck ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.radgroupreply ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.radacct       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.radpostauth   ENABLE ROW LEVEL SECURITY;

-- No policies added — RLS with zero policies = implicit deny for all roles
-- except service_role (which bypasses RLS by default in Supabase).
