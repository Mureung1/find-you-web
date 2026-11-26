import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from google.auth.exceptions import GoogleAuthError
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import auth, claims, management, matching
from .db import initialize, public_lost_items
from .dependencies import DB, require_location
from .models import (
    CandidateQuery, CandidateResult, Category, Coordinates, FoundRegistration, Location,
    LostRegistration, PublicLostItem, RegistrationResult,
)
from .neighborhoods import neighborhood_at
from .semantic import TextEncoder


@asynccontextmanager
async def lifespan(app: FastAPI):
    default_path = Path(__file__).parent / "data" / "find-you.sqlite3"
    app.state.db_path = Path(os.environ.get("FIND_YOU_DB_PATH", str(default_path)))
    app.state.google_login = auth.configure_google_login()
    app.state.admin_user_ids = {
        value.strip() for value in os.environ.get("FIND_YOU_ADMIN_USER_IDS", "").split(",") if value.strip()
    }
    live = os.environ.get("FIND_YOU_LIVE") == "1"
    app.state.demo_mode = not live
    if live and (app.state.google_login is None or not app.state.google_login.secure_cookie):
        raise ValueError("FIND_YOU_LIVE=1 requires Google login and an HTTPS origin")
    initialize(app.state.db_path, with_demo=not live)
    text_model_path = os.environ.get("FIND_YOU_TEXT_MODEL_PATH", "").strip()
    app.state.text_encoder = TextEncoder(Path(text_model_path)) if text_model_path else None
    yield


app = FastAPI(title="Find you API", lifespan=lifespan)
app.include_router(management.router)
app.include_router(claims.router)


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [{"field": error["loc"][-1], "code": error["type"]} for error in exc.errors()]
    return JSONResponse(
        status_code=422, headers={"Cache-Control": "no-store"},
        content={"detail": "입력 항목을 확인해 주세요.", "fields": fields},
    )


@app.exception_handler(StarletteHTTPException)
async def uncacheable_http_error(request: Request, exc: StarletteHTTPException) -> Response:
    response = await http_exception_handler(request, exc)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health(db: DB) -> dict[str, str]:
    db.execute("SELECT 1 FROM locations LIMIT 1").fetchone()
    return {"status": "ok"}


@app.get("/api/auth/session")
def auth_session(request: Request, db: DB) -> dict:
    login = request.app.state.google_login
    if login is None:
        return {"google_client_id": None, "origin": None, "user": None, "demo_mode": request.app.state.demo_mode}
    user = auth.current_user(db, request.cookies.get(auth.SESSION_COOKIE))
    account = {**dict(user), "is_admin": auth.is_admin(request, user["user_id"])} if user else None
    return {"google_client_id": login.client_id, "origin": login.origin, "user": account, "demo_mode": request.app.state.demo_mode}


@app.post("/api/auth/google")
async def google_login(request: Request, db: DB) -> RedirectResponse:
    login = request.app.state.google_login
    if login is None:
        raise HTTPException(status_code=503, detail="Google 로그인 설정을 준비 중입니다.")
    credential = await auth.google_credential(request)
    headers = {"Cache-Control": "no-store"}
    try:
        subject, name = await run_in_threadpool(auth.verify_google_identity, credential, login.client_id)
    except (ValueError, GoogleAuthError):
        return RedirectResponse("/login?error=google", status_code=303, headers=headers)

    token = auth.start_session(db, subject, name, request.cookies.get(auth.SESSION_COOKIE))
    response = RedirectResponse("/", status_code=303, headers=headers)
    response.set_cookie(
        auth.SESSION_COOKIE, token, max_age=auth.SESSION_SECONDS,
        httponly=True, secure=login.secure_cookie, samesite="lax",
    )
    return response


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: DB) -> None:
    login = request.app.state.google_login
    if login is None:
        return
    auth.require_same_origin(request, login)
    token = request.cookies.get(auth.SESSION_COOKIE)
    if token:
        with db:
            auth.end_session(db, token)
    response.delete_cookie(auth.SESSION_COOKIE, httponly=True, secure=login.secure_cookie, samesite="lax")


@app.get("/api/locations")
def locations(db: DB) -> list[Location]:
    rows = db.execute("SELECT location_id, region, dong FROM locations ORDER BY region, dong, location_id")
    return [Location(**dict(row)) for row in rows]


@app.post("/api/locations/nearby")
def nearby_location(coordinates: Coordinates, db: DB) -> Location:
    location_id = neighborhood_at(coordinates.latitude, coordinates.longitude)
    row = db.execute(
        "SELECT location_id, region, dong FROM locations WHERE location_id = ?", (location_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="현재 위치의 동네를 찾지 못했어요. 동네 이름으로 검색해 주세요.")
    return Location(**dict(row))


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
def register_lost_item(item: LostRegistration, request: Request, db: DB) -> RegistrationResult:
    owner_id = auth.registration_owner(request, db)
    require_location(db, item.location_id)
    item_id = str(uuid4())
    with db:
        db.execute(
            """
            INSERT INTO items (item_id, kind, location_id, category, title, event_date, consent_to_publish, status, owner_id)
            VALUES (?, 'lost', ?, ?, ?, ?, ?, 'searching', ?)
            """,
            (item_id, item.location_id, item.category, item.title, item.event_date.isoformat(), item.consent_to_publish, owner_id),
        )
    return RegistrationResult(item_id=item_id)


@app.post("/api/found-items", status_code=201)
def register_found_item(item: FoundRegistration, request: Request, db: DB) -> RegistrationResult:
    owner_id = auth.registration_owner(request, db)
    require_location(db, item.location_id)
    item_id = str(uuid4())
    with db:
        db.execute(
            """
            INSERT INTO items (item_id, kind, location_id, category, title, event_date, features, status, owner_id)
            VALUES (?, 'found', ?, ?, ?, ?, ?, 'held', ?)
            """,
            (item_id, item.location_id, item.category, item.title, item.event_date.isoformat(), item.features, owner_id),
        )
    return RegistrationResult(item_id=item_id)


@app.post("/api/candidates/check")
def check_candidates(query: CandidateQuery, request: Request, db: DB) -> CandidateResult:
    require_location(db, query.location_id)
    return CandidateResult(has_candidate=matching.has_candidate(db, query, encoder=request.app.state.text_encoder))
