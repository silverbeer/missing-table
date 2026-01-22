"""
Test Data Factories using Faker

This module provides factory functions to generate deterministic test data
for all entity types in the Missing Table application.

Usage:
    from tests.fixtures.factories import TeamFactory, MatchFactory, UserFactory

    # Create a test team with default values
    team = TeamFactory.create()

    # Create a test team with custom values
    team = TeamFactory.create(name="Custom Team", city="Boston, MA")

    # Create multiple teams
    teams = TeamFactory.create_batch(5)

    # Build team data without persisting (for API tests)
    team_data = TeamFactory.build()
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from faker import Faker

# Initialize Faker with seed for reproducibility
fake = Faker()
Faker.seed(42)  # Deterministic test data


class BaseFactory:
    """Base factory class with common utilities."""

    @classmethod
    def reset_seed(cls, seed: int = 42):
        """Reset Faker seed for deterministic tests."""
        Faker.seed(seed)

    @classmethod
    def load_seed_data(cls, filename: str) -> dict[str, Any]:
        """Load seed data from JSON file."""
        fixtures_dir = Path(__file__).parent / "data"
        file_path = fixtures_dir / filename

        with open(file_path) as f:
            return json.load(f)


class ReferenceDataFactory(BaseFactory):
    """Factory for reference data (age groups, divisions, seasons, etc.)."""

    @classmethod
    def age_group(cls, **kwargs) -> dict[str, Any]:
        """Create age group data."""
        defaults = {
            "id": fake.random_int(min=1, max=100),
            "name": fake.random_element(["U13", "U14", "U15", "U16", "U17", "U19"]),
            "description": fake.sentence(),
        }
        defaults.update(kwargs)
        return defaults

    @classmethod
    def division(cls, **kwargs) -> dict[str, Any]:
        """Create division data."""
        defaults = {
            "id": fake.random_int(min=1, max=100),
            "name": fake.random_element(["Premier", "Division 1", "Division 2", "Division 3"]),
            "level": fake.random_int(min=0, max=3),
        }
        defaults.update(kwargs)
        return defaults

    @classmethod
    def season(cls, **kwargs) -> dict[str, Any]:
        """Create season data."""
        year = fake.year()
        defaults = {
            "id": fake.random_int(min=1, max=100),
            "name": f"{year}-{int(year) + 1}",
            "start_date": f"{year}-08-01",
            "end_date": f"{int(year) + 1}-05-31",
            "is_active": fake.boolean(),
        }
        defaults.update(kwargs)
        return defaults

    @classmethod
    def match_type(cls, **kwargs) -> dict[str, Any]:
        """Create match type data."""
        defaults = {
            "id": fake.random_int(min=1, max=100),
            "name": fake.random_element(["League", "Cup", "Friendly", "Playoff"]),
            "description": fake.sentence(),
        }
        defaults.update(kwargs)
        return defaults

    @classmethod
    def load_all(cls) -> dict[str, list[dict[str, Any]]]:
        """Load all reference data from seed file."""
        return cls.load_seed_data("reference_data.json")


class TeamFactory(BaseFactory):
    """Factory for creating test team data."""

    @classmethod
    def build(cls, **kwargs) -> dict[str, Any]:
        """Build team data without persisting."""
        defaults = {
            "id": fake.random_int(min=1, max=10000),
            "name": f"{fake.city()} {fake.random_element(['FC', 'United', 'Strikers', 'Eagles', 'Raiders'])}",
            "city": fake.city() + ", " + fake.state_abbr(),
            "age_group_id": fake.random_int(min=1, max=6),
            "division_id": fake.random_int(min=1, max=4),
            "season_id": 1,  # Default to current season
            "coach": fake.name(),
            "contact_email": fake.email(),
        }
        defaults.update(kwargs)
        return defaults

    @classmethod
    def create(cls, **kwargs) -> dict[str, Any]:
        """Create team data (alias for build - actual persistence handled by tests)."""
        return cls.build(**kwargs)

    @classmethod
    def create_batch(cls, count: int, **kwargs) -> list[dict[str, Any]]:
        """Create multiple teams."""
        return [cls.create(**kwargs) for _ in range(count)]

    @classmethod
    def load_seeds(cls) -> list[dict[str, Any]]:
        """Load team seed data from JSON file."""
        data = cls.load_seed_data("teams.json")
        return data.get("teams", [])


class MatchFactory(BaseFactory):
    """Factory for creating test match data."""

    @classmethod
    def build(cls, **kwargs) -> dict[str, Any]:
        """Build match data without persisting."""
        match_date = fake.date_between(start_date="-30d", end_date="+30d")
        defaults = {
            "id": fake.random_int(min=1, max=10000),
            "match_date": match_date.isoformat(),
            "home_team_id": fake.random_int(min=1, max=100),
            "away_team_id": fake.random_int(min=1, max=100),
            "home_score": fake.random_int(min=0, max=5) if fake.boolean(chance_of_getting_true=70) else None,
            "away_score": fake.random_int(min=0, max=5) if fake.boolean(chance_of_getting_true=70) else None,
            "season_id": 1,
            "age_group_id": fake.random_int(min=1, max=6),
            "match_type_id": fake.random_int(min=1, max=4),
            "division_id": fake.random_int(min=1, max=4),
            "venue": fake.city() + " Stadium",
            "scheduled_time": fake.time(),
        }
        defaults.update(kwargs)
        return defaults

    @classmethod
    def create(cls, **kwargs) -> dict[str, Any]:
        """Create match data (alias for build)."""
        return cls.build(**kwargs)

    @classmethod
    def create_batch(cls, count: int, **kwargs) -> list[dict[str, Any]]:
        """Create multiple matches."""
        return [cls.create(**kwargs) for _ in range(count)]

    @classmethod
    def upcoming(cls, days: int = 7, **kwargs) -> dict[str, Any]:
        """Create upcoming match data."""
        match_date = datetime.now() + timedelta(days=fake.random_int(min=1, max=days))
        return cls.build(match_date=match_date.date().isoformat(), home_score=None, away_score=None, **kwargs)

    @classmethod
    def completed(cls, **kwargs) -> dict[str, Any]:
        """Create completed match data with scores."""
        match_date = datetime.now() - timedelta(days=fake.random_int(min=1, max=30))
        return cls.build(
            match_date=match_date.date().isoformat(),
            home_score=fake.random_int(min=0, max=5),
            away_score=fake.random_int(min=0, max=5),
            **kwargs,
        )


class UserFactory(BaseFactory):
    """Factory for creating test user data."""

    @classmethod
    def build(cls, **kwargs) -> dict[str, Any]:
        """Build user data without persisting."""
        first_name = fake.first_name()
        last_name = fake.last_name()
        defaults = {
            "id": fake.uuid4(),
            "email": fake.email(),
            "display_name": f"{first_name} {last_name}",
            "role": "user",
        }
        defaults.update(kwargs)
        return defaults

    @classmethod
    def create(cls, **kwargs) -> dict[str, Any]:
        """Create user data (alias for build)."""
        return cls.build(**kwargs)

    @classmethod
    def admin(cls, **kwargs) -> dict[str, Any]:
        """Create admin user data."""
        return cls.build(role="admin", **kwargs)

    @classmethod
    def team_manager(cls, **kwargs) -> dict[str, Any]:
        """Create team manager user data."""
        return cls.build(role="team_manager", **kwargs)

    @classmethod
    def regular_user(cls, **kwargs) -> dict[str, Any]:
        """Create regular user data."""
        return cls.build(role="user", **kwargs)

    @classmethod
    def load_seeds(cls) -> list[dict[str, Any]]:
        """Load user seed data from JSON file."""
        data = cls.load_seed_data("users.json")
        return data.get("users", [])


class AuthFactory(BaseFactory):
    """Factory for creating authentication-related test data."""

    @classmethod
    def credentials(cls, **kwargs) -> dict[str, str]:
        """Create login credentials."""
        defaults = {"email": fake.email(), "password": "TestPassword123!"}
        defaults.update(kwargs)
        return defaults

    @classmethod
    def jwt_token(cls, **kwargs) -> str:
        """Create mock JWT token for testing."""
        # This is a mock token for testing - not a real JWT
        return f"mock_jwt_token_{fake.uuid4()}"

    @classmethod
    def auth_headers(cls, token: str | None = None) -> dict[str, str]:
        """Create authentication headers."""
        if token is None:
            token = cls.jwt_token()
        return {"Authorization": f"Bearer {token}"}


class StandingsFactory(BaseFactory):
    """Factory for creating test standings/league table data."""

    @classmethod
    def team_stats(cls, **kwargs) -> dict[str, Any]:
        """Create team statistics for standings."""
        played = fake.random_int(min=0, max=30)
        wins = fake.random_int(min=0, max=played)
        losses = fake.random_int(min=0, max=played - wins)
        draws = played - wins - losses

        defaults = {
            "team": f"{fake.city()} FC",
            "team_id": fake.random_int(min=1, max=100),
            "played": played,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "goals_for": fake.random_int(min=0, max=played * 3),
            "goals_against": fake.random_int(min=0, max=played * 3),
            "goal_difference": 0,  # Calculated below
            "points": wins * 3 + draws,
        }
        defaults.update(kwargs)
        defaults["goal_difference"] = defaults["goals_for"] - defaults["goals_against"]
        return defaults

    @classmethod
    def league_table(cls, num_teams: int = 10, **kwargs) -> list[dict[str, Any]]:
        """Create complete league table with multiple teams."""
        table = [cls.team_stats(**kwargs) for _ in range(num_teams)]
        # Sort by points (descending), then goal difference
        table.sort(key=lambda x: (x["points"], x["goal_difference"]), reverse=True)
        return table


# Utility function to reset all factories
def reset_all_factories(seed: int = 42):
    """Reset all factories to use the same seed."""
    Faker.seed(seed)


# Utility function to load all seed data
def load_all_seed_data() -> dict[str, Any]:
    """Load all seed data from JSON files."""
    return {
        "reference": ReferenceDataFactory.load_all(),
        "teams": TeamFactory.load_seeds(),
        "users": UserFactory.load_seeds(),
    }


# Example usage (for documentation purposes)
if __name__ == "__main__":
    # Create a test team
    team = TeamFactory.create(name="Test United FC", city="Boston, MA")

    # Create multiple matches
    matches = MatchFactory.create_batch(5)

    # Create users with different roles
    admin = UserFactory.admin(email="admin@test.com")
    manager = UserFactory.team_manager(email="manager@test.com")
    user = UserFactory.regular_user(email="user@test.com")

    # Create a league table
    table = StandingsFactory.league_table(num_teams=8)

    # Load all seed data
    seed_data = load_all_seed_data()
