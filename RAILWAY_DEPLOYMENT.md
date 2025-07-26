# Railway + Supabase Deployment Guide

This guide shows how to deploy your sports league app using Railway (frontend + backend) and Supabase (database).

## Cost Breakdown

### Railway Costs
- **Hobby Plan**: $5/month per service
- **Pro Plan**: $20/month per service
- **Redis Add-on**: $3/month

### Supabase Costs
- **Free Tier**: Up to 500MB database, 50MB file storage
- **Pro Plan**: $25/month (8GB database, 100GB storage)

### Total Monthly Cost
- **Small Scale**: $13/month (Railway Hobby + Supabase Free)
- **Production Scale**: $53/month (Railway Pro + Supabase Pro + Redis)

## Prerequisites

1. **Railway Account**: Sign up at [railway.app](https://railway.app)
2. **Supabase Account**: Sign up at [supabase.com](https://supabase.com)
3. **GitHub Repository**: Your code should be in a GitHub repo
4. **Railway CLI**: `npm install -g @railway/cli`

## Step 1: Set Up Supabase

### 1.1 Create Supabase Project
```bash
# Go to https://supabase.com/dashboard
# Click "New Project"
# Choose organization, name, password, region
# Wait for database to be ready (~2 minutes)
```

### 1.2 Run Database Migrations
```bash
# Copy your migration files to Supabase
# Go to SQL Editor in Supabase dashboard
# Run your migration files in order:

-- 1. Copy contents of supabase/migrations/001_create_schema.sql
-- 2. Copy contents of supabase/migrations/002_add_divisions.sql
-- 3. Continue with all migration files...
```

### 1.3 Get Supabase Credentials
```bash
# In Supabase Dashboard > Settings > API
# Copy these values:
PROJECT_URL=https://your-project.supabase.co
ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# In Settings > Database
JWT_SECRET=your-jwt-secret
```

## Step 2: Deploy Backend to Railway

### 2.1 Create Railway Project
```bash
# Login to Railway
railway login

# Create new project (in backend directory)
cd backend
railway init
# Choose "Empty Project"
# Name it "sports-league-backend"
```

### 2.2 Add Redis (Optional but Recommended)
```bash
# Add Redis for rate limiting
railway add redis

# This creates a Redis instance and sets REDIS_URL automatically
```

### 2.3 Set Environment Variables
```bash
# Set all required environment variables
railway variables set SUPABASE_URL="https://your-project.supabase.co"
railway variables set SUPABASE_ANON_KEY="your-anon-key"
railway variables set SUPABASE_SERVICE_KEY="your-service-key"
railway variables set SUPABASE_JWT_SECRET="your-jwt-secret"
railway variables set CSRF_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
railway variables set ENVIRONMENT="production"
railway variables set USE_REDIS_RATE_LIMIT="true"

# Railway automatically sets PORT and REDIS_URL
```

### 2.4 Deploy Backend
```bash
# Connect to GitHub repository
railway link

# Deploy
railway deploy

# Get the backend URL
railway domain
# Example: https://sports-league-backend-production.up.railway.app
```

## Step 3: Deploy Frontend to Railway

### 3.1 Create Frontend Project
```bash
# Create separate Railway project for frontend
cd ../frontend
railway init
# Choose "Empty Project"
# Name it "sports-league-frontend"
```

### 3.2 Set Frontend Environment Variables
```bash
# Set environment variables for build
railway variables set VUE_APP_SUPABASE_URL="https://your-project.supabase.co"
railway variables set VUE_APP_SUPABASE_ANON_KEY="your-anon-key"
railway variables set VUE_APP_API_URL="https://your-backend.up.railway.app"
```

### 3.3 Configure Build Process
```bash
# Railway will automatically detect Vue.js and build it
# Make sure your package.json has the build script
```

### 3.4 Deploy Frontend
```bash
# Connect to GitHub repository
railway link

# Deploy
railway deploy

# Get the frontend URL
railway domain
# Example: https://sports-league-frontend-production.up.railway.app
```

## Step 4: Configure Custom Domain (Optional)

### 4.1 Add Custom Domain to Frontend
```bash
# In Railway dashboard for frontend project
# Go to Settings > Domains
# Add your custom domain (e.g., yourdomain.com)
# Update your DNS to point to Railway
```

### 4.2 Add API Subdomain
```bash
# In Railway dashboard for backend project
# Go to Settings > Domains
# Add API subdomain (e.g., api.yourdomain.com)
```

### 4.3 Update Frontend Environment
```bash
# Update API URL to use custom domain
railway variables set VUE_APP_API_URL="https://api.yourdomain.com"

# Redeploy frontend
railway deploy
```

## Step 5: Set Up Monitoring

### 5.1 Railway Monitoring
```bash
# Railway provides built-in monitoring
# View logs: railway logs
# View metrics in dashboard
```

### 5.2 Add Health Check Endpoint
Your backend already has `/health` endpoint. Verify it works:
```bash
curl https://your-backend.up.railway.app/health
```

## Step 6: Set Up CI/CD (Optional)

### 6.1 Automatic Deployments
Railway automatically deploys when you push to your GitHub repository's main branch.

### 6.2 GitHub Actions for Testing
```yaml
# .github/workflows/test.yml
name: Test

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.13'
    
    - name: Install dependencies
      run: |
        cd backend
        pip install uv
        uv pip install -e ".[dev]"
    
    - name: Run tests
      run: |
        cd backend
        pytest

  test-frontend:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '18'
    
    - name: Install and test
      run: |
        cd frontend
        npm ci
        npm run lint
```

## Deployment Commands Reference

### Backend Management
```bash
# View logs
railway logs

# Restart service
railway redeploy

# Access shell
railway shell

# View environment variables
railway variables

# Scale up/down
railway up  # Scale up
railway down  # Scale down
```

### Frontend Management
```bash
# Same commands work for frontend
railway logs
railway redeploy
railway variables
```

### Database Management
```bash
# Access Supabase dashboard
# https://supabase.com/dashboard/project/your-project

# Run SQL queries
# Use SQL Editor in dashboard

# View real-time data
# Use Table Editor in dashboard
```

## Troubleshooting

### Common Issues

#### 1. Build Failures
```bash
# Check build logs
railway logs --deployment

# Common fixes:
# - Ensure all dependencies are in pyproject.toml/package.json
# - Check Python/Node version requirements
# - Verify environment variables are set
```

#### 2. Environment Variable Issues
```bash
# List all variables
railway variables

# Remove incorrect variable
railway variables delete VARIABLE_NAME

# Set correct variable
railway variables set VARIABLE_NAME="value"
```

#### 3. CORS Issues
```bash
# Update CORS origins in backend/app.py
origins = [
    "https://your-frontend.up.railway.app",
    "https://yourdomain.com",
    "http://localhost:8080"  # for development
]
```

#### 4. Database Connection Issues
```bash
# Verify Supabase credentials
railway variables | grep SUPABASE

# Test connection
railway shell
python -c "
from supabase import create_client
import os
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_ANON_KEY'))
print('Connection successful!')
"
```

### Performance Optimization

#### 1. Enable Caching
```bash
# Redis is already configured for rate limiting
# You can extend it for application caching
```

#### 2. Optimize Frontend Build
```javascript
// vue.config.js
module.exports = {
  configureWebpack: {
    optimization: {
      splitChunks: {
        chunks: 'all'
      }
    }
  }
}
```

#### 3. Database Optimization
```sql
-- Add indexes for frequently queried columns
CREATE INDEX idx_games_season_id ON games(season_id);
CREATE INDEX idx_games_date ON games(game_date);
CREATE INDEX idx_teams_age_group ON team_mappings(age_group_id);
```

## Cost Optimization Tips

### 1. Use Hobby Plans for Development
```bash
# Hobby plans sleep after 30 minutes of inactivity
# Perfect for development/staging environments
```

### 2. Monitor Usage
```bash
# Check Railway dashboard for resource usage
# Upgrade to Pro only when needed
```

### 3. Optimize Database Queries
```python
# Use select() to limit returned columns
response = client.table('games').select('id, home_score, away_score').execute()

# Use pagination for large datasets
response = client.table('games').select('*').range(0, 49).execute()
```

### 4. Use Supabase Edge Functions
```javascript
// For complex backend logic, use Supabase Edge Functions
// They're cheaper than running full backend containers
```

## Scaling Strategy

### Stage 1: MVP (Free/Hobby Tiers)
- Railway Hobby plans
- Supabase Free tier
- Total: ~$10/month

### Stage 2: Small Business (Pro Plans)
- Railway Pro plans
- Supabase Pro tier
- Total: ~$70/month

### Stage 3: Scale Up (Multiple Instances)
- Multiple Railway instances
- Supabase with additional resources
- Consider CDN (CloudFlare)
- Total: ~$150/month

## Migration from Development

### 1. Database Migration
```bash
# Export development data
supabase db dump --local > backup.sql

# Import to production
# Use Supabase dashboard SQL editor to run backup.sql
```

### 2. Environment Sync
```bash
# Copy .env to Railway variables
cat .env | while read line; do
  if [[ $line == *"="* && $line != "#"* ]]; then
    key=$(echo $line | cut -d '=' -f1)
    value=$(echo $line | cut -d '=' -f2-)
    railway variables set "$key=$value"
  fi
done
```

### 3. DNS Update
```bash
# Update DNS records to point to Railway domains
# A record: yourdomain.com -> Railway frontend
# CNAME record: api.yourdomain.com -> Railway backend
```

## Support Resources

- **Railway Docs**: https://docs.railway.app
- **Supabase Docs**: https://supabase.com/docs
- **Railway Discord**: https://railway.app/discord
- **Supabase Discord**: https://supabase.com/discord

## Quick Commands Summary

```bash
# Initial setup
railway login
cd backend && railway init && railway add redis
cd frontend && railway init

# Set environment variables
railway variables set KEY="value"

# Deploy
railway deploy

# Monitor
railway logs
railway status

# Scale
railway scale --replicas 2
```