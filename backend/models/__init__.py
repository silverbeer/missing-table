"""
Pydantic models for data validation and serialization.

All models are organized by domain for better maintainability.
"""

# Auth models
from .auth import (
    AdminPlayerTeamAssignment,
    AdminPlayerTeamEnd,
    AdminPlayerUpdate,
    PlayerCustomization,
    PlayerHistoryCreate,
    PlayerHistoryUpdate,
    ProfilePhotoSlot,
    RefreshTokenRequest,
    RoleUpdate,
    UserLogin,
    UserProfile,
    UserProfileUpdate,
    UserSignup,
)

# Club models
from .clubs import Club, ClubData, ClubWithTeams, TeamData, load_clubs_from_json

# League/Division models
from .leagues import (
    DivisionCreate,
    DivisionUpdate,
    League,
    LeagueCreate,
    LeagueUpdate,
)

# Live match models
from .live_match import (
    GoalEvent,
    LiveMatchClock,
    LiveMatchState,
    LiveMatchSummary,
    MatchEventResponse,
    MessageEvent,
)

# Match models
from .matches import EnhancedMatch, MatchPatch, MatchSubmissionData

# Roster models
from .roster import (
    BulkRenumberRequest,
    BulkRosterCreate,
    BulkRosterPlayer,
    JerseyNumberUpdate,
    RenumberEntry,
    RosterPlayerCreate,
    RosterPlayerResponse,
    RosterPlayerUpdate,
)

# Season/AgeGroup models
from .seasons import AgeGroupCreate, AgeGroupUpdate, SeasonCreate, SeasonUpdate

# Team models
from .teams import Team, TeamMappingCreate, TeamMatchTypeMapping, TeamUpdate

# Note: MatchData has Pydantic compatibility issues, import directly if needed
# from .match_data import MatchData

__all__ = [
    "AdminPlayerTeamAssignment",
    "AdminPlayerTeamEnd",
    "AdminPlayerUpdate",
    "AgeGroupCreate",
    "AgeGroupUpdate",
    "BulkRenumberRequest",
    "BulkRosterCreate",
    "BulkRosterPlayer",
    # Clubs
    "Club",
    "ClubData",
    "ClubWithTeams",
    "DivisionCreate",
    "DivisionUpdate",
    # Matches
    "EnhancedMatch",
    "GoalEvent",
    "JerseyNumberUpdate",
    # Leagues
    "League",
    "LeagueCreate",
    "LeagueUpdate",
    # Live Match
    "LiveMatchClock",
    "LiveMatchState",
    "LiveMatchSummary",
    "MatchEventResponse",
    "MatchPatch",
    "MatchSubmissionData",
    "MessageEvent",
    "PlayerCustomization",
    "PlayerHistoryCreate",
    "PlayerHistoryUpdate",
    "ProfilePhotoSlot",
    "RefreshTokenRequest",
    "RenumberEntry",
    "RoleUpdate",
    # Roster
    "RosterPlayerCreate",
    "RosterPlayerResponse",
    "RosterPlayerUpdate",
    # Seasons
    "SeasonCreate",
    "SeasonUpdate",
    # Teams
    "Team",
    "TeamData",
    "TeamMappingCreate",
    "TeamMatchTypeMapping",
    "TeamUpdate",
    "UserLogin",
    "UserProfile",
    "UserProfileUpdate",
    # Auth
    "UserSignup",
    "load_clubs_from_json",
]
