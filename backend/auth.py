import json
import os
import sqlite3
from dataclasses import dataclass
from functools import partial
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe
from time import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from fastapi import HTTPException, Request
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.id_token import verify_oauth2_token


SESSION_COOKIE = "find_you_session"
SESSION_SECONDS = 7 * 24 * 60 * 60


@dataclass(frozen=True)
class GoogleLogin:
    client_id: str
    origin: str

    @property
    def secure_cookie(self) -> bool:
        return self.origin.startswith("https://")


def configure_google_login() -> GoogleLogin | None:
    client_id = os.environ.get("FIND_YOU_GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        return None
    origin = os.environ.get("FIND_YOU_AUTH_ORIGIN", "http://localhost:3000").strip().rstrip("/")
    url = urlsplit(origin)
    local_http = url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
    if not (url.scheme == "https" or local_http) or not url.hostname or url.path or url.query or url.fragment or url.username is not None:
        raise ValueError("FIND_YOU_AUTH_ORIGIN must be an HTTPS origin or an HTTP loopback origin")
    return GoogleLogin(client_id, origin)


async def google_credential(request: Request) -> str:
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 16_384:
            raise HTTPException(status_code=413, detail="로그인 요청이 너무 큽니다.")
        body.extend(chunk)

    content_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    try:
        if content_type == "application/json":
            fields = json.loads(body)
        elif content_type == "application/x-www-form-urlencoded":
            pairs = parse_qs(body.decode(), max_num_fields=12, errors="strict")
            fields = {name: values[0] for name, values in pairs.items() if len(values) == 1}
        else:
            raise HTTPException(status_code=415, detail="지원하지 않는 로그인 요청 형식입니다.")
    except ValueError as error:
        raise HTTPException(status_code=400, detail="로그인 요청을 확인해 주세요.") from error

    credential = fields.get("credential") if isinstance(fields, dict) else None
    submitted_csrf = fields.get("g_csrf_token") if isinstance(fields, dict) else None
    cookie_csrf = request.cookies.get("g_csrf_token")
    if not isinstance(credential, str) or not credential or not isinstance(submitted_csrf, str) or not cookie_csrf:
        raise HTTPException(status_code=400, detail="로그인 요청을 확인해 주세요.")
    if not compare_digest(cookie_csrf.encode(), submitted_csrf.encode()):
        raise HTTPException(status_code=400, detail="로그인 요청을 확인해 주세요.")
    return credential


def verify_google_identity(credential: str, client_id: str) -> tuple[str, str]:
    claims = verify_oauth2_token(credential, partial(GoogleRequest(), timeout=5), audience=client_id)
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise ValueError("Missing Google account identifier")
    name = claims.get("name")
    display_name = name.strip()[:100] if isinstance(name, str) else ""
    return subject, display_name or "Google 사용자"


def session_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def start_session(db: sqlite3.Connection, subject: str, name: str, old_token: str | None) -> str:
    now = int(time())
    token = token_urlsafe(32)
    with db:
        user_id = db.execute(
            """
            INSERT INTO users (user_id, google_sub, display_name) VALUES (?, ?, ?)
            ON CONFLICT (google_sub) DO UPDATE SET display_name = excluded.display_name
            RETURNING user_id
            """,
            (str(uuid4()), subject, name),
        ).fetchone()["user_id"]
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        if old_token:
            end_session(db, old_token)
        db.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (session_hash(token), user_id, now + SESSION_SECONDS),
        )
    return token


def current_user(db: sqlite3.Connection, token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    return db.execute(
        """
        SELECT u.user_id, u.display_name
        FROM sessions s JOIN users u ON s.user_id = u.user_id
        WHERE s.token_hash = ? AND s.expires_at > ?
        """,
        (session_hash(token), int(time())),
    ).fetchone()


def end_session(db: sqlite3.Connection, token: str) -> None:
    db.execute("DELETE FROM sessions WHERE token_hash = ?", (session_hash(token),))


def require_same_origin(request: Request, login: GoogleLogin) -> None:
    if request.headers.get("origin") != login.origin:
        raise HTTPException(status_code=403, detail="로그인에 등록된 사이트 주소에서 다시 시도해 주세요.")


def registration_owner(request: Request, db: sqlite3.Connection) -> str | None:
    login = request.app.state.google_login
    if login is None:
        return None
    user = current_user(db, request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(status_code=401, detail="로그인한 뒤 등록해 주세요.")
    require_same_origin(request, login)
    return user["user_id"]
