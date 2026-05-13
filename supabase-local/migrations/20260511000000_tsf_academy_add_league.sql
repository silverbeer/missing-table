-- Add League match type for TSF Academy (id=35) across U13-U16.
-- Follow-up to 20260510000000 which registered Friendly + Tournament only.
SELECT setval(
  pg_get_serial_sequence('team_match_types', 'id'),
  GREATEST((SELECT COALESCE(MAX(id), 1) FROM team_match_types), 1)
);

INSERT INTO team_match_types (team_id, age_group_id, match_type_id, is_active)
SELECT 35, ag.id, mt.id, true
FROM age_groups ag
CROSS JOIN match_types mt
WHERE ag.name IN ('U13','U14','U15','U16')
  AND mt.name = 'League'
ON CONFLICT (team_id, match_type_id, age_group_id) DO NOTHING;
