import json
import socket
import unittest
from contextlib import closing
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic, sleep
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import uvicorn
from PIL import Image

from backend import auth
from backend.db import connect, initialize
from backend.team_data import evaluate_dataset, import_dataset
from backend.team_evaluation import evaluate as evaluate_team_export


ORIGIN = "http://localhost:3000"
FEATURES = "손잡이에 별 스티커"
QUERY = {"location_id": "mapo-seongsan", "category": "accessory", "features": "스티커 별 손잡이에"}


def test_photo() -> bytes:
    image = Image.new("RGB", (8, 8), "green")
    exif = image.getexif()
    exif[272] = "Private camera information"
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


class LiveAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        work = cls.enterClassContext(TemporaryDirectory())
        cls.db_path = Path(work) / "api.sqlite3"
        initialize(cls.db_path)
        cls.tokens = {}
        with closing(connect(cls.db_path)) as db:
            for name in ("finder", "claimant", "other", "reviewer"):
                cls.tokens[name] = auth.start_session(db, name, name, None)
            reviewer = auth.current_user(db, cls.tokens["reviewer"])["user_id"]

        cls.enterClassContext(patch.dict("os.environ", {
            "FIND_YOU_DB_PATH": str(cls.db_path),
            "FIND_YOU_GOOGLE_CLIENT_ID": "test.apps.googleusercontent.com",
            "FIND_YOU_AUTH_ORIGIN": ORIGIN,
            "FIND_YOU_ADMIN_USER_IDS": reviewer,
            "FIND_YOU_LIVE": "0",
            "FIND_YOU_TEXT_MODEL_PATH": "",
        }))
        listener = cls.enterClassContext(socket.socket())
        listener.bind(("127.0.0.1", 0))
        cls.api = f"http://127.0.0.1:{listener.getsockname()[1]}"
        server = uvicorn.Server(uvicorn.Config("backend.main:app", log_level="error", ws="none"))
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        cls.addClassCleanup(thread.join, 5)
        cls.addClassCleanup(setattr, server, "should_exit", True)
        deadline = monotonic() + 5
        while not server.started and thread.is_alive() and monotonic() < deadline:
            sleep(0.02)
        if not server.started:
            raise RuntimeError("Isolated FastAPI server did not start")

    def request(self, path, *, actor=None, method="GET", body=None, code=200, origin=ORIGIN, media=None):
        headers = {"Origin": origin}
        if actor:
            headers["Cookie"] = f"{auth.SESSION_COOKIE}={self.tokens[actor]}"
        if body is not None:
            headers["Content-Type"] = media or "application/json"
            if media is None:
                body = json.dumps(body).encode()
        request = Request(self.api + path, method=method, headers=headers, data=body)
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            content = response.read()
            self.assertEqual(response.status, code, (method, path, content[:400]))
            if response.headers.get_content_type() == "application/json":
                self.assertIn("no-store", response.headers.get("Cache-Control", ""))
                return json.loads(content)
            return content, response.headers

    def test_private_photos_claim_review_and_return(self):
        item = {**QUERY, "title": "테스트 우산", "event_date": "2026-01-01", "features": FEATURES}
        # Use a unique neighborhood to keep the demo seed out of this workflow.
        item["location_id"] = "mapo-yeonnam"
        query = {**QUERY, "location_id": item["location_id"]}
        item_id = self.request("/api/found-items", actor="finder", method="POST", body=item, code=201)["item_id"]
        path = f"/api/my/items/{item_id}"
        edit = {**item, "title": "수정한 테스트 우산", "kind": "found"}
        self.request("/api/my/items", code=401)
        self.assertEqual(self.request("/api/my/items", actor="other"), [])
        self.request(path, actor="other", method="PUT", body=edit, code=404)
        self.request(path, actor="reviewer", method="DELETE", code=404)
        self.request(path, actor="finder", method="PUT", body=edit, code=403, origin="https://other.example")
        self.request(path, actor="finder", method="PUT", body=edit)
        self.assertEqual(self.request("/api/my/items", actor="finder")[0]["title"], edit["title"])

        self.request(f"{path}/photos", actor="finder", method="POST", body=b"not an image", media="image/jpeg", code=422)
        photo = self.request(f"{path}/photos", actor="finder", method="POST", body=test_photo(), media="image/jpeg", code=201)
        photo_path = f"{path}/photos/{photo['position']}"
        self.request(photo_path, code=401)
        self.request(photo_path, actor="other", code=404)
        for actor in ("finder", "reviewer"):
            content, headers = self.request(photo_path, actor=actor)
            self.assertEqual(headers["Cache-Control"], "private, no-store")
            with Image.open(BytesIO(content)) as image:
                self.assertFalse(image.getexif())
        self.assertEqual(self.request("/api/candidates/check", method="POST", body=query), {"has_candidate": True})

        proof = {**query, "proof": "안쪽에 이름을 지운 자리가 있어요."}
        self.request("/api/claims", method="POST", body=proof, code=401)
        claim_id = self.request("/api/claims", actor="claimant", method="POST", body=proof, code=201)["claim_id"]
        self.assertEqual(
            self.request("/api/claims", actor="claimant", method="POST", body=proof, code=201)["claim_id"], claim_id,
        )
        rival = self.request("/api/claims", actor="other", method="POST", body=proof, code=201)["claim_id"]
        own_claim = self.request("/api/claims/mine", actor="claimant")[0]
        self.assertEqual(own_claim["claim_id"], claim_id)
        self.assertNotIn("approved_item_id", own_claim)
        self.assertEqual(self.request("/api/claims/mine", actor="finder"), [])
        self.request("/api/claims/review", actor="claimant", code=403)
        queue = self.request("/api/claims/review", actor="reviewer")
        self.assertEqual(queue[0]["candidates"][0]["item_id"], item_id)

        decision_path = f"/api/claims/{claim_id}/review"
        approval = {"action": "approve", "item_id": item_id, "reply": "보관 담당자에게 문의해 주세요."}
        self.request(decision_path, actor="claimant", method="POST", body=approval, code=403)
        self.request(decision_path, actor="reviewer", method="POST", body=approval)
        self.request(f"/api/claims/{rival}/review", actor="reviewer", method="POST", body=approval, code=409)
        self.request(path, actor="finder", method="DELETE", code=409)
        self.request(photo_path, actor="finder", method="DELETE", code=409)
        self.assertEqual(self.request("/api/candidates/check", method="POST", body=query), {"has_candidate": False})
        self.assertEqual(self.request("/api/claims/mine", actor="claimant")[0]["reply"], approval["reply"])

        self.request(decision_path, actor="reviewer", method="POST", body={"action": "return"})
        self.assertEqual(self.request("/api/claims/mine", actor="claimant")[0]["status"], "returned")
        self.assertEqual(self.request("/api/claims/mine", actor="other")[0]["status"], "rejected")
        self.assertEqual(self.request("/api/my/items", actor="finder")[0]["status"], "returned")
        self.request(path, actor="finder", method="DELETE")
        self.request(photo_path, actor="reviewer", code=404)
        with closing(connect(self.db_path)) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM item_photos WHERE item_id = ?", (item_id,)).fetchone())

    def test_consent_edit_and_delete(self):
        item = {"location_id": "mapo-seongsan", "category": "bag", "title": "공개 동의 테스트 가방",
                "event_date": "2026-01-01", "consent_to_publish": False}
        result = self.request("/api/lost-items", actor="finder", method="POST", body=item, code=201)
        item_id = result["item_id"]
        self.assertNotIn(item_id, {row["item_id"] for row in self.request("/api/lost-items")})
        path = f"/api/my/items/{item_id}"
        edit = {**item, "consent_to_publish": True, "kind": "lost", "status": "returned"}
        self.request(path, actor="finder", method="PUT", body=edit)
        public = next(row for row in self.request("/api/lost-items") if row["item_id"] == item_id)
        self.assertEqual(public["status"], "returned")
        self.assertNotIn("owner_id", public)
        self.request(path, actor="finder", method="DELETE")
        self.assertNotIn(item_id, {row["item_id"] for row in self.request("/api/lost-items")})


