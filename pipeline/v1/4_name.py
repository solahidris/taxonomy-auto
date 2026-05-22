#!/usr/bin/env python3
"""V1 Step 4: Hierarchical LLM naming for multi-level taxonomy.

Names each level in context of its parent:
- Level 1: Category names (broad)
- Level 2: Subcategory names (within category context)
- Level 3+: Micro-niche names (specific, actionable)

Also extracts top exemplar creators per niche.
"""

import json
import numpy as np
from pathlib import Path
from openai import OpenAI
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

client = OpenAI()
PROJECT_ROOT = Path(__file__).parent.parent.parent
IN_CLUSTERS = PROJECT_ROOT / "data/v1/clusters.json"
IN_META = PROJECT_ROOT / "data/v1/metadata.json"
OUT = PROJECT_ROOT / "data/v1/taxonomy.json"
MODEL = "gpt-4o-mini"


def get_category_groups(clusters: dict) -> dict[int, list[str]]:
    """Group niche IDs by their category."""
    groups = defaultdict(list)
    for niche_id, data in clusters.items():
        cat_id = data.get("category_id", 0)
        groups[cat_id].append(niche_id)
    return dict(groups)


def get_exemplar_creators(niche_data: dict, metadata: list, top_n: int = 10) -> list[dict]:
    """Extract top creators from a niche based on frequency."""
    indices = niche_data["indices"]
    channel_counts = defaultdict(int)
    channel_info = {}

    for idx in indices:
        if idx < len(metadata):
            ch_id = metadata[idx].get("channel_id", "")
            ch_title = metadata[idx].get("channel_title", "")
            if ch_id and ch_title:
                channel_counts[ch_id] += 1
                channel_info[ch_id] = ch_title

    # Sort by video count in niche
    sorted_channels = sorted(channel_counts.items(), key=lambda x: -x[1])[:top_n]

    return [
        {"channel_id": ch_id, "channel_title": channel_info[ch_id], "video_count": count}
        for ch_id, count in sorted_channels
    ]


def name_category(cat_id: int, niche_ids: list[str], clusters: dict) -> str:
    """Name a top-level category based on its niches."""
    # Collect sample data from all niches in category
    all_titles = []
    all_tags = []
    all_channels = []

    for niche_id in niche_ids[:15]:  # Sample from first 15 niches
        data = clusters[niche_id]
        all_titles.extend(data.get("sample_titles", [])[:5])
        all_tags.extend(data.get("sample_tags", [])[:10])
        all_channels.extend(data.get("sample_channels", [])[:3])

    prompt = f"""You are naming a broad CATEGORY for short-form video content creators.

This category contains these sample video titles:
{chr(10).join(f'- {t}' for t in all_titles[:20])}

Common tags: {', '.join(list(set(all_tags))[:20])}
Sample channels: {', '.join(list(set(all_channels))[:8])}

Name this category with 1-3 words that broadly describe the content type.
Examples: "Fitness & Health", "Gaming", "Beauty & Fashion", "Food & Cooking", "Tech & Gadgets"

Return ONLY the category name, nothing else."""

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=30,
    )
    return resp.choices[0].message.content.strip().strip('"')


def name_subcategory(subcat_niches: list[str], clusters: dict, parent_category: str) -> str:
    """Name a subcategory within its parent category context."""
    all_titles = []
    all_tags = []

    for niche_id in subcat_niches[:10]:
        data = clusters[niche_id]
        all_titles.extend(data.get("sample_titles", [])[:5])
        all_tags.extend(data.get("sample_tags", [])[:8])

    prompt = f"""You are naming a SUBCATEGORY within the "{parent_category}" category.

Sample video titles in this subcategory:
{chr(10).join(f'- {t}' for t in all_titles[:15])}

Common tags: {', '.join(list(set(all_tags))[:15])}

Name this subcategory with 2-4 words. It should be more specific than "{parent_category}".
Examples for "Fitness & Health": "Calisthenics & Bodyweight", "Yoga & Flexibility", "Weight Loss Journey"

Return ONLY the subcategory name, nothing else."""

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=40,
    )
    return resp.choices[0].message.content.strip().strip('"')


def name_niche(niche_data: dict, parent_subcategory: str, parent_category: str) -> str:
    """Name a specific niche within its hierarchy context."""
    titles = niche_data.get("sample_titles", [])[:12]
    tags = niche_data.get("sample_tags", [])[:15]
    channels = niche_data.get("sample_channels", [])[:5]

    prompt = f"""You are naming a specific NICHE for short-form video creators.

Category: {parent_category}
Subcategory: {parent_subcategory}

Sample video titles:
{chr(10).join(f'- {t}' for t in titles)}

Tags: {', '.join(tags)}
Sample creators: {', '.join(channels)}

Create a specific, actionable niche name (3-6 words) that:
1. Describes the content focus precisely
2. Is more specific than "{parent_subcategory}"
3. A creator could identify with

Good examples: "Quick HIIT Home Workouts", "Budget Meal Prep Ideas", "Beginner Guitar Tutorials"
Bad examples: "Videos", "Content", "Stuff" (too vague)

Return ONLY the niche name, nothing else."""

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=50,
    )
    return resp.choices[0].message.content.strip().strip('"')


