#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv('.env.dev', override=True)

from dao.enhanced_data_access_fixed import SupabaseConnection

db_conn = SupabaseConnection()

print("Divisions in DEV database:\n")
divisions = db_conn.client.table('divisions').select('*, leagues(name)').order('id').execute()
for d in divisions.data:
    print(f"  ID {d['id']}: {d['name']} (League: {d.get('leagues', {}).get('name', 'N/A')}, league_id={d['league_id']})")
