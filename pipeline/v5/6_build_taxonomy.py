#!/usr/bin/env python3
"""
V5 Step 4: Build unified taxonomy from cross-platform data

Strategy:
1. Load V4 taxonomy as base (676 niches)
2. Cluster new cross-platform data (TikTok + Instagram + new YouTube)
3. Match new clusters to existing niches OR create new ones
4. Apply LLM naming for genuinely new niches
5. Output V5 taxonomy with cross-platform validation
"""

import json
import os
import sys
from pathlib import Path
import numpy as np
from collections import defaultdict
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "v5"
V4_DIR = Path(__file__).parent.parent.parent / "data" / "v4"

# Clustering params
N_COARSE_CLUSTERS = 25  # More clusters due to more data
MIN_CLUSTER_SIZE = 5
SIMILARITY_THRESHOLD = 0.75  # For matching to existing niches


def load_v4_taxonomy():
    """Load existing V4 taxonomy."""
    v4_file = V4_DIR / "taxonomy.json"
    if v4_file.exists():
        with open(v4_file) as f:
            return json.load(f)
    return None


def load_v4_centroids():
    """Load V4 centroids for comparison."""
    # Try to reconstruct from V1 data (V4 uses same base)
    v1_centroids = Path(__file__).parent.parent.parent / "data" / "v1" / "centroids.json"
    if v1_centroids.exists():
        with open(v1_centroids) as f:
            return json.load(f)
    return None


def cluster_new_data(embeddings, metadata, n_clusters=25):
    """Cluster new cross-platform embeddings."""
    print(f"\nClustering {len(embeddings)} videos into {n_clusters} coarse clusters...")

    # Filter to only new data (not V1)
    new_indices = [i for i, m in enumerate(metadata) if m.get("source") == "v5_new"]
    if len(new_indices) < 100:
        print(f"Only {len(new_indices)} new videos, skipping re-clustering")
        return None, None

    new_embeddings = embeddings[new_indices]

    # PCA reduction
    print("  Reducing dimensions with PCA...")
    pca = PCA(n_components=min(100, len(new_embeddings) - 1))
    reduced = pca.fit_transform(new_embeddings)
    print(f"  Explained variance: {pca.explained_variance_ratio_.sum() * 100:.1f}%")

    # K-Means clustering
    print(f"  Running K-Means (k={n_clusters})...")
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(reduced)

    # Build clusters
    clusters = defaultdict(list)
    for idx, label in enumerate(labels):
        original_idx = new_indices[idx]
        clusters[label].append({
            "idx": original_idx,
            "metadata": metadata[original_idx],
            "embedding": embeddings[original_idx].tolist(),
        })

    # Filter small clusters
    valid_clusters = {k: v for k, v in clusters.items() if len(v) >= MIN_CLUSTER_SIZE}
    print(f"  Found {len(valid_clusters)} clusters with {MIN_CLUSTER_SIZE}+ videos")

    return valid_clusters, kmeans


def match_to_existing_niches(clusters, v4_centroids, embeddings):
    """Match new clusters to existing V4 niches."""
    if not v4_centroids:
        return {}, clusters

    print("\nMatching new clusters to existing niches...")

    # Build centroid matrix from V4
    v4_niche_ids = list(v4_centroids.keys())
    v4_centroid_matrix = np.array([v4_centroids[nid] for nid in v4_niche_ids])

    matched = {}
    new_niches = {}

    for cluster_id, cluster_videos in clusters.items():
        # Compute cluster centroid
        cluster_embeddings = np.array([v["embedding"] for v in cluster_videos])
        cluster_centroid = cluster_embeddings.mean(axis=0).reshape(1, -1)

        # Find most similar V4 niche
        similarities = cosine_similarity(cluster_centroid, v4_centroid_matrix)[0]
        best_match_idx = similarities.argmax()
        best_similarity = similarities[best_match_idx]

        if best_similarity >= SIMILARITY_THRESHOLD:
            # Match to existing niche
            matched_niche_id = v4_niche_ids[best_match_idx]
            matched[cluster_id] = {
                "v4_niche_id": matched_niche_id,
                "similarity": float(best_similarity),
                "video_count": len(cluster_videos),
                "platforms": list(set(v["metadata"]["platform"] for v in cluster_videos)),
            }
        else:
            # New niche
            new_niches[cluster_id] = cluster_videos

    print(f"  Matched to existing: {len(matched)} clusters")
    print(f"  New niches: {len(new_niches)} clusters")

    return matched, new_niches


