#!/usr/bin/env python3
"""
Database backup script for Missing Table
Creates a timestamped backup of the current database state
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path

def backup_database():
    """Create a backup of the current database"""
    # Create backups directory if it doesn't exist
    backup_dir = Path("../backups")
    backup_dir.mkdir(exist_ok=True)
    
    # Remove old backups (keep only the 3 most recent)
    existing_backups = sorted(backup_dir.glob("missing_table_backup_*.sql"), 
                            key=lambda x: x.stat().st_mtime, 
                            reverse=True)
    
    if len(existing_backups) > 2:
        print("🧹 Removing old backups...")
        for old_backup in existing_backups[2:]:
            old_backup.unlink()
            print(f"  Removed: {old_backup.name}")
    
    # Create timestamp for backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"missing_table_backup_{timestamp}.sql"
    
    print(f"⚽ Creating database backup: {backup_file.name}")
    
    # Database connection details
    db_url = "postgresql://postgres:postgres@localhost:54322/postgres"
    
    # Run pg_dump to create backup
    try:
        subprocess.run([
            "pg_dump",
            db_url,
            "-f", str(backup_file),
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--no-comments",
            "--schema=public"
        ], check=True, capture_output=True, text=True)
        
        # Get file size
        size_mb = backup_file.stat().st_size / (1024 * 1024)
        print(f"✅ Backup created successfully: {backup_file.name} ({size_mb:.2f} MB)")
        
        # Show what tables were backed up
        with open(backup_file, 'r') as f:
            content = f.read()
            tables = []
            for line in content.split('\n'):
                if 'CREATE TABLE' in line and 'public.' in line:
                    table_name = line.split('public.')[1].split(' ')[0]
                    tables.append(table_name)
            
            if tables:
                print(f"📊 Backed up {len(tables)} tables:")
                for table in sorted(set(tables)):
                    print(f"   - {table}")
        
        return backup_file
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error creating backup: {e}")
        if e.stderr:
            print(f"   {e.stderr}")
        return None
    except FileNotFoundError:
        print("❌ Error: pg_dump not found. Please ensure PostgreSQL client tools are installed.")
        print("   On macOS: brew install postgresql")
        print("   On Ubuntu: sudo apt-get install postgresql-client")
        return None

if __name__ == "__main__":
    backup_database()