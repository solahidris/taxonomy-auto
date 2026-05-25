#!/usr/bin/env python3
"""V7 Pipeline Step 7: Name clusters using GPT-4 to create fitness taxonomy.

Creates human-readable names for:
- Categories (broad fitness themes)
- Subcategories/Niches (specific content types)

Also extracts top exemplar creators per niche.
"""

import json
import time
from pathlib import Path
from openai import OpenAI
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

client = OpenAI()
PROJECT_ROOT = Path(__file__).parent.parent.parent
IN_CLUSTERS = PROJECT_ROOT / "data/v7/clusters.json"
IN_META = PROJECT_ROOT / "data/v7/metadata.json"
OUT = PROJECT_ROOT / "data/v7/taxonomy.json"
MODEL = "gpt-4o-mini"


def get_exemplar_creators(cluster_data: dict, metadata: list, top_n: int = 5) -> list[dict]:
    """Extract top creators from a cluster based on video count and performance."""
    indices = cluster_data["indices"]
    author_stats = defaultdict(lambda: {"count": 0, "views": 0, "outliers": 0})

    for idx in indices:
        if idx < len(metadata):
            author = metadata[idx].get("author", "")
            if author:
                author_stats[author]["count"] += 1
                author_stats[author]["views"] += metadata[idx].get("views", 0)
                if metadata[idx].get("is_outlier"):
                    author_stats[author]["outliers"] += 1

    # Sort by video count, then by views
    sorted_authors = sorted(
        author_stats.items(),
        key=lambda x: (x[1]["count"], x[1]["views"]),
        reverse=True
    )[:top_n]

    return [
        {
            "author": author,
            "video_count": stats["count"],
            "total_views": stats["views"],
            "outlier_count": stats["outliers"],
        }
        for author, stats in sorted_authors
    ]


def get_top_videos(cluster_data: dict, metadata: list, top_n: int = 3) -> list[dict]:
    """Extract top videos from a cluster, prioritizing high 3R scores and views."""
    indices = cluster_data["indices"]
    videos = []

    for idx in indices:
        if idx < len(metadata):
            m = metadata[idx]
            # Calculate total 3R score
            total_3r = (m.get("r1_score", 0) or 0) + (m.get("r2_score", 0) or 0) + (m.get("r3_score", 0) or 0)
            videos.append({
                "video_id": m.get("video_id", ""),
                "title": m.get("title", "")[:100],
                "author": m.get("author", ""),
                "views": m.get("views", 0),
                "is_outlier": m.get("is_outlier", False),
                "r1_score": m.get("r1_score", 0) or 0,
                "r2_score": m.get("r2_score", 0) or 0,
                "r3_score": m.get("r3_score", 0) or 0,
                "total_3r": total_3r,
                "format_type": m.get("format_type", ""),
                "core_topic": m.get("core_topic", ""),
            })

    # Sort by total 3R score (desc), then by views (desc)
    sorted_videos = sorted(
        videos,
        key=lambda x: (x["total_3r"], x["views"]),
        reverse=True
    )[:top_n]

    return sorted_videos


def name_category(cat_id: str, cluster_ids: list[str], clusters: dict) -> str:
    """Name a top-level fitness category."""
    all_titles = []
    all_hashtags = []
    all_topics = []
    all_formats = []

    for cluster_id in cluster_ids:
        if cluster_id in clusters:
            data = clusters[cluster_id]
            all_titles.extend(data.get("sample_titles", [])[:5])
            all_hashtags.extend(data.get("sample_hashtags", [])[:10])
            all_topics.extend(data.get("sample_topics", [])[:5])
            all_formats.extend(data.get("format_types", []))

    prompt = f"""You are naming a broad FITNESS CATEGORY for TikTok content creators.

This category contains videos with these characteristics:

Sample video titles:
{chr(10).join(f'- {t}' for t in all_titles[:15])}

Common hashtags: {', '.join(list(set(all_hashtags))[:15])}
Core topics: {', '.join(list(set(all_topics))[:10])}
Content formats: {', '.join(list(set(all_formats))[:8])}

Name this fitness category with 2-4 words that broadly describe the content theme.
Examples: "Strength Training", "Weight Loss & Diet", "Workout Motivation", "Form & Technique", "Fitness Humor"

Return ONLY the category name, nothing else."""

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=30,
    )
    return resp.choices[0].message.content.strip().strip('"')


def name_cluster(cluster_data: dict, parent_category: str) -> dict:
    """Name a specific cluster/niche within its category context."""
    titles = cluster_data.get("sample_titles", [])[:12]
    hashtags = cluster_data.get("sample_hashtags", [])[:15]
    authors = cluster_data.get("sample_authors", [])[:5]
    topics = cluster_data.get("sample_topics", [])[:8]
    formats = cluster_data.get("format_types", [])

    prompt = f"""You are naming a specific FITNESS NICHE for TikTok creators.

Parent Category: {parent_category}

Sample video titles in this niche:
{chr(10).join(f'- {t}' for t in titles)}

Hashtags: {', '.join(hashtags)}
Core topics: {', '.join(topics)}
Content formats: {', '.join(formats)}
Sample creators: {', '.join(authors)}

Provide:
1. A specific niche name (3-6 words) that describes this content type
2. A one-sentence description of what makes this niche unique
3. The target audience (who would watch this)

Good niche names: "Quick Gym Humor Skits", "Home Workout Tutorials", "Gym Fail Compilations", "Motivational Transformation Stories"

Return as JSON (no markdown):
{{"name": "...", "description": "...", "target_audience": "..."}}"""

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=150,
    )

    content = resp.choices[0].message.content.strip()
    # Handle markdown code blocks
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "name": "Fitness Content",
            "description": "General fitness content",
            "target_audience": "Fitness enthusiasts"
        }


