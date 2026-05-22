#!/usr/bin/env python3
"""V1 Step 5: Multi-label classification with open-set detection.

Features:
- Multi-label: Returns top N niches with confidence scores
- Hierarchical: Shows category -> subcategory -> niche path
- Open-set detection: Flags creators that don't fit well (potential new niches)
- Confidence calibration: Based on cosine similarity distribution

Usage:
    python 5_classify.py "I make cooking videos for busy professionals"
    python 5_classify.py --batch input.txt
"""

import json
import argparse
import numpy as np
from pathlib import Path
from openai import OpenAI
from sklearn.preprocessing import normalize
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

client = OpenAI()
PROJECT_ROOT = Path(__file__).parent.parent.parent
TAXONOMY = PROJECT_ROOT / "data/v1/taxonomy.json"
EMBEDDINGS = PROJECT_ROOT / "data/v1/embeddings.npy"
MODEL = "text-embedding-3-small"

# Classification parameters
TOP_N = 5  # Number of niche matches to return
UNKNOWN_THRESHOLD = 0.35  # Below this = potential unknown niche
HIGH_CONFIDENCE_THRESHOLD = 0.55  # Above this = high confidence match
MULTI_LABEL_GAP = 0.08  # If 2nd best is within this of best, include both


def load_taxonomy():
    """Load taxonomy with precomputed centroids."""
    taxonomy = json.loads(TAXONOMY.read_text())

    # Build centroid matrix for fast similarity computation
    niche_ids = list(taxonomy["niches"].keys())
    centroids = np.array([taxonomy["niches"][n]["centroid"] for n in niche_ids])
    centroids = normalize(centroids.astype(np.float64))

    return taxonomy, niche_ids, centroids


def embed_text(text: str) -> np.ndarray:
    """Embed a single text using OpenAI API."""
    resp = client.embeddings.create(model=MODEL, input=[text])
    vec = np.array(resp.data[0].embedding, dtype=np.float64)
    return normalize(vec.reshape(1, -1))[0]


def compute_confidence(similarity: float, all_similarities: np.ndarray) -> dict:
    """Compute confidence metrics from similarity score."""
    # Percentile rank among all niches
    percentile = (all_similarities < similarity).sum() / len(all_similarities) * 100

    # Calibrated confidence (0-100 scale)
    # Map similarity range [0.2, 0.7] to confidence [0, 100]
    calibrated = max(0, min(100, (similarity - 0.2) / 0.5 * 100))

    return {
        "raw_similarity": float(similarity),
        "confidence": round(calibrated, 1),
        "percentile": round(percentile, 1),
    }


def classify_creator(bio: str, taxonomy: dict, niche_ids: list, centroids: np.ndarray) -> dict:
    """Classify a creator bio and return multi-label results with confidence."""
    # Embed the bio
    bio_vec = embed_text(bio)

    # Compute similarities to all niche centroids
    similarities = centroids @ bio_vec

    # Sort by similarity
    sorted_indices = np.argsort(similarities)[::-1]

    # Get top N matches
    matches = []
    for i in range(min(TOP_N, len(sorted_indices))):
        idx = sorted_indices[i]
        niche_id = niche_ids[idx]
        niche_data = taxonomy["niches"][niche_id]
        sim = similarities[idx]

        conf = compute_confidence(sim, similarities)

        matches.append({
            "rank": i + 1,
            "niche_id": niche_id,
            "niche_name": niche_data["name"],
            "category": niche_data["category_name"],
            "subcategory": niche_data["subcategory_name"],
            "hierarchy": f"{niche_data['category_name']} > {niche_data['subcategory_name']} > {niche_data['name']}",
            "confidence": conf["confidence"],
            "raw_similarity": conf["raw_similarity"],
            "percentile": conf["percentile"],
            "exemplar_creators": niche_data.get("exemplar_creators", [])[:5],
            "sample_titles": niche_data.get("sample_titles", [])[:5],
        })

    # Determine primary/secondary labels
    primary_matches = [matches[0]] if matches else []
    secondary_matches = []

    if len(matches) > 1:
        # Check if multiple niches are close enough to be relevant
        best_sim = matches[0]["raw_similarity"]
        for m in matches[1:]:
            if best_sim - m["raw_similarity"] < MULTI_LABEL_GAP:
                secondary_matches.append(m)
            else:
                break

    # Open-set detection
    best_similarity = matches[0]["raw_similarity"] if matches else 0
    is_unknown = best_similarity < UNKNOWN_THRESHOLD
    is_high_confidence = best_similarity >= HIGH_CONFIDENCE_THRESHOLD

    # Generate classification summary
    if is_unknown:
        classification_status = "UNKNOWN"
        status_message = "This creator may represent a NEW or UNDERSERVED niche not well covered by current taxonomy."
    elif is_high_confidence:
        classification_status = "HIGH_CONFIDENCE"
        status_message = "Strong match found in taxonomy."
    else:
        classification_status = "MODERATE"
        status_message = "Reasonable match, but creator may span multiple niches."

    # Multi-label determination
    all_labels = primary_matches + secondary_matches
    is_multi_label = len(all_labels) > 1

    return {
        "input_bio": bio,
        "classification_status": classification_status,
        "status_message": status_message,
        "is_unknown_niche": is_unknown,
        "is_multi_label": is_multi_label,
        "primary_niche": primary_matches[0] if primary_matches else None,
        "all_matches": matches,
        "recommended_labels": all_labels,
        "stats": {
            "best_similarity": float(best_similarity),
            "similarity_gap_to_2nd": float(matches[0]["raw_similarity"] - matches[1]["raw_similarity"]) if len(matches) > 1 else 0,
            "num_close_matches": len(all_labels),
        }
    }


