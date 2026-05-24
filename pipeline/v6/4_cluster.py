#!/usr/bin/env python3
"""V6 Step 4: Hierarchical clustering for 3-4 level taxonomy.

With 8-12K videos across diverse categories, we use:
  Level 1: K-Means (k=25) — broad categories
  Level 2: K-Means (k=5-7) — subcategories within each category
  Level 3: HDBSCAN — micro-niches within each subcategory
  Level 4: Split large micro-niches (>60 videos) into sub-niches

Target: 400-700 leaf niches from data alone.
"""

import json
import numpy as np
from pathlib import Path
from sklearn.cluster import KMeans, HDBSCAN
from sklearn.decomposition import PCA
from sklearn.preprocessing import normalize
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "v6"
IN_EMB = DATA_DIR / "embeddings.npy"
IN_META = DATA_DIR / "metadata.json"
OUT = DATA_DIR / "clusters.json"

N_CATEGORIES = 25
N_SUBCATS_PER_CAT = 6
MIN_MICRO_SIZE = 5
MIN_FOR_SPLIT = 60


def cluster_kmeans(embeddings, indices, n_clusters, label=""):
    if len(indices) < n_clusters * 2:
        return {0: indices}
    sub_emb = embeddings[indices]
    k = min(n_clusters, len(indices) // 2)
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(sub_emb)
    result = defaultdict(list)
    for i, lbl in enumerate(labels):
        result[lbl].append(indices[i])
    return {k: np.array(v) for k, v in result.items()}


def cluster_hdbscan(embeddings, indices, min_size=5):
    if len(indices) < min_size * 2:
        return {0: indices}
    sub_emb = embeddings[indices]
    hdb = HDBSCAN(min_cluster_size=min_size, min_samples=2)
    labels = hdb.fit_predict(sub_emb)
    result = defaultdict(list)
    for i, lbl in enumerate(labels):
        result[lbl].append(indices[i])
    return {k: np.array(v) for k, v in result.items()}


def make_cluster_data(indices, embeddings, metadata, embeddings_raw=None):
    idxs = indices[:20]
    # Store centroid in original embedding space (1536-dim) so the classify
    # endpoint can compare directly against text-embedding-3-small query vectors.
    # embeddings_raw is the pre-PCA array; fall back to embeddings if not provided.
    centroid_source = embeddings_raw if embeddings_raw is not None else embeddings
    return {
        "indices": [int(i) for i in indices],
        "count": len(indices),
        "sample_titles": [metadata[i]["title"] for i in idxs if i < len(metadata)],
        "sample_tags": list({
            t for i in indices[:30] for t in metadata[i].get("hashtags", [])[:5]
            if i < len(metadata)
        })[:25],
        "sample_channels": list({
            metadata[i].get("author", "") for i in indices[:20]
            if i < len(metadata) and metadata[i].get("author")
        })[:10],
        "centroid": centroid_source[indices].mean(axis=0).tolist(),
    }


def main():
    print("Loading V6 embeddings...")
    embeddings_raw = np.load(IN_EMB)
    metadata = json.loads(IN_META.read_text())
    n = len(embeddings_raw)
    assert n == len(metadata), f"Mismatch: {n} embeddings vs {len(metadata)} metadata"
    print(f"Loaded {n} videos")

    # Normalize and reduce dimensions
    print("Normalizing embeddings...")
    embeddings = normalize(embeddings_raw.astype(np.float64))

    print("PCA reduction to 100 dims...")
    pca = PCA(n_components=min(100, n - 1))
    reduced = pca.fit_transform(embeddings)
    print(f"  Explained variance: {pca.explained_variance_ratio_.sum() * 100:.1f}%")

    all_indices = np.arange(n)
    clusters: dict = {}
    niche_counter = 0

    # Level 1: Top categories
    print(f"\nLevel 1: K-Means k={N_CATEGORIES} categories...")
    cat_groups = cluster_kmeans(reduced, all_indices, N_CATEGORIES, "L1")

    for cat_id, cat_indices in cat_groups.items():
        print(f"  Category {cat_id}: {len(cat_indices)} videos")

        # Level 2: Subcategories
        n_subcats = max(2, min(N_SUBCATS_PER_CAT, len(cat_indices) // 30))
        subcat_groups = cluster_kmeans(reduced, cat_indices, n_subcats, f"L2-cat{cat_id}")

        for subcat_id, subcat_indices in subcat_groups.items():
            # Level 3: HDBSCAN micro-niches
            micro_groups = cluster_hdbscan(reduced, subcat_indices, MIN_MICRO_SIZE)

            for micro_id, micro_indices in micro_groups.items():
                if len(micro_indices) < MIN_MICRO_SIZE:
                    continue  # Skip tiny clusters (noise from HDBSCAN label=-1)

                # Level 4: Split large micro-niches
                if len(micro_indices) >= MIN_FOR_SPLIT:
                    n_splits = min(4, len(micro_indices) // 20)
                    splits = cluster_kmeans(reduced, micro_indices, n_splits, f"L4")
                    for split_id, split_indices in splits.items():
                        if len(split_indices) >= MIN_MICRO_SIZE:
                            niche_id = f"n{niche_counter}"
                            clusters[niche_id] = make_cluster_data(split_indices, reduced, metadata, embeddings_raw)
                            clusters[niche_id]["category_id"] = int(cat_id)
                            clusters[niche_id]["subcategory_id"] = int(subcat_id)
                            niche_counter += 1
                else:
                    niche_id = f"n{niche_counter}"
                    clusters[niche_id] = make_cluster_data(micro_indices, reduced, metadata, embeddings_raw)
                    clusters[niche_id]["category_id"] = int(cat_id)
                    clusters[niche_id]["subcategory_id"] = int(subcat_id)
                    niche_counter += 1

    # Coverage check
    assigned = sum(c["count"] for c in clusters.values())
    print(f"\nClustering complete:")
    print(f"  Niches: {len(clusters)}")
    print(f"  Videos assigned: {assigned}/{n} ({assigned/n*100:.1f}%)")

    with open(OUT, "w") as f:
        json.dump(clusters, f)
    print(f"Saved → {OUT}")


if __name__ == "__main__":
    main()
