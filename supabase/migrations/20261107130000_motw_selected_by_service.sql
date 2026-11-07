-- SB-1553: record which service account picked the Match of the Week.
--
-- The MOTW agent writes through a service-account JWT (permission manage_motw),
-- which has no user_profiles row, so `selected_by` (a user uuid) cannot name it.
-- Every write sets both columns: an admin pick clears this, an agent pick leaves
-- selected_by NULL.

ALTER TABLE public.match_of_the_week
    ADD COLUMN IF NOT EXISTS selected_by_service text;

COMMENT ON COLUMN public.match_of_the_week.selected_by_service IS
    'Service account that made the pick (e.g. motw-agent), when not a person. NULL for a pick made by an admin.';
