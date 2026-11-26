"""The MOTW world (motw_fakes) plus what a team dossier needs (SB-1780).

MT's default data: scraped results only, no rosters, no logged goals. Added to
the MOTW world: pro academies, a Homegrown-only team, a registered team with no
games, a test team, a friendly and tournament matches (no division, never side
ages), and a match where a side's age is recorded as playing up.
"""

from motw_fakes import CLUBS, EMPIRE, NEW_ENGLAND, NORTHEAST, TEAMS, TURNPIKE, U15, U16, deps, match, played, reg
from motw_fakes import default_matches as motw_matches
from motw_fakes import team as motw_team

from mt_ai.tools.schemas import Viewer

PRO_A, PRO_B = 10, 11  # pro academies, U15 Empire
HG_ONLY = 9  # U15 Northeast only, two League games
UNPLAYED = 12  # registered U15 New England, no games
TEST_TEAM = 14
STRONG_A, STRONG_B, FILLER_A, FILLER_B = 1, 2, 15, 16
MIXED, OTHER_ONLY = 17, 18  # registered in a league that is not Homegrown, Academy or Flex
SHOWCASE = 299

REAL = Viewer(include_test=False)
TESTER = Viewer(include_test=True)


def club(club_id: int, *, pro: bool = False, test: bool = False) -> dict:
    return {
        "id": club_id,
        "name": f"Club {club_id}",
        "timezone": "America/New_York",
        "is_test": test,
        "pro_academy": pro,
        "logo_url": f"https://cdn.example/{club_id}.png",
    }


DOSSIER_CLUBS = [
    *CLUBS,
    club(HG_ONLY),
    club(PRO_A, pro=True),
    club(PRO_B, pro=True),
    club(UNPLAYED),
    club(TEST_TEAM, test=True),
    club(FILLER_A),
    club(FILLER_B),
    club(MIXED),
    club(OTHER_ONLY),
]
OTHER_LEAGUE = {
    "age_groups": {"id": U15, "name": "U15"},
    "divisions": {"id": SHOWCASE, "name": "Showcase", "league_id": 77, "leagues": {"name": "Showcase League"}},
}

DOSSIER_TEAMS = [
    *TEAMS,
    motw_team(HG_ONLY, reg(U15, NORTHEAST)),
    motw_team(PRO_A, reg(U15, EMPIRE)),
    motw_team(PRO_B, reg(U15, EMPIRE)),
    motw_team(UNPLAYED, reg(U15, NEW_ENGLAND)),
    motw_team(TEST_TEAM, reg(U15, NORTHEAST)),
    motw_team(FILLER_A, reg(U15, TURNPIKE)),
    motw_team(FILLER_B, reg(U15, TURNPIKE)),
    motw_team(MIXED, reg(U15, NORTHEAST), OTHER_LEAGUE),
    motw_team(OTHER_ONLY, OTHER_LEAGUE),
]


def off_table(home, away, day, *, hs=None, as_=None, age=U15, mtype="Tournament", mid=None, **extra) -> dict:
    """A friendly or tournament match: no division, and (scraped) no side ages."""
    m = match(home, away, day, NORTHEAST, age=age, hs=hs, as_=as_, mtype=mtype, mid=mid)
    m.update(division_id=None, league_name=None, **extra)
    return m


def dossier_matches() -> list[dict]:
    return [
        *motw_matches(),
        # Team 1: one more (oldest) League game, so it has six League/Flex results,
        # and a newer friendly loss that form and streaks must not count.
        played(1, 2, "2026-09-05", NORTHEAST, 2, 2),
        off_table(1, 7, "2026-11-01", hs=0, as_=1, mtype="Friendly"),
        # Team 9: Homegrown only, two League games (a small sample), and a
        # tournament win over a pro academy.
        played(HG_ONLY, 3, "2026-10-04", NORTHEAST, 2, 1),
        played(6, HG_ONLY, "2026-10-11", NORTHEAST, 1, 0),
        off_table(HG_ONLY, PRO_A, "2026-10-25", hs=3, as_=2, mid=610),
        # Empire: one pro academy beats another.
        played(PRO_B, PRO_A, "2026-10-18", EMPIRE, 2, 1, mid=611),
        # Playing up. 601: team 5's U15 side recorded in a U16 match. 602: a
        # scraped U16 tournament match for team 3, registered at U15 only.
        {**match(5, 7, "2026-11-14", NORTHEAST, age=U16, mid=601), "home_age_group_id": U15},
        off_table(3, 8, "2026-11-15", age=U16, mid=602),
    ]


def ordering_matches() -> list[dict]:
    """Turnpike only, six teams: team 4 beats the leader (older) and the runner-up (newer)."""
    t = TURNPIKE
    return [
        played(STRONG_A, 3, "2026-09-05", t, 3, 0),
        played(STRONG_A, FILLER_A, "2026-09-12", t, 2, 0),
        played(STRONG_A, FILLER_B, "2026-09-19", t, 4, 0),
        played(STRONG_B, 3, "2026-09-05", t, 1, 0),
        played(STRONG_B, FILLER_A, "2026-09-12", t, 2, 1),
        played(STRONG_B, FILLER_B, "2026-09-19", t, 1, 1),
        played(4, STRONG_A, "2026-10-01", t, 1, 0, mid=701),
        played(4, STRONG_B, "2026-10-20", t, 1, 0, mid=702),
        played(3, 4, "2026-10-24", t, 1, 0),
        played(FILLER_A, 4, "2026-10-25", t, 1, 0),
        played(FILLER_B, 4, "2026-10-26", t, 1, 0),
    ]


def dossier_deps(matches=None, **kw):
    return deps(dossier_matches() if matches is None else matches, teams=DOSSIER_TEAMS, clubs=DOSSIER_CLUBS, **kw)
