-- Seed data for teams
-- This creates sample teams for each age group and division combination

-- First, let's create some teams
-- Note: Adjust the age_group_id and division_id based on your actual IDs

DO $$
DECLARE
    age_group RECORD;
    division RECORD;
    team_counter INT := 1;
BEGIN
    -- Loop through all age groups
    FOR age_group IN SELECT id, name FROM age_groups LOOP
        -- Loop through all divisions
        FOR division IN SELECT id, name FROM divisions LOOP
            -- Create 2 teams for each age group/division combination
            FOR i IN 1..2 LOOP
                INSERT INTO teams (name, age_group_id, division_id, abbreviation, academy_team)
                VALUES (
                    'Team ' || division.name || ' ' || age_group.name || ' ' || i,
                    age_group.id,
                    division.id,
                    'T' || LEFT(division.name, 2) || LEFT(age_group.name, 3) || i,
                    false
                );
                team_counter := team_counter + 1;
            END LOOP;
        END LOOP;
    END LOOP;
    
    RAISE NOTICE 'Created % teams', team_counter - 1;
END $$;

-- Create a few specific teams with real-looking names
INSERT INTO teams (name, age_group_id, division_id, abbreviation, academy_team)
SELECT 
    'FC United ' || ag.name,
    ag.id,
    d.id,
    'FCU' || RIGHT(ag.name, 2),
    true
FROM age_groups ag
CROSS JOIN divisions d
WHERE ag.name IN ('U15', 'U16', 'U17')
AND d.name = 'Northeast'
ON CONFLICT DO NOTHING;

INSERT INTO teams (name, age_group_id, division_id, abbreviation, academy_team)
SELECT 
    'City Soccer ' || ag.name,
    ag.id,
    d.id,
    'CS' || RIGHT(ag.name, 2),
    false
FROM age_groups ag
CROSS JOIN divisions d
WHERE ag.name IN ('U13', 'U14', 'U15')
AND d.name = 'Central'
ON CONFLICT DO NOTHING;