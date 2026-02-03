# Testing Parent Clubs

**Environment:** Local (http://localhost:8080) or Prod (https://missingtable.com)
**Date:** 2025-10-30
**Status:** ✅ Ready for Testing

## Quick Start

### Option 1: Interactive Testing Script (Recommended)

```bash
cd backend
export APP_ENV=local

# Run interactive test
python test_parent_clubs.py

# Or with token
python test_parent_clubs.py --token YOUR_TOKEN

# Or set token as environment variable
export AUTH_TOKEN="your_token_here"
python test_parent_clubs.py
```

The script will:
1. ✅ Test API authentication
2. ✅ List all existing teams
3. ✅ Create a parent club (if you want)
4. ✅ Link teams to the parent club
5. ✅ Test all club endpoints
6. ✅ Verify database functions

### Option 2: Manual API Testing

#### Get Your Auth Token

Login to get a token:
```bash
curl -X POST https://dev.missingtable.com/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"YOUR_USERNAME","password":"YOUR_PASSWORD"}' \  # pragma: allowlist secret
  | python3 -m json.tool
```

Save the token:
```bash
export TOKEN="your_access_token_here"
```

#### Test Endpoints

**1. List all parent clubs:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://dev.missingtable.com/api/clubs \
  | python3 -m json.tool
```

**2. Create a parent club:**
```bash
curl -X POST https://dev.missingtable.com/api/clubs \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"IFA","city":"Weymouth, MA"}' \
  | python3 -m json.tool
```

**3. Get teams for a club:**
```bash
# Replace {CLUB_ID} with actual ID from step 2
curl -H "Authorization: Bearer $TOKEN" \
  https://dev.missingtable.com/api/clubs/{CLUB_ID}/teams \
  | python3 -m json.tool
```

**4. Get all teams with parent info:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  'https://dev.missingtable.com/api/teams?include_parent=true' \
  | python3 -m json.tool
```

**5. Filter teams by club:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  'https://dev.missingtable.com/api/teams?club_id={CLUB_ID}&include_parent=true' \
  | python3 -m json.tool
```

### Option 3: Direct Database Testing

```bash
cd backend
export APP_ENV=local

python -c "
from dao.enhanced_data_access_fixed import SupabaseConnection, EnhancedSportsDAO

conn = SupabaseConnection()
dao = EnhancedSportsDAO(conn)

# Create parent club
parent = dao.create_parent_club('IFA', 'Weymouth, MA')
print(f'Created parent club: {parent}')

# Link a team
dao.update_team_parent_club(team_id=2, parent_club_id=parent['id'])

# Test database functions
is_parent = dao.is_parent_club(parent['id'])
print(f'Is parent club: {is_parent}')

teams = dao.get_club_teams(parent['id'])
print(f'Club teams: {len(teams)}')
"
```

## Test Scenarios

### Scenario 1: Create IFA Parent Club with Two Teams

This simulates a real-world scenario where "IFA" has both Academy and Homegrown teams.

**Steps:**

1. **Create parent club "IFA":**
   ```bash
   curl -X POST https://dev.missingtable.com/api/clubs \
     -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"name":"IFA","city":"Weymouth, MA"}' \
     | python3 -m json.tool
   ```

   Save the `id` from response (e.g., `PARENT_ID=1`)

2. **Find or create Academy and Homegrown teams:**
   ```bash
   # List teams to find IFA teams
   curl -H "Authorization: Bearer $TOKEN" \
     https://dev.missingtable.com/api/teams \
     | python3 -m json.tool | grep -A 3 "IFA"
   ```

3. **Link teams to parent (via database):**
   ```bash
   cd backend && export APP_ENV=local

   python -c "
   from dao.enhanced_data_access_fixed import SupabaseConnection, EnhancedSportsDAO

   conn = SupabaseConnection()
   dao = EnhancedSportsDAO(conn)

   # Link Academy team
   dao.update_team_parent_club(team_id=2, parent_club_id=1)

   # Link Homegrown team
   dao.update_team_parent_club(team_id=3, parent_club_id=1)

   print('✅ Teams linked to parent club')
   "
   ```

4. **Verify the hierarchy:**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     https://dev.missingtable.com/api/clubs/1/teams \
     | python3 -m json.tool
   ```

   Should show:
   - IFA (parent club)
   - IFA Academy (child team)
   - IFA Homegrown (child team)

