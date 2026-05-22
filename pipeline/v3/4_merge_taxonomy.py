#!/usr/bin/env python3
"""
V3 Step 4: Merge Validated Sub-Niches into Taxonomy

This script creates the V3 taxonomy by:
1. Starting with V2 taxonomy (234 niches)
2. Adding validated and partial sub-niches as new entries
3. Maintaining clear source tagging (embedding_clustered, hashtag_discovered, llm_generated)
4. Creating parent-child relationships

Output: data/v3/taxonomy.json
"""

import json
from pathlib import Path
from collections import defaultdict

# Paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
V2_DIR = DATA_DIR / "v2"
V3_DIR = DATA_DIR / "v3"

# Include partial validations?
INCLUDE_PARTIAL = True


def load_v2_taxonomy():
    """Load V2 taxonomy."""
    with open(V2_DIR / "taxonomy.json") as f:
        return json.load(f)


def load_validated_suggestions():
    """Load validated suggestions from step 3."""
    with open(V3_DIR / "validated_suggestions.json") as f:
        return json.load(f)


def generate_sub_niche_id(parent_id: str, index: int) -> str:
    """Generate unique ID for a sub-niche."""
    return f"v3_sub_{parent_id}_{index}"


def main():
    print("=" * 60)
    print("V3 Step 4: Merge Validated Sub-Niches into Taxonomy")
    print("=" * 60)

    # Load data
    print("\nLoading V2 taxonomy...")
    v2_taxonomy = load_v2_taxonomy()

    print("Loading validated suggestions...")
    validated = load_validated_suggestions()

    # Start with V2 taxonomy structure
    v3_taxonomy = {
        "version": "3.0",
        "approach": "hybrid_embedding_hashtag_llm",
        "categories": v2_taxonomy["categories"].copy(),
        "subcategories": v2_taxonomy["subcategories"].copy(),
        "niches": {},
        "sub_niches": {},  # New: LLM-generated sub-niches
        "stats": {
            "total_niches": 0,
            "v1_embedding_niches": 0,
            "v2_hashtag_niches": 0,
            "v3_llm_sub_niches": 0,
            "validated_sub_niches": 0,
            "partial_sub_niches": 0,
            "total_categories": len(v2_taxonomy["categories"]),
            "total_subcategories": len(v2_taxonomy["subcategories"])
        }
    }

    # Copy V2 niches, adding has_sub_niches flag
    print("\nCopying V2 niches...")
    for niche_id, niche_data in v2_taxonomy["niches"].items():
        niche_copy = niche_data.copy()
        niche_copy["has_sub_niches"] = False
        niche_copy["sub_niche_ids"] = []
        v3_taxonomy["niches"][niche_id] = niche_copy

        # Count by source
        source = niche_data.get("source", "embedding_clustered")
        if source == "embedding_clustered":
            v3_taxonomy["stats"]["v1_embedding_niches"] += 1
        elif source == "hashtag_discovered":
            v3_taxonomy["stats"]["v2_hashtag_niches"] += 1

    # Add validated sub-niches
    print("Adding validated sub-niches...")
    sub_niche_count = 0

    for niche_id, result in validated["suggestions"].items():
        parent_niche = v3_taxonomy["niches"].get(niche_id)
        if not parent_niche:
            continue

        sub_niches_added = []

        for idx, sub in enumerate(result.get("sub_niches", [])):
            status = sub.get("validation_status", "unvalidated")

            # Skip unvalidated unless we want to keep them
            if status == "unvalidated":
                continue
            if status == "partial" and not INCLUDE_PARTIAL:
                continue

            # Generate unique ID
            sub_id = generate_sub_niche_id(niche_id, idx)

            # Create sub-niche entry
            sub_niche_entry = {
                "id": sub_id,
                "name": sub.get("name", "Unknown"),
                "description": sub.get("description", ""),
                "source": "llm_generated",
                "confidence": "inferred",
                "validation_status": status,
                "video_support": sub.get("video_support", 0),
                "parent_niche_id": niche_id,
                "parent_niche_name": parent_niche.get("name", ""),
                "category_name": parent_niche.get("category_name", ""),
                "subcategory_name": parent_niche.get("subcategory_name", ""),
                "target_audience": sub.get("target_audience", ""),
                "validation_keywords": sub.get("validation_keywords", []),
                "expected_hashtags": sub.get("expected_hashtags", []),
                "matched_terms": sub.get("matched_terms", []),
                "matching_video_indices": sub.get("matching_video_indices", [])
            }

            v3_taxonomy["sub_niches"][sub_id] = sub_niche_entry
            sub_niches_added.append(sub_id)
            sub_niche_count += 1

            # Update stats
            v3_taxonomy["stats"]["v3_llm_sub_niches"] += 1
            if status == "validated":
                v3_taxonomy["stats"]["validated_sub_niches"] += 1
            elif status == "partial":
                v3_taxonomy["stats"]["partial_sub_niches"] += 1

        # Update parent niche
        if sub_niches_added:
            parent_niche["has_sub_niches"] = True
            parent_niche["sub_niche_ids"] = sub_niches_added

    # Calculate total niches
    v3_taxonomy["stats"]["total_niches"] = (
        len(v3_taxonomy["niches"]) +
        len(v3_taxonomy["sub_niches"])
    )

    # Build hierarchy for easier UI consumption
    hierarchy = defaultdict(lambda: {"name": "", "subcategories": defaultdict(lambda: {"name": "", "niches": []})})

    for niche_id, niche in v3_taxonomy["niches"].items():
        cat_name = niche.get("category_name", "Unknown")
        subcat_name = niche.get("subcategory_name", "General")

        # Find category ID
        cat_id = None
        for cid, cdata in v3_taxonomy["categories"].items():
            if cdata.get("name") == cat_name:
                cat_id = cid
                break
        if not cat_id:
            cat_id = f"cat_{cat_name.lower().replace(' ', '_')}"

        hierarchy[cat_id]["name"] = cat_name
        subcat_key = f"{cat_id}_{subcat_name.lower().replace(' ', '_')}"
        hierarchy[cat_id]["subcategories"][subcat_key]["name"] = subcat_name
        hierarchy[cat_id]["subcategories"][subcat_key]["niches"].append({
            "id": niche_id,
            "name": niche.get("name", ""),
            "video_count": niche.get("video_count", 0),
            "source": niche.get("source", ""),
            "has_sub_niches": niche.get("has_sub_niches", False),
            "sub_niche_count": len(niche.get("sub_niche_ids", []))
        })

    # Convert hierarchy to regular dict
    v3_taxonomy["hierarchy"] = {k: {"name": v["name"], "subcategories": dict(v["subcategories"])} for k, v in hierarchy.items()}

    # Save taxonomy
    output_path = V3_DIR / "taxonomy.json"
    with open(output_path, "w") as f:
        json.dump(v3_taxonomy, f, indent=2)

    print(f"\nV3 Taxonomy Stats:")
    print(f"  V1 embedding niches: {v3_taxonomy['stats']['v1_embedding_niches']}")
    print(f"  V2 hashtag niches: {v3_taxonomy['stats']['v2_hashtag_niches']}")
    print(f"  V3 LLM sub-niches: {v3_taxonomy['stats']['v3_llm_sub_niches']}")
    print(f"    - Validated: {v3_taxonomy['stats']['validated_sub_niches']}")
    print(f"    - Partial: {v3_taxonomy['stats']['partial_sub_niches']}")
    print(f"  ────────────────────")
    print(f"  TOTAL: {v3_taxonomy['stats']['total_niches']} niches")
    print(f"\nSaved to: {output_path}")

    # Show sample sub-niches
    print(f"\nSample LLM-generated sub-niches:")
    count = 0
    for sub_id, sub in v3_taxonomy["sub_niches"].items():
        if count >= 5:
            break
        print(f"  - {sub['name']}")
        print(f"    Parent: {sub['parent_niche_name']}")
        print(f"    Status: {sub['validation_status']} ({sub['video_support']} videos)")
        count += 1


if __name__ == "__main__":
    main()
