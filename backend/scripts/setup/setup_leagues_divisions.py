#!/usr/bin/env python3
"""
Setup leagues and divisions needed for clubs.json sync.
"""

import requests

# Login
login_response = requests.post("http://localhost:8000/api/auth/login", json={"username": "tom", "password": "admin123"})
token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Create Academy league
response = requests.post(
    "http://localhost:8000/api/leagues",
    headers=headers,
    json={"name": "Academy", "description": "MLS Next Academy league", "is_active": True},
)
if response.status_code in [200, 201]:
    pass
elif "already exists" in response.text.lower():
    # Get existing league ID
    leagues = requests.get("http://localhost:8000/api/leagues", headers=headers).json()
    academy_league = next(l for l in leagues if l["name"] == "Academy")
else:
    pass

# Get leagues
leagues = requests.get("http://localhost:8000/api/leagues", headers=headers).json()
homegrown_league_id = next(l["id"] for l in leagues if l["name"] == "Homegrown")
academy_league_id = next(l["id"] for l in leagues if l["name"] == "Academy")


# Create divisions/conferences
divisions_to_create = [
    {
        "name": "Northeast",
        "league_id": homegrown_league_id,
        "description": "Northeast Division (Homegrown)",
    },
    {
        "name": "New England",
        "league_id": academy_league_id,
        "description": "New England Conference (Academy)",
    },
]

for div in divisions_to_create:
    response = requests.post("http://localhost:8000/api/divisions", headers=headers, json=div)
    if response.status_code in [200, 201] or "already exists" in response.text.lower():
        pass
    else:
        pass

# Verify
divisions = requests.get("http://localhost:8000/api/divisions", headers=headers).json()
for div in divisions:
    league_name = next(l["name"] for l in leagues if l["id"] == div["league_id"])
