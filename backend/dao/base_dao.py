"""
Base Data Access Object for MissingTable.

Provides common functionality and connection management for all DAOs.
All domain-specific DAOs should inherit from BaseDAO.

## Caching

Two decorators provide clean caching for DAO methods:

### @dao_cache - Cache read operations

    @dao_cache("teams:all")
    def get_all_teams(self):
        return self.client.table("teams").select("*").execute().data

    @dao_cache("teams:club:{club_id}")
    def get_club_teams(self, club_id: int):
        return self.client.table("teams").eq("club_id", club_id).execute().data

The decorator:
1. Builds cache key from pattern (substituting {arg_name} with actual values)
2. Checks Redis - returns cached data if found
3. On miss - runs method, caches result, returns it

### @invalidates_cache - Clear cache after writes

    @invalidates_cache("mt:dao:teams:*")
    def add_team(self, name: str, city: str):
        return self.client.table("teams").insert({...}).execute()

After successful completion, clears all keys matching the pattern(s).
"""

import functools
import inspect
import json
import os
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from supabase import Client

logger = structlog.get_logger()

# Shared Redis client for all DAOs
_redis_client = None


def get_redis_client():
    """Get sync Redis client for DAO-level caching.

    Returns a shared Redis client instance, or None if caching is disabled
    or Redis is unavailable. Gracefully degrades - app continues without cache.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    if os.getenv("CACHE_ENABLED", "false").lower() != "true":
        return None

    try:
        import redis

        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.from_url(url, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception as e:
        logger.warning("dao_redis_connection_failed", error=str(e))
        return None


def clear_cache(pattern: str) -> int:
    """Clear cache entries matching a pattern.

    Args:
        pattern: Redis key pattern (e.g., "mt:dao:clubs:*")

    Returns:
        Number of keys deleted
    """
    redis_client = get_redis_client()
    if not redis_client:
        return 0
    try:
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match=pattern, count=100)
            if keys:
                deleted += redis_client.delete(*keys)
            if cursor == 0:
                break
        if deleted > 0:
            logger.info("dao_cache_cleared", pattern=pattern, deleted=deleted)
        return deleted
    except Exception as e:
        logger.warning("dao_cache_clear_error", pattern=pattern, error=str(e))
        return 0


def cache_get(key: str):
    """Get a value from cache.

    Args:
        key: Cache key

    Returns:
        Deserialized value or None if not found/error
    """
    redis_client = get_redis_client()
    if not redis_client:
        return None
    try:
        cached = redis_client.get(key)
        if cached:
            logger.info("dao_cache_hit", key=key)
            return json.loads(cached)
    except Exception as e:
        logger.warning("dao_cache_get_error", key=key, error=str(e))
    return None


def cache_set(key: str, value, ttl: int = 86400) -> bool:
    """Set a value in cache.

    Args:
        key: Cache key
        value: Value to cache (will be JSON serialized)
        ttl: Time to live in seconds (default 24 hours)

    Returns:
        True if successful, False otherwise
    """
    redis_client = get_redis_client()
    if not redis_client:
        return False
    try:
        redis_client.setex(key, ttl, json.dumps(value, default=str))
        logger.info("dao_cache_set", key=key)
        return True
    except Exception as e:
        logger.warning("dao_cache_set_error", key=key, error=str(e))
        return False


# =============================================================================
# CACHING DECORATORS
# =============================================================================


def dao_cache(key_pattern: str, ttl: int = 86400):
    """Decorator to cache DAO method results.

    Args:
        key_pattern: Cache key pattern with optional {arg} placeholders.
                     e.g., "teams:all" or "teams:club:{club_id}"
        ttl: Time to live in seconds (default 24 hours)

    Example:
        @dao_cache("teams:club:{club_id}")
        def get_club_teams(self, club_id: int):
            return self.client.table("teams").eq("club_id", club_id).execute().data

    How it works:
        1. When get_club_teams(club_id=5) is called
        2. Decorator builds key: "mt:dao:teams:club:5"
        3. Checks Redis for cached data
        4. If found: returns cached data (method never runs)
        5. If not found: runs method, caches result, returns it
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Build cache key by substituting {arg_name} with actual values
            # Get parameter names from function signature (skip 'self')
            sig = inspect.signature(func)
            param_names = list(sig.parameters.keys())[1:]

            # Map positional args to their names
            key_values = dict(zip(param_names, args, strict=False))
            key_values.update(kwargs)

            # Build full cache key: mt:dao:{pattern with substitutions}
            try:
                cache_key = f"mt:dao:{key_pattern.format(**key_values)}"
            except KeyError as e:
                # If pattern has placeholder not in args, skip caching
                logger.warning("dao_cache_key_error", pattern=key_pattern, missing=str(e))
                return func(self, *args, **kwargs)

            # Try to get from cache
            cached = cache_get(cache_key)
            if cached is not None:
                return cached

            # Cache miss - run the actual method
            logger.debug("dao_cache_miss", key=cache_key, method=func.__name__)
            result = func(self, *args, **kwargs)

            # Cache the result (only if not None)
            if result is not None:
                cache_set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


