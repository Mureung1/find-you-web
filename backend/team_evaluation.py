"""Evaluate the team's public-data export without writing to the service database."""

import argparse
import json
from collections import Counter, defaultdict
from heapq import nlargest
from math import log
from pathlib import Path

from .db import normalize_text
from .matching import MIN_SEMANTIC_SCORE, TOP_K, WORDS
from .semantic import TextEncoder


def terms(text: str) -> set[str]:
    return {word for word in WORDS.findall(normalize_text(text)) if len(word) >= 2}


def evaluate(root: Path, model: TextEncoder | None = None) -> dict:
    records = json.loads((root / "items.json").read_bytes())["items"]
    cases = json.loads((root / "eval_cases.json").read_bytes())["cases"]
    documents = {
        item["id"]: normalize_text(" ".join(
            item[field] for field in ("item_name", "category_main", "category_sub", "color")
            if item.get(field) and item[field] != "미상"
        ))
        for item in records if item["record_type"] == "found"
    }
    postings = defaultdict(set)
    for item_id, description in documents.items():
        for word in terms(description):
            postings[word].add(item_id)

    text_cases = [case for case in cases if case["query"].get("text")]
    if model:
        import numpy as np

        item_ids = list(documents)
        positions = {item_id: position for position, item_id in enumerate(item_ids)}
        unique = dict.fromkeys(documents.values())
        vectors = model.encode(list(unique))
        text_positions = {description: position for position, description in enumerate(unique)}
        text_rows = [text_positions[description] for description in documents.values()]
        query_vectors = model.encode([case["query"]["text"] for case in text_cases])
        semantic_scores = query_vectors @ vectors.T

    metrics = defaultdict(Counter)
    for query_index, case in enumerate(text_cases):
        excluded = set(case["exclude_item_ids"])
        expected = set(case["answer_item_ids"])
        if not expected <= documents.keys() or not excluded <= documents.keys() or expected & excluded:
            raise ValueError(f"Invalid evaluation IDs for {case['case_id']}")
        text = case["query"]["text"]
        weights = Counter()
        for word in sorted(terms(text)):
            matches = postings.get(word, set())
            weight = log((1 + len(documents)) / (1 + len(matches)))
            for item_id in matches - excluded:
                weights[item_id] += weight
        keyword = nlargest(TOP_K, weights, key=lambda item_id: (weights[item_id], item_id))
        rankings = {"keyword": (keyword, bool(keyword))}
        if model:
            scores = semantic_scores[query_index, text_rows].copy()
            scores[[positions[item_id] for item_id in excluded]] = -np.inf
            order = np.argsort(-scores, kind="stable")[:TOP_K]
            rankings["semantic"] = (
                [item_ids[index] for index in order if np.isfinite(scores[index])],
                bool(len(order) and scores[order[0]] >= MIN_SEMANTIC_SCORE),
            )

        for method, (found, has_candidate) in rankings.items():
            summary = metrics[method]
            if expected:
                summary["positive"] += 1
                summary["top_1_hits"] += int(bool(found and found[0] in expected))
                summary["top_5_hits"] += int(bool(expected.intersection(found)))
                summary["positive_with_candidate"] += int(has_candidate)
                summary["top_5_hits_with_candidate"] += int(has_candidate and bool(expected.intersection(found)))
            else:
                summary["negative"] += 1
                summary["negative_with_candidate"] += int(has_candidate)

    return {
        "found_items": len(documents),
        "masked_item_photos": sum(bool(item.get("image")) for item in records if item["record_type"] == "found"),
        "synthetic_cases": len(cases),
        "text_cases": len(text_cases),
        "skipped_photo_only_cases": len(cases) - len(text_cases),
        "has_legal_neighborhood_field": any(item.get("location_code") for item in records),
        "metrics": dict(metrics),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--text-model", type=Path)
    args = parser.parse_args()
    model = TextEncoder(args.text_model) if args.text_model else None
    print(json.dumps(evaluate(args.source, model), indent=2))


if __name__ == "__main__":
    main()
