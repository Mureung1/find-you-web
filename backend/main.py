import os
import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import matching
from .db import connect, initialize, public_lost_items
from .models import (
    CandidateQuery, CandidateResult, Category, FoundRegistration, Location,
    LostRegistration, PublicLostItem, RegistrationResult,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    default_path = Path(__file__).parent / "data" / "find-you.sqlite3"
    app.state.db_path = Path(os.environ.get("FIND_YOU_DB_PATH", str(default_path)))
    initialize(app.state.db_path)
    yield


app = FastAPI(title="Find you API", lifespan=lifespan)


def database(request: Request, response: Response) -> Iterator[sqlite3.Connection]:
    response.headers["Cache-Control"] = "no-store"
    with closing(connect(request.app.state.db_path)) as db:
        yield db


DB = Annotated[sqlite3.Connection, Depends(database)]


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [{"field": error["loc"][-1], "code": error["type"]} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "입력 항목을 확인해 주세요.", "fields": fields})


def require_location(db: sqlite3.Connection, location_id: str) -> None:
    if db.execute("SELECT 1 FROM locations WHERE location_id = ?", (location_id,)).fetchone() is None:
        raise HTTPException(status_code=422, detail="목록에 있는 동네를 선택해 주세요.")


@app.get("/api/health")
def health(db: DB) -> dict[str, str]:
    db.execute("SELECT 1 FROM locations LIMIT 1").fetchone()
    return {"status": "ok"}


@app.get("/api/locations")
def locations(db: DB) -> list[Location]:
    rows = db.execute("SELECT location_id, region, dong FROM locations ORDER BY region, dong, location_id")
    return [Location(**dict(row)) for row in rows]


@app.get("/api/lost-items")
def list_lost_items(
    db: DB,
    q: Annotated[str, Query(max_length=100)] = "",
    region: Annotated[str | None, Query(max_length=80)] = None,
    location_id: Annotated[str | None, Query(max_length=80)] = None,
    category: Category | None = None,
) -> list[PublicLostItem]:
    return [
        PublicLostItem(
            item_id=row["item_id"], title=row["title"], category=row["category"],
            location=Location(**dict(row)), event_date=row["event_date"], status=row["status"],
        )
        for row in public_lost_items(db, q, region, location_id, category)
    ]


@app.post("/api/lost-items", status_code=201)
def register_lost_item(item: LostRegistration, db: DB) -> RegistrationResult:
    require_location(db, item.location_id)
    item_id = str(uuid4())
    with db:
        db.execute(
            """
            INSERT INTO items (item_id, kind, location_id, category, title, event_date, consent_to_publish, status)
            VALUES (?, 'lost', ?, ?, ?, ?, ?, 'searching')
            """,
            (item_id, item.location_id, item.category, item.title, item.event_date.isoformat(), item.consent_to_publish),
        )
    return RegistrationResult(item_id=item_id)


@app.post("/api/found-items", status_code=201)
def register_found_item(item: FoundRegistration, db: DB) -> RegistrationResult:
    require_location(db, item.location_id)
    item_id = str(uuid4())
    with db:
        db.execute(
            """
            INSERT INTO items (item_id, kind, location_id, category, title, event_date, features, status)
            VALUES (?, 'found', ?, ?, ?, ?, ?, 'held')
            """,
            (item_id, item.location_id, item.category, item.title, item.event_date.isoformat(), item.features),
        )
    return RegistrationResult(item_id=item_id)


@app.post("/api/candidates/check")
def check_candidates(query: CandidateQuery, db: DB) -> CandidateResult:
    require_location(db, query.location_id)
    return CandidateResult(has_candidate=matching.has_candidate(db, query))