def name_new_niches(new_clusters, metadata):
    """Use LLM to name genuinely new niches."""
    if not new_clusters or not OPENAI_API_KEY:
        return {}

    try:
        from openai import OpenAI
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "openai", "-q"])
        from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)

    named_niches = {}
    print(f"\nNaming {len(new_clusters)} new niches with GPT-4o-mini...")

    for cluster_id, videos in tqdm(new_clusters.items()):
        # Sample titles and hashtags
        sample_titles = [v["metadata"]["title"] for v in videos[:15]]
        all_hashtags = []
        for v in videos:
            all_hashtags.extend(v["metadata"].get("hashtags", []))

        # Count hashtags
        from collections import Counter
        top_hashtags = [h for h, _ in Counter(all_hashtags).most_common(10)]

        # Get platform distribution (filter None)
        platforms = list(set(v["metadata"]["platform"] for v in videos if v["metadata"].get("platform")))

        prompt = f"""You are naming micro-niches for a short-form video taxonomy (TikTok/Reels/Shorts).

Video titles from this cluster:
{chr(10).join(f'- {t}' for t in sample_titles)}

Top hashtags: {', '.join(f'#{h}' for h in top_hashtags)}
Platforms: {', '.join(platforms)}

Name this content niche specifically. Not "fitness" — more like "Calisthenics Bodyweight Training" or "Hyrox Race Prep".

Return JSON only:
{{
  "name": "2-4 word specific niche name",
  "description": "One sentence: who creates this content and what it covers",
  "keywords": ["5", "example", "hashtags"]
}}"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)

            named_niches[f"v5_new_{cluster_id}"] = {
                "id": f"v5_new_{cluster_id}",
                "name": result.get("name", f"New Niche {cluster_id}"),
                "description": result.get("description", ""),
                "keywords": result.get("keywords", top_hashtags[:5]),
                "source": "v5_discovered",
                "platforms": platforms,
                "video_count": len(videos),
                "top_hashtags": top_hashtags,
            }
        except Exception as e:
            print(f"  Error naming cluster {cluster_id}: {e}")
            continue

    return named_niches


def build_v5_taxonomy(v4_taxonomy, matched_clusters, new_named_niches, metadata):
    """Build final V5 taxonomy."""
    print("\nBuilding V5 taxonomy...")

    # Start with V4 taxonomy structure
    v5_taxonomy = {
        "version": "5.0",
        "generated_at": "2026-05-23",
        "platforms": ["youtube", "tiktok", "instagram"],
        "approach": "A + B + C + cross-platform",
        "stats": {
            "v4_niches": 0,
            "v5_new_niches": len(new_named_niches),
            "cross_platform_validated": len(matched_clusters),
        },
        "categories": [],
    }

    # Copy V4 structure and add cross-platform validation
    if v4_taxonomy and "tree" in v4_taxonomy:
        v5_taxonomy["categories"] = v4_taxonomy["tree"]
        v5_taxonomy["stats"]["v4_niches"] = v4_taxonomy.get("total_niches", 0)

        # Add cross-platform validation flags
        for category in v5_taxonomy["categories"]:
            for child in category.get("children", []):
                niche_id = child.get("id")
                # Check if this niche was validated by new platform data
                for cluster_id, match_info in matched_clusters.items():
                    if match_info.get("v4_niche_id") == niche_id:
                        child["cross_platform_validated"] = True
                        child["validation_platforms"] = match_info.get("platforms", [])
                        child["validation_similarity"] = match_info.get("similarity", 0)
                        break

    # Add new discovered niches as a new category
    if new_named_niches:
        new_category = {
            "id": "v5_discovered",
            "name": "Cross-Platform Discoveries",
            "description": "Niches discovered through TikTok and Instagram data not present in YouTube-only taxonomy",
            "source": "v5_cross_platform",
            "children": list(new_named_niches.values()),
        }
        v5_taxonomy["categories"].append(new_category)

    # Calculate totals
    total_niches = v5_taxonomy["stats"]["v4_niches"] + len(new_named_niches)
    v5_taxonomy["total_niches"] = total_niches

    # Platform distribution in metadata
    platform_counts = defaultdict(int)
    for m in metadata:
        platform_counts[m.get("platform", "unknown")] += 1
    v5_taxonomy["platform_distribution"] = dict(platform_counts)

    return v5_taxonomy


def save_taxonomy(taxonomy, centroids=None):
    """Save V5 taxonomy and centroids."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Save taxonomy
    with open(DATA_DIR / "taxonomy.json", "w") as f:
        json.dump(taxonomy, f, indent=2)
    print(f"\nSaved taxonomy -> {DATA_DIR / 'taxonomy.json'}")

    if centroids:
        with open(DATA_DIR / "centroids.json", "w") as f:
            json.dump(centroids, f)
        print(f"Saved centroids -> {DATA_DIR / 'centroids.json'}")


def main():
    print("=== V5: Building Unified Cross-Platform Taxonomy ===\n")

    # Load V4 taxonomy
    v4_taxonomy = load_v4_taxonomy()
    v4_centroids = load_v4_centroids()

    if v4_taxonomy:
        print(f"Loaded V4 taxonomy: {v4_taxonomy.get('total_niches', 0)} niches")
    else:
        print("No V4 taxonomy found, will build from scratch")

    # Load V5 embeddings and metadata
    embeddings_file = DATA_DIR / "embeddings.npy"
    metadata_file = DATA_DIR / "metadata.json"

    if not embeddings_file.exists():
        print("ERROR: No embeddings found. Run 5_embed.py first.")
        sys.exit(1)

    embeddings = np.load(embeddings_file)
    with open(metadata_file) as f:
        metadata = json.load(f)

    print(f"Loaded {len(embeddings)} embeddings")

    # Cluster new data
    clusters, kmeans = cluster_new_data(embeddings, metadata)

    if clusters:
        # Match to existing niches
        matched, new_clusters = match_to_existing_niches(clusters, v4_centroids, embeddings)

        # Name new niches
        new_named = name_new_niches(new_clusters, metadata)
    else:
        matched = {}
        new_named = {}

    # Build final taxonomy
    taxonomy = build_v5_taxonomy(v4_taxonomy, matched, new_named, metadata)

    # Save
    save_taxonomy(taxonomy)

    # Print summary
    print("\n=== V5 Taxonomy Summary ===")
    print(f"Total niches: {taxonomy.get('total_niches', 0)}")
    print(f"  - From V4: {taxonomy['stats']['v4_niches']}")
    print(f"  - New (V5): {taxonomy['stats']['v5_new_niches']}")
    print(f"  - Cross-platform validated: {taxonomy['stats']['cross_platform_validated']}")
    print(f"Platforms: {', '.join(taxonomy.get('platforms', []))}")


if __name__ == "__main__":
    main()
