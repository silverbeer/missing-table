# ruff: noqa: T201  # this is a CLI tool; print() is the intended output channel
"""Load the 2026 MLS NEXT Cup playoff matches into Missing Table.

Inputs:
  - scripts/mlsnext-cup/sched/{championship,premier}_U{13,14,15,16,17,19}.json
    (scraped from modular11.com via Playwright; older age groups have no
    matches scheduled and their files are empty arrays)
  - backend/data/mls-next-clubs.json — division + pro_academy lookup by
    (team name, age group)

Behavior:
  - Resolves each team's division by name via the clubmap data
  - Looks up clubs and teams BEFORE create to handle the case where local
    DB has a copy from a prior backup-restore (the teams_name_club_league
    constraint isn't covered by the idempotency in PR #354)
  - Treats HTTP 200 OR 201 as match-create success (the endpoint returns
    201; an earlier version of this script tripped on that)
  - Accepts MLS Next Cup playoff matches only — TBD-vs-TBD bracket
    placeholder slots are skipped

Usage:
  # Dry run against local — shows the create plan, no writes
  cd backend && uv run python ../scripts/mlsnext-cup/load_cup.py --base http://localhost:8000 --dry-run

  # Local write
  cd backend && uv run python ../scripts/mlsnext-cup/load_cup.py --base http://localhost:8000 --write

  # Prod (after `./switch-env.sh prod` and `mt_cli login`)
  cd backend && uv run python ../scripts/mlsnext-cup/load_cup.py \\
    --base https://api.missingtable.com \\
    --division-mapping prod \\
    --tournament-name "2026 MLS NEXT Cup" \\
    --dry-run

Notes:
  - `match create` is NOT idempotent — running twice with --write will
    create duplicate matches. Always --dry-run first.
  - The cached mt_cli token in backend/.mt-cli-state.json is read for
    auth. Make sure you've logged in to the right environment.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHED_DIR = Path(__file__).resolve().parent / "sched"
CLUBMAP_FILE = REPO_ROOT / "backend" / "data" / "mls-next-clubs.json"
TOKEN_FILE = REPO_ROOT / "backend" / ".mt-cli-state.json"

# Match the schedule's bracket+age-group names to the JSON filenames.
SCHED_FILES = [
    ("Championship", "U13"), ("Championship", "U14"),
    ("Premier", "U13"),      ("Premier", "U14"),
    # U15-U19 files exist but are empty arrays (no scheduled playoff matches).
]

# Per-env division-name → division-id maps.
DIVISION_MAPS = {
    "local": {
        "Mid-Atlantic": 128, "Mid-America": 129, "Frontier": 130,
        "Northwest": 131, "Southwest": 132, "Southeast": 133,
        "Northeast": 1, "Florida": 127,
    },
    "prod": {
        "Mid-Atlantic": 190, "Mid-America": 191, "Frontier": 192,
        "Northwest": 193, "Southwest": 194, "Southeast": 195,
        "Northeast": 1, "Florida": 127,
    },
}

# Schedule team names sometimes differ slightly from the clubmap (e.g. the
# schedule uses the current abbreviated name at U13/U14 while the clubmap
# row for those age groups still has the older full name).
CLUBMAP_NAME_ALIASES = {
    "Los Angeles SC": "Los Angeles Soccer Club",
}

AGE_GROUP_TO_ID = {"U13": 1, "U14": 2, "U15": 3, "U16": 4, "U17": 5, "U19": 7}
SEASON_ID = 3  # 2025-2026


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", required=True, help="MT API base URL, e.g. http://localhost:8000")
    p.add_argument("--division-mapping", default="local", choices=DIVISION_MAPS.keys(),
                   help="Which (env, name → division_id) map to use. Verify with refdata before --write.")
    p.add_argument("--tournament-name", default="2026 MLS NEXT Cup")
    p.add_argument("--tournament-start", default="2026-05-23")
    p.add_argument("--tournament-end", default="2026-05-31")
    p.add_argument("--dry-run", action="store_true", help="Print the create plan; do not write.")
    p.add_argument("--write", action="store_true", help="Actually create rows in the target MT.")
    args = p.parse_args()
    if not args.dry_run and not args.write:
        p.error("must specify --dry-run OR --write")
    if args.dry_run and args.write:
        p.error("--dry-run and --write are mutually exclusive")
    return args


def load_token() -> str:
    state = json.loads(TOKEN_FILE.read_text())
    return state["access_token"]


def load_matches() -> list[dict]:
    rows = []
    for _bracket, _ag in SCHED_FILES:
        f = SCHED_DIR / f"{_bracket.lower()}_{_ag}.json"
        if not f.exists():
            continue
        rows.extend(json.loads(f.read_text()))
    # Drop TBD-vs-TBD placeholder slots.
    return [r for r in rows if r["home"] != "TBD" and r["away"] != "TBD"]


def load_clubmap() -> dict:
    data = json.loads(CLUBMAP_FILE.read_text())
    return {(r["team"].lower(), r["age_group"]): r for r in data["teams"]}


def resolve_clubmap(team_name: str, age_group: str, idx: dict) -> dict | None:
    alias = CLUBMAP_NAME_ALIASES.get(team_name, team_name)
    return idx.get((alias.lower(), age_group))


def parse_kickoff(date_str: str, time_str: str) -> tuple[str, str]:
    """Convert ('05/28/26', '09:00am') → (match_date='2026-05-28', kickoff='2026-05-28T15:00:00Z').

    Schedule times are local Salt Lake City (Mountain Daylight Time, UTC-6 in May).
    """
    mm, dd, yy = date_str.split("/")
    year = 2000 + int(yy)
    hr = int(time_str[:2])
    mn = int(time_str[3:5])
    ampm = time_str[5:].lower()
    if ampm == "pm" and hr != 12:
        hr += 12
    if ampm == "am" and hr == 12:
        hr = 0
    utc_hr = hr + 6  # MDT → UTC
    day_off = 0
    if utc_hr >= 24:
        utc_hr -= 24
        day_off = 1
    match_date = f"{year:04d}-{int(mm):02d}-{int(dd) + day_off:02d}"
    kickoff = f"{match_date}T{utc_hr:02d}:{mn:02d}:00Z"
    return match_date, kickoff


def main():
    args = parse_args()
    base = args.base.rstrip("/")
    div_map = DIVISION_MAPS[args.division_mapping]
    token = load_token()
    headers = {"Authorization": f"Bearer {token}"}

    matches = load_matches()
    clubmap = load_clubmap()

    # Compute per-team metadata: union of age groups + division + pro flag.
    teams_meta: dict[str, dict] = {}
    unresolved: list[tuple[str, str]] = []
    for m in matches:
        for side in ("home", "away"):
            name = m[side]
            row = resolve_clubmap(name, m["age_group"], clubmap)
            if row is None:
                unresolved.append((name, m["age_group"]))
                continue
            meta = teams_meta.setdefault(name, {
                "ages": set(), "division": row["division"], "is_pro_academy": row["is_pro_academy"],
            })
            meta["ages"].add(m["age_group"])

    if unresolved:
        print(f"UNRESOLVED ({len(unresolved)} entries) — fix CLUBMAP_NAME_ALIASES or backend/data/mls-next-clubs.json:")
        for name, ag in unresolved:
            print(f"  {name} / {ag}")
        sys.exit(1)

    plan = {
        "matches_total": len(matches),
        "unique_teams": len(teams_meta),
        "tournament_name": args.tournament_name,
        "base": base,
        "division_mapping": args.division_mapping,
    }

    print(f"=== LOAD PLAN ({'dry-run' if args.dry_run else 'WRITE'}) ===")
    for k, v in plan.items():
        print(f"  {k}: {v}")

    if args.dry_run:
        # Resolve everything via reads only.
        with httpx.Client(timeout=60) as c:
            r = c.get(f"{base}/api/admin/tournaments", headers=headers)
            r.raise_for_status()
            existing_tournaments = {t["name"]: t["id"] for t in r.json()}
        tournament_exists = args.tournament_name in existing_tournaments
        print(f"\ntournament exists in target: {tournament_exists}")
        if tournament_exists:
            print(f"  existing id: {existing_tournaments[args.tournament_name]}")

        # Probe each team for existence (cheap read).
        with httpx.Client(timeout=60) as c:
            existing_teams = 0
            missing_teams = []
            for name in sorted(teams_meta):
                r = c.get(f"{base}/api/admin/teams/lookup", params={"name": name}, headers=headers)
                if r.status_code == 200 and r.json().get("exact"):
                    existing_teams += 1
                else:
                    missing_teams.append(name)
            print(f"teams already in target: {existing_teams}/{len(teams_meta)}")
            print(f"teams that need create: {len(missing_teams)}")
            if missing_teams:
                print(f"  sample: {missing_teams[:8]}")

        print(f"\nmatches that would be created (always all {len(matches)} — match-create is NOT idempotent)")
        print("Re-run with --write to apply.")
        return

    # WRITE path.
    team_id_by_name: dict[str, int] = {}
    stats: dict[str, int] = defaultdict(int)
    with httpx.Client(timeout=60) as c:
        # Ensure tournament.
        r = c.get(f"{base}/api/admin/tournaments", headers=headers)
        r.raise_for_status()
        existing = {t["name"]: t for t in r.json()}
        if args.tournament_name in existing:
            tournament_id = existing[args.tournament_name]["id"]
            print(f"reusing tournament id={tournament_id}")
        else:
            payload = {
                "name": args.tournament_name,
                "start_date": args.tournament_start,
                "end_date": args.tournament_end,
                "age_group_ids": sorted({AGE_GROUP_TO_ID[ag] for meta in teams_meta.values() for ag in meta["ages"]}),
                "description": "MLS NEXT Cup Championship & Premier brackets (single-elimination playoffs)",
            }
            r = c.post(f"{base}/api/admin/tournaments", json=payload, headers=headers)
            r.raise_for_status()
            tournament_id = r.json()["id"]
            print(f"created tournament id={tournament_id}")

        # Resolve teams (lookup-first, fall back to create).
        for name, meta in sorted(teams_meta.items()):
            r = c.get(f"{base}/api/admin/teams/lookup", params={"name": name}, headers=headers)
            if r.status_code == 200 and r.json().get("exact"):
                team_id_by_name[name] = r.json()["exact"]["id"]
                stats["team_existing"] += 1
                continue

            club_r = c.post(f"{base}/api/clubs", json={
                "name": name, "city": "—",
                "description": f"{name} (MLS NEXT {meta['division']} Division)",
            }, headers=headers)
            if club_r.status_code != 200:
                print(f"ERR club {name}: {club_r.status_code} {club_r.text[:200]}")
                stats["club_errors"] += 1
                continue
            club_id = club_r.json()["id"]
            stats["club_created"] += 1

            team_r = c.post(f"{base}/api/teams", json={
                "name": name, "city": "—",
                "age_group_ids": sorted(AGE_GROUP_TO_ID[ag] for ag in meta["ages"]),
                "division_id": div_map[meta["division"]],
                "club_id": club_id,
                "academy_team": meta["is_pro_academy"],
            }, headers=headers)
            if team_r.status_code != 200:
                print(f"ERR team {name}: {team_r.status_code} {team_r.text[:200]}")
                stats["team_errors"] += 1
                continue
            body = team_r.json()
            if body.get("team"):
                team_id_by_name[name] = body["team"]["id"]
                stats["team_created"] += 1

        # Create matches (NOT idempotent — only run once per environment).
        for m in matches:
            home_id = team_id_by_name.get(m["home"])
            away_name = m["away"]
            if not home_id or away_name not in team_id_by_name:
                print(f"SKIP {m['match_id']}: missing team id ({m['home']} or {away_name})")
                stats["match_skipped"] += 1
                continue
            match_date, kickoff = parse_kickoff(m["date"], m["time"])
            payload = {
                "our_team_id": home_id,
                "opponent_name": away_name,
                "match_date": match_date,
                "age_group_id": AGE_GROUP_TO_ID[m["age_group"]],
                "season_id": SEASON_ID,
                "is_home": True,
                "scheduled_kickoff": kickoff,
                "tournament_round": "round_of_32",
                "tournament_group": m["bracket"],  # "Championship" or "Premier"
                "match_status": "scheduled",
            }
            r = c.post(f"{base}/api/admin/tournaments/{tournament_id}/matches", json=payload, headers=headers)
            if r.status_code in (200, 201):
                stats["match_created"] += 1
            else:
                print(f"ERR match {m['match_id']}: {r.status_code} {r.text[:200]}")
                stats["match_errors"] += 1

    print("\n=== RESULTS ===")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
