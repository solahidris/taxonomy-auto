#!/usr/bin/env python3
"""V1 Step 3: Recursive hierarchical clustering for 3-4 level taxonomy.

Level 1: K-Means (k=20) for top categories
Level 2: K-Means (k=5-8) for subcategories within each category
Level 3: HDBSCAN for micro-niches within each subcategory
Level 4: (optional) Further split large micro-niches

Target: 500-1000 leaf niches organized in 3-4 levels.
"""

import json
import numpy as np
from pathlib import Path
from sklearn.cluster import KMeans, HDBSCAN
from sklearn.preprocessing import normalize
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent.parent
IN_EMB = PROJECT_ROOT / "data/v1/embeddings.npy"
IN_META = PROJECT_ROOT / "data/v1/metadata.json"
OUT = PROJECT_ROOT / "data/v1/clusters.json"

# Clustering parameters
N_CATEGORIES = 20          # Level 1: top categories
N_SUBCATS_PER_CAT = 6      # Level 2: subcategories per category (avg)
MIN_MICRO_SIZE = 5         # Level 3: minimum micro-niche size
MIN_FOR_SPLIT = 50         # Level 4: split micro-niches larger than this


def get_cluster_data(indices: np.ndarray, embeddings: np.ndarray, metadata: list) -> dict:
    """Extract sample data for a cluster."""
    sample_indices = indices[:15]
    return {
        "indices": indices.tolist(),
        "count": len(indices),
        "sample_titles": [metadata[i]["title"] for i in sample_indices],
        "sample_tags": list({
            t for i in indices[:30] for t in metadata[i].get("tags", [])[:5]
        })[:25],
        "sample_channels": list({
            metadata[i].get("channel_title", "") for i in indices[:20]
        })[:10],
        "centroid": embeddings[indices].mean(axis=0).tolist(),
    }


