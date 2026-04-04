-- Drop FreeRADIUS tables — iron-claw RADIUS scraper has been decommissioned.
-- These tables were added in 20260215000000_add_radius_tables.sql and are
-- no longer used.

DROP TABLE IF EXISTS public.radpostauth;
DROP TABLE IF EXISTS public.radacct;
DROP TABLE IF EXISTS public.radgroupreply;
DROP TABLE IF EXISTS public.radgroupcheck;
DROP TABLE IF EXISTS public.radusergroup;
DROP TABLE IF EXISTS public.radreply;
DROP TABLE IF EXISTS public.radcheck;