### Scenario 2: List All Parent Clubs

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://dev.missingtable.com/api/clubs \
  | python3 -m json.tool
```

Expected response:
```json
[
  {
    "id": 1,
    "name": "IFA",
    "city": "Weymouth, MA",
    "academy_team": false,
    "parent_club_id": null,
    "teams": [
      {"id": 2, "name": "IFA Academy", ...},
      {"id": 3, "name": "IFA Homegrown", ...}
    ],
    "team_count": 2
  }
]
```

### Scenario 3: Filter Teams by Club

```bash
# Get only teams belonging to club ID 1
curl -H "Authorization: Bearer $TOKEN" \
  'https://dev.missingtable.com/api/teams?club_id=1' \
  | python3 -m json.tool
```

### Scenario 4: Teams with Parent Information

```bash
curl -H "Authorization: Bearer $TOKEN" \
  'https://dev.missingtable.com/api/teams?include_parent=true' \
  | python3 -m json.tool
```

Expected response for child team:
```json
{
  "id": 2,
  "name": "IFA Academy",
  "parent_club": {
    "id": 1,
    "name": "IFA",
    "city": "Weymouth, MA"
  },
  "is_parent_club": false,
  ...
}
```

## Verification Checklist

After testing, verify:

- [ ] ✅ Can create parent clubs via API
- [ ] ✅ Can list all parent clubs with child teams
- [ ] ✅ Can get teams for a specific club
- [ ] ✅ Parent club info includes team count
- [ ] ✅ Can filter teams by club_id
- [ ] ✅ Teams endpoint shows parent club info when requested
- [ ] ✅ `is_parent_club` flag is correct
- [ ] ✅ Database functions work correctly
- [ ] ✅ Authentication is properly enforced
- [ ] ✅ Admin-only endpoints require admin role

## Database Functions Testing

Test the PostgreSQL functions directly:

```sql
-- Connect to DEV database
psql "postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres"

-- Test is_parent_club
SELECT is_parent_club(1);

-- Test get_club_teams
SELECT * FROM get_club_teams(1);

-- Test get_parent_club
SELECT * FROM get_parent_club(2);

-- View teams with parent info
SELECT * FROM teams_with_parent WHERE parent_club_id = 1 OR id = 1;
```

## Common Issues & Solutions

### Issue: "Not authenticated"
**Solution:** Ensure you're passing the token in the Authorization header:
```bash
-H "Authorization: Bearer YOUR_TOKEN"
```

### Issue: "Forbidden" (403)
**Solution:** Some endpoints require admin role. Check your user's role:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://dev.missingtable.com/api/auth/me
```

### Issue: "Could not find the function public.is_parent_club"
**Solution:** Ensure migration `20251030184100_add_parent_club_to_teams.sql` is applied to DEV:
```bash
cd supabase-local
npx supabase link --project-ref [DEV_PROJECT_REF]
npx supabase db push --linked
```

### Issue: Connection timeout from local machine
**Solution:** Use the testing script which connects via the pod, or test via the API endpoints.

## Next Steps After Testing

1. **Document findings** - Note any issues or suggestions
2. **Create test data** - Set up realistic club hierarchies
3. **Frontend integration** - Update Vue components to use new endpoints
4. **Production deployment** - Once validated in DEV

## Related Documentation

- [Club API Implementation](./CLUB_API_IMPLEMENTATION.md) - Complete API reference
- [Parent Club Migration Guide](./PARENT_CLUB_MIGRATION_GUIDE.md) - Database migration details
- [Club League Implementation Plan](./CLUB_LEAGUE_IMPLEMENTATION_PLAN.md) - Overall implementation plan

---

**Last Updated:** 2025-10-30
**Environment:** DEV (https://dev.missingtable.com)
**Status:** ✅ Ready for Testing
