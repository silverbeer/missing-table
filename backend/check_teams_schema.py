#!/usr/bin/env python3
"""Check teams table schema."""
import requests

# Login
response = requests.post("http://localhost:8000/api/auth/login", json={
    "username": "tom",
    "password": "admin123"
})
token = response.json()["access_token"]

# Get a team to see its columns
teams_response = requests.get(
    "http://localhost:8000/api/teams",
    headers={"Authorization": f"Bearer {token}"}
)

teams = teams_response.json()
if teams:
    print("Sample team columns:")
    print(list(teams[0].keys()))
    print(f"\nSample team data:")
    print(teams[0])
else:
    print("No teams in database")
