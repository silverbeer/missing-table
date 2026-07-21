-- Position taxonomy migration (SB-284)
--
-- The position vocabulary changed from a flat 4-3-3-shaped list to a grouped
-- taxonomy (GK/DEF/MID/FWD -> specific codes). Side-specific codes are
-- retired for player positions: LCB/RCB -> CB, LCM/RCM -> CM.
--
-- Data-only migration: player positions stay text[] (ordered, first entry =
-- primary). Code validation lives in the backend (Pydantic), not a CHECK
-- constraint, so future taxonomy tweaks don't need DDL.
--
-- match_lineups.positions is intentionally untouched: those are formation
-- SLOT codes (LCB there is correct).

-- 1. players.positions: remap legacy codes, dedupe preserving order
--    (first occurrence wins, e.g. [LCB, RCB] -> [CB]).
WITH remapped AS (
    SELECT
        p.id,
        (
            SELECT array_agg(code ORDER BY first_ord)
            FROM (
                SELECT
                    CASE u.code
                        WHEN 'LCB' THEN 'CB'
                        WHEN 'RCB' THEN 'CB'
                        WHEN 'LCM' THEN 'CM'
                        WHEN 'RCM' THEN 'CM'
                        ELSE u.code
                    END AS code,
                    min(u.ord) AS first_ord
                FROM unnest(p.positions) WITH ORDINALITY AS u(code, ord)
                GROUP BY 1
            ) dedup
        ) AS new_positions
    FROM players p
    WHERE p.positions && ARRAY['LCB', 'RCB', 'LCM', 'RCM']
)
UPDATE players p
SET positions = r.new_positions
FROM remapped r
WHERE p.id = r.id;

-- 2. player_team_history.positions: same remap.
WITH remapped AS (
    SELECT
        h.id,
        (
            SELECT array_agg(code ORDER BY first_ord)
            FROM (
                SELECT
                    CASE u.code
                        WHEN 'LCB' THEN 'CB'
                        WHEN 'RCB' THEN 'CB'
                        WHEN 'LCM' THEN 'CM'
                        WHEN 'RCM' THEN 'CM'
                        ELSE u.code
                    END AS code,
                    min(u.ord) AS first_ord
                FROM unnest(h.positions) WITH ORDINALITY AS u(code, ord)
                GROUP BY 1
            ) dedup
        ) AS new_positions
    FROM player_team_history h
    WHERE h.positions && ARRAY['LCB', 'RCB', 'LCM', 'RCM']
)
UPDATE player_team_history h
SET positions = r.new_positions
FROM remapped r
WHERE h.id = r.id;

-- 3. user_profiles.positions: same remap + dedupe as parts 1-2. The old
--    AdminPlayers checkbox UI could write multi-position arrays here (e.g.
--    ["LCB","RCB"]), so a bare string-replace would mint duplicates
--    (["CB","CB"]); remap through jsonb with first-occurrence dedupe.
--
--    Column type differs by environment (schema drift): jsonb in prod,
--    text (JSON string) in the local baseline. PL/pgSQL only plans the
--    branch it executes, so each branch can assume its column type.
DO $$
DECLARE
    col_type text;
BEGIN
    SELECT data_type INTO col_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'user_profiles'
      AND column_name = 'positions';

    IF col_type = 'jsonb' THEN
        UPDATE user_profiles up
        SET positions = (
            SELECT coalesce(jsonb_agg(code ORDER BY first_ord), '[]'::jsonb)
            FROM (
                SELECT
                    CASE u.code
                        WHEN 'LCB' THEN 'CB'
                        WHEN 'RCB' THEN 'CB'
                        WHEN 'LCM' THEN 'CM'
                        WHEN 'RCM' THEN 'CM'
                        ELSE u.code
                    END AS code,
                    min(u.ord) AS first_ord
                FROM jsonb_array_elements_text(up.positions) WITH ORDINALITY AS u(code, ord)
                GROUP BY 1
            ) dedup
        )
        WHERE jsonb_typeof(up.positions) = 'array'
          AND up.positions::text ~ '"(LCB|RCB|LCM|RCM)"';
    ELSE
        UPDATE user_profiles up
        SET positions = (
            SELECT coalesce(jsonb_agg(code ORDER BY first_ord), '[]'::jsonb)::text
            FROM (
                SELECT
                    CASE u.code
                        WHEN 'LCB' THEN 'CB'
                        WHEN 'RCB' THEN 'CB'
                        WHEN 'LCM' THEN 'CM'
                        WHEN 'RCM' THEN 'CM'
                        ELSE u.code
                    END AS code,
                    min(u.ord) AS first_ord
                FROM jsonb_array_elements_text(up.positions::jsonb) WITH ORDINALITY AS u(code, ord)
                GROUP BY 1
            ) dedup
        )
        WHERE up.positions ~ '"(LCB|RCB|LCM|RCM)"'
          AND up.positions ~ '^\s*\[';  -- only valid JSON arrays
    END IF;
END $$;
