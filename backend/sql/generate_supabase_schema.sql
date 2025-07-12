-- ===============================================
-- Supabase Schema for Sports League Application
-- ===============================================
-- 
-- Instructions:
-- 1. Create a new Supabase project at https://supabase.com/dashboard
-- 2. Go to SQL Editor in your new project
-- 3. Copy and paste this entire SQL script
-- 4. Click "Run" to create all tables and indexes
--
-- This will create a clean schema ready for data migration
-- ===============================================

-- Drop existing tables if doing a clean migration
DROP TABLE IF EXISTS games CASCADE;
DROP TABLE IF EXISTS team_mappings CASCADE;
DROP TABLE IF EXISTS teams CASCADE;
DROP TABLE IF EXISTS game_types CASCADE;
DROP TABLE IF EXISTS seasons CASCADE;
DROP TABLE IF EXISTS age_groups CASCADE;

-- ===============================================
-- Reference Tables
-- ===============================================

-- Age Groups (U13, U14, etc.)
CREATE TABLE age_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seasons (2024-2025, etc.)
CREATE TABLE seasons (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Game Types (League, Tournament, etc.)
CREATE TABLE game_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ===============================================
-- Core Tables
-- ===============================================

-- Teams
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    city VARCHAR(100) DEFAULT 'Unknown City',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Team Mappings (many-to-many relationships for teams)
CREATE TABLE team_mappings (
    id SERIAL PRIMARY KEY,
    team_id INTEGER REFERENCES teams(id) ON DELETE CASCADE,
    age_group_id INTEGER REFERENCES age_groups(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, age_group_id)
);

-- Games
CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team_id INTEGER REFERENCES teams(id),
    away_team_id INTEGER REFERENCES teams(id),
    home_score INTEGER DEFAULT 0,
    away_score INTEGER DEFAULT 0,
    season_id INTEGER REFERENCES seasons(id),
    age_group_id INTEGER REFERENCES age_groups(id),
    game_type_id INTEGER REFERENCES game_types(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT different_teams CHECK (home_team_id != away_team_id)
);

-- ===============================================
-- Indexes for Performance
-- ===============================================

CREATE INDEX idx_games_date ON games(game_date);
CREATE INDEX idx_games_home_team ON games(home_team_id);
CREATE INDEX idx_games_away_team ON games(away_team_id);
CREATE INDEX idx_games_season ON games(season_id);
CREATE INDEX idx_games_age_group ON games(age_group_id);
CREATE INDEX idx_team_mappings_team ON team_mappings(team_id);
CREATE INDEX idx_team_mappings_age_group ON team_mappings(age_group_id);

-- ===============================================
-- Enable Row Level Security (RLS)
-- ===============================================

ALTER TABLE age_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE seasons ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE games ENABLE ROW LEVEL SECURITY;

-- Create policies for service role (full access)
CREATE POLICY "Service role has full access to age_groups" ON age_groups FOR ALL USING (true);
CREATE POLICY "Service role has full access to seasons" ON seasons FOR ALL USING (true);
CREATE POLICY "Service role has full access to game_types" ON game_types FOR ALL USING (true);
CREATE POLICY "Service role has full access to teams" ON teams FOR ALL USING (true);
CREATE POLICY "Service role has full access to team_mappings" ON team_mappings FOR ALL USING (true);
CREATE POLICY "Service role has full access to games" ON games FOR ALL USING (true);

-- ===============================================
-- Success Message
-- ===============================================
-- Schema created successfully!
-- Next steps:
-- 1. Copy your project URL and service key from Settings > API
-- 2. Update your .env file with the new credentials
-- 3. Run: python migrate_to_new_supabase.py