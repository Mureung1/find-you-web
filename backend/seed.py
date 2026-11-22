from pathlib import Path
from sqlite3 import Connection


def migrate_demo_locations(db: Connection) -> None:
    replacements = [
        ("mapo-seongsan", "haeon-east-library"),
        ("mapo-yeonnam", "haeon-west-library"),
        ("mapo-seongsan", "haeon-east-student-center"),
        ("mapo-sangam", "world-cup-park"),
        ("seodaemun-sinchon", "narae-main-hall"),
    ]
    db.executemany("UPDATE items SET location_id = ? WHERE location_id = ?", replacements)
    db.executemany("DELETE FROM locations WHERE location_id = ?", [(old_id,) for _, old_id in replacements])


def seed_demo(db: Connection) -> None:
    db.executemany(
        "INSERT OR IGNORE INTO locations (location_id, region, dong) VALUES (?, ?, ?)",
        [
            ("mapo-mangwon", "서울 마포구", "망원동"),
            ("mapo-sangam", "서울 마포구", "상암동"),
            ("mapo-seongsan", "서울 마포구", "성산동"),
            ("mapo-yeonnam", "서울 마포구", "연남동"),
            ("seodaemun-sinchon", "서울 서대문구", "신촌동"),
        ],
    )
    db.executemany(
        """
        INSERT OR IGNORE INTO items
            (item_id, kind, location_id, category, title, event_date, consent_to_publish, status)
        VALUES (?, 'lost', ?, ?, ?, ?, 1, ?)
        """,
        [
            ("demo-lost-01", "mapo-seongsan", "electronics", "흰색 무선 이어폰", "2026-11-21", "searching"),
            ("demo-lost-02", "mapo-yeonnam", "wallet", "검정색 반지갑", "2026-11-20", "searching"),
            ("demo-lost-03", "mapo-sangam", "accessory", "연두색 텀블러", "2026-11-20", "searching"),
            ("demo-lost-04", "mapo-seongsan", "card", "파란색 교통카드", "2026-11-19", "searching"),
            ("demo-lost-05", "seodaemun-sinchon", "bag", "남색 에코백", "2026-11-18", "returned"),
            ("demo-lost-06", "mapo-yeonnam", "clothing", "회색 니트 장갑", "2026-11-17", "searching"),
        ],
    )
    db.execute(
        """
        INSERT OR IGNORE INTO items
            (item_id, kind, location_id, category, title, event_date, features, status)
        VALUES ('demo-found-01', 'found', 'mapo-seongsan', 'accessory',
                '접이식 우산', '2026-11-21', '손잡이에 별 스티커', 'held')
        """,
    )
    fixture = Path(__file__).with_name("fixtures") / "demo-umbrella.png"
    db.execute(
        """
        INSERT OR IGNORE INTO item_photos (item_id, position, content_type, content)
        VALUES ('demo-found-01', 0, 'image/png', ?)
        """,
        (fixture.read_bytes(),),
    )
