#!/usr/bin/env python3
"""
V4 Step 3: Validate LLM Suggestions Against Video Data

Same validation logic as V3.

Output: data/v4/validated_suggestions.json
"""

import json
import re
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
V1_DIR = DATA_DIR / "v1"
V4_DIR = DATA_DIR / "v4"

# Validation thresholds
VALIDATED_THRESHOLD = 5
PARTIAL_THRESHOLD = 2


def load_llm_suggestions():
    """Load LLM suggestions from step 2."""
    with open(V4_DIR / "llm_suggestions.json") as f:
        return json.load(f)


def load_v1_metadata():
    """Load V1 video metadata."""
    with open(V1_DIR / "metadata.json") as f:
        data = json.load(f)
        if isinstance(data, list):
            return data
        return data.get("videos", [])


def normalize_text(text: str) -> str:
    """Normalize text for matching."""
    return re.sub(r'[^a-z0-9\s]', '', text.lower())


def count_matching_videos(sub_niche: dict, videos: list) -> dict:
    """Count how many videos match a sub-niche's validation keywords."""

    keywords = sub_niche.get("validation_keywords", [])
    expected_hashtags = sub_niche.get("expected_hashtags", [])
    name_words = sub_niche.get("name", "").lower().split()

    all_terms = set()
    for kw in keywords:
        all_terms.add(normalize_text(kw))
    for tag in expected_hashtags:
        all_terms.add(normalize_text(tag))
    for word in name_words:
        if len(word) > 3:
            all_terms.add(normalize_text(word))

    common_words = {"the", "and", "for", "with", "how", "what", "your", "tips", "tutorial"}
    all_terms = all_terms - common_words

    if not all_terms:
        return {"matching_videos": 0, "matching_indices": [], "matched_terms": []}

    matching_indices = []
    matched_terms = set()

    for idx, video in enumerate(videos):
        title = normalize_text(video.get("title", ""))
        tags = [normalize_text(t) for t in video.get("tags", [])]
        desc = normalize_text(video.get("description", "")[:200])

        video_text = f"{title} {' '.join(tags)} {desc}"

        matches = 0
        for term in all_terms:
            if term in video_text:
                matches += 1
                matched_terms.add(term)

        if matches >= 2:
            matching_indices.append(idx)

    return {
        "matching_videos": len(matching_indices),
        "matching_indices": matching_indices[:20],
        "matched_terms": list(matched_terms)
    }


def validate_sub_niche(sub_niche: dict, videos: list) -> dict:
    """Validate a sub-niche and determine its validation status."""

    match_result = count_matching_videos(sub_niche, videos)
    video_count = match_result["matching_videos"]

    if video_count >= VALIDATED_THRESHOLD:
        status = "validated"
    elif video_count >= PARTIAL_THRESHOLD:
        status = "partial"
    else:
        status = "unvalidated"

    validated = {
        **sub_niche,
        "validation_status": status,
        "video_support": video_count,
        "matching_video_indices": match_result["matching_indices"],
        "matched_terms": match_result["matched_terms"]
    }

    return validated


def main():
    print("=" * 60)
    print("V4 Step 3: Validate LLM Suggestions")
    print("=" * 60)

    print("\nLoading LLM suggestions...")
    suggestions = load_llm_suggestions()

    print("Loading V1 metadata...")
    videos = load_v1_metadata()
    print(f"Total videos: {len(videos)}")

    validated_results = {
        "version": "4.0",
        "total_suggestions": suggestions["total_sub_niches_suggested"],
        "validated": 0,
        "partial": 0,
        "unvalidated": 0,
        "suggestions": {}
    }

    print(f"\nValidating {suggestions['total_sub_niches_suggested']} sub-niche suggestions...")

    for niche_id, result in suggestions["suggestions"].items():
        parent_name = result.get("parent_niche", "Unknown")
        sub_niches = result.get("sub_niches", [])

        validated_subs = []
        for sub in sub_niches:
            validated_sub = validate_sub_niche(sub, videos)
            validated_subs.append(validated_sub)

            status = validated_sub["validation_status"]
            validated_results[status] += 1

        validated_results["suggestions"][niche_id] = {
            "parent_niche": parent_name,
            "sub_niches": validated_subs
        }

    # Save results
    output_path = V4_DIR / "validated_suggestions.json"
    with open(output_path, "w") as f:
        json.dump(validated_results, f, indent=2)

    total = validated_results['total_suggestions']
    val = validated_results['validated']
    par = validated_results['partial']
    unval = validated_results['unvalidated']
    validation_rate = (val + par) / total * 100 if total > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"Validation Results:")
    print(f"  Total suggestions: {total}")
    print(f"  Validated (>={VALIDATED_THRESHOLD} videos): {val} ({val/total*100:.1f}%)")
    print(f"  Partial ({PARTIAL_THRESHOLD}-{VALIDATED_THRESHOLD-1} videos): {par} ({par/total*100:.1f}%)")
    print(f"  Unvalidated (<{PARTIAL_THRESHOLD} videos): {unval} ({unval/total*100:.1f}%)")
    print(f"  Validation rate: {validation_rate:.1f}%")
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