def invalidates_cache(*patterns: str):
    """Decorator to clear cache after a write operation succeeds.

    Args:
        *patterns: One or more cache key patterns to clear.
                   e.g., "mt:dao:teams:*", "mt:dao:clubs:*"

    Example:
        @invalidates_cache("mt:dao:teams:*")
        def add_team(self, name: str, city: str):
            return self.client.table("teams").insert({...}).execute()

        @invalidates_cache("mt:dao:teams:*", "mt:dao:clubs:*")
        def update_team_club(self, team_id: int, club_id: int):
            ...

    How it works:
        1. Runs the wrapped method
        2. If successful (no exception), clears all keys matching each pattern
        3. Returns the method's result
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Run the actual method first
            result = func(self, *args, **kwargs)

            # On success, invalidate cache patterns
            for pattern in patterns:
                clear_cache(pattern)

            return result

        return wrapper

    return decorator


class BaseDAO:
    """Base DAO with shared connection logic and common utilities."""

    def __init__(self, connection_holder):
        """
        Initialize with a SupabaseConnection.

        Args:
            connection_holder: SupabaseConnection instance

        Raises:
            TypeError: If connection_holder is not a SupabaseConnection
        """
        from dao.match_dao import SupabaseConnection

        if not isinstance(connection_holder, SupabaseConnection):
            raise TypeError("connection_holder must be a SupabaseConnection instance")

        self.connection_holder = connection_holder
        self.client: Client = connection_holder.get_client()

    def execute_query(self, query, operation_name: str = "database operation"):
        """
        Execute a Supabase query with common error handling.

        Args:
            query: Supabase query object (result of .select(), .insert(), etc.)
            operation_name: Description of the operation for logging

        Returns:
            Query response data

        Raises:
            Exception: Re-raises any database errors after logging
        """
        try:
            response = query.execute()
            return response
        except Exception as e:
            logger.exception(
                f"Error during {operation_name}",
                operation=operation_name,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    def safe_execute(self, query, operation_name: str = "database operation", default=None):
        """
        Execute a query with error handling that returns a default value on error.

        Useful for non-critical queries where you want to continue execution
        even if the query fails.

        Args:
            query: Supabase query object
            operation_name: Description of the operation for logging
            default: Value to return if query fails (default: None)

        Returns:
            Query response data or default value on error
        """
        try:
            response = query.execute()
            return response
        except Exception as e:
            logger.warning(
                f"Non-critical error during {operation_name}",
                operation=operation_name,
                error_type=type(e).__name__,
                error_message=str(e),
                returning_default=default,
            )
            return default

    def get_by_id(self, table: str, record_id: int, id_field: str = "id") -> dict | None:
        """
        Generic method to get a single record by ID.

        Args:
            table: Table name
            record_id: Record ID to fetch
            id_field: Name of the ID field (default: "id")

        Returns:
            dict: Record data or None if not found

        Raises:
            Exception: If database query fails
        """
        try:
            response = self.client.table(table).select("*").eq(id_field, record_id).execute()
            return response.data[0] if response.data else None
        except Exception:
            logger.exception(
                f"Error fetching record from {table}",
                table=table,
                record_id=record_id,
                id_field=id_field,
            )
            raise

    def get_all(self, table: str, order_by: str | None = None) -> list[dict]:
        """
        Generic method to get all records from a table.

        Args:
            table: Table name
            order_by: Optional field name to order by

        Returns:
            list[dict]: List of records

        Raises:
            Exception: If database query fails
        """
        try:
            query = self.client.table(table).select("*")
            if order_by:
                query = query.order(order_by)
            response = query.execute()
            return response.data
        except Exception:
            logger.exception(f"Error fetching all records from {table}", table=table, order_by=order_by)
            raise

    def exists(self, table: str, field: str, value) -> bool:
        """
        Check if a record exists with the given field value.

        Args:
            table: Table name
            field: Field name to check
            value: Value to match

        Returns:
            bool: True if record exists, False otherwise
        """
        try:
            response = self.client.table(table).select("id").eq(field, value).limit(1).execute()
            return len(response.data) > 0
        except Exception:
            logger.exception(f"Error checking existence in {table}", table=table, field=field, value=value)
            return False

    def delete_by_id(self, table: str, record_id: int, id_field: str = "id") -> bool:
        """
        Generic method to delete a record by ID.

        Args:
            table: Table name
            record_id: Record ID to delete
            id_field: Name of the ID field (default: "id")

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.client.table(table).delete().eq(id_field, record_id).execute()
            logger.info(f"Deleted record from {table}", table=table, record_id=record_id)
            return True
        except Exception:
            logger.exception(f"Error deleting record from {table}", table=table, record_id=record_id)
            return False
