#!/bin/bash

# Start the backend with Supabase CLI configuration

# Check if .env.local exists, if not create it with template
if [ ! -f .env.local ]; then
    echo "Creating .env.local template..."
    cat > .env.local << 'EOF'
# Supabase Local Development Configuration
# Replace these with your actual local Supabase keys
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_SERVICE_KEY=your_service_key_here
SUPABASE_ANON_KEY=your_anon_key_here
EOF
    echo "📝 Created .env.local template"
    echo "Please update .env.local with your actual Supabase local keys"
    echo "You can find them by running: supabase status"
    exit 1
fi

# Export environment variables from .env.local (ignore comments)
export $(cat .env.local | grep -v '^#' | xargs)

# Validate required environment variables
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_KEY" ]; then
    echo "❌ Error: Missing required environment variables"
    echo "Please check your .env.local file contains:"
    echo "  SUPABASE_URL=http://127.0.0.1:54321"
    echo "  SUPABASE_SERVICE_KEY=your_actual_service_key"
    echo "  SUPABASE_ANON_KEY=your_actual_anon_key"
    exit 1
fi

echo "Starting backend with Supabase CLI configuration..."
echo "Supabase URL: $SUPABASE_URL"

# Start the backend
uv run python app.py 