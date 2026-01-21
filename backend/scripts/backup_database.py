#!/usr/bin/env python3
"""
Database backup script for Missing Table
Creates a timestamped backup of the current database state
"""

import subprocess
from datetime import datetime
from pathlib import Path


def backup_database():
    """Create a backup of the current database"""
    # Create backups directory if it doesn't exist
    backup_dir = Path("../backups")
    backup_dir.mkdir(exist_ok=True)

    # Remove old backups (keep only the 3 most recent)
    existing_backups = sorted(
        backup_dir.glob("missing_table_backup_*.sql"), key=lambda x: x.stat().st_mtime, reverse=True
    )

    if len(existing_backups) > 2:
        for old_backup in existing_backups[2:]:
            old_backup.unlink()

    # Create timestamp for backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"missing_table_backup_{timestamp}.sql"

    # Database connection details
    db_url = "postgresql://postgres:postgres@localhost:54322/postgres"

    # Run pg_dump to create backup
    try:
        subprocess.run(
            [
                "pg_dump",
                db_url,
                "-f",
                str(backup_file),
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                "--no-comments",
                "--schema=public",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        # Get file size
        backup_file.stat().st_size / (1024 * 1024)

        # Show what tables were backed up
        with open(backup_file) as f:
            content = f.read()
            tables = []
            for line in content.split("\n"):
                if "CREATE TABLE" in line and "public." in line:
                    table_name = line.split("public.")[1].split(" ")[0]
                    tables.append(table_name)

            if tables:
                for _table in sorted(set(tables)):
                    pass

        return backup_file

    except subprocess.CalledProcessError as e:
        if e.stderr:
            pass
        return None
    except FileNotFoundError:
        return None


if __name__ == "__main__":
    backup_database()
