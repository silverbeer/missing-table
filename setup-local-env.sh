#!/bin/bash

# Setup script for Missing Table local development environment

set -e

echo "🚀 Missing Table Local Development Setup"
echo "======================================="

# Check if supabase is running
if ! pgrep -f "supabase.*postgres" > /dev/null; then
    echo "❌ Supabase is not running. Please run 'supabase start' first."
    exit 1
fi

echo "✅ Supabase is running"

# Get Supabase status and extract credentials
echo "📋 Getting Supabase credentials..."
SUPABASE_STATUS=$(supabase status)

# Extract the keys from status output
SUPABASE_URL=$(echo "$SUPABASE_STATUS" | grep "API URL" | awk '{print $3}')
SUPABASE_ANON_KEY=$(echo "$SUPABASE_STATUS" | grep "anon key:" | awk '{print $3}')
SUPABASE_SERVICE_KEY=$(echo "$SUPABASE_STATUS" | grep "service_role key:" | awk '{print $3}')
SUPABASE_JWT_SECRET=$(echo "$SUPABASE_STATUS" | grep "JWT secret:" | awk '{print $3}')

# Create backend .env file
echo "📄 Creating backend/.env file..."
cat > backend/.env << EOF
# Local Supabase Configuration
SUPABASE_URL=$SUPABASE_URL
SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY
SUPABASE_SERVICE_KEY=$SUPABASE_SERVICE_KEY
SUPABASE_JWT_SECRET=$SUPABASE_JWT_SECRET

# Disable monitoring for local development
DISABLE_LOGFIRE=true
EOF

echo "✅ Created backend/.env with Supabase credentials"

# Install backend dependencies
echo "📦 Installing backend dependencies..."
cd backend
uv sync
cd ..

# Restore database from backup
echo "🗃️  Restoring database from backup..."
./scripts/db_tools.sh restore

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
npm install --silent
cd ..

echo ""
echo "🎉 Setup complete! You can now start the services:"
echo ""
echo "Backend:  cd backend && uv run python app.py"
echo "Frontend: cd frontend && npm run serve"
echo ""
echo "Access URLs:"
echo "- Frontend: http://localhost:8081"
echo "- Backend:  http://localhost:8000"
echo "- API Docs: http://localhost:8000/docs"
echo "- Supabase: http://localhost:54323"