-- Add team-game type mapping to support different team participation contexts
-- This allows teams to participate in specific game types (League, Tournament, Friendly, etc.)

-- Create team_game_types mapping table
CREATE TABLE team_game_types (
    id SERIAL PRIMARY KEY,
    team_id INTEGER REFERENCES teams(id) ON DELETE CASCADE,
    game_type_id INTEGER REFERENCES game_types(id) ON DELETE CASCADE,
    age_group_id INTEGER REFERENCES age_groups(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, game_type_id, age_group_id)
);

-- Create indexes for performance
CREATE INDEX idx_team_game_types_team ON team_game_types(team_id);
CREATE INDEX idx_team_game_types_game_type ON team_game_types(game_type_id);
CREATE INDEX idx_team_game_types_age_group ON team_game_types(age_group_id);
CREATE INDEX idx_team_game_types_active ON team_game_types(is_active);

-- Populate existing league teams with League game type participation
-- This ensures all current teams can participate in League games
INSERT INTO team_game_types (team_id, game_type_id, age_group_id, is_active)
SELECT 
    tm.team_id,
    gt.id as game_type_id,
    tm.age_group_id,
    true as is_active
FROM team_mappings tm
CROSS JOIN game_types gt
WHERE gt.name = 'League'
AND tm.team_id IS NOT NULL
AND tm.age_group_id IS NOT NULL;

-- Also make existing league teams available for Friendly games
-- This allows league teams to play friendlies as well
INSERT INTO team_game_types (team_id, game_type_id, age_group_id, is_active)
SELECT 
    tm.team_id,
    gt.id as game_type_id,
    tm.age_group_id,
    true as is_active
FROM team_mappings tm
CROSS JOIN game_types gt
WHERE gt.name = 'Friendly'
AND tm.team_id IS NOT NULL
AND tm.age_group_id IS NOT NULL;

-- Also make existing league teams available for Tournament games
-- This allows league teams to participate in tournaments
INSERT INTO team_game_types (team_id, game_type_id, age_group_id, is_active)
SELECT 
    tm.team_id,
    gt.id as game_type_id,
    tm.age_group_id,
    true as is_active
FROM team_mappings tm
CROSS JOIN game_types gt
WHERE gt.name = 'Tournament'
AND tm.team_id IS NOT NULL
AND tm.age_group_id IS NOT NULL;

-- Also make existing league teams available for Playoff games
INSERT INTO team_game_types (team_id, game_type_id, age_group_id, is_active)
SELECT 
    tm.team_id,
    gt.id as game_type_id,
    tm.age_group_id,
    true as is_active
FROM team_mappings tm
CROSS JOIN game_types gt
WHERE gt.name = 'Playoff'
AND tm.team_id IS NOT NULL
AND tm.age_group_id IS NOT NULL;