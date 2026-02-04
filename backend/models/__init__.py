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

# Lineup models
from .lineup import (
    LineupPositionEntry,
    LineupPositionResponse,
    LineupResponse,
    LineupSave,
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

# Playoff models
from .playoffs import AdvanceWinnerRequest, GenerateBracketRequest, PlayoffBracketSlot

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
    "AdvanceWinnerRequest",
    "AgeGroupCreate",
    "AgeGroupUpdate",
    "BulkRenumberRequest",
    "BulkRosterCreate",
    "BulkRosterPlayer",
    "Club",
    "ClubData",
    "ClubWithTeams",
    "DivisionCreate",
    "DivisionUpdate",
    "EnhancedMatch",
    "GenerateBracketRequest",
    "GoalEvent",
    "JerseyNumberUpdate",
    "League",
    "LeagueCreate",
    "LeagueUpdate",
    "LineupPositionEntry",
    "LineupPositionResponse",
    "LineupResponse",
    "LineupSave",
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
    "PlayoffBracketSlot",
    "ProfilePhotoSlot",
    "RefreshTokenRequest",
    "RenumberEntry",
    "RoleUpdate",
    "RosterPlayerCreate",
    "RosterPlayerResponse",
    "RosterPlayerUpdate",
    "SeasonCreate",
    "SeasonUpdate",
    "Team",
    "TeamData",
    "TeamMappingCreate",
    "TeamMatchTypeMapping",
    "TeamUpdate",
    "UserLogin",
    "UserProfile",
    "UserProfileUpdate",
    "UserSignup",
    "load_clubs_from_json",
]
