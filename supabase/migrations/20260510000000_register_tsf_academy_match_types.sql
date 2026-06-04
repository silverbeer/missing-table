-- Register TSF Academy (id=35, HG Northeast) for Friendly + Tournament
-- across U13, U14, U15, U16. Team had zero rows in team_match_types
-- so it was invisible in age-group filtered views.
--
-- Sync the id sequence first in case prior data loads inserted rows with
-- explicit ids (sequence can lag behind max(id) and cause silent PK
-- conflicts swallowed by ON CONFLICT). pg_get_serial_sequence is used so
-- the migration works regardless of whether the sequence is named
-- team_match_types_id_seq (new) or team_game_types_id_seq (legacy).
SELECT setval(
  pg_get_serial_sequence('team_match_types', 'id'),
  GREATEST((SELECT COALESCE(MAX(id), 1) FROM team_match_types), 1)
);

INSERT INTO team_match_types (team_id, age_group_id, match_type_id, is_active)
SELECT 35, ag.id, mt.id, true
FROM age_groups ag
CROSS JOIN match_types mt
WHERE ag.name IN ('U13','U14','U15','U16')
  AND mt.name IN ('Friendly','Tournament')
ON CONFLICT (team_id, match_type_id, age_group_id) DO NOTHING;
