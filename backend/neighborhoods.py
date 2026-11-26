import gzip
import json
from functools import cache
from pathlib import Path
from sqlite3 import Connection

from shapely.geometry import Point, shape
from shapely.strtree import STRtree


FIXTURES = Path(__file__).with_name("fixtures")
LEGACY_IDS = {
    "1144012300": "mapo-mangwon",
    "1144012400": "mapo-yeonnam",
    "1144012500": "mapo-seongsan",
    "1144012700": "mapo-sangam",
    "1141011400": "seodaemun-sinchon",
}


def seed_neighborhoods(db: Connection) -> None:
    entries = json.loads((FIXTURES / "korean-neighborhoods.json").read_text(encoding="utf-8"))
    db.executemany(
        """
        INSERT INTO locations (location_id, region, dong) VALUES (?, ?, ?)
        ON CONFLICT(location_id) DO UPDATE SET region = excluded.region, dong = excluded.dong
        """,
        ((LEGACY_IDS.get(code, code), region, dong) for code, region, dong in entries),
    )


@cache
def boundary_index() -> tuple[STRtree, tuple[str, ...]]:
    with gzip.open(FIXTURES / "korean-neighborhood-boundaries.json.gz", "rt", encoding="utf-8") as file:
        boundaries = json.load(file)
    return STRtree([shape(geometry) for geometry in boundaries.values()]), tuple(boundaries)


def neighborhood_at(latitude: float, longitude: float) -> str | None:
    index, codes = boundary_index()
    matches = index.query(Point(longitude, latitude), predicate="covered_by")
    if len(matches) != 1:
        return None
    code = codes[matches[0]]
    return LEGACY_IDS.get(code, code)
