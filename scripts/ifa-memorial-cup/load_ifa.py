# ruff: noqa: T201  # CLI tool; print() is the intended output channel
"""Load the IFA Memorial Cup 2026 — U14 Boys Diamond Bracket A — into MT.

Inputs are hardcoded from the published schedule screenshots (Bracket A,
May 23-25 2026 EDT). 5-team round-robin = 10 group-stage matches.

Usage:
  cd backend && uv run python ../scripts/ifa-memorial-cup/load_ifa.py \\
    --base http://localhost:8000 --dry-run

  cd backend && uv run python ../scripts/ifa-memorial-cup/load_ifa.py \\
    --base http://localhost:8000 --write

For prod (after `./switch-env.sh prod` and `mt_cli login`):
  cd backend && uv run python ../scripts/ifa-memorial-cup/load_ifa.py \\
    --base https://api.missingtable.com --write

Notes:
  - Match-create is NOT idempotent — only run --write once per environment.
  - Tournament create IS idempotent (lookup-first by name).
  - Team create is lookup-first per team name (same as the MLS Cup loader).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
TOKEN_FILE = REPO_ROOT / "backend" / ".mt-cli-state.json"

TOURNAMENT_NAME = "2026 IFA MEMORIAL DAY CUP"
TOURNAMENT_START = "2026-05-23"
TOURNAMENT_END = "2026-05-25"
TOURNAMENT_LOCATION = "MA"
TOURNAMENT_DESC = (
    "IFA Memorial Day weekend tournament (loaded: U14 Boys Diamond Bracket A)"
)
AGE_GROUP_ID_U14 = 2
SEASON_ID = 3  # 2025-2026
TOURNAMENT_GROUP_LABEL = "U14 Boys Diamond Bracket A"

# 5 teams in the bracket. Order doesn't matter — lookup-first by name.
TEAMS = [
    "A.C. Connecticut B2012 ECNL",
    "FA Euro New York 2012 MLS NEXT HD",
    "IFA U14 MLS NEXT HG",
    "New England Revolution Academy 2012s",
    "SUSA FC B12 ACADEMY",
]

# The IFA tournament schedule uses verbose team labels (e.g.
# "IFA U14 MLS NEXT HG", "New England Revolution Academy 2012s") that
# don't match the canonical team rows already in MT (which are just "IFA",
# "New England Revolution", etc., tagged with the U14 age group via
# team_mappings). Without this map, the loader would fan out a parallel
# "IFA U14 MLS NEXT HG" team — invisible to `My Club → IFA → U14`.
#
# Map: schedule label → existing team name in MT. Lookup is by exact name
# (case-sensitive). When matched, the loader reuses the existing team_id
# and skips both club and team create.
SCHEDULE_TEAM_TO_EXISTING_TEAM = {
    "IFA U14 MLS NEXT HG":                  "IFA",
    "FA Euro New York 2012 MLS NEXT HD":    "FA Euro New York",
    "New England Revolution Academy 2012s": "New England Revolution",
    # A.C. Connecticut B2012 ECNL — no canonical row yet; create new team
    # SUSA FC B12 ACADEMY        — no canonical row yet; create new team
}

# When a NEW team must be created, it still benefits from being attached
# to an existing parent club row (so `My Club → <club>` later lists it).
# Empty for the IFA Cup since both genuinely-new teams (A.C. Connecticut,
# SUSA) also have no existing parent club in MT.
NEW_TEAM_PARENT_CLUB = {}

# Each row: (source_match_id, home, away, match_date, kickoff_utc, venue)
# EDT → UTC: +4h.
MATCHES = [
    # Sat May 23
    (1825, "SUSA FC B12 ACADEMY", "New England Revolution Academy 2012s",
     "2026-05-23", "2026-05-23T12:00:00Z", "SBLI Fields at Progin Park - Field 14"),
    (1827, "FA Euro New York 2012 MLS NEXT HD", "SUSA FC B12 ACADEMY",
     "2026-05-23", "2026-05-23T16:25:00Z", "Algonquin Regional High School - Grass #2"),
    (1822, "New England Revolution Academy 2012s", "FA Euro New York 2012 MLS NEXT HD",
     "2026-05-23", "2026-05-23T20:30:00Z", "SBLI Fields at Progin Park - 4"),
    (1826, "A.C. Connecticut B2012 ECNL", "IFA U14 MLS NEXT HG",
     "2026-05-23", "2026-05-23T23:20:00Z", "Algonquin Regional High School - Stadium"),
    # Sun May 24
    (1824, "IFA U14 MLS NEXT HG", "FA Euro New York 2012 MLS NEXT HD",
     "2026-05-24", "2026-05-24T16:15:00Z", "Algonquin Regional High School - Grass #2"),
    (1818, "A.C. Connecticut B2012 ECNL", "SUSA FC B12 ACADEMY",
     "2026-05-24", "2026-05-24T16:15:00Z", "SBLI Fields at Progin Park - 9"),
    (1821, "SUSA FC B12 ACADEMY", "IFA U14 MLS NEXT HG",
     "2026-05-24", "2026-05-24T19:05:00Z", "SBLI Fields at Progin Park - 7"),
    (1823, "New England Revolution Academy 2012s", "A.C. Connecticut B2012 ECNL",
     "2026-05-24", "2026-05-24T21:55:00Z", "Algonquin Regional High School - Stadium"),
    # Mon May 25
    (1820, "FA Euro New York 2012 MLS NEXT HD", "A.C. Connecticut B2012 ECNL",
     "2026-05-25", "2026-05-25T13:30:00Z", "SBLI Fields at Progin Park - 6"),
    (1819, "IFA U14 MLS NEXT HG", "New England Revolution Academy 2012s",
     "2026-05-25", "2026-05-25T18:00:00Z", "SBLI Fields at Progin Park - 6"),
]


def parse_args():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--base", required=True, help="MT API base URL")
    p.add_argument("--dry-run", action="store_true", help="Print plan; do not write")
    p.add_argument("--write", action="store_true", help="Actually create rows")
    args = p.parse_args()
    if not args.dry_run and not args.write:
        p.error("must specify --dry-run OR --write")
    if args.dry_run and args.write:
        p.error("--dry-run and --write are mutually exclusive")
    return args


def load_token() -> str:
    state = json.loads(TOKEN_FILE.read_text())
    return state["access_token"]


def main():
    args = parse_args()
    base = args.base.rstrip("/")
    token = load_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Sanity-check the 5 teams match what's used in MATCHES.
    used_team_names = {n for row in MATCHES for n in (row[1], row[2])}
    missing = used_team_names - set(TEAMS)
    if missing:
        print(f"BUG in script: matches reference unknown teams: {missing}")
        sys.exit(2)

    print(f"=== IFA MEMORIAL CUP LOAD ({'dry-run' if args.dry_run else 'WRITE'}) ===")
    print(f"  base: {base}")
    print(f"  tournament: {TOURNAMENT_NAME}  ({TOURNAMENT_START} → {TOURNAMENT_END}, U14)")
    print(f"  teams: {len(TEAMS)}")
    print(f"  matches: {len(MATCHES)}  (all group_stage in '{TOURNAMENT_GROUP_LABEL}')")

    with httpx.Client(timeout=60) as c:
        # ── Tournament: lookup-first ──
        r = c.get(f"{base}/api/admin/tournaments", headers=headers)
        r.raise_for_status()
        existing_tournaments = {t["name"]: t for t in r.json()}
        if TOURNAMENT_NAME in existing_tournaments:
            tournament_id = existing_tournaments[TOURNAMENT_NAME]["id"]
            print(f"\n[tournament] exists in target: id={tournament_id}")
        else:
            print("\n[tournament] NOT FOUND — would create new")
            if args.write:
                payload = {
                    "name": TOURNAMENT_NAME,
                    "start_date": TOURNAMENT_START,
                    "end_date": TOURNAMENT_END,
                    "location": TOURNAMENT_LOCATION,
                    "age_group_ids": [AGE_GROUP_ID_U14],
                    "description": TOURNAMENT_DESC,
                }
                r = c.post(f"{base}/api/admin/tournaments", json=payload, headers=headers)
                r.raise_for_status()
                tournament_id = r.json()["id"]
                print(f"[tournament] CREATED id={tournament_id}")
            else:
                tournament_id = None  # dry-run: keep going so team lookups print

        # ── Clubs: pull full index once so we can match by name ──
        r = c.get(f"{base}/api/clubs", params={"include_teams": "false"}, headers=headers)
        r.raise_for_status()
        club_id_by_name: dict[str, int] = {club["name"]: club["id"] for club in r.json()}

        # ── Resolve each team. Two-step lookup:
        #   1. Schedule alias → canonical team name (e.g. "IFA U14 MLS NEXT HG" → "IFA")
        #   2. Look that name up via /api/admin/teams/lookup; use its id.
        # If unmapped + lookup-miss → plan a create against the matching
        # parent club (existing or new).
        team_id_by_name: dict[str, int] = {}
        plan_alias_hit: list[tuple[str, str]] = []          # (schedule_name, canonical_name)
        plan_existing: list[str] = []                       # exact-name hit, no alias needed
        plan_new_team_existing_club: list[tuple[str, str]] = []
        plan_new_team_new_club: list[str] = []
        for name in TEAMS:
            canonical = SCHEDULE_TEAM_TO_EXISTING_TEAM.get(name, name)
            r = c.get(
                f"{base}/api/admin/teams/lookup",
                params={"name": canonical},
                headers=headers,
            )
            if r.status_code == 200 and r.json().get("exact"):
                team_id_by_name[name] = r.json()["exact"]["id"]
                if canonical == name:
                    plan_existing.append(name)
                else:
                    plan_alias_hit.append((name, canonical))
                continue
            club_name = NEW_TEAM_PARENT_CLUB.get(name, name)
            if club_name in club_id_by_name:
                plan_new_team_existing_club.append((name, club_name))
            else:
                plan_new_team_new_club.append(name)

        total_resolved = len(plan_existing) + len(plan_alias_hit)
        print(f"\n[teams] existing (reused): {total_resolved}/{len(TEAMS)}")
        for t in plan_existing:
            print(f"    {t}  →  team id={team_id_by_name[t]} (exact match)")
        for sched, canon in plan_alias_hit:
            print(f"    {sched}  →  team '{canon}' id={team_id_by_name[sched]} (alias)")
        if plan_new_team_existing_club:
            print("[teams] need create (reusing existing club):")
            for t, c_ in plan_new_team_existing_club:
                print(f"    {t}  →  club '{c_}' (id={club_id_by_name[c_]})")
        if plan_new_team_new_club:
            print(f"[teams] need create (new club): {plan_new_team_new_club}")

        if args.dry_run:
            print(f"\n[matches] would create {len(MATCHES)} matches (not idempotent — single shot)")
            print("Re-run with --write to apply.")
            return

        # ── Create missing teams ──
        stats: dict[str, int] = defaultdict(int)
        for name in plan_new_team_new_club + [t for t, _ in plan_new_team_existing_club]:
            club_name = NEW_TEAM_PARENT_CLUB.get(name, name)
            club_id = club_id_by_name.get(club_name)
            if club_id is None:
                club_r = c.post(
                    f"{base}/api/clubs",
                    json={"name": club_name, "city": "—", "description": f"{club_name} (IFA Cup 2026)"},
                    headers=headers,
                )
                if club_r.status_code != 200:
                    print(f"ERR club {club_name}: {club_r.status_code} {club_r.text[:200]}")
                    stats["club_errors"] += 1
                    continue
                club_id = club_r.json()["id"]
                club_id_by_name[club_name] = club_id
                stats["club_created"] += 1

            team_r = c.post(
                f"{base}/api/teams",
                json={
                    "name": name,
                    "city": "—",
                    "age_group_ids": [AGE_GROUP_ID_U14],
                    "club_id": club_id,
                    "academy_team": False,
                },
                headers=headers,
            )
            if team_r.status_code != 200:
                print(f"ERR team {name}: {team_r.status_code} {team_r.text[:200]}")
                stats["team_errors"] += 1
                continue
            body = team_r.json()
            if body.get("team"):
                team_id_by_name[name] = body["team"]["id"]
                stats["team_created"] += 1

        # ── Create matches ──
        # CRITICAL: opponent_name must be the *canonical* team name (post-alias).
        # The backend's get_or_create_opponent_team does only exact-name match,
        # with no alias awareness. If we pass the verbose schedule name here,
        # it'll create an orphan duplicate team with no club_id even though
        # we already resolved the team_id on the script side.
        for source_id, home, away, match_date, kickoff_utc, venue in MATCHES:
            home_id = team_id_by_name.get(home)
            if home_id is None or away not in team_id_by_name:
                print(f"SKIP {source_id}: missing team id ({home} or {away})")
                stats["match_skipped"] += 1
                continue
            del venue  # matches table has no venue column yet — drop silently
            canonical_away = SCHEDULE_TEAM_TO_EXISTING_TEAM.get(away, away)
            payload = {
                "our_team_id": home_id,
                "opponent_name": canonical_away,
                "match_date": match_date,
                "age_group_id": AGE_GROUP_ID_U14,
                "season_id": SEASON_ID,
                "is_home": True,
                "scheduled_kickoff": kickoff_utc,
                "tournament_round": "group_stage",
                "tournament_group": TOURNAMENT_GROUP_LABEL,
                "match_status": "scheduled",
            }
            r = c.post(
                f"{base}/api/admin/tournaments/{tournament_id}/matches",
                json=payload,
                headers=headers,
            )
            if r.status_code in (200, 201):
                stats["match_created"] += 1
            else:
                print(f"ERR match {source_id}: {r.status_code} {r.text[:200]}")
                stats["match_errors"] += 1

    print("\n=== RESULTS ===")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
