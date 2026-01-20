"""
Roster Data Access Object.

Handles all database operations related to team rosters (players table):
- Roster CRUD operations
- Jersey number management
- Account linking
- Display name computation
"""

import structlog

from dao.base_dao import BaseDAO, dao_cache, invalidates_cache

logger = structlog.get_logger()

# Cache patterns for invalidation
ROSTER_CACHE_PATTERN = "mt:dao:roster:*"


class RosterDAO(BaseDAO):
    """Data access object for roster (players table) operations."""

    # === Read Operations ===

    @dao_cache("roster:team:{team_id}:season:{season_id}")
    def get_team_roster(self, team_id: int, season_id: int) -> list[dict]:
        """
        Get all roster entries for a team in a specific season.

        Args:
            team_id: Team ID
            season_id: Season ID

        Returns:
            List of player dicts with computed display_name
        """
        try:
            # Use explicit FK relationship to avoid ambiguity with created_by FK
            response = self.client.table('players').select('''
                *,
                user_profile:user_profiles!players_user_profile_id_fkey(
                    id, display_name, first_name, last_name,
                    photo_1_url, photo_2_url, photo_3_url, profile_photo_slot)
            ''').eq('team_id', team_id).eq('season_id', season_id).eq(
                'is_active', True
            ).order('jersey_number').execute()

            players = response.data or []
            # Add computed display_name to each player
            return [self._add_display_name(p) for p in players]

        except Exception as e:
            logger.error(
                "roster_get_team_error",
                team_id=team_id, season_id=season_id, error=str(e)
            )
            return []

    def get_player_by_id(self, player_id: int) -> dict | None:
        """
        Get a single roster entry by ID.

        Args:
            player_id: Player ID

        Returns:
            Player dict with computed display_name, or None if not found
        """
        try:
            response = self.client.table('players').select('''
                *,
                user_profile:user_profiles!players_user_profile_id_fkey(
                    id, display_name, first_name, last_name,
                    photo_1_url, photo_2_url, photo_3_url, profile_photo_slot)
            ''').eq('id', player_id).execute()

            if response.data and len(response.data) > 0:
                return self._add_display_name(response.data[0])
            return None

        except Exception as e:
            logger.error("roster_get_player_error", player_id=player_id, error=str(e))
            return None

    def get_player_by_jersey(
        self, team_id: int, season_id: int, jersey_number: int
    ) -> dict | None:
        """
        Get roster entry by jersey number (unique within team/season).

        Args:
            team_id: Team ID
            season_id: Season ID
            jersey_number: Jersey number to look up

        Returns:
            Player dict with computed display_name, or None if not found
        """
        try:
            response = self.client.table('players').select('''
                *,
                user_profile:user_profiles!players_user_profile_id_fkey(
                    id, display_name, first_name, last_name,
                    photo_1_url, photo_2_url, photo_3_url, profile_photo_slot)
            ''').eq('team_id', team_id).eq('season_id', season_id).eq(
                'jersey_number', jersey_number
            ).execute()

            if response.data and len(response.data) > 0:
                return self._add_display_name(response.data[0])
            return None

        except Exception as e:
            logger.error(
                "roster_get_by_jersey_error",
                team_id=team_id, season_id=season_id,
                jersey_number=jersey_number, error=str(e)
            )
            return None

    def get_player_by_user_profile_id(
        self,
        user_profile_id: str,
        team_id: int | None = None,
        season_id: int | None = None,
    ) -> dict | None:
        """
        Get roster entry linked to a user profile.

        When team_id and season_id are provided, returns the specific
        player entry for that team/season. Otherwise, returns the most
        recent active player entry.

        Args:
            user_profile_id: User profile ID (UUID)
            team_id: Optional team ID filter
            season_id: Optional season ID filter

        Returns:
            Player dict with computed display_name, or None if not found
        """
        try:
            query = self.client.table('players').select('''
                *,
                user_profile:user_profiles!players_user_profile_id_fkey(
                    id, display_name, first_name, last_name,
                    photo_1_url, photo_2_url, photo_3_url, profile_photo_slot)
            ''').eq('user_profile_id', user_profile_id).eq('is_active', True)

            if team_id is not None:
                query = query.eq('team_id', team_id)
            if season_id is not None:
                query = query.eq('season_id', season_id)

            # Order by created_at descending to get most recent
            response = query.order('created_at', desc=True).limit(1).execute()

            if response.data and len(response.data) > 0:
                return self._add_display_name(response.data[0])
            return None

        except Exception as e:
            logger.error(
                "roster_get_by_user_profile_error",
                user_profile_id=user_profile_id,
                team_id=team_id, season_id=season_id, error=str(e)
            )
            return None

    # === Create Operations ===

    @invalidates_cache(ROSTER_CACHE_PATTERN)
    def create_player(
        self,
        team_id: int,
        season_id: int,
        jersey_number: int,
        first_name: str | None = None,
        last_name: str | None = None,
        positions: list[str] | None = None,
        created_by: str | None = None,
    ) -> dict | None:
        """
        Create a new roster entry.

        Args:
            team_id: Team ID
            season_id: Season ID
            jersey_number: Jersey number (1-99, unique per team/season)
            first_name: Optional first name
            last_name: Optional last name
            positions: Optional list of position codes
            created_by: Optional user ID of creator

        Returns:
            Created player dict, or None on error
        """
        try:
            data = {
                'team_id': team_id,
                'season_id': season_id,
                'jersey_number': jersey_number,
                'is_active': True,
            }
            if first_name:
                data['first_name'] = first_name
            if last_name:
                data['last_name'] = last_name
            if positions:
                data['positions'] = positions
            if created_by:
                data['created_by'] = created_by

            response = self.client.table('players').insert(data).execute()

            if response.data and len(response.data) > 0:
                logger.info(
                    "roster_player_created",
                    player_id=response.data[0]['id'],
                    team_id=team_id,
                    jersey_number=jersey_number
                )
                return self._add_display_name(response.data[0])
            return None

        except Exception as e:
            logger.error(
                "roster_create_error",
                team_id=team_id, jersey_number=jersey_number, error=str(e)
            )
            return None

    @invalidates_cache(ROSTER_CACHE_PATTERN)
    def bulk_create_players(
        self,
        team_id: int,
        season_id: int,
        players: list[dict],
        created_by: str | None = None,
    ) -> list[dict]:
        """
        Create multiple roster entries at once.

        Args:
            team_id: Team ID
            season_id: Season ID
            players: List of dicts with jersey_number, optional first_name, last_name, positions
            created_by: Optional user ID of creator

        Returns:
            List of created player dicts
        """
        try:
            data = []
            for p in players:
                entry = {
                    'team_id': team_id,
                    'season_id': season_id,
                    'jersey_number': p['jersey_number'],
                    'is_active': True,
                }
                if p.get('first_name'):
                    entry['first_name'] = p['first_name']
                if p.get('last_name'):
                    entry['last_name'] = p['last_name']
                if p.get('positions'):
                    entry['positions'] = p['positions']
                if created_by:
                    entry['created_by'] = created_by
                data.append(entry)

            response = self.client.table('players').insert(data).execute()

            created = response.data or []
            logger.info(
                "roster_bulk_created",
                team_id=team_id,
                count=len(created)
            )
            return [self._add_display_name(p) for p in created]

        except Exception as e:
            logger.error(
                "roster_bulk_create_error",
                team_id=team_id, count=len(players), error=str(e)
            )
            return []

    # === Update Operations ===

    @invalidates_cache(ROSTER_CACHE_PATTERN)
    def update_player(
        self,
        player_id: int,
        first_name: str | None = None,
        last_name: str | None = None,
        positions: list[str] | None = None,
    ) -> dict | None:
        """
        Update a roster entry's name or positions.

        Args:
            player_id: Player ID
            first_name: New first name (None to keep current)
            last_name: New last name (None to keep current)
            positions: New positions (None to keep current)

        Returns:
            Updated player dict, or None on error
        """
        try:
            data = {}
            if first_name is not None:
                data['first_name'] = first_name or None
            if last_name is not None:
                data['last_name'] = last_name or None
            if positions is not None:
                data['positions'] = positions or []

            if not data:
                # Nothing to update
                return self.get_player_by_id(player_id)

            response = self.client.table('players').update(data).eq(
                'id', player_id
            ).execute()

            if response.data and len(response.data) > 0:
                logger.info("roster_player_updated", player_id=player_id)
                return self._add_display_name(response.data[0])
            return None

        except Exception as e:
            logger.error("roster_update_error", player_id=player_id, error=str(e))
            return None

    @invalidates_cache(ROSTER_CACHE_PATTERN)
    def update_jersey_number(
        self,
        player_id: int,
        new_number: int,
    ) -> dict | None:
        """
        Change a player's jersey number.

        Args:
            player_id: Player ID
            new_number: New jersey number (1-99)

        Returns:
            Updated player dict, or None on error (e.g., number already taken)
        """
        try:
            response = self.client.table('players').update({
                'jersey_number': new_number
            }).eq('id', player_id).execute()

            if response.data and len(response.data) > 0:
                logger.info(
                    "roster_number_updated",
                    player_id=player_id,
                    new_number=new_number
                )
                return self._add_display_name(response.data[0])
            return None

        except Exception as e:
            logger.error(
                "roster_number_update_error",
                player_id=player_id, new_number=new_number, error=str(e)
            )
            return None

    @invalidates_cache(ROSTER_CACHE_PATTERN)
    def bulk_renumber(
        self,
        team_id: int,
        season_id: int,
        changes: list[dict],
    ) -> bool:
        """
        Reassign multiple jersey numbers at once.

        Uses negative numbers as temporary placeholders to avoid uniqueness
        constraint violations during swaps.

        Args:
            team_id: Team ID
            season_id: Season ID
            changes: List of dicts with player_id and new_number

        Returns:
            True if successful, False on error
        """
        try:
            # Step 1: Set all affected players to negative numbers (temporary)
            for i, change in enumerate(changes):
                self.client.table('players').update({
                    'jersey_number': -(i + 1000)  # Negative temp value
                }).eq('id', change['player_id']).eq('team_id', team_id).eq(
                    'season_id', season_id
                ).execute()

            # Step 2: Set final numbers
            for change in changes:
                self.client.table('players').update({
                    'jersey_number': change['new_number']
                }).eq('id', change['player_id']).eq('team_id', team_id).eq(
                    'season_id', season_id
                ).execute()

            logger.info(
                "roster_bulk_renumbered",
                team_id=team_id,
                count=len(changes)
            )
            return True

        except Exception as e:
            logger.error(
                "roster_bulk_renumber_error",
                team_id=team_id, error=str(e)
            )
            return False

    @invalidates_cache(ROSTER_CACHE_PATTERN)
    def link_user_to_player(
        self,
        player_id: int,
        user_profile_id: str,
    ) -> dict | None:
        """
        Link an MT account to a roster entry.

        Called when a player accepts an invitation tied to a roster entry.

        Args:
            player_id: Player ID (roster entry)
            user_profile_id: User profile ID to link

        Returns:
            Updated player dict, or None on error
        """
        try:
            response = self.client.table('players').update({
                'user_profile_id': user_profile_id
            }).eq('id', player_id).execute()

            if response.data and len(response.data) > 0:
                logger.info(
                    "roster_user_linked",
                    player_id=player_id,
                    user_profile_id=user_profile_id
                )
                # Fetch full player with user_profile data
                return self.get_player_by_id(player_id)
            return None

        except Exception as e:
            logger.error(
                "roster_link_user_error",
                player_id=player_id,
                user_profile_id=user_profile_id,
                error=str(e)
            )
            return None

    # === Delete Operations ===

    @invalidates_cache(ROSTER_CACHE_PATTERN)
    def delete_player(self, player_id: int) -> bool:
        """
        Remove a roster entry (soft delete by setting is_active=false).

        Args:
            player_id: Player ID to remove

        Returns:
            True if successful, False on error
        """
        try:
            response = self.client.table('players').update({
                'is_active': False
            }).eq('id', player_id).execute()

            if response.data and len(response.data) > 0:
                logger.info("roster_player_deleted", player_id=player_id)
                return True
            return False

        except Exception as e:
            logger.error("roster_delete_error", player_id=player_id, error=str(e))
            return False

    @invalidates_cache(ROSTER_CACHE_PATTERN)
    def hard_delete_player(self, player_id: int) -> bool:
        """
        Permanently remove a roster entry.

        Use sparingly - soft delete (delete_player) is preferred.

        Args:
            player_id: Player ID to remove

        Returns:
            True if successful, False on error
        """
        try:
            self.client.table('players').delete().eq(
                'id', player_id
            ).execute()

            logger.info("roster_player_hard_deleted", player_id=player_id)
            return True

        except Exception as e:
            logger.error("roster_hard_delete_error", player_id=player_id, error=str(e))
            return False

    # === Helper Methods ===

    def _add_display_name(self, player: dict) -> dict:
        """
        Add computed display_name to a player dict.

        Priority:
        1. Linked user's display_name or full name
        2. Roster entry's first_name + last_name
        3. Jersey number only: "#23"

        Args:
            player: Player dict from database

        Returns:
            Player dict with display_name and has_account added
        """
        user_profile = player.get('user_profile')
        has_account = user_profile is not None and user_profile.get('id') is not None

        display_name = None

        # Try linked user's name first
        if has_account:
            if user_profile.get('display_name'):
                display_name = user_profile['display_name']
            elif user_profile.get('first_name') or user_profile.get('last_name'):
                first = user_profile.get('first_name', '')
                last = user_profile.get('last_name', '')
                display_name = f"{first} {last}".strip()

        # Fall back to roster entry's name
        if not display_name and (player.get('first_name') or player.get('last_name')):
            first = player.get('first_name', '')
            last = player.get('last_name', '')
            display_name = f"{first} {last}".strip()

        # Final fallback: jersey number only
        if not display_name:
            display_name = f"#{player['jersey_number']}"

        player['display_name'] = display_name
        player['has_account'] = has_account

        return player

    @staticmethod
    def get_display_name(player: dict) -> str:
        """
        Static helper to get display name from a player dict.

        Useful when you have a player dict and just need the name.

        Args:
            player: Player dict (may or may not have display_name computed)

        Returns:
            Display name string
        """
        if player.get('display_name'):
            return player['display_name']

        # Try roster entry name
        if player.get('first_name') or player.get('last_name'):
            return f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()

        # Jersey number only
        return f"#{player.get('jersey_number', '?')}"
