#!/usr/bin/env python3
"""V7 Pipeline Step 6: Cluster videos into fitness taxonomy.

Adapted for 240 TikTok fitness videos:
- Level 1: K-Means (k=6-8) for main fitness categories
- Level 2: K-Means (k=3-5) for subcategories within each
- Level 3: HDBSCAN for micro-niches (if enough data)

Target: 20-40 leaf niches organized in 2-3 levels.
"""

import json
import numpy as np
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent.parent
IN_EMB = PROJECT_ROOT / "data/v7/embeddings.npy"
IN_META = PROJECT_ROOT / "data/v7/metadata.json"
OUT = PROJECT_ROOT / "data/v7/clusters.json"

# Clustering parameters (adjusted for 240 videos)
N_CATEGORIES = 6           # Level 1: main fitness categories
N_SUBCATS_PER_CAT = 4      # Level 2: subcategories per category
MIN_CLUSTER_SIZE = 3       # Minimum viable cluster


def get_cluster_data(indices: np.ndarray, embeddings: np.ndarray, metadata: list) -> dict:
    """Extract sample data for a cluster."""
    sample_indices = indices[:15]
    return {
        "indices": indices.tolist(),
        "count": len(indices),
        "sample_titles": [metadata[i]["title"] for i in sample_indices if i < len(metadata)],
        "sample_hashtags": list({
            t for i in indices[:30] if i < len(metadata)
            for t in metadata[i].get("hashtags", [])[:5]
        })[:25],
        "sample_authors": list({
            metadata[i].get("author", "") for i in indices[:20] if i < len(metadata)
        })[:10],
        "sample_topics": list({
            metadata[i].get("core_topic", "") for i in indices[:20]
            if i < len(metadata) and metadata[i].get("core_topic")
        })[:8],
        "format_types": list({
            metadata[i].get("format_type", "") for i in indices
            if i < len(metadata) and metadata[i].get("format_type")
        }),
        "avg_r1": np.mean([metadata[i].get("r1_score", 0) for i in indices if i < len(metadata)]),
        "avg_r2": np.mean([metadata[i].get("r2_score", 0) for i in indices if i < len(metadata)]),
        "avg_r3": np.mean([metadata[i].get("r3_score", 0) for i in indices if i < len(metadata)]),
        "outlier_count": sum(1 for i in indices if i < len(metadata) and metadata[i].get("is_outlier")),
        "total_views": sum(metadata[i].get("views", 0) for i in indices if i < len(metadata)),
        "centroid": embeddings[indices].mean(axis=0).tolist(),
    }


def cluster_level(
    embeddings: np.ndarray,
    indices: np.ndarray,
    n_clusters: int,
) -> dict[int, np.ndarray]:
    """Run K-Means clustering on a subset of embeddings."""
    if len(indices) < n_clusters * 2:
        # Not enough data to split further
        return {0: indices}

    sub_emb = embeddings[indices]
    actual_k = min(n_clusters, max(2, len(indices) // 3))
    kmeans = KMeans(n_clusters=actual_k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(sub_emb)

    clusters = defaultdict(list)
    for i, label in enumerate(labels):
        clusters[label].append(indices[i])

    return {k: np.array(v) for k, v in clusters.items()}


def main():
    print("=" * 60)
    print("V7 Pipeline: Clustering Videos")
    print("=" * 60)

    print("\nLoading embeddings...")
    embeddings = np.load(IN_EMB)
    metadata = json.loads(IN_META.read_text())
    n_videos = len(embeddings)

    assert len(embeddings) == len(metadata), "Mismatch between embeddings and metadata"
    print(f"Loaded {n_videos} videos")

    # Normalize embeddings for cosine similarity
    normed = normalize(embeddings.astype(np.float64))
    all_indices = np.arange(n_videos)

    # =========================================================================
    # LEVEL 1: Main Fitness Categories (K-Means)
    # =========================================================================
    print(f"\nLevel 1: Creating {N_CATEGORIES} main categories...")
    level1_clusters = cluster_level(normed, all_indices, N_CATEGORIES)
    print(f"  Created {len(level1_clusters)} categories")
    for cat_id, indices in level1_clusters.items():
        print(f"    Category {cat_id}: {len(indices)} videos")

    # =========================================================================
    # LEVEL 2: Subcategories (K-Means within each category)
    # =========================================================================
    print(f"\nLevel 2: Creating subcategories...")
    level2_clusters = {}
    for cat_id, cat_indices in level1_clusters.items():
        # Determine number of subcategories based on category size
        n_sub = max(2, min(N_SUBCATS_PER_CAT, len(cat_indices) // 8))
        subclusters = cluster_level(normed, cat_indices, n_sub)
        for sub_id, sub_indices in subclusters.items():
            if len(sub_indices) >= MIN_CLUSTER_SIZE:
                level2_clusters[f"c{cat_id}_s{sub_id}"] = sub_indices

    print(f"  Created {len(level2_clusters)} subcategories")

    # =========================================================================
    # Build output structure
    # =========================================================================
    print("\nBuilding cluster output...")
    output = {
        "clusters": {},
        "hierarchy": {
            "categories": {},
            "subcategories": {}
        },
        "stats": {}
    }

    # Store category-level info
    for cat_id, cat_indices in level1_clusters.items():
        cat_data = get_cluster_data(cat_indices, normed, metadata)
        output["hierarchy"]["categories"][f"c{cat_id}"] = {
            "count": len(cat_indices),
            "sample_topics": cat_data["sample_topics"],
            "sample_hashtags": cat_data["sample_hashtags"][:10],
            "format_types": cat_data["format_types"],
        }

    # Store subcategory-level info (these are our final clusters for V7)
    for subcat_id, indices in level2_clusters.items():
        parts = subcat_id.split("_")
        cat_id = int(parts[0][1:])

        cluster_data = get_cluster_data(indices, normed, metadata)
        cluster_data["cluster_id"] = subcat_id
        cluster_data["category_id"] = cat_id

        output["clusters"][subcat_id] = cluster_data
        output["hierarchy"]["subcategories"][subcat_id] = {
            "category_id": cat_id,
            "count": len(indices),
        }

    # Calculate stats
    sizes = [c["count"] for c in output["clusters"].values()]
    total_classified = sum(sizes)

    output["stats"] = {
        "total_clusters": len(output["clusters"]),
        "total_categories": len(level1_clusters),
        "videos_classified": total_classified,
        "total_videos": n_videos,
        "coverage": total_classified / n_videos,
        "cluster_sizes": {
            "max": max(sizes) if sizes else 0,
            "min": min(sizes) if sizes else 0,
            "median": float(np.median(sizes)) if sizes else 0,
            "mean": float(np.mean(sizes)) if sizes else 0,
        }
    }

    print("\n" + "=" * 60)
    print("CLUSTERING RESULTS")
    print("=" * 60)
    print(f"Total clusters: {output['stats']['total_clusters']}")
    print(f"Categories: {output['stats']['total_categories']}")
    print(f"Videos classified: {total_classified}/{n_videos} ({output['stats']['coverage']:.1%})")
    print(f"Cluster sizes: max={output['stats']['cluster_sizes']['max']}, "
          f"median={output['stats']['cluster_sizes']['median']:.0f}, "
          f"min={output['stats']['cluster_sizes']['min']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, indent=2))
    print(f"\nClusters saved → {OUT}")


if __name__ == "__main__":
    main()
