#!/usr/bin/env python3
"""Step 3: Two-level clustering.

Level 1: K-Means (k=20) for broad categories.
Level 2: HDBSCAN within each broad cluster for micro-niches.
Outputs data/clusters.json with sample titles/tags per cluster.
"""

import json
import numpy as np
from pathlib import Path
from sklearn.cluster import KMeans, HDBSCAN
from sklearn.decomposition import PCA
from sklearn.preprocessing import normalize

IN_EMB = Path("data/embeddings.npy")
IN_META = Path("data/metadata.json")
OUT = Path("data/clusters.json")

N_COARSE = 15
MIN_MICRO_SIZE = 3


def main():
    print("Loading embeddings...")
    embeddings = np.load(IN_EMB)
    metadata = json.loads(IN_META.read_text())
    assert len(embeddings) == len(metadata), "Mismatch between embeddings and metadata"

    normed = normalize(embeddings.astype(np.float64))

    n_components = min(100, normed.shape[1], normed.shape[0] - 1)
    print(f"Reducing to {n_components} dims with PCA...")
    pca = PCA(n_components=n_components, random_state=42)
    reduced = pca.fit_transform(normed)
    print(f"  Explained variance: {pca.explained_variance_ratio_.sum():.2%}")

    print(f"Running K-Means (k={N_COARSE})...")
    kmeans = KMeans(n_clusters=N_COARSE, random_state=42, n_init=10)
    coarse_labels = kmeans.fit_predict(reduced)

    print("Running HDBSCAN micro-clusters within each coarse cluster...")
    clusters: dict[str, dict] = {}

    for coarse_id in range(N_COARSE):
        indices = np.where(coarse_labels == coarse_id)[0]

        if len(indices) < MIN_MICRO_SIZE * 2:
            key = f"c{coarse_id}_m0"
            clusters[key] = {
                "coarse_id": coarse_id,
                "micro_id": 0,
                "indices": indices.tolist(),
                "sample_titles": [metadata[i]["title"] for i in indices[:10]],
                "sample_tags": list({
                    t for i in indices[:20] for t in metadata[i].get("tags", [])[:5]
                })[:20],
                "centroid": normed[indices].mean(axis=0).tolist(),
            }
            continue

        sub = reduced[indices]
        hdb = HDBSCAN(min_cluster_size=MIN_MICRO_SIZE)
        micro_labels = hdb.fit_predict(sub)

        for micro_id in set(micro_labels):
            if micro_id == -1:
                continue
            micro_mask = micro_labels == micro_id
            micro_indices = indices[micro_mask]
            key = f"c{coarse_id}_m{micro_id}"
            clusters[key] = {
                "coarse_id": coarse_id,
                "micro_id": int(micro_id),
                "indices": micro_indices.tolist(),
                "sample_titles": [metadata[i]["title"] for i in micro_indices[:10]],
                "sample_tags": list({
                    t for i in micro_indices[:20] for t in metadata[i].get("tags", [])[:5]
                })[:20],
                "centroid": normed[micro_indices].mean(axis=0).tolist(),
            }

        noise_indices = indices[micro_labels == -1]
        if len(noise_indices) >= MIN_MICRO_SIZE:
            key = f"c{coarse_id}_noise"
            clusters[key] = {
                "coarse_id": coarse_id,
                "micro_id": -1,
                "indices": noise_indices.tolist(),
                "sample_titles": [metadata[i]["title"] for i in noise_indices[:10]],
                "sample_tags": list({
                    t for i in noise_indices[:20] for t in metadata[i].get("tags", [])[:5]
                })[:20],
                "centroid": normed[noise_indices].mean(axis=0).tolist(),
            }

    total_classified = sum(len(c["indices"]) for c in clusters.values())
    print(f"\nFound {len(clusters)} micro-niches across {N_COARSE} coarse clusters")
    print(f"Classified {total_classified}/{len(embeddings)} videos ({total_classified/len(embeddings):.1%})")

    OUT.write_text(json.dumps(clusters, indent=2))
    print(f"Clusters saved → {OUT}")


if __name__ == "__main__":
    main()
