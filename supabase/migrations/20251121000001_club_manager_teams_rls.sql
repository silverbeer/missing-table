-- Migration: Add RLS policies for club managers to manage teams
-- This allows club managers to create and update teams within their assigned club

-- Drop the existing admin-only policy for teams
DROP POLICY IF EXISTS teams_admin_all ON teams;

-- Create new policies that allow club managers to manage teams in their club

-- INSERT policy: admins can insert any team, club_managers only their club
CREATE POLICY teams_insert_policy ON teams FOR INSERT
WITH CHECK (
    -- Admins can insert any team
    EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'admin')
    OR
    -- Club managers can only insert teams into their club
    (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'club_manager')
     AND club_id = (SELECT club_id FROM user_profiles WHERE id = auth.uid()))
);

-- UPDATE policy: admins can update any team, club_managers only their club's teams
CREATE POLICY teams_update_policy ON teams FOR UPDATE
USING (
    EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'admin')
    OR
    (EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'club_manager')
     AND club_id = (SELECT club_id FROM user_profiles WHERE id = auth.uid()))
);

-- DELETE policy: only admins can delete teams
CREATE POLICY teams_delete_policy ON teams FOR DELETE
USING (
    EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND role = 'admin')
);
