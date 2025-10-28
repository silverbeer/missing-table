-- Supabase Database Schema
-- Based on existing SQLite structure from data_access.py
-- Run this in Supabase SQL Editor

-- Drop existing tables if they exist (for clean setup)
DROP TABLE IF EXISTS games CASCADE;
DROP TABLE IF EXISTS teams CASCADE;

-- Create teams table
CREATE TABLE teams (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    city TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create games table
CREATE TABLE games (
    id BIGSERIAL PRIMARY KEY,
    game_date DATE NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    home_score INTEGER NOT NULL,
    away_score INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Foreign key constraints (referencing team names)
    CONSTRAINT fk_home_team FOREIGN KEY (home_team) REFERENCES teams(name) ON UPDATE CASCADE,
    CONSTRAINT fk_away_team FOREIGN KEY (away_team) REFERENCES teams(name) ON UPDATE CASCADE
);

-- Create indexes for better performance
CREATE INDEX idx_games_home_team ON games(home_team);
CREATE INDEX idx_games_away_team ON games(away_team);
CREATE INDEX idx_games_date ON games(game_date);
CREATE INDEX idx_teams_name ON teams(name);

-- Enable Row Level Security (recommended for production)
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE games ENABLE ROW LEVEL SECURITY;

-- Create policies for read access
CREATE POLICY "Allow public read access to teams" ON teams FOR SELECT USING (true);
CREATE POLICY "Allow public read access to games" ON games FOR SELECT USING (true);

-- For development, also allow insert/update/delete (remove in production)
CREATE POLICY "Allow all operations on teams" ON teams FOR ALL USING (true);
CREATE POLICY "Allow all operations on games" ON games FOR ALL USING (true);

-- Verify tables were created
SELECT 'Teams table created' as status;
SELECT 'Games table created' as status;