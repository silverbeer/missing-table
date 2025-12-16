"""
TSC Test Configuration.

Contains all prefixes, entity names, and password patterns for TSC journey tests.
"""

import os
from dataclasses import dataclass, field


@dataclass
class TSCConfig:
    """Configuration for TSC journey tests."""

    # Test suite prefix (tsc_a_ for pytest, tsc_b_ for Bruno)
    prefix: str = "tsc_a_"

    # Base URL (configurable via environment)
    base_url: str = field(default_factory=lambda: os.getenv("BASE_URL", "http://localhost:8000"))

    # Password pattern: {username}123!
    password_suffix: str = "123!"

    # Entity names (will be prefixed)
    season_name: str = "test_season"
    age_group_name: str = "u18"
    division_name: str = "division_1"
    club_name: str = "soccer_club"
    premier_team_name: str = "premier_team"
    reserve_team_name: str = "reserve_team"

    # User names (will be prefixed)
    admin_username: str = "admin"
    club_manager_username: str = "club_mgr"
    team_manager_username: str = "team_mgr"
    player_username: str = "player"
    club_fan_username: str = "club_fan"
    team_fan_username: str = "team_fan"

    def prefixed(self, name: str) -> str:
        """Add prefix to a name."""
        return f"{self.prefix}{name}"

    def password_for(self, username: str) -> str:
        """Generate password for a username: {username}123!"""
        return f"{username}{self.password_suffix}"

    # Prefixed entity names
    @property
    def full_season_name(self) -> str:
        return self.prefixed(self.season_name)

    @property
    def full_age_group_name(self) -> str:
        return self.prefixed(self.age_group_name)

    @property
    def full_division_name(self) -> str:
        return self.prefixed(self.division_name)

    @property
    def full_club_name(self) -> str:
        return self.prefixed(self.club_name)

    @property
    def full_premier_team_name(self) -> str:
        return self.prefixed(self.premier_team_name)

    @property
    def full_reserve_team_name(self) -> str:
        return self.prefixed(self.reserve_team_name)

    # Prefixed usernames
    @property
    def full_admin_username(self) -> str:
        return self.prefixed(self.admin_username)

    @property
    def full_club_manager_username(self) -> str:
        return self.prefixed(self.club_manager_username)

    @property
    def full_team_manager_username(self) -> str:
        return self.prefixed(self.team_manager_username)

    @property
    def full_player_username(self) -> str:
        return self.prefixed(self.player_username)

    @property
    def full_club_fan_username(self) -> str:
        return self.prefixed(self.club_fan_username)

    @property
    def full_team_fan_username(self) -> str:
        return self.prefixed(self.team_fan_username)

    # Passwords
    @property
    def admin_password(self) -> str:
        return self.password_for(self.full_admin_username)

    @property
    def club_manager_password(self) -> str:
        return self.password_for(self.full_club_manager_username)

    @property
    def team_manager_password(self) -> str:
        return self.password_for(self.full_team_manager_username)

    @property
    def player_password(self) -> str:
        return self.password_for(self.full_player_username)

    @property
    def club_fan_password(self) -> str:
        return self.password_for(self.full_club_fan_username)

    @property
    def team_fan_password(self) -> str:
        return self.password_for(self.full_team_fan_username)


# Default configuration for pytest (tsc_a_ prefix)
PYTEST_CONFIG = TSCConfig(prefix="tsc_a_")

# Configuration for Bruno (tsc_b_ prefix)
BRUNO_CONFIG = TSCConfig(prefix="tsc_b_")
