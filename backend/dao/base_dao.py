"""
Base Data Access Object for MissingTable.

Provides common functionality and connection management for all DAOs.
All domain-specific DAOs should inherit from BaseDAO.
"""

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from supabase import Client

logger = structlog.get_logger()


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
                error_message=str(e)
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
                returning_default=default
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
                id_field=id_field
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
            logger.exception(
                f"Error fetching all records from {table}",
                table=table,
                order_by=order_by
            )
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
            logger.exception(
                f"Error checking existence in {table}",
                table=table,
                field=field,
                value=value
            )
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
            logger.info(
                f"Deleted record from {table}",
                table=table,
                record_id=record_id
            )
            return True
        except Exception:
            logger.exception(
                f"Error deleting record from {table}",
                table=table,
                record_id=record_id
            )
            return False
