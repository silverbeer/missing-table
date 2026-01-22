#!/usr/bin/env python3
"""
Backup auth.users and related auth tables from Supabase.
This backs up the actual auth schema data needed to restore users.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from supabase import Client, create_client

# Load environment
backend_path = Path(__file__).parent
app_env = os.getenv("APP_ENV", "local")
env_path = backend_path / f".env.{app_env}"

if not env_path.exists():
    env_path = backend_path / ".env"

load_dotenv(env_path, override=True)

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

if not url or not key:
    raise Exception("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")

supabase: Client = create_client(url, key)


# Use PostgREST to query auth schema (requires service role key)
try:
    # Query auth.users - PostgREST can access auth schema with service key

    # We need to use RPC or direct SQL since PostgREST restricts auth schema
    # Let's generate SQL to get the data

    sql = """
-- Backup auth.users data
-- Run this in Supabase SQL Editor and save the results

SELECT
    id,
    email,
    encrypted_password,
    email_confirmed_at,
    invited_at,
    confirmation_token,
    confirmation_sent_at,
    recovery_token,
    recovery_sent_at,
    email_change_token_new,
    email_change,
    email_change_sent_at,
    last_sign_in_at,
    raw_app_meta_data,
    raw_user_meta_data,
    is_super_admin,
    created_at,
    updated_at,
    phone,
    phone_confirmed_at,
    phone_change,
    phone_change_token,
    phone_change_sent_at,
    email_change_token_current,
    email_change_confirm_status,
    banned_until,
    reauthentication_token,
    reauthentication_sent_at,
    is_sso_user,
    deleted_at
FROM auth.users
ORDER BY created_at;

-- Also backup auth.identities (links users to auth methods)
SELECT
    id,
    user_id,
    identity_data,
    provider,
    last_sign_in_at,
    created_at,
    updated_at
FROM auth.identities
ORDER BY created_at;
"""

    output_file = backend_path / f"auth_backup_{app_env}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    with open(output_file, "w") as f:
        f.write(sql)

    # Alternative: Try to get via admin API

    # Try using the Admin API
    try:
        # Supabase Admin API for listing users
        import requests

        admin_url = f"{url}/auth/v1/admin/users"
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        response = requests.get(admin_url, headers=headers)

        if response.status_code == 200:
            users_data = response.json()
            users = users_data.get("users", [])

            # Save to JSON
            backup_data = {
                "backup_info": {
                    "environment": app_env,
                    "created_at": datetime.now().isoformat(),
                    "method": "admin_api",
                    "user_count": len(users),
                },
                "users": users,
            }

            json_file = backend_path / f"auth_users_{app_env}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(json_file, "w") as f:
                json.dump(backup_data, f, indent=2)

            for _user in users:
                pass

        else:
            pass

    except Exception:
        pass

except Exception:
    sys.exit(1)
