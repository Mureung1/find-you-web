import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response

from .db import connect


def database(request: Request, response: Response) -> Iterator[sqlite3.Connection]:
    response.headers["Cache-Control"] = "no-store"
    with closing(connect(request.app.state.db_path)) as db:
        yield db


DB = Annotated[sqlite3.Connection, Depends(database)]


def require_location(db: sqlite3.Connection, location_id: str) -> None:
    if db.execute("SELECT 1 FROM locations WHERE location_id = ?", (location_id,)).fetchone() is None:
        raise HTTPException(status_code=422, detail="목록에 있는 동네를 선택해 주세요.")


@contextmanager
def write_transaction(db: sqlite3.Connection) -> Iterator[None]:
    with db:
        db.execute("BEGIN IMMEDIATE")
        yield
