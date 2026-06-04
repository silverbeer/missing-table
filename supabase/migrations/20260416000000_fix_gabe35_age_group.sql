-- Fix player_team_history for gabe35 (player_id: 4a4c4b2b-caf3-4ca2-b5f5-c1e3b414b61d)
--
-- Root cause: create_player_history_entry used limit(1) on team_mappings without ordering,
-- so for team_id=19 (IFA) which has mappings for U13/U14/U15/U16, it non-deterministically
-- picked U13 instead of U14. The IFA Academy entry (correct HG team) was also left with
-- is_current=false when it should be the primary current assignment.
--
-- Entry 28: IFA team, 2025-2026 — wrong age_group (U13), correct to U14
UPDATE player_team_history
SET age_group_id = 2  -- U14
WHERE id = 28
  AND player_id = '4a4c4b2b-caf3-4ca2-b5f5-c1e3b414b61d'
  AND age_group_id = 1;  -- safety check: only update if still U13

-- Entry 26: IFA Academy (HG Northeast), 2025-2026 — mark as current
UPDATE player_team_history
SET is_current = true
WHERE id = 26
  AND player_id = '4a4c4b2b-caf3-4ca2-b5f5-c1e3b414b61d';
