# 🚀 Supabase Migration Guide

This guide will help you migrate from your problematic Supabase project to a fresh one.

## 📋 Prerequisites

- Access to Supabase dashboard
- SQLite database with your data (`mlsnext_u13_fall.db`)
- Python environment with dependencies installed

## 🔧 Step-by-Step Migration

### 1. Create New Supabase Project

1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Click **"New Project"**
3. Fill in:
   - **Project name**: `missing-table-prod` (or your choice)
   - **Database Password**: Save this securely!
   - **Region**: Choose a different region than before (e.g., if you used US East, try US West)
4. Click **"Create Project"** and wait for it to initialize

### 2. Create Database Schema

1. In your new project, go to **SQL Editor** (left sidebar)
2. Click **"New Query"**
3. Copy the entire contents of `generate_supabase_schema.sql`
4. Paste into the SQL editor
5. Click **"Run"** (or press Cmd/Ctrl + Enter)
6. You should see "Success. No rows returned"

### 3. Get Your Credentials

1. Go to **Settings** → **API** in your Supabase project
2. Copy these values:
   - **Project URL**: `https://YOUR_PROJECT_ID.supabase.co`
   - **anon public**: Your anonymous key
   - **service_role**: Your service role key (click "Reveal" to see it)

### 4. Update Environment Variables

Create a new `.env` file (or update existing):

```bash
# Backup old credentials
cp .env .env.old

# Update .env with new credentials
SUPABASE_URL=https://YOUR_NEW_PROJECT.supabase.co
SUPABASE_ANON_KEY=your_new_anon_key
SUPABASE_SERVICE_KEY=your_new_service_role_key
```

### 5. Run Migration Script

```bash
# Run the migration
uv run python migrate_to_new_supabase.py

# Or with explicit credentials
uv run python migrate_to_new_supabase.py \
  --url "https://YOUR_NEW_PROJECT.supabase.co" \
  --key "your_service_role_key"
```

The script will:
- ✅ Connect to both databases
- ✅ Create the schema (you already did this)
- ✅ Populate reference data (age groups, seasons, game types)
- ✅ Migrate all 19 teams
- ✅ Migrate all 234 games
- ✅ Verify the migration

### 6. Test the Migration

```bash
# Restart your API server
pkill -f uvicorn
uv run uvicorn app:app --reload --host 0.0.0.0 --port 8000

# In another terminal, test the CLI
uv run mt-cli recent-games
uv run mt-cli table
```

### 7. Update Frontend (if needed)

If you have the frontend running, no changes needed - it will automatically use the new backend.

## 🚨 Troubleshooting

### Connection Issues
- Make sure you're using the **service_role** key, not the anon key
- Check that the project is fully initialized (green status)
- Ensure no VPN is active

### Migration Errors
- If teams already exist, the script will handle it gracefully
- Games are inserted in batches - if one fails, others will still succeed
- Check the verification output to ensure counts match

### SSL Issues
If you still get SSL errors with the new project:
1. Try a different region
2. Contact Supabase support
3. Use the local Docker fallback

## 📊 Expected Results

After successful migration:
- 19 teams
- 234 games
- 1 season (2024-2025)
- 1 age group (U13) 
- 1 game type (League)

All data will be properly linked with foreign keys and ready to use!

## 🎯 Next Steps

1. Test all CLI commands
2. Verify the web UI works
3. Delete or pause the old project to avoid confusion
4. Consider setting up automated backups in the new project

## 💡 Local Development Option

If you need to work offline or have continued SSL issues:

```bash
cd supabase-local
docker-compose up -d
python setup_local_supabase.py
# Then run migration pointing to local Supabase
```

Good luck with your migration! 🎉