class TeamData(unittest.TestCase):
    def test_old_sqlite_keeps_items_and_photos(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        db_path = root / "old.sqlite3"
        with closing(connect(db_path)) as db:
            db.executescript("""
                CREATE TABLE locations (location_id TEXT PRIMARY KEY, region TEXT NOT NULL, place TEXT NOT NULL);
                CREATE TABLE items (
                    item_id TEXT PRIMARY KEY, kind TEXT, location_id TEXT REFERENCES locations(location_id),
                    category TEXT, title TEXT, event_date TEXT, features TEXT, consent_to_publish INTEGER DEFAULT 0,
                    status TEXT
                );
                CREATE TABLE item_photos (
                    item_id TEXT REFERENCES items(item_id) ON DELETE CASCADE, position INTEGER,
                    content_type TEXT, content BLOB, PRIMARY KEY (item_id, position)
                );
                INSERT INTO locations VALUES ('haeon-west-library', '기존 지역', '기존 장소');
                INSERT INTO items VALUES (
                    'old-found', 'found', 'haeon-west-library', 'accessory', '우산', '2026-01-01',
                    '손잡이 표식', 0, 'held'
                );
            """)
            db.execute("INSERT INTO item_photos VALUES ('old-found', 0, 'image/jpeg', ?)", (test_photo(),))
            db.commit()
        initialize(db_path, with_demo=False)
        initialize(db_path, with_demo=False)
        with closing(connect(db_path)) as db:
            rows = db.execute("SELECT item_id, location_id, owner_id FROM items").fetchall()
            self.assertEqual([tuple(row) for row in rows], [("old-found", "mapo-yeonnam", None)])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM item_photos").fetchone()[0], 1)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_team_export_respects_excluded_items(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        items = {"items": [
            {"id": "found", "record_type": "found", "item_name": "우산", "image": "images/item.jpg"},
            {"id": "lost", "record_type": "lost", "item_name": "우산"},
        ]}
        cases = {"cases": [
            {"case_id": "positive", "query": {"text": "우산"}, "answer_item_ids": ["found"], "exclude_item_ids": []},
            {"case_id": "held-out", "query": {"text": "우산"}, "answer_item_ids": [], "exclude_item_ids": ["found"]},
            {"case_id": "photo-only", "query": {"image": "images/query.jpg"}},
        ]}
        (root / "items.json").write_text(json.dumps(items), encoding="utf8")
        (root / "eval_cases.json").write_text(json.dumps(cases), encoding="utf8")
        result = evaluate_team_export(root)
        self.assertEqual(result["found_items"], 1)
        self.assertEqual(result["skipped_photo_only_cases"], 1)
        self.assertEqual(result["metrics"]["keyword"]["top_5_hits"], 1)
        self.assertEqual(result["metrics"]["keyword"]["negative_with_candidate"], 0)

    def test_import_and_evaluate(self):
        root = Path(self.enterContext(TemporaryDirectory())).resolve()
        db_path = root / "clean.sqlite3"
        initialize(db_path, with_demo=False)
        db = self.enterContext(closing(connect(db_path)))
        (root / "image.jpg").write_bytes(test_photo())
        item = {"record_id": "umbrella", "kind": "found", "location_code": "TEAM-SEONGSAN",
                "category": "accessory", "title": "우산", "event_date": "2026-01-01", "features": FEATURES,
                "image_paths": ["image.jpg"]}
        source = root / "items.json"
        source.write_text(json.dumps([item]), encoding="utf8")
        mapping = {"TEAM-SEONGSAN": "mapo-seongsan"}
        self.assertEqual(import_dataset(db, root, "test", mapping), 1)
        item_id = db.execute("SELECT item_id FROM items").fetchone()["item_id"]
        self.assertEqual(import_dataset(db, root, "test", mapping), 1)
        self.assertEqual([row["item_id"] for row in db.execute("SELECT item_id FROM items")], [item_id])
        self.assertEqual(db.execute("SELECT COUNT(*) FROM item_photos").fetchone()[0], 1)

        query = {"location_code": "TEAM-SEONGSAN", "category": "accessory", "features": QUERY["features"]}
        cases = [
            {"case_id": "reordered", "query": query, "expected_found_record_ids": ["umbrella"]},
            {"case_id": "wrong-dong", "query": {**query, "location_code": "mapo-yeonnam"},
             "expected_found_record_ids": []},
        ]
        (root / "eval_cases.json").write_text(json.dumps(cases), encoding="utf8")
        summary = evaluate_dataset(db, root, "test", mapping)
        self.assertEqual(summary["exact"]["misses"], 1)
        self.assertEqual(summary["similarity"]["hits"], 1)
        self.assertEqual(summary["similarity"]["false_positives"], 0)

        bad_photo = {**item, "record_id": "bad", "image_paths": ["../outside.jpg"]}
        source.write_text(json.dumps([{**item, "title": "롤백되는 수정"}, bad_photo]), encoding="utf8")
        with self.assertRaises(ValueError):
            import_dataset(db, root, "test", mapping)
        self.assertEqual(db.execute("SELECT title FROM items").fetchone()["title"], item["title"])
