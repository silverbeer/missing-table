#!/bin/bash
# Test script for Leagues and Clubs functionality

echo "========================================="
echo "Testing Leagues and Clubs API"
echo "========================================="

# Get auth token
echo "1. Logging in as tom..."
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"tom","password":"admin123"}' | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

if [ -z "$TOKEN" ]; then
  echo "❌ Failed to get auth token"
  exit 1
fi
echo "✅ Logged in successfully"
echo ""

# Test 1: Get all leagues
echo "2. Getting all leagues..."
curl -s http://localhost:8000/api/leagues \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
echo ""

# Test 2: Get all clubs
echo "3. Getting all clubs..."
curl -s http://localhost:8000/api/clubs \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
echo ""

# Test 3: Create a test club
echo "4. Creating a test club (IFA)..."
curl -s -X POST http://localhost:8000/api/clubs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"IFA","city":"Weymouth, MA","website":"https://ifa.com"}' | python3 -m json.tool
echo ""

# Test 4: Get all clubs again
echo "5. Getting all clubs (should now include IFA)..."
curl -s http://localhost:8000/api/clubs \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
echo ""

# Test 5: Get teams to check league_id and club_id
echo "6. Getting first 5 teams with league/club info..."
curl -s "http://localhost:8000/api/teams?limit=5" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
echo ""

echo "========================================="
echo "Test completed!"
echo "========================================="
