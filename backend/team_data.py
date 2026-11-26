"""Import team photos and records, or compare matchers on labeled cases."""

import argparse
import json
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter

from . import matching
from .claims import ensure_item_editable, remove_pending_candidate
from .db import connect, initialize
from .dependencies import require_location, write_transaction
from .images import MAX_PHOTO_BYTES, MAX_PHOTOS, sanitize_photo
from .models import CandidateQuery, Category, Features, Title
from .neighborhoods import LEGACY_IDS


RecordID = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class SourceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: RecordID
    kind: Literal["lost", "found"]
    location_code: RecordID
    category: Category
    title: Title
    event_date: date
    features: Features | None = None
    image_paths: list[str] = Field(default_factory=list, max_length=MAX_PHOTOS)


class SourceQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_code: RecordID
    category: Category
    features: Features


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: RecordID
    query: SourceQuery
    expected_found_record_ids: list[RecordID]


def location_id(db: sqlite3.Connection, code: str, mapping: dict[str, str]) -> str:
    resolved = mapping.get(code, LEGACY_IDS.get(code, code))
    require_location(db, resolved)
    return resolved


def photo_data(root: Path, relative_path: str) -> bytes:
    relative = Path(relative_path)
    path = (root / relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"사진 경로가 데이터셋 안의 파일을 가리켜야 합니다: {relative_path}")
    with path.open("rb") as photo:
        return sanitize_photo(photo.read(MAX_PHOTO_BYTES + 1))


def import_dataset(db: sqlite3.Connection, root: Path, dataset_id: str, mapping: dict[str, str]) -> int:
    source = TypeAdapter(list[SourceItem]).validate_json((root / "items.json").read_bytes())
    if len({item.record_id for item in source}) != len(source):
        raise ValueError("items.json에 중복 record_id가 있어요.")

    with write_transaction(db):
        for item in source:
            if item.kind == "found" and item.features is None:
                raise ValueError(f"{item.record_id}: 습득물에는 식별 특징이 필요해요.")
            place = location_id(db, item.location_code, mapping)
            features = item.features if item.kind == "found" else None
            photos = [photo_data(root, path) for path in item.image_paths]
            previous = db.execute(
                """
                SELECT i.item_id, i.kind, i.owner_id, i.location_id, i.category, i.title, i.features
                FROM imported_items m JOIN items i ON i.item_id = m.item_id
                WHERE m.dataset_id = ? AND m.record_id = ?
                """,
                (dataset_id, item.record_id),
            ).fetchone()
            if previous:
                if previous["kind"] != item.kind or previous["owner_id"] is not None:
                    raise ValueError(f"{item.record_id}: 기존 게시글의 유형이나 작성자를 바꿀 수 없어요.")
                item_id = previous["item_id"]
                ensure_item_editable(db, item_id)
                if (place, item.category, item.title, features) != (
                    previous["location_id"], previous["category"], previous["title"], previous["features"],
                ):
                    remove_pending_candidate(db, item_id)
                db.execute(
                    """
                    UPDATE items SET location_id = ?, category = ?, title = ?, event_date = ?, features = ?
                    WHERE item_id = ?
                    """,
                    (place, item.category, item.title, item.event_date.isoformat(), features, item_id),
                )
                db.execute("DELETE FROM item_photos WHERE item_id = ?", (item_id,))
            else:
                item_id = str(uuid4())
                status = "held" if item.kind == "found" else "searching"
                db.execute(
                    """
                    INSERT INTO items (item_id, kind, location_id, category, title, event_date, features, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (item_id, item.kind, place, item.category, item.title, item.event_date.isoformat(), features, status),
                )
                db.execute(
                    "INSERT INTO imported_items (dataset_id, record_id, item_id) VALUES (?, ?, ?)",
                    (dataset_id, item.record_id, item_id),
                )
            db.executemany(
                "INSERT INTO item_photos (item_id, position, content_type, content) VALUES (?, ?, 'image/jpeg', ?)",
                [(item_id, position, photo) for position, photo in enumerate(photos)],
            )
    return len(source)


def evaluate_dataset(db: sqlite3.Connection, root: Path, dataset_id: str, mapping: dict[str, str]) -> dict:
    cases = TypeAdapter(list[EvaluationCase]).validate_json((root / "eval_cases.json").read_bytes())
    if not cases or len({case.case_id for case in cases}) != len(cases):
        raise ValueError("eval_cases.json에는 고유한 평가 케이스가 하나 이상 필요해요.")
    ids = {row["record_id"]: row["item_id"] for row in db.execute(
        """
        SELECT m.record_id, m.item_id FROM imported_items m JOIN items i ON i.item_id = m.item_id
        WHERE m.dataset_id = ? AND i.kind = 'found'
        """,
        (dataset_id,),
    )}
    summaries = {key: Counter(cases=len(cases), hits=0, misses=0, false_positives=0, wrong_top_1=0)
                 for key in ("exact", "similarity")}
    for case in cases:
        if any(record_id not in ids for record_id in case.expected_found_record_ids):
            raise ValueError(f"{case.case_id}: 정답 습득물이 가져온 데이터에 없어요.")
        expected = {ids[record_id] for record_id in case.expected_found_record_ids}
        query = CandidateQuery(
            location_id=location_id(db, case.query.location_code, mapping),
            category=case.query.category, features=case.query.features,
        )
        for label, summary in summaries.items():
            predicted = [candidate.item_id for candidate in matching.candidates(db, query, exact=label == "exact")]
            if expected:
                summary["hits" if expected.intersection(predicted) else "misses"] += 1
                if predicted and predicted[0] not in expected:
                    summary["wrong_top_1"] += 1
            elif predicted:
                summary["false_positives"] += 1
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("import", "evaluate"))
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--location-map", type=Path)
    args = parser.parse_args()
    try:
        mapping = args.location_map.read_bytes() if args.location_map else b"{}"
        locations = TypeAdapter(dict[str, str]).validate_json(mapping)
        dataset_id = TypeAdapter(RecordID).validate_python(args.dataset)
        initialize(args.db, with_demo=False)
        with closing(connect(args.db)) as db:
            if args.action == "import":
                count = import_dataset(db, args.source.resolve(), dataset_id, locations)
                print(json.dumps({"records": count}))
            else:
                print(json.dumps(evaluate_dataset(db, args.source.resolve(), dataset_id, locations), indent=2))
    except (OSError, ValueError, HTTPException) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