def cluster_level(
    embeddings: np.ndarray,
    indices: np.ndarray,
    metadata: list,
    n_clusters: int,
    level_name: str
) -> dict[int, np.ndarray]:
    """Run K-Means clustering on a subset of embeddings."""
    if len(indices) < n_clusters * 2:
        # Not enough data to split further
        return {0: indices}

    sub_emb = embeddings[indices]
    kmeans = KMeans(n_clusters=min(n_clusters, len(indices) // 2), random_state=42, n_init=10)
    labels = kmeans.fit_predict(sub_emb)

    clusters = defaultdict(list)
    for i, label in enumerate(labels):
        clusters[label].append(indices[i])

    return {k: np.array(v) for k, v in clusters.items()}


def hdbscan_cluster(
    embeddings: np.ndarray,
    indices: np.ndarray,
    min_cluster_size: int = 5
) -> dict[int, np.ndarray]:
    """Run HDBSCAN on a subset for micro-niche discovery."""
    if len(indices) < min_cluster_size * 2:
        return {0: indices}

    sub_emb = embeddings[indices]
    hdb = HDBSCAN(min_cluster_size=min_cluster_size, min_samples=2)
    labels = hdb.fit_predict(sub_emb)

    clusters = defaultdict(list)
    for i, label in enumerate(labels):
        clusters[label].append(indices[i])

    return {k: np.array(v) for k, v in clusters.items()}


def main():
    print("Loading embeddings...")
    embeddings = np.load(IN_EMB)
    metadata = json.loads(IN_META.read_text())
    n_videos = len(embeddings)

    assert len(embeddings) == len(metadata), "Mismatch between embeddings and metadata"
    print(f"Loaded {n_videos} videos")

    # Normalize embeddings
    normed = normalize(embeddings.astype(np.float64))
    all_indices = np.arange(n_videos)

    # =========================================================================
    # LEVEL 1: Top Categories (K-Means, k=20)
    # =========================================================================
    print(f"\nLevel 1: Creating {N_CATEGORIES} top categories...")
    level1_clusters = cluster_level(normed, all_indices, metadata, N_CATEGORIES, "cat")
    print(f"  Created {len(level1_clusters)} categories")

    # =========================================================================
    # LEVEL 2: Subcategories (K-Means within each category)
    # =========================================================================
    print(f"\nLevel 2: Creating subcategories...")
    level2_clusters = {}
    for cat_id, cat_indices in level1_clusters.items():
        # Determine number of subcategories based on category size
        n_sub = max(3, min(10, len(cat_indices) // 50))
        subclusters = cluster_level(normed, cat_indices, metadata, n_sub, f"c{cat_id}_sub")
        for sub_id, sub_indices in subclusters.items():
            level2_clusters[f"c{cat_id}_s{sub_id}"] = sub_indices
    print(f"  Created {len(level2_clusters)} subcategories")

    # =========================================================================
    # LEVEL 3: Micro-niches (HDBSCAN within each subcategory)
    # =========================================================================
    print(f"\nLevel 3: Creating micro-niches with HDBSCAN...")
    level3_clusters = {}
    for subcat_id, subcat_indices in level2_clusters.items():
        micros = hdbscan_cluster(normed, subcat_indices, MIN_MICRO_SIZE)
        for micro_id, micro_indices in micros.items():
            if micro_id == -1:
                # Noise cluster - keep if large enough
                if len(micro_indices) >= MIN_MICRO_SIZE:
                    level3_clusters[f"{subcat_id}_noise"] = micro_indices
            else:
                level3_clusters[f"{subcat_id}_m{micro_id}"] = micro_indices
    print(f"  Created {len(level3_clusters)} micro-niches")

    # =========================================================================
    # LEVEL 4 (optional): Split very large micro-niches
    # =========================================================================
    print(f"\nLevel 4: Splitting large micro-niches (>{MIN_FOR_SPLIT} videos)...")
    final_clusters = {}
    splits = 0
    for niche_id, niche_indices in level3_clusters.items():
        if len(niche_indices) > MIN_FOR_SPLIT:
            # Split into smaller pieces
            n_split = max(2, len(niche_indices) // 30)
            sub_niches = cluster_level(normed, niche_indices, metadata, n_split, f"{niche_id}_split")
            for split_id, split_indices in sub_niches.items():
                if len(split_indices) >= 3:  # Minimum viable niche
                    final_clusters[f"{niche_id}_v{split_id}"] = split_indices
                    splits += 1
        else:
            if len(niche_indices) >= 3:
                final_clusters[niche_id] = niche_indices

    print(f"  Split {splits} large niches")
    print(f"  Final: {len(final_clusters)} leaf niches")

    # =========================================================================
    # Build output structure with hierarchy info
    # =========================================================================
    print("\nBuilding cluster output...")
    output = {}
    for niche_id, indices in final_clusters.items():
        # Parse hierarchy from ID
        parts = niche_id.split("_")
        cat_id = int(parts[0][1:]) if parts[0].startswith("c") else 0

        cluster_data = get_cluster_data(indices, normed, metadata)
        cluster_data["niche_id"] = niche_id
        cluster_data["category_id"] = cat_id
        cluster_data["hierarchy_depth"] = len(parts)
        output[niche_id] = cluster_data

    # Stats
    sizes = [c["count"] for c in output.values()]
    total_classified = sum(sizes)

    print("\n" + "=" * 50)
    print("CLUSTERING RESULTS")
    print("=" * 50)
    print(f"Total leaf niches: {len(output)}")
    print(f"Videos classified: {total_classified}/{n_videos} ({total_classified/n_videos:.1%})")
    print(f"Niche sizes: max={max(sizes)}, median={np.median(sizes):.0f}, min={min(sizes)}")
    print(f"Categories: {len(level1_clusters)}")
    print(f"Subcategories: {len(level2_clusters)}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, indent=2))
    print(f"\nClusters saved → {OUT}")


if __name__ == "__main__":
    main()
