"""
Database Schema Query Tool

Enables agents to understand the MT database structure:
- Table schemas and columns
- Foreign key relationships
- Required vs optional fields
- Data types and constraints

Used by Mocker agent to generate constraint-aware test data.
"""

import os
from typing import Dict, List, Any, Optional
from crewai.tools import BaseTool
from supabase import create_client, Client


class QuerySchemaTool(BaseTool):
    """Tool to query Supabase database schema and relationships"""

    name: str = "query_schema"
    description: str = (
        "Query the Supabase database schema to understand table structures, "
        "foreign key relationships, required fields, and data constraints. "
        "Use this to generate valid test data that respects database constraints. "
        "Returns detailed schema information for specified tables."
    )

    def _run(self, table_name: Optional[str] = None) -> str:
        """
        Query database schema information

        Args:
            table_name: Specific table to query (optional). If None, returns all tables.

        Returns:
            Formatted string with schema information
        """
        try:
            # Get Supabase credentials from environment
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

            if not supabase_url or not supabase_key:
                return (
                    "❌ Error: Supabase credentials not found. "
                    "Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env.local"
                )

            # Create Supabase client
            supabase: Client = create_client(supabase_url, supabase_key)

            # Query information schema for table details
            if table_name:
                return self._get_table_schema(supabase, table_name)
            else:
                return self._get_all_tables(supabase)

        except Exception as e:
            return f"❌ Error querying schema: {e}"

    def _get_all_tables(self, supabase: Client) -> str:
        """Get list of all tables in the database"""
        try:
            # Query information_schema.tables
            result = supabase.rpc(
                "get_all_tables",
                {}
            ).execute()

            if result.data:
                output = ["📊 Database Tables:\n"]
                for table in result.data:
                    output.append(f"  • {table['table_name']}")
                return "\n".join(output)
            else:
                # Fallback: Known MT tables
                tables = [
                    "teams", "matches", "clubs", "leagues", "divisions",
                    "age_groups", "seasons", "match_types", "team_mappings",
                    "team_match_types", "user_profiles", "positions"
                ]
                output = ["📊 Known Database Tables:\n"]
                for table in tables:
                    output.append(f"  • {table}")
                return "\n".join(output)

        except Exception as e:
            return f"❌ Error getting tables: {e}"

    def _get_table_schema(self, supabase: Client, table_name: str) -> str:
        """Get detailed schema for a specific table"""
        try:
            # For now, return hardcoded schema for key tables
            # TODO: Query information_schema dynamically when RPC available

            schemas = {
                "matches": {
                    "columns": [
                        {"name": "id", "type": "bigint", "required": False, "note": "Auto-generated"},
                        {"name": "home_team_id", "type": "bigint", "required": True, "fk": "teams.id"},
                        {"name": "away_team_id", "type": "bigint", "required": True, "fk": "teams.id"},
                        {"name": "match_date", "type": "date", "required": True},
                        {"name": "home_score", "type": "integer", "required": False},
                        {"name": "away_score", "type": "integer", "required": False},
                        {"name": "season_id", "type": "bigint", "required": True, "fk": "seasons.id"},
                        {"name": "age_group_id", "type": "bigint", "required": True, "fk": "age_groups.id"},
                        {"name": "division_id", "type": "bigint", "required": False, "fk": "divisions.id"},
                        {"name": "match_type_id", "type": "bigint", "required": False, "fk": "match_types.id"},
                        {"name": "external_id", "type": "text", "required": False},
                        {"name": "created_at", "type": "timestamp", "required": False, "note": "Auto-generated"},
                    ],
                    "constraints": [
                        "home_team_id != away_team_id",
                        "match_date must be within season date range",
                    ]
                },
                "teams": {
                    "columns": [
                        {"name": "id", "type": "bigint", "required": False, "note": "Auto-generated"},
                        {"name": "name", "type": "text", "required": True},
                        {"name": "club_id", "type": "bigint", "required": False, "fk": "clubs.id"},
                        {"name": "age_group_id", "type": "bigint", "required": False, "fk": "age_groups.id"},
                        {"name": "division_id", "type": "bigint", "required": False, "fk": "divisions.id"},
                        {"name": "external_id", "type": "text", "required": False},
                    ]
                },
                "clubs": {
                    "columns": [
                        {"name": "id", "type": "bigint", "required": False, "note": "Auto-generated"},
                        {"name": "name", "type": "text", "required": True},
                        {"name": "league_id", "type": "bigint", "required": False, "fk": "leagues.id"},
                    ]
                },
                "seasons": {
                    "columns": [
                        {"name": "id", "type": "bigint", "required": False, "note": "Auto-generated"},
                        {"name": "name", "type": "text", "required": True},
                        {"name": "start_date", "type": "date", "required": True},
                        {"name": "end_date", "type": "date", "required": True},
                        {"name": "is_active", "type": "boolean", "required": False, "note": "Default: true"},
                    ]
                },
                "age_groups": {
                    "columns": [
                        {"name": "id", "type": "bigint", "required": False, "note": "Auto-generated"},
                        {"name": "name", "type": "text", "required": True},
                        {"name": "display_order", "type": "integer", "required": False},
                    ]
                }
            }

            if table_name not in schemas:
                return f"❌ Schema not available for table: {table_name}\nKnown tables: {', '.join(schemas.keys())}"

            schema = schemas[table_name]
            output = [f"\n📊 Schema for table: {table_name}\n"]
            output.append("Columns:")

            for col in schema["columns"]:
                required = "REQUIRED" if col["required"] else "optional"
                fk = f" (FK → {col['fk']})" if col.get("fk") else ""
                note = f" [{col['note']}]" if col.get("note") else ""
                output.append(f"  • {col['name']}: {col['type']} ({required}){fk}{note}")

            if schema.get("constraints"):
                output.append("\nConstraints:")
                for constraint in schema["constraints"]:
                    output.append(f"  • {constraint}")

            return "\n".join(output)

        except Exception as e:
            return f"❌ Error getting schema for {table_name}: {e}"


# Export for tool registration
__all__ = ["QuerySchemaTool"]
