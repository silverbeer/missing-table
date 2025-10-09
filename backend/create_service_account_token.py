#!/usr/bin/env python3
"""
Service Account Token Generation Utility

Creates JWT tokens for service accounts like match-scraper to authenticate API requests.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth import AuthManager


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Generate service account tokens")
    parser.add_argument("--service-name", required=True, help="Name of the service (e.g., match-scraper)")
    parser.add_argument(
        "--permissions",
        nargs="+",
        default=["manage_matches"],
        help="Permissions to grant (default: manage_matches)"
    )
    parser.add_argument(
        "--expires-days",
        type=int,
        default=365,
        help="Token expiration in days (default: 365)"
    )
    parser.add_argument(
        "--output-file",
        help="Save token to file instead of printing to console"
    )

    args = parser.parse_args()

    # Mock supabase client for AuthManager (only needed for user auth, not service accounts)
    class MockSupabase:
        def table(self, name):
            return self

        def select(self, *args):
            return self

        def eq(self, *args):
            return self

        def execute(self):
            return type('obj', (object,), {'data': []})

    auth_manager = AuthManager(MockSupabase())

    try:
        token = auth_manager.create_service_account_token(
            service_name=args.service_name,
            permissions=args.permissions,
            expires_days=args.expires_days
        )

        # Calculate expiration date for display
        expiration = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Output information
        info = f"""
Service Account Token Generated Successfully!

Service Name: {args.service_name}
Permissions: {', '.join(args.permissions)}
Expires: {expiration} (+{args.expires_days} days)

Token:
{token}

Usage:
- Add this token to your match-scraper environment as MISSING_TABLE_API_TOKEN
- Use as Bearer token in Authorization header: "Authorization: Bearer {token}"

Example API calls:
curl -H "Authorization: Bearer {token}" \\
     -H "Content-Type: application/json" \\
     -X POST http://localhost:8000/api/matches \\
     -d '{{"match_date": "2024-03-15", "home_team_id": 1, ...}}'

curl -H "Authorization: Bearer {token}" \\
     -H "Content-Type: application/json" \\
     -X PUT http://localhost:8000/api/matches/123 \\
     -d '{{"match_date": "2024-03-15", "home_score": 2, "away_score": 1, ...}}'

SECURITY NOTES:
- Keep this token secure and never commit it to version control
- Use environment variables to store the token in match-scraper
- Rotate tokens periodically for security
"""

        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(token)
            print(f"Token saved to: {args.output_file}")
            print(info.replace(f"Token:\n{token}\n", "Token: [saved to file]\n"))
        else:
            print(info)

    except Exception as e:
        print(f"Error generating token: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()