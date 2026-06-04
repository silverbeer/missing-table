#!/bin/bash
# Start backend with local Supabase configuration

echo "🚀 Starting backend with local Supabase..."
echo "📊 Local Supabase endpoints:"
echo "   PostgreSQL: localhost:5432"
echo "   REST API: http://localhost:55321"
echo ""

# Export local environment variables (ignore comments)
export $(cat .env.local | grep -v '^#' | xargs)

# Unset conflicting VIRTUAL_ENV to avoid uv warning
unset VIRTUAL_ENV

# Start the backend
uv run python app.py 