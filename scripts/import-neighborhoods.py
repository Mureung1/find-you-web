"""Build the Korean neighborhood fixtures from downloaded code and boundary files."""

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile


FIXTURES = Path(__file__).resolve().parents[1] / "backend" / "fixtures"
REORGANIZED_PROVINCES = {
    "강원도": "강원특별자치도",
    "전라북도": "전북특별자치도",
    "광주광역시": "전남광주통합특별시",
    "전라남도": "전남광주통합특별시",
}
RENAMED_TOWNS = {
    "구지면": "구지읍",
    "양지면": "양지읍",
    "대소면": "대소읍",
    "금수면": "금수강산면",
    "호명면": "호명읍",
    "능서면": "세종대왕면",
}


def active_towns(archive: Path) -> dict[str, str]:
    with ZipFile(archive) as source:
        [filename] = (name for name in source.namelist() if name.endswith(".txt"))
        lines = source.read(filename).decode("cp949").splitlines()[1:]
    return {
        code: name
        for code, name, state in (line.split("\t") for line in lines if line.strip())
        if state.strip() == "존재" and code[5:8] != "000" and code.endswith("00")
    }


def location_row(code: str, full_name: str) -> tuple[str, str, str]:
    region, dong = full_name.rsplit(" ", 1)
    if region.startswith("서울특별시 "):
        region = "서울 " + region.removeprefix("서울특별시 ")
    return code, region, dong


def boundary_keys(name: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    province, *district, dong = name.split()
    province = REORGANIZED_PROVINCES.get(province, province)
    dong = RENAMED_TOWNS.get(dong, dong)
    if province == "인천광역시" and district == ["동구"]:
        district = ["제물포구"]
    exact = (province, *district, dong)
    # These cities changed districts without changing many legal-town names.
    if province == "인천광역시":
        return exact, (province, dong)
    if district and district[0] in {"부천시", "화성시"}:
        return exact, (province, district[0], dong)
    return exact, exact


def match_boundaries(towns: dict[str, str], features: list[dict]) -> dict[str, dict]:
    shapes = {feature["properties"]["EMD_CD"] + "00": feature for feature in features}
    available = collections_by_name(shapes, towns)
    assigned = {}
    used = set()
    for code in towns.keys() & shapes.keys():
        assigned[code] = shapes[code]["geometry"]
        used.add(code)

    pending = {code: boundary_keys(towns[code]) for code in towns.keys() - assigned.keys()}
    for level in range(2):
        # Require a one-to-one match before assigning any retired code to a current town.
        by_shape: dict[str, list[str]] = defaultdict(list)
        for code, keys in pending.items():
            match = available[level].get(keys[level], set()) - used
            if len(match) == 1:
                [candidate] = match
                by_shape[candidate].append(code)
        for candidate, codes in by_shape.items():
            if len(codes) == 1:
                [code] = codes
                assigned[code] = shapes[candidate]["geometry"]
                used.add(candidate)
                del pending[code]
    return assigned


def collections_by_name(
    shapes: dict[str, dict], towns: dict[str, str],
) -> tuple[dict[tuple[str, ...], set[str]], dict[tuple[str, ...], set[str]]]:
    exact = defaultdict(set)
    relaxed = defaultdict(set)
    for code, feature in shapes.items():
        if code not in towns:
            exact_key, relaxed_key = boundary_keys(feature["properties"]["FULL_NM"])
            exact[exact_key].add(code)
            relaxed[relaxed_key].add(code)
    return exact, relaxed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codes_zip", type=Path)
    parser.add_argument("boundaries_geojson", type=Path)
    args = parser.parse_args()
    towns = active_towns(args.codes_zip)
    features = json.loads(args.boundaries_geojson.read_text(encoding="utf-8"))["features"]
    if not (len(towns) > 5000 and len(features) > 5000):
        raise ValueError("Expected nationwide code and boundary files")
    geometry = match_boundaries(towns, features)
    rows = [location_row(code, towns[code]) for code in sorted(towns)]
    (FIXTURES / "korean-neighborhoods.json").write_text(
        "[\n" + ",\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n]\n", encoding="utf-8",
    )
    payload = json.dumps(geometry, sort_keys=True, separators=(",", ":")).encode()
    (FIXTURES / "korean-neighborhood-boundaries.json.gz").write_bytes(gzip.compress(payload, mtime=0))
    print(f"Catalog: {len(towns)}. Matched boundaries: {len(geometry)}.")
    for code in sorted(towns.keys() - geometry.keys()):
        print(code, towns[code])


if __name__ == "__main__":
    main()
