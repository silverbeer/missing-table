#!/usr/bin/env python3
"""
Fix IFA Club team data mismatches.

Issues found:
1. IFA Academy (id=123) - team league is Homegrown but division is Academy's New England
2. IFA Elite Futsal 2012 White (id=184) - has wrong duplicate mapping to Northeast/Homegrown
3. IFA Futsal South 2012 Boys (id=185) - has wrong duplicate mapping to Northeast/Homegrown
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return create_client(url, key)


def main():
    client = get_supabase_client()

    print("=" * 60)
    print("Fixing IFA Club team data mismatches")
    print("=" * 60)

    # Fix 1: Update IFA Academy's league_id from 1 (Homegrown) to 2 (Academy)
    print("\n1. Updating IFA Academy (id=123) league_id: 1 → 2 (Academy)")
    result = client.table("teams").update({"league_id": 2}).eq("id", 123).execute()
    print(f"   Updated {len(result.data)} record(s)")

    # Fix 2: Delete wrong mapping for IFA Elite Futsal 2012 White
    print("\n2. Deleting wrong mapping for IFA Elite Futsal 2012 White (mapping_id=207)")
    result = client.table("team_mappings").delete().eq("id", 207).execute()
    print(f"   Deleted {len(result.data)} record(s)")

    # Fix 3: Delete wrong mapping for IFA Futsal South 2012 Boys
    print("\n3. Deleting wrong mapping for IFA Futsal South 2012 Boys (mapping_id=208)")
    result = client.table("team_mappings").delete().eq("id", 208).execute()
    print(f"   Deleted {len(result.data)} record(s)")

    print("\n" + "=" * 60)
    print("Done! Verifying fixes...")
    print("=" * 60)

    # Verify the fixes
    print("\nVerifying IFA Club teams:")
    result = client.table("teams").select(
        "id, name, league_id, leagues!teams_league_id_fkey(name)"
    ).in_("id", [123, 184, 185]).execute()

    for team in result.data:
        league_name = team.get("leagues", {}).get("name", "Unknown")
        print(f"  - {team['name']} (id={team['id']}): league={league_name}")

    print("\nVerifying team_mappings:")
    result = client.table("team_mappings").select(
        "id, team_id, teams!team_mappings_team_id_fkey(name), division_id, divisions!team_mappings_division_id_fkey(name)"
    ).in_("team_id", [123, 184, 185]).execute()

    for mapping in result.data:
        team_name = mapping.get("teams", {}).get("name", "Unknown")
        division_name = mapping.get("divisions", {}).get("name", "Unknown")
        print(f"  - mapping_id={mapping['id']}: {team_name} → {division_name}")


if __name__ == "__main__":
    main()