def main():
    print("Loading clusters and metadata...")
    clusters = json.loads(IN_CLUSTERS.read_text())
    metadata = json.loads(IN_META.read_text())

    print(f"Loaded {len(clusters)} clusters, {len(metadata)} videos")

    # =========================================================================
    # Step 1: Group niches by category and subcategory
    # =========================================================================
    print("\nAnalyzing hierarchy structure...")

    # Parse hierarchy from niche IDs
    category_niches = defaultdict(list)  # cat_id -> [niche_ids]
    subcategory_niches = defaultdict(list)  # subcat_key -> [niche_ids]

    for niche_id in clusters.keys():
        parts = niche_id.split("_")
        if parts[0].startswith("c"):
            cat_id = int(parts[0][1:])
        else:
            cat_id = 0

        # Extract subcategory key (e.g., "c0_s1")
        if len(parts) >= 2 and parts[1].startswith("s"):
            subcat_key = f"{parts[0]}_{parts[1]}"
        else:
            subcat_key = parts[0]

        category_niches[cat_id].append(niche_id)
        subcategory_niches[subcat_key].append(niche_id)

    print(f"  Categories: {len(category_niches)}")
    print(f"  Subcategories: {len(subcategory_niches)}")

    # =========================================================================
    # Step 2: Name categories (Level 1)
    # =========================================================================
    print("\nNaming categories...")
    category_names = {}
    for cat_id in sorted(category_niches.keys()):
        niche_ids = category_niches[cat_id]
        name = name_category(cat_id, niche_ids, clusters)
        category_names[cat_id] = name
        print(f"  Category {cat_id}: {name} ({len(niche_ids)} niches)")

    # =========================================================================
    # Step 3: Name subcategories (Level 2)
    # =========================================================================
    print("\nNaming subcategories...")
    subcategory_names = {}
    for subcat_key in sorted(subcategory_niches.keys()):
        niche_ids = subcategory_niches[subcat_key]
        # Get parent category
        parts = subcat_key.split("_")
        if parts[0].startswith("c"):
            cat_id = int(parts[0][1:])
        else:
            cat_id = 0
        parent_cat = category_names.get(cat_id, "General")

        name = name_subcategory(niche_ids, clusters, parent_cat)
        subcategory_names[subcat_key] = name
        print(f"  {subcat_key}: {name}")

    # =========================================================================
    # Step 4: Name individual niches (Level 3+) and extract exemplars
    # =========================================================================
    print("\nNaming niches and extracting exemplar creators...")
    taxonomy = {
        "categories": {},
        "subcategories": {},
        "niches": {},
        "stats": {}
    }

    # Store category info
    for cat_id, name in category_names.items():
        taxonomy["categories"][cat_id] = {
            "name": name,
            "niche_count": len(category_niches[cat_id])
        }

    # Store subcategory info
    for subcat_key, name in subcategory_names.items():
        parts = subcat_key.split("_")
        cat_id = int(parts[0][1:]) if parts[0].startswith("c") else 0
        taxonomy["subcategories"][subcat_key] = {
            "name": name,
            "category_id": cat_id,
            "category_name": category_names.get(cat_id, "General"),
            "niche_count": len(subcategory_niches[subcat_key])
        }

    # Name each niche
    for i, (niche_id, niche_data) in enumerate(clusters.items()):
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(clusters)}")

        # Get hierarchy
        parts = niche_id.split("_")
        cat_id = int(parts[0][1:]) if parts[0].startswith("c") else 0
        if len(parts) >= 2 and parts[1].startswith("s"):
            subcat_key = f"{parts[0]}_{parts[1]}"
        else:
            subcat_key = parts[0]

        parent_cat = category_names.get(cat_id, "General")
        parent_subcat = subcategory_names.get(subcat_key, "General")

        # Name the niche
        niche_name = name_niche(niche_data, parent_subcat, parent_cat)

        # Get exemplar creators
        exemplars = get_exemplar_creators(niche_data, metadata)

        taxonomy["niches"][niche_id] = {
            "name": niche_name,
            "category_id": cat_id,
            "category_name": parent_cat,
            "subcategory_key": subcat_key,
            "subcategory_name": parent_subcat,
            "video_count": niche_data["count"],
            "hierarchy_depth": niche_data.get("hierarchy_depth", 3),
            "exemplar_creators": exemplars,
            "sample_titles": niche_data.get("sample_titles", [])[:10],
            "sample_tags": niche_data.get("sample_tags", [])[:15],
            "centroid": niche_data.get("centroid", []),
        }

    # Stats
    taxonomy["stats"] = {
        "total_niches": len(clusters),
        "total_categories": len(category_names),
        "total_subcategories": len(subcategory_names),
        "total_videos": sum(n["video_count"] for n in taxonomy["niches"].values()),
    }

    print("\n" + "=" * 50)
    print("TAXONOMY RESULTS")
    print("=" * 50)
    print(f"Categories: {taxonomy['stats']['total_categories']}")
    print(f"Subcategories: {taxonomy['stats']['total_subcategories']}")
    print(f"Niches: {taxonomy['stats']['total_niches']}")
    print(f"Videos covered: {taxonomy['stats']['total_videos']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(taxonomy, indent=2))
    print(f"\nTaxonomy saved -> {OUT}")


if __name__ == "__main__":
    main()
