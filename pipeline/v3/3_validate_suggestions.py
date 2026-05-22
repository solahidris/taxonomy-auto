#!/usr/bin/env python3
"""
V3 Step 3: Validate LLM Suggestions Against Video Data

This script validates LLM-suggested sub-niches by checking if they have
real video support in our dataset. Uses keyword matching against video titles.

Validation rules:
- ≥5 videos matching keywords = "validated"
- 2-4 videos = "partial"
- 0-1 videos = "unvalidated" (keep for future data collection)

Output: data/v3/validated_suggestions.json
"""

import json
import re
from collections import defaultdict
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
V1_DIR = DATA_DIR / "v1"
V3_DIR = DATA_DIR / "v3"

# Validation thresholds
VALIDATED_THRESHOLD = 5  # Videos needed for "validated"
PARTIAL_THRESHOLD = 2    # Videos needed for "partial"


def load_llm_suggestions():
    """Load LLM suggestions from step 2."""
    with open(V3_DIR / "llm_suggestions.json") as f:
        return json.load(f)


def load_v1_metadata():
    """Load V1 video metadata."""
    with open(V1_DIR / "metadata.json") as f:
        data = json.load(f)
        # Handle both list format and dict format
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

    # Combine all matching terms
    all_terms = set()
    for kw in keywords:
        all_terms.add(normalize_text(kw))
    for tag in expected_hashtags:
        all_terms.add(normalize_text(tag))
    for word in name_words:
        if len(word) > 3:  # Skip short words
            all_terms.add(normalize_text(word))

    # Remove common words
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

        # Check for keyword matches
        matches = 0
        for term in all_terms:
            if term in video_text:
                matches += 1
                matched_terms.add(term)

        # Require at least 2 term matches for a video match
        if matches >= 2:
            matching_indices.append(idx)

    return {
        "matching_videos": len(matching_indices),
        "matching_indices": matching_indices[:20],  # Limit stored indices
        "matched_terms": list(matched_terms)
    }


def validate_sub_niche(sub_niche: dict, videos: list) -> dict:
    """Validate a sub-niche and determine its validation status."""

    match_result = count_matching_videos(sub_niche, videos)
    video_count = match_result["matching_videos"]

    # Determine validation status
    if video_count >= VALIDATED_THRESHOLD:
        status = "validated"
    elif video_count >= PARTIAL_THRESHOLD:
        status = "partial"
    else:
        status = "unvalidated"

    # Update sub-niche with validation info
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
    print("V3 Step 3: Validate LLM Suggestions")
    print("=" * 60)

    # Load data
    print("\nLoading LLM suggestions...")
    suggestions = load_llm_suggestions()

    print("Loading V1 metadata...")
    videos = load_v1_metadata()
    print(f"Total videos: {len(videos)}")

    # Validate each sub-niche
    validated_results = {
        "version": "3.0",
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

            # Count by status
            status = validated_sub["validation_status"]
            validated_results[status] += 1

        validated_results["suggestions"][niche_id] = {
            "parent_niche": parent_name,
            "sub_niches": validated_subs
        }

    # Save results
    output_path = V3_DIR / "validated_suggestions.json"
    with open(output_path, "w") as f:
        json.dump(validated_results, f, indent=2)

    print(f"\nValidation Results:")
    print(f"  Total suggestions: {validated_results['total_suggestions']}")
    print(f"  Validated (≥{VALIDATED_THRESHOLD} videos): {validated_results['validated']}")
    print(f"  Partial ({PARTIAL_THRESHOLD}-{VALIDATED_THRESHOLD-1} videos): {validated_results['partial']}")
    print(f"  Unvalidated (<{PARTIAL_THRESHOLD} videos): {validated_results['unvalidated']}")
    print(f"\nSaved to: {output_path}")

    # Show validated examples
    print(f"\nValidated sub-niches (sample):")
    count = 0
    for niche_id, result in validated_results["suggestions"].items():
        for sub in result.get("sub_niches", []):
            if sub["validation_status"] == "validated" and count < 10:
                print(f"  - {sub['name']} ({sub['video_support']} videos)")
                count += 1
        if count >= 10:
            break


if __name__ == "__main__":
    main()
