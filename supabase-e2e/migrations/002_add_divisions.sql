-- Add divisions table and update schema for age-group specific divisions

-- Create divisions table
CREATE TABLE divisions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add division_id to team_mappings table (age-group specific divisions)
ALTER TABLE team_mappings 
ADD COLUMN division_id INTEGER REFERENCES divisions(id);

-- Create index for performance
CREATE INDEX idx_team_mappings_division ON team_mappings(division_id);

-- Insert initial division data
INSERT INTO divisions (name, description) VALUES 
    ('Northeast', 'Northeast Division'),
    ('Southeast', 'Southeast Division'),
    ('Central', 'Central Division'),
    ('Southwest', 'Southwest Division'),
    ('Northwest', 'Northwest Division'),
    ('Pacific', 'Pacific Division');

-- Update existing team_mappings records to Northeast division
-- Since all current teams are U13 and in Northeast division
UPDATE team_mappings 
SET division_id = (SELECT id FROM divisions WHERE name = 'Northeast')
WHERE age_group_id = (SELECT id FROM age_groups WHERE name = 'U13');

-- Optionally, add division_id to games table for easier querying
-- This denormalizes the data slightly but improves query performance
ALTER TABLE games 
ADD COLUMN division_id INTEGER REFERENCES divisions(id);

-- Create index for games division
CREATE INDEX idx_games_division ON games(division_id);

-- Update existing games with division information
-- This assumes games inherit division from home team's age group
UPDATE games g
SET division_id = tm.division_id
FROM team_mappings tm
WHERE g.home_team_id = tm.team_id 
  AND g.age_group_id = tm.age_group_id
  AND tm.division_id IS NOT NULL;