# Supabase Setup Guide

## 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign up/login
2. Click "New Project"
3. Choose your organization
4. Set project name: `missing-table`
5. Set database password (save this!)
6. Choose region (closest to your users)
7. Click "Create new project"

## 2. Get Project Credentials

Once your project is created:

1. Go to **Settings** → **API**
2. Copy the following values:
   - **Project URL**: `https://your-project-id.supabase.co`
   - **Anon (public) key**: `eyJ...` (starts with eyJ)
   - **Service role key**: `eyJ...` (starts with eyJ)

## 3. Update Environment Variables

Update your `.env` file with the actual values:

```bash
SUPABASE_URL=https://your-actual-project-id.supabase.co
SUPABASE_ANON_KEY=your-actual-anon-key
SUPABASE_SERVICE_KEY=your-actual-service-role-key
ENVIRONMENT=local
```

## 4. Create Database Schema

In the Supabase SQL Editor, run:

```sql
-- Create teams table
CREATE TABLE teams (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  city TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create games table
CREATE TABLE games (
  id BIGSERIAL PRIMARY KEY,
  game_date DATE NOT NULL,
  home_team TEXT NOT NULL REFERENCES teams(name),
  away_team TEXT NOT NULL REFERENCES teams(name),
  home_score INTEGER NOT NULL,
  away_score INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX idx_games_home_team ON games(home_team);
CREATE INDEX idx_games_away_team ON games(away_team);
CREATE INDEX idx_games_date ON games(game_date);
```

## 5. Configure Row Level Security (Optional)

For production, enable RLS:

```sql
-- Enable RLS
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE games ENABLE ROW LEVEL SECURITY;

-- Allow read access to all authenticated users
CREATE POLICY "Allow read access to teams" ON teams FOR SELECT USING (true);
CREATE POLICY "Allow read access to games" ON games FOR SELECT USING (true);
```

## 6. Test Connection

After updating your `.env` file, test the connection:

```bash
uv sync  # Install new dependencies
uv run python -c "
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_ANON_KEY')
supabase = create_client(url, key)
print('Supabase connection successful!')
"
```

## Next Steps

Once setup is complete, you can proceed with the data migration from SQLite to Supabase.