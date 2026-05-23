#!/usr/bin/env python3
"""
V4 Step 4: Merge Validated Sub-Niches into Taxonomy

Creates V4 taxonomy by adding all validated sub-niches to V2 base.

Output: data/v4/taxonomy.json
"""

import json
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
V2_DIR = DATA_DIR / "v2"
V4_DIR = DATA_DIR / "v4"


def load_v2_taxonomy():
    """Load V2 taxonomy as base."""
    with open(V2_DIR / "taxonomy.json") as f:
        return json.load(f)


def load_validated_suggestions():
    """Load validated suggestions from step 3."""
    with open(V4_DIR / "validated_suggestions.json") as f:
        return json.load(f)


def main():
    print("=" * 60)
    print("V4 Step 4: Merge Validated Sub-Niches into Taxonomy")
    print("=" * 60)

    print("\nLoading V2 taxonomy...")
    v2_taxonomy = load_v2_taxonomy()

    print("Loading validated suggestions...")
    validated = load_validated_suggestions()

    # Create V4 taxonomy structure
    v4_taxonomy = {
        "version": "4.0",
        "approach": "A + B + C (Hashtag + Embedding + LLM Full)",
        "categories": v2_taxonomy.get("categories", {}),
        "subcategories": v2_taxonomy.get("subcategories", {}),
        "niches": {},
        "sub_niches": {},
        "stats": {
            "total_niches": 0,
            "v1_embedding_niches": 0,
            "v2_hashtag_niches": 0,
            "v4_llm_sub_niches": 0,
            "validated_sub_niches": 0,
            "partial_sub_niches": 0,
            "total_categories": len(v2_taxonomy.get("categories", {})),
            "total_subcategories": len(v2_taxonomy.get("subcategories", {})),
        }
    }

    # Copy all V2 niches
    for niche_id, niche_data in v2_taxonomy["niches"].items():
        v4_taxonomy["niches"][niche_id] = {
            **niche_data,
            "has_sub_niches": False,
            "sub_niche_ids": []
        }

        if niche_data.get("source") == "embedding_clustered":
            v4_taxonomy["stats"]["v1_embedding_niches"] += 1
        elif niche_data.get("source") == "hashtag_discovered":
            v4_taxonomy["stats"]["v2_hashtag_niches"] += 1

    # Add validated and partial sub-niches
    sub_niche_counter = 0
    for niche_id, result in validated["suggestions"].items():
        parent_niche = result.get("parent_niche", "Unknown")

        for sub in result.get("sub_niches", []):
            status = sub.get("validation_status", "unvalidated")

            # Only include validated and partial sub-niches
            if status in ["validated", "partial"]:
                sub_niche_id = f"v4_sub_niche_{niche_id.split('_')[-1]}_{sub_niche_counter}"
                sub_niche_counter += 1

                # Get parent niche info
                parent_data = v4_taxonomy["niches"].get(niche_id, {})

                sub_niche_entry = {
                    "id": sub_niche_id,
                    "name": sub["name"],
                    "description": sub.get("description", ""),
                    "source": "llm_generated",
                    "confidence": "inferred",
                    "validation_status": status,
                    "video_support": sub.get("video_support", 0),
                    "parent_niche_id": niche_id,
                    "parent_niche_name": parent_niche,
                    "category_name": parent_data.get("category_name", ""),
                    "subcategory_name": parent_data.get("subcategory_name", ""),
                    "target_audience": sub.get("target_audience", ""),
                    "validation_keywords": sub.get("validation_keywords", []),
                    "expected_hashtags": sub.get("expected_hashtags", []),
                    "matched_terms": sub.get("matched_terms", [])
                }

                v4_taxonomy["sub_niches"][sub_niche_id] = sub_niche_entry
                v4_taxonomy["stats"]["v4_llm_sub_niches"] += 1

                if status == "validated":
                    v4_taxonomy["stats"]["validated_sub_niches"] += 1
                else:
                    v4_taxonomy["stats"]["partial_sub_niches"] += 1

                # Update parent niche
                if niche_id in v4_taxonomy["niches"]:
                    v4_taxonomy["niches"][niche_id]["has_sub_niches"] = True
                    v4_taxonomy["niches"][niche_id]["sub_niche_ids"].append(sub_niche_id)

    # Calculate total
    v4_taxonomy["stats"]["total_niches"] = (
        v4_taxonomy["stats"]["v1_embedding_niches"] +
        v4_taxonomy["stats"]["v2_hashtag_niches"] +
        v4_taxonomy["stats"]["v4_llm_sub_niches"]
    )

    # Save taxonomy
    output_path = V4_DIR / "taxonomy.json"
    with open(output_path, "w") as f:
        json.dump(v4_taxonomy, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"V4 Taxonomy Created:")
    print(f"  V1 embedding niches: {v4_taxonomy['stats']['v1_embedding_niches']}")
    print(f"  V2 hashtag niches: {v4_taxonomy['stats']['v2_hashtag_niches']}")
    print(f"  V4 LLM sub-niches: {v4_taxonomy['stats']['v4_llm_sub_niches']}")
    print(f"    - Validated: {v4_taxonomy['stats']['validated_sub_niches']}")
    print(f"    - Partial: {v4_taxonomy['stats']['partial_sub_niches']}")
    print(f"  TOTAL NICHES: {v4_taxonomy['stats']['total_niches']}")
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
