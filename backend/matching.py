from sqlite3 import Connection

from .db import normalize_text
from .models import CandidateQuery


def has_candidate(db: Connection, query: CandidateQuery) -> bool:
    """Local deterministic adapter. Replace the implementation when the team module is ready."""
    return db.execute(
        """
        SELECT 1 FROM items
        WHERE kind = 'found' AND status = 'held' AND location_id = ? AND category = ?
            AND normalize_text(features) = ?
        LIMIT 1
        """,
        (query.location_id, query.category, normalize_text(query.features)),
    ).fetchone() is not None
