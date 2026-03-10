"""SQLite local cache for contacts synced from OnePageCRM."""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "contacts.db"


def get_db():
    """Get a database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create the contacts table if it doesn't exist."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id TEXT PRIMARY KEY,
            full_name TEXT,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            company_name TEXT,
            data JSON,
            synced_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            synced_at TEXT,
            contact_count INTEGER
        )
    """)
    conn.commit()
    conn.close()


def save_contacts(contacts: list[dict]):
    """Save a list of contacts to the local database."""
    conn = get_db()
    now = datetime.now().isoformat()
    for c in contacts:
        conn.execute(
            """INSERT OR REPLACE INTO contacts (id, full_name, first_name, last_name, email, company_name, data, synced_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                c.get("id", ""),
                c.get("full_name", ""),
                c.get("first_name", ""),
                c.get("last_name", ""),
                c.get("email", ""),
                c.get("company_name", ""),
                json.dumps(c),
                now,
            ),
        )
    conn.execute(
        "INSERT INTO sync_log (synced_at, contact_count) VALUES (?, ?)",
        (now, len(contacts)),
    )
    conn.commit()
    conn.close()


def search_contacts_local(query: str) -> list[dict]:
    """Search contacts in local database."""
    conn = get_db()
    rows = conn.execute(
        """SELECT data FROM contacts
           WHERE full_name LIKE ? OR email LIKE ? OR company_name LIKE ?
           ORDER BY full_name
           LIMIT 50""",
        (f"%{query}%", f"%{query}%", f"%{query}%"),
    ).fetchall()
    conn.close()
    return [json.loads(row["data"]) for row in rows]


def list_contacts_local() -> list[dict]:
    """List all contacts from local database."""
    conn = get_db()
    rows = conn.execute("SELECT data FROM contacts ORDER BY full_name").fetchall()
    conn.close()
    return [json.loads(row["data"]) for row in rows]


def get_contact_local(contact_id: str) -> dict | None:
    """Get a single contact by ID from local database."""
    conn = get_db()
    row = conn.execute("SELECT data FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    conn.close()
    if row:
        return json.loads(row["data"])
    return None


def get_contact_count() -> int:
    """Get total number of contacts in local database."""
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as cnt FROM contacts").fetchone()
    conn.close()
    return row["cnt"]


def get_last_sync() -> str | None:
    """Get the timestamp of the last sync."""
    conn = get_db()
    row = conn.execute("SELECT synced_at FROM sync_log ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if row:
        return row["synced_at"]
    return None


# Initialize on import
init_db()
