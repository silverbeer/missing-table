-- Create the sports league database schema

-- Age Groups
CREATE TABLE age_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seasons
CREATE TABLE seasons (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Game Types
CREATE TABLE game_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

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

-- Create indexes for performance
CREATE INDEX idx_games_date ON games(game_date);
CREATE INDEX idx_games_home_team ON games(home_team_id);
CREATE INDEX idx_games_away_team ON games(away_team_id);
CREATE INDEX idx_games_season ON games(season_id);
CREATE INDEX idx_games_age_group ON games(age_group_id);
CREATE INDEX idx_team_mappings_team ON team_mappings(team_id);
CREATE INDEX idx_team_mappings_age_group ON team_mappings(age_group_id);

-- Insert reference data
INSERT INTO age_groups (name) VALUES 
    ('U13'), ('U14'), ('U15'), ('U16'), ('U17'), ('U18'), ('U19'), ('Open');

INSERT INTO seasons (name, start_date, end_date) VALUES 
    ('2023-2024', '2023-09-01', '2024-06-30'),
    ('2024-2025', '2024-09-01', '2025-06-30'),
    ('2025-2026', '2025-09-01', '2026-06-30');

INSERT INTO game_types (name) VALUES 
    ('League'), ('Tournament'), ('Friendly'), ('Playoff'); 