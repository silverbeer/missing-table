"""
File Writer Tool

Safely writes generated code to files:
- Test files to backend/tests/
- API client methods to backend/api_client/
- Creates backups before overwriting
- Validates Python syntax

Used by Forge agent to persist generated code.
"""

import os
import ast
import shutil
from typing import Optional
from datetime import datetime
from pathlib import Path
from crewai.tools import BaseTool


class FileWriterTool(BaseTool):
    """Tool to safely write generated code to files"""

    name: str = "write_file"
    description: str = (
        "Safely writes Python code to files with automatic backups. "
        "Validates syntax before writing. Creates directories if needed. "
        "Returns confirmation of successful write or error message."
    )

    def _run(
        self,
        file_path: str,
        content: str,
        backup: bool = True,
        validate: bool = True
    ) -> str:
        """
        Write content to a file

        Args:
            file_path: Path to file (relative to project root)
            content: Content to write
            backup: Create backup before overwriting (default: True)
            validate: Validate Python syntax before writing (default: True)

        Returns:
            Success or error message
        """
        try:
            # Get project root
            project_root = Path(__file__).parent.parent.parent
            full_path = project_root / file_path

            # Validate Python syntax if requested
            if validate and file_path.endswith(".py"):
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    return f"❌ Invalid Python syntax: {e}"

            # Create directory if it doesn't exist
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Create backup if file exists
            if backup and full_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = full_path.with_suffix(f".backup_{timestamp}{full_path.suffix}")
                shutil.copy2(full_path, backup_path)

            # Write file
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Success message
            lines = len(content.splitlines())
            return f"✅ Successfully wrote {lines} lines to {file_path}"

        except Exception as e:
            return f"❌ Error writing file: {e}"


class FileAppenderTool(BaseTool):
    """Tool to append code to existing files (e.g., api_client methods)"""

    name: str = "append_to_file"
    description: str = (
        "Appends Python code to an existing file, typically to add new methods "
        "to an existing class. Validates syntax and creates backups."
    )

    def _run(
        self,
        file_path: str,
        content: str,
        position: str = "end",
        marker: Optional[str] = None
    ) -> str:
        """
        Append content to a file

        Args:
            file_path: Path to file (relative to project root)
            content: Content to append
            position: Where to insert ("end" or "before_marker")
            marker: Line marker to insert before (if position="before_marker")

        Returns:
            Success or error message
        """
        try:
            # Get project root
            project_root = Path(__file__).parent.parent.parent
            full_path = project_root / file_path

            if not full_path.exists():
                return f"❌ File not found: {file_path}"

            # Read existing content
            with open(full_path, "r", encoding="utf-8") as f:
                existing_content = f.read()

            # Determine insertion point
            if position == "end":
                new_content = existing_content + "\n" + content
            elif position == "before_marker" and marker:
                if marker in existing_content:
                    new_content = existing_content.replace(
                        marker,
                        content + "\n" + marker
                    )
                else:
                    return f"❌ Marker not found: {marker}"
            else:
                return f"❌ Invalid position: {position}"

            # Validate Python syntax
            try:
                ast.parse(new_content)
            except SyntaxError as e:
                return f"❌ Invalid Python syntax after append: {e}"

            # Create backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = full_path.with_suffix(f".backup_{timestamp}{full_path.suffix}")
            shutil.copy2(full_path, backup_path)

            # Write updated content
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"✅ Successfully appended to {file_path}"

        except Exception as e:
            return f"❌ Error appending to file: {e}"


# Export for tool registration
__all__ = ["FileWriterTool", "FileAppenderTool"]
