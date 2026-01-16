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

# Season/AgeGroup models
from .seasons import AgeGroupCreate, AgeGroupUpdate, SeasonCreate, SeasonUpdate

# Team models
from .teams import Team, TeamMappingCreate, TeamMatchTypeMapping, TeamUpdate

# Note: MatchData has Pydantic compatibility issues, import directly if needed
# from .match_data import MatchData

__all__ = [
    # Auth
    "UserSignup",
    "UserLogin",
    "UserProfile",
    "RoleUpdate",
    "UserProfileUpdate",
    "RefreshTokenRequest",
    "ProfilePhotoSlot",
    "PlayerCustomization",
    "PlayerHistoryCreate",
    "PlayerHistoryUpdate",
    "AdminPlayerUpdate",
    "AdminPlayerTeamAssignment",
    "AdminPlayerTeamEnd",
    # Matches
    "EnhancedMatch",
    "MatchPatch",
    "MatchSubmissionData",
    # Live Match
    "LiveMatchClock",
    "GoalEvent",
    "MessageEvent",
    "MatchEventResponse",
    "LiveMatchState",
    "LiveMatchSummary",
    # Teams
    "Team",
    "TeamUpdate",
    "TeamMatchTypeMapping",
    "TeamMappingCreate",
    # Clubs
    "Club",
    "ClubWithTeams",
    "ClubData",
    "TeamData",
    "load_clubs_from_json",
    # Leagues
    "League",
    "LeagueCreate",
    "LeagueUpdate",
    "DivisionCreate",
    "DivisionUpdate",
    # Seasons
    "SeasonCreate",
    "SeasonUpdate",
    "AgeGroupCreate",
    "AgeGroupUpdate",
]
