"""
Backfill torrent hashes from URLs.

Mikan torrent URLs have the format:
https://mikanani.me/Download/YYYYMMDD/{HASH}.torrent

This script extracts the hash from the URL and updates the database.
"""
import re
import sqlite3
import sys


def extract_hash_from_url(url: str) -> str | None:
    """Extract torrent hash from Mikan URL."""
    # Match pattern: /Download/YYYYMMDD/{HASH}.torrent
    match = re.search(r'/Download/\d+/([a-f0-9]{40})\.torrent', url, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Also check for magnet links
    if url.startswith('magnet:'):
        match = re.search(r'urn:btih:([a-f0-9]{40})', url, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def backfill_hashes(db_path: str):
    """Backfill hash field from torrent URLs."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all torrents without hashes
    cursor.execute("SELECT id, url FROM torrent WHERE hash IS NULL OR hash = ''")
    torrents = cursor.fetchall()
    
    print(f"Found {len(torrents)} torrents without hashes")
    
    updated = 0
    skipped = 0
    
    for torrent_id, url in torrents:
        hash_value = extract_hash_from_url(url)
        if hash_value:
            cursor.execute("UPDATE torrent SET hash = ? WHERE id = ?", (hash_value, torrent_id))
            updated += 1
            print(f"✓ Updated torrent ID {torrent_id}: {hash_value}")
        else:
            skipped += 1
            print(f"✗ Skipped torrent ID {torrent_id}: could not extract hash from {url}")
    
    conn.commit()
    conn.close()
    
    print(f"\nDone! Updated: {updated}, Skipped: {skipped}")

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "backend/src/data/data.db"
    backfill_hashes(db_path)
