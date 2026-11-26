from datetime import UTC, datetime
from sqlite3 import Connection
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, StringConstraints

from . import auth, matching
from .db import normalize_text
from .dependencies import DB, require_location, write_transaction
from .models import CandidateQuery


router = APIRouter(prefix="/api/claims", tags=["claims"])
Proof = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)]


class ClaimRequest(CandidateQuery):
    proof: Proof


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "reject", "return"]
    item_id: str | None = None
    reply: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""


def ensure_item_editable(db: Connection, item_id: str) -> None:
    if db.execute(
        "SELECT 1 FROM claims WHERE approved_item_id = ? AND status = 'approved'", (item_id,),
    ).fetchone():
        raise HTTPException(status_code=409, detail="소유 확인이 승인된 습득물은 반환을 완료한 뒤 변경할 수 있어요.")


def remove_pending_candidate(db: Connection, item_id: str) -> None:
    db.execute(
        """
        DELETE FROM claim_candidates
        WHERE item_id = ? AND claim_id IN (SELECT claim_id FROM claims WHERE status = 'pending')
        """,
        (item_id,),
    )
    db.execute(
        """
        UPDATE claims SET status = 'rejected'
        WHERE status = 'pending'
          AND NOT EXISTS (SELECT 1 FROM claim_candidates cc WHERE cc.claim_id = claims.claim_id)
        """
    )


@router.post("", status_code=201)
def request_claim(data: ClaimRequest, request: Request, db: DB) -> dict[str, str]:
    actor = auth.require_user(request, db, write=True)["user_id"]
    require_location(db, data.location_id)
    eligible = matching.eligible_items(db, data)
    matches = matching.rank_items(eligible, data.features, encoder=request.app.state.text_encoder)
    initial = {item["item_id"]: item for item in eligible}
    with write_transaction(db):
        existing = db.execute(
            """
            SELECT claim_id FROM claims
            WHERE claimant_id = ? AND location_id = ? AND category = ?
              AND normalize_text(features) = ? AND status IN ('pending', 'approved')
            """,
            (actor, data.location_id, data.category, normalize_text(data.features)),
        ).fetchone()
        if existing:
            return {"claim_id": existing["claim_id"]}

        current = {item["item_id"]: item for item in matching.eligible_items(db, data)}
        item_ids = [candidate.item_id for candidate in matches
                    if initial[candidate.item_id] == current.get(candidate.item_id)]
        if not item_ids:
            raise HTTPException(status_code=409, detail="현재 확인을 요청할 수 있는 후보가 없어요.")
        claim_id = str(uuid4())
        db.execute(
            """
            INSERT INTO claims (claim_id, claimant_id, location_id, category, features, proof, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (claim_id, actor, data.location_id, data.category, data.features, data.proof, datetime.now(UTC).isoformat()),
        )
        db.executemany(
            "INSERT INTO claim_candidates (claim_id, item_id) VALUES (?, ?)",
            [(claim_id, item_id) for item_id in item_ids],
        )
    return {"claim_id": claim_id}


@router.get("/mine")
def my_claims(request: Request, db: DB) -> list[dict]:
    actor = auth.require_user(request, db)["user_id"]
    rows = db.execute(
        """
        SELECT c.claim_id, c.category, c.features, c.proof, c.status, c.created_at, c.reply,
               l.region, l.dong
        FROM claims c JOIN locations l ON l.location_id = c.location_id
        WHERE c.claimant_id = ?
        ORDER BY c.created_at DESC
        """,
        (actor,),
    )
    return [dict(row) for row in rows]


@router.get("/review")
def review_queue(request: Request, db: DB) -> list[dict]:
    auth.require_admin(request, db)
    rows = db.execute(
        """
        SELECT c.claim_id, c.category, c.features, c.proof, c.status, c.created_at, c.reply,
               c.approved_item_id, u.display_name AS claimant, l.region, l.dong
        FROM claims c JOIN users u ON u.user_id = c.claimant_id JOIN locations l ON l.location_id = c.location_id
        WHERE c.status IN ('pending', 'approved')
        ORDER BY c.created_at
        """
    ).fetchall()
    result = []
    for claim in rows:
        items = db.execute(
            """
            SELECT i.item_id, i.title, i.features, i.event_date FROM claim_candidates cc
            JOIN items i ON i.item_id = cc.item_id AND i.status = 'held'
            WHERE cc.claim_id = ? AND (
                i.item_id = ? OR (? IS NULL AND NOT EXISTS (
                    SELECT 1 FROM claims c WHERE c.approved_item_id = i.item_id AND c.status = 'approved'
                ))
            )
            ORDER BY i.event_date DESC, i.item_id
            """,
            (claim["claim_id"], claim["approved_item_id"], claim["approved_item_id"]),
        ).fetchall()
        result.append({
            **dict(claim),
            "candidates": [
                {
                    **dict(item),
                    "photo_positions": [row["position"] for row in db.execute(
                        "SELECT position FROM item_photos WHERE item_id = ? ORDER BY position", (item["item_id"],),
                    )],
                }
                for item in items
            ],
        })
    return result


@router.post("/{claim_id}/review")
def decide_claim(claim_id: str, decision: Decision, request: Request, db: DB) -> dict[str, str]:
    reviewer = auth.require_admin(request, db, write=True)
    with write_transaction(db):
        claim = db.execute(
            "SELECT status, claimant_id, approved_item_id FROM claims WHERE claim_id = ?", (claim_id,),
        ).fetchone()
        if claim is None:
            raise HTTPException(status_code=404, detail="확인 요청을 찾을 수 없어요.")
        if claim["claimant_id"] == reviewer:
            raise HTTPException(status_code=403, detail="다른 담당자가 이 요청을 검토해야 해요.")

        expected = "approved" if decision.action == "return" else "pending"
        if claim["status"] != expected:
            raise HTTPException(status_code=409, detail="요청 상태가 바뀌었어요. 목록을 새로고침해 주세요.")

        if decision.action == "approve":
            selected = db.execute(
                """
                SELECT i.item_id FROM claim_candidates cc JOIN items i ON i.item_id = cc.item_id
                WHERE cc.claim_id = ? AND i.item_id = ? AND i.status = 'held' AND NOT EXISTS (
                    SELECT 1 FROM claims c WHERE c.approved_item_id = i.item_id AND c.status = 'approved'
                )
                """,
                (claim_id, decision.item_id),
            ).fetchone()
            if selected is None:
                raise HTTPException(status_code=409, detail="확인할 수 있는 습득물을 선택해 주세요.")
            db.execute(
                """
                UPDATE claims SET status = 'approved', approved_item_id = ?, reviewer_id = ?, reply = ?
                WHERE claim_id = ?
                """,
                (selected["item_id"], reviewer, decision.reply or None, claim_id),
            )
            return {"status": "approved"}

        if decision.action == "reject":
            db.execute("UPDATE claims SET status = 'rejected', reviewer_id = ? WHERE claim_id = ?", (reviewer, claim_id))
            return {"status": "rejected"}

        item_id = claim["approved_item_id"]
        updated = db.execute("UPDATE items SET status = 'returned' WHERE item_id = ? AND status = 'held'", (item_id,))
        if updated.rowcount != 1:
            raise HTTPException(status_code=409, detail="반환할 수 있는 습득물이 없어요.")
        db.execute("UPDATE claims SET status = 'returned' WHERE claim_id = ?", (claim_id,))
        remove_pending_candidate(db, item_id)
        return {"status": "returned"}