def main():
    print("=" * 60)
    print("V7 Pipeline: Naming Taxonomy")
    print("=" * 60)

    print("\nLoading clusters and metadata...")
    cluster_data = json.loads(IN_CLUSTERS.read_text())
    metadata = json.loads(IN_META.read_text())

    clusters = cluster_data["clusters"]
    hierarchy = cluster_data["hierarchy"]

    print(f"Loaded {len(clusters)} clusters, {len(metadata)} videos")

    # =========================================================================
    # Step 1: Group clusters by category
    # =========================================================================
    print("\nAnalyzing hierarchy structure...")
    category_clusters = defaultdict(list)
    for cluster_id in clusters.keys():
        parts = cluster_id.split("_")
        cat_id = parts[0]  # e.g., "c0"
        category_clusters[cat_id].append(cluster_id)

    print(f"  Categories: {len(category_clusters)}")

    # =========================================================================
    # Step 2: Name categories
    # =========================================================================
    print("\nNaming categories...")
    category_names = {}
    for cat_id in sorted(category_clusters.keys()):
        cluster_ids = category_clusters[cat_id]
        name = name_category(cat_id, cluster_ids, clusters)
        category_names[cat_id] = name
        print(f"  {cat_id}: {name} ({len(cluster_ids)} clusters)")
        time.sleep(0.3)

    # =========================================================================
    # Step 3: Name each cluster/niche
    # =========================================================================
    print("\nNaming clusters...")
    taxonomy = {
        "categories": {},
        "niches": {},
        "stats": {}
    }

    # Store category info
    for cat_id, name in category_names.items():
        cat_info = hierarchy["categories"].get(cat_id, {})
        taxonomy["categories"][cat_id] = {
            "name": name,
            "cluster_count": len(category_clusters[cat_id]),
            "video_count": cat_info.get("count", 0),
        }

    # Name each cluster
    for i, (cluster_id, data) in enumerate(clusters.items()):
        print(f"  [{i+1}/{len(clusters)}] {cluster_id}...")

        parts = cluster_id.split("_")
        cat_id = parts[0]
        parent_category = category_names.get(cat_id, "Fitness")

        # Name the cluster
        naming_result = name_cluster(data, parent_category)

        # Get exemplar creators
        exemplars = get_exemplar_creators(data, metadata)

        # Get top videos by 3R score
        top_videos = get_top_videos(data, metadata, top_n=3)

        taxonomy["niches"][cluster_id] = {
            "name": naming_result.get("name", "Fitness Content"),
            "description": naming_result.get("description", ""),
            "target_audience": naming_result.get("target_audience", ""),
            "category_id": cat_id,
            "category_name": parent_category,
            "video_count": data["count"],
            "total_views": data.get("total_views", 0),
            "outlier_count": data.get("outlier_count", 0),
            "avg_3r_scores": {
                "reproducible": round(data.get("avg_r1", 0), 2),
                "relatable": round(data.get("avg_r2", 0), 2),
                "repeatable": round(data.get("avg_r3", 0), 2),
            },
            "exemplar_creators": exemplars,
            "top_videos": top_videos,
            "sample_titles": data.get("sample_titles", [])[:8],
            "sample_hashtags": data.get("sample_hashtags", [])[:12],
            "format_types": data.get("format_types", []),
            "centroid": data.get("centroid", []),
        }

        print(f"      → {naming_result.get('name', 'Unknown')}")
        time.sleep(0.3)

    # Stats
    taxonomy["stats"] = {
        "total_categories": len(category_names),
        "total_niches": len(clusters),
        "total_videos": sum(n["video_count"] for n in taxonomy["niches"].values()),
        "total_views": sum(n["total_views"] for n in taxonomy["niches"].values()),
        "total_outliers": sum(n["outlier_count"] for n in taxonomy["niches"].values()),
    }

    print("\n" + "=" * 60)
    print("TAXONOMY RESULTS")
    print("=" * 60)
    print(f"Categories: {taxonomy['stats']['total_categories']}")
    print(f"Niches: {taxonomy['stats']['total_niches']}")
    print(f"Videos covered: {taxonomy['stats']['total_videos']}")
    print(f"Total views: {taxonomy['stats']['total_views']:,}")
    print(f"Outlier videos: {taxonomy['stats']['total_outliers']}")

    print("\nCategories:")
    for cat_id, cat_info in taxonomy["categories"].items():
        print(f"  {cat_info['name']}: {cat_info['cluster_count']} niches, {cat_info['video_count']} videos")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(taxonomy, indent=2))
    print(f"\nTaxonomy saved → {OUT}")


if __name__ == "__main__":
    main()