def print_result(result: dict):
    """Pretty print classification result."""
    print("\n" + "=" * 60)
    print(f"INPUT: {result['input_bio'][:80]}...")
    print("=" * 60)

    # Status
    status = result["classification_status"]
    if status == "UNKNOWN":
        print(f"\n[!] STATUS: {status}")
        print(f"    {result['status_message']}")
    elif status == "HIGH_CONFIDENCE":
        print(f"\n[*] STATUS: {status}")
    else:
        print(f"\n[~] STATUS: {status}")

    # Primary match
    if result["primary_niche"]:
        p = result["primary_niche"]
        print(f"\n PRIMARY NICHE: {p['niche_name']}")
        print(f"   Hierarchy: {p['hierarchy']}")
        print(f"   Confidence: {p['confidence']}%")

        if p.get("exemplar_creators"):
            creators = [c["channel_title"] for c in p["exemplar_creators"][:3]]
            print(f"   Similar creators: {', '.join(creators)}")

    # Multi-label
    if result["is_multi_label"]:
        print(f"\n MULTI-LABEL: Creator spans multiple niches:")
        for m in result["recommended_labels"][1:]:
            print(f"   + {m['niche_name']} ({m['confidence']}%)")

    # All matches
    print(f"\n TOP {len(result['all_matches'])} MATCHES:")
    for m in result["all_matches"]:
        conf_bar = "*" * int(m["confidence"] / 10)
        print(f"   {m['rank']}. [{conf_bar:10}] {m['confidence']:5.1f}% | {m['niche_name']}")
        print(f"      {m['hierarchy']}")

    # Unknown niche suggestion
    if result["is_unknown_niche"]:
        print("\n [!] POTENTIAL NEW NICHE DETECTED")
        print("     This creator's content may not fit existing categories well.")
        print("     Consider creating a new niche based on their unique focus.")


def main():
    parser = argparse.ArgumentParser(description="Classify creator bios into taxonomy")
    parser.add_argument("bio", nargs="?", help="Creator bio to classify")
    parser.add_argument("--batch", type=str, help="File with bios (one per line)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    print("Loading taxonomy...")
    taxonomy, niche_ids, centroids = load_taxonomy()
    print(f"Loaded {len(niche_ids)} niches")

    if args.batch:
        # Batch mode
        bios = Path(args.batch).read_text().strip().split("\n")
        results = []
        for bio in bios:
            if bio.strip():
                result = classify_creator(bio.strip(), taxonomy, niche_ids, centroids)
                results.append(result)
                if not args.json:
                    print_result(result)

        if args.json:
            print(json.dumps(results, indent=2))

    elif args.bio:
        # Single bio mode
        result = classify_creator(args.bio, taxonomy, niche_ids, centroids)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print_result(result)

    else:
        # Interactive mode
        print("\nEnter creator bios (empty line to quit):")
        while True:
            bio = input("\nBio> ").strip()
            if not bio:
                break
            result = classify_creator(bio, taxonomy, niche_ids, centroids)
            print_result(result)


if __name__ == "__main__":
    main()
