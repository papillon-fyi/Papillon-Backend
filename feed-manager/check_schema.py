#!/usr/bin/env python3
"""
Check database schema and show any missing columns.
Run this from the feed-manager directory.
"""

import sqlite3

def check_schema():
    conn = sqlite3.connect('feeds.db')
    cursor = conn.cursor()
    
    # Expected columns in Feed table based on models.py
    expected_feed_columns = [
        'id', 'uri', 'handle', 'record_name', 'display_name', 
        'description', 'prompt', 'avatar_path', 'ranking_weights',
        'blueprint_hash', 'access_jwt'
    ]
    
    # Get actual columns
    cursor.execute("PRAGMA table_info(feed)")
    actual_columns = [row[1] for row in cursor.fetchall()]
    
    print("Current Feed table columns:")
    for col in actual_columns:
        print(f"  ✓ {col}")
    
    # Find missing columns
    missing = [col for col in expected_feed_columns if col not in actual_columns]
    
    if missing:
        print(f"\n⚠ Missing columns: {', '.join(missing)}")
    else:
        print("\n✓ All expected columns present!")
    
    conn.close()

if __name__ == "__main__":
    check_schema()
