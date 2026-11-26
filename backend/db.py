import sqlite3
import unicodedata
from contextlib import closing
from pathlib import Path

from .models import CATEGORY_LABELS, Category
from .neighborhoods import seed_neighborhoods
from .seed import migrate_demo_locations, seed_demo


SCHEMA = """
CREATE TABLE IF NOT EXISTS locations (
    location_id TEXT PRIMARY KEY NOT NULL,
    region TEXT NOT NULL,
    dong TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY NOT NULL,
    google_sub TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('lost', 'found')),
    location_id TEXT NOT NULL REFERENCES locations(location_id),
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    event_date TEXT NOT NULL,
    features TEXT,
    consent_to_publish INTEGER NOT NULL DEFAULT 0 CHECK (consent_to_publish IN (0, 1)),
    status TEXT NOT NULL,
    owner_id TEXT REFERENCES users(user_id),
    CHECK (
        (kind = 'lost' AND features IS NULL AND status IN ('searching', 'returned')) OR
        (kind = 'found' AND features IS NOT NULL AND consent_to_publish = 0 AND status IN ('held', 'returned'))
    )
);

CREATE TABLE IF NOT EXISTS item_photos (
    item_id TEXT NOT NULL REFERENCES items(item_id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    content_type TEXT NOT NULL,
    content BLOB NOT NULL,
    PRIMARY KEY (item_id, position)
);

CREATE INDEX IF NOT EXISTS public_items_date ON items(event_date DESC, item_id)
    WHERE kind = 'lost' AND consent_to_publish = 1;

CREATE INDEX IF NOT EXISTS held_items_location ON items(location_id, category)
    WHERE kind = 'found' AND status = 'held';
"""


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def connect(path: Path) -> sqlite3.Connection:
    # FastAPI can run dependency setup, the handler, and cleanup on different worker threads.
    db = sqlite3.connect(path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.create_function("normalize_text", 1, normalize_text, deterministic=True)
    db.create_function("category_label", 1, lambda value: CATEGORY_LABELS.get(value, value), deterministic=True)
    return db


def initialize(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(path)) as db, db:
        db.executescript(SCHEMA)
        db.execute("BEGIN IMMEDIATE")
        columns = {row["name"] for row in db.execute("PRAGMA table_info(locations)")}
        legacy = "place" in columns
        if legacy:
            db.execute("ALTER TABLE locations RENAME COLUMN place TO dong")
        if not any(row["name"] == "owner_id" for row in db.execute("PRAGMA table_info(items)")):
            db.execute("ALTER TABLE items ADD COLUMN owner_id TEXT REFERENCES users(user_id)")
        seed_neighborhoods(db)
        seed_demo(db)
        if legacy:
            migrate_demo_locations(db)


def public_lost_items(
    db: sqlite3.Connection, query: str, region: str | None, location_id: str | None, category: Category | None
) -> list[sqlite3.Row]:
    conditions = ["i.kind = 'lost'", "i.consent_to_publish = 1"]
    values: list[str] = []
    for column, value in [("l.region", region), ("i.location_id", location_id), ("i.category", category)]:
        if value:
            conditions.append(f"{column} = ?")
            values.append(value)

    searchable_text = """normalize_text(
        i.title || ' ' || category_label(i.category) || ' ' || l.region || ' ' || l.dong
    )"""
    for word in normalize_text(query).split():
        conditions.append(f"instr({searchable_text}, ?) > 0")
        values.append(word)

    return db.execute(
        f"""
        SELECT i.item_id, i.title, i.category, i.event_date, i.status, l.location_id, l.region, l.dong
        FROM items i JOIN locations l ON i.location_id = l.location_id
        WHERE {' AND '.join(conditions)}
        ORDER BY i.event_date DESC, i.item_id
        """,
        values,
    ).fetchall()
