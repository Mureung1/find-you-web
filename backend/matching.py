import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from sqlite3 import Connection, Row

from .db import normalize_text
from .models import CandidateQuery
from .semantic import TextEncoder

TOP_K = 5
MIN_SCORE = 0.76
MIN_SEMANTIC_SCORE = 0.90
WORDS = re.compile(r"[^\W_]+")


@dataclass(frozen=True)
class Candidate:
    item_id: str
    score: float


def feature_score(query: str, features: str, *, exact: bool = False) -> float:
    original_query = normalize_text(query)
    original_features = normalize_text(features)
    if original_query == original_features:
        return 1.0
    if exact:
        return 0.0
    query_words = WORDS.findall(original_query)
    feature_words = WORDS.findall(original_features)
    left, right = " ".join(query_words), " ".join(feature_words)
    if min(len(left.replace(" ", "")), len(right.replace(" ", ""))) < 5:
        return 0.0
    return max(
        SequenceMatcher(None, left, right, autojunk=False).ratio(),
        SequenceMatcher(None, sorted(query_words), sorted(feature_words), autojunk=False).ratio(),
    )


def eligible_items(db: Connection, query: CandidateQuery) -> list[Row]:
    return db.execute(
        """
        SELECT item_id, title, features FROM items
        WHERE kind = 'found' AND status = 'held' AND location_id = ? AND category = ?
          AND NOT EXISTS (
              SELECT 1 FROM claims WHERE approved_item_id = items.item_id AND status = 'approved'
          )
        """,
        (query.location_id, query.category),
    ).fetchall()


def rank_items(
    rows: list[Row], features: str, *, exact: bool = False, encoder: TextEncoder | None = None,
) -> list[Candidate]:
    accepted = []
    remaining = []
    for row in rows:
        score = feature_score(features, row["features"], exact=exact)
        if score >= MIN_SCORE:
            accepted.append(Candidate(row["item_id"], score))
        else:
            remaining.append(row)
    if encoder is not None and not exact and remaining and len("".join(WORDS.findall(features))) >= 5:
        scores = encoder.similarities(features, [f"{row['title']} {row['features']}" for row in remaining])
        accepted.extend(Candidate(row["item_id"], score) for row, score in zip(remaining, scores, strict=True)
                        if score >= MIN_SEMANTIC_SCORE)
    return sorted(accepted, key=lambda candidate: (-candidate.score, candidate.item_id))[:TOP_K]


def candidates(
    db: Connection, query: CandidateQuery, *, exact: bool = False, encoder: TextEncoder | None = None,
) -> list[Candidate]:
    return rank_items(eligible_items(db, query), query.features, exact=exact, encoder=encoder)


def has_candidate(db: Connection, query: CandidateQuery, *, encoder: TextEncoder | None = None) -> bool:
    return bool(candidates(db, query, encoder=encoder))
