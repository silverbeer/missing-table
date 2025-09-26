#!/bin/bash
# Helper script to configure cloud Supabase credentials

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header "Supabase Cloud Credentials Setup"

echo "This script will help you configure your cloud Supabase credentials."
echo "You'll need to get these values from your Supabase dashboard."
echo ""

# Check if .env.dev files exist
backend_env="$SCRIPT_DIR/backend/.env.dev"
frontend_env="$SCRIPT_DIR/frontend/.env.dev"

if [ ! -f "$backend_env" ] || [ ! -f "$frontend_env" ]; then
    print_error "Environment files not found. Please run the migration setup first."
    exit 1
fi

print_warning "Before proceeding, please:"
echo "1. Go to https://supabase.com/dashboard"
echo "2. Select your 'missing-table' project"
echo "3. Go to Settings > API"
echo "4. Copy the following values:"
echo "   - Project URL"
echo "   - anon public key"
echo "   - service_role secret key"
echo "5. Go to Settings > Auth"
echo "   - Copy JWT Secret"
echo "6. Go to Settings > Database"
echo "   - Copy Connection String (URI format)"
echo ""

read -p "Do you have these values ready? (y/n): " ready
if [ "$ready" != "y" ] && [ "$ready" != "Y" ]; then
    echo "Please gather the credentials first, then run this script again."
    exit 0
fi

echo ""
print_header "Entering Credentials"

# Get Project URL
echo "Enter your Supabase Project URL (e.g., https://abcdefgh.supabase.co):"
read -p "URL: " project_url

if [[ ! "$project_url" =~ ^https://.*\.supabase\.co$ ]]; then
    print_warning "URL format should be: https://[project-id].supabase.co"
fi

# Get anon key
echo ""
echo "Enter your anon public key:"
read -p "Anon Key: " anon_key

# Get service key
echo ""
echo "Enter your service_role secret key:"
read -s -p "Service Key: " service_key
echo ""

# Get JWT Secret
echo ""
echo "Enter your JWT Secret:"
read -s -p "JWT Secret: " jwt_secret
echo ""

# Get Database URL
echo ""
echo "Enter your Database Connection String (URI format):"
echo "Should look like: postgresql://postgres.[project-id]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres"
read -p "Database URL: " database_url

# Update backend .env.dev
echo ""
print_header "Updating Backend Configuration"

# Create backup
cp "$backend_env" "$backend_env.backup.$(date +%Y%m%d_%H%M%S)"

# Update the file
sed -i.tmp \
    -e "s|SUPABASE_URL=.*|SUPABASE_URL=$project_url|" \
    -e "s|SUPABASE_ANON_KEY=.*|SUPABASE_ANON_KEY=$anon_key|" \
    -e "s|SUPABASE_SERVICE_KEY=.*|SUPABASE_SERVICE_KEY=$service_key|" \
    -e "s|SUPABASE_JWT_SECRET=.*|SUPABASE_JWT_SECRET=$jwt_secret|" \
    -e "s|DATABASE_URL=.*|DATABASE_URL=$database_url|" \
    "$backend_env"

rm "$backend_env.tmp"

print_success "Backend configuration updated"

# Update frontend .env.dev
print_header "Updating Frontend Configuration"

# Create backup
cp "$frontend_env" "$frontend_env.backup.$(date +%Y%m%d_%H%M%S)"

# Update the file
sed -i.tmp \
    -e "s|VUE_APP_SUPABASE_URL=.*|VUE_APP_SUPABASE_URL=$project_url|" \
    -e "s|VUE_APP_SUPABASE_ANON_KEY=.*|VUE_APP_SUPABASE_ANON_KEY=$anon_key|" \
    "$frontend_env"

rm "$frontend_env.tmp"

print_success "Frontend configuration updated"

echo ""
print_header "Testing Configuration"

# Test connection
echo "Testing Supabase connection..."
cd "$SCRIPT_DIR/backend" || exit 1

export APP_ENV=dev

if uv run python -c "
from dao.enhanced_data_access_fixed import SupabaseConnection
try:
    conn = SupabaseConnection()
    print('✅ Connection successful!')
except Exception as e:
    print(f'❌ Connection failed: {e}')
    exit(1)
" 2>/dev/null; then
    print_success "Supabase connection test passed!"
else
    print_error "Supabase connection test failed. Please check your credentials."
fi

echo ""
print_header "Next Steps"

echo "1. Apply database migrations to your cloud database:"
echo "   ./switch-env.sh dev"
echo "   npx supabase db push"
echo ""
echo "2. Migrate your data to the cloud:"
echo "   ./scripts/db_tools.sh backup"
echo "   ./scripts/db_tools.sh restore --cloud"
echo ""
echo "3. Test the full setup:"
echo "   ./start.sh"
echo ""

print_success "Cloud credentials configuration complete!"

echo ""
print_warning "Security Note:"
echo "- Your credentials are now stored in .env.dev files"
echo "- These files should NOT be committed to git"
echo "- Backups of original files were created with .backup suffix"