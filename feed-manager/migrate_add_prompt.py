#!/usr/bin/env python3
"""
Migration script to add the 'prompt' column to the Feed table.
Run this from the feed-manager directory.
"""

import sqlite3
import sys

def migrate_add_prompt_column():
    try:
        # Connect to the database
        conn = sqlite3.connect('feeds.db')
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(feed)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'prompt' in columns:
            print("✓ Column 'prompt' already exists. No migration needed.")
            return
        
        # Add the prompt column
        print("Adding 'prompt' column to feed table...")
        cursor.execute("ALTER TABLE feed ADD COLUMN prompt TEXT NULL")
        conn.commit()
        
        print("✓ Migration successful! The 'prompt' column has been added.")
        
    except sqlite3.Error as e:
        print(f"✗ Database error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate_add_prompt_column()
