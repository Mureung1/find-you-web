import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Body, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool

from . import auth
from .claims import ensure_item_editable, remove_pending_candidate
from .dependencies import DB, require_location, write_transaction
from .images import MAX_PHOTO_BYTES, MAX_PHOTOS, PHOTO_TYPES, sanitize_photo
from .models import FoundRegistration, LostRegistration


router = APIRouter(prefix="/api/my/items", tags=["my items"])


class LostEdit(LostRegistration):
    kind: Literal["lost"]
    status: Literal["searching", "returned"]


class FoundEdit(FoundRegistration):
    kind: Literal["found"]


ItemEdit = Annotated[LostEdit | FoundEdit, Body(discriminator="kind")]


def require_item(
    db: sqlite3.Connection, item_id: str, owner_id: str, *, staff_read: bool = False,
) -> sqlite3.Row:
    item = db.execute(
        """
        SELECT kind, location_id, category, title, features FROM items
        WHERE item_id = ? AND (owner_id = ? OR (? AND kind = 'found'))
        """,
        (item_id, owner_id, staff_read),
    ).fetchone()
    if item is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없어요.")
    return item


@router.get("")
def my_items(request: Request, db: DB) -> list[dict]:
    owner_id = auth.require_user(request, db)["user_id"]
    rows = db.execute(
        """
        SELECT i.item_id, i.kind, i.title, i.category, i.event_date, i.status, i.location_id,
               i.features, i.consent_to_publish, l.region, l.dong,
               EXISTS (SELECT 1 FROM claims c WHERE c.approved_item_id = i.item_id AND c.status = 'approved') AS locked
        FROM items i JOIN locations l ON l.location_id = i.location_id
        WHERE i.owner_id = ?
        ORDER BY i.event_date DESC, i.item_id
        """,
        (owner_id,),
    ).fetchall()
    photos: dict[str, list[int]] = {}
    for row in db.execute(
        """
        SELECT p.item_id, p.position FROM item_photos p JOIN items i ON i.item_id = p.item_id
        WHERE i.owner_id = ? ORDER BY p.position
        """,
        (owner_id,),
    ):
        photos.setdefault(row["item_id"], []).append(row["position"])
    return [
        {
            **dict(row),
            "consent_to_publish": bool(row["consent_to_publish"]),
            "locked": bool(row["locked"]),
            "photo_positions": photos.get(row["item_id"], []),
        }
        for row in rows
    ]


@router.put("/{item_id}")
def edit_item(item_id: str, item: ItemEdit, request: Request, db: DB) -> dict[str, bool]:
    owner_id = auth.require_user(request, db, write=True)["user_id"]
    with write_transaction(db):
        previous = require_item(db, item_id, owner_id)
        if previous["kind"] != item.kind:
            raise HTTPException(status_code=422, detail="등록 유형을 확인해 주세요.")
        ensure_item_editable(db, item_id)
        require_location(db, item.location_id)
        if isinstance(item, FoundEdit):
            if (item.location_id, item.category, item.title, item.features) != (
                previous["location_id"], previous["category"], previous["title"], previous["features"],
            ):
                remove_pending_candidate(db, item_id)
            db.execute(
                """
                UPDATE items SET title = ?, category = ?, event_date = ?, location_id = ?, features = ?
                WHERE item_id = ?
                """,
                (item.title, item.category, item.event_date.isoformat(), item.location_id, item.features, item_id),
            )
        else:
            db.execute(
                """
                UPDATE items SET title = ?, category = ?, event_date = ?, location_id = ?, status = ?, consent_to_publish = ?
                WHERE item_id = ?
                """,
                (item.title, item.category, item.event_date.isoformat(), item.location_id, item.status,
                 item.consent_to_publish, item_id),
            )
    return {"ok": True}


@router.delete("/{item_id}")
def delete_item(item_id: str, request: Request, db: DB) -> dict[str, bool]:
    owner_id = auth.require_user(request, db, write=True)["user_id"]
    with write_transaction(db):
        require_item(db, item_id, owner_id)
        ensure_item_editable(db, item_id)
        remove_pending_candidate(db, item_id)
        db.execute("DELETE FROM items WHERE item_id = ?", (item_id,))
    return {"ok": True}


@router.get("/{item_id}/photos/{position}")
def read_photo(item_id: str, position: int, request: Request, db: DB) -> Response:
    actor = auth.require_user(request, db)["user_id"]
    require_item(db, item_id, actor, staff_read=auth.is_admin(request, actor))
    photo = db.execute(
        "SELECT content_type, content FROM item_photos WHERE item_id = ? AND position = ?", (item_id, position),
    ).fetchone()
    if photo is None or photo["content_type"] not in PHOTO_TYPES.values():
        raise HTTPException(status_code=404, detail="사진을 찾을 수 없어요.")
    return Response(
        content=photo["content"], media_type=photo["content_type"],
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": "inline",
            "Cross-Origin-Resource-Policy": "same-origin",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{item_id}/photos", status_code=201)
async def upload_photo(item_id: str, request: Request, db: DB) -> dict[str, int]:
    owner_id = auth.require_user(request, db, write=True)["user_id"]
    item = require_item(db, item_id, owner_id)
    if item["kind"] != "found":
        raise HTTPException(status_code=422, detail="습득물 게시글에 사진을 추가할 수 있어요.")
    ensure_item_editable(db, item_id)
    content_type = request.headers.get("content-type", "").partition(";")[0].lower()
    if content_type not in PHOTO_TYPES.values():
        raise HTTPException(status_code=415, detail="JPEG, PNG 또는 WebP 사진을 선택해 주세요.")
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=413, detail="사진은 장당 8MB 이하로 올려 주세요.")
        raw.extend(chunk)
    try:
        photo = await run_in_threadpool(sanitize_photo, bytes(raw), content_type)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    with write_transaction(db):
        require_item(db, item_id, owner_id)
        ensure_item_editable(db, item_id)
        current = db.execute(
            "SELECT COUNT(*) AS count, COALESCE(MAX(position), -1) + 1 AS position FROM item_photos WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        if current["count"] >= MAX_PHOTOS:
            raise HTTPException(status_code=409, detail="한 게시글에 사진을 4장까지 올릴 수 있어요.")
        db.execute(
            "INSERT INTO item_photos (item_id, position, content_type, content) VALUES (?, ?, 'image/jpeg', ?)",
            (item_id, current["position"], photo),
        )
    return {"position": current["position"]}


@router.delete("/{item_id}/photos/{position}")
def delete_photo(item_id: str, position: int, request: Request, db: DB) -> dict[str, bool]:
    owner_id = auth.require_user(request, db, write=True)["user_id"]
    with write_transaction(db):
        require_item(db, item_id, owner_id)
        ensure_item_editable(db, item_id)
        deleted = db.execute("DELETE FROM item_photos WHERE item_id = ? AND position = ?", (item_id, position))
        if deleted.rowcount != 1:
            raise HTTPException(status_code=404, detail="사진을 찾을 수 없어요.")
    return {"ok": True}
