#!/usr/bin/env python3
"""
V3 Step 1: Analyze Niches for Sub-Niche Discovery

This script prepares niche data for LLM-driven sub-niche breakdown by:
1. Loading V2 taxonomy and V1 video metadata
2. For each niche with enough videos, sampling representative content
3. Extracting patterns (titles, hashtags, keywords) for LLM analysis
4. Identifying niches that are good candidates for breakdown

Output: data/v3/niche_analysis.json
"""

import json
import os
from collections import defaultdict
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
V1_DIR = DATA_DIR / "v1"
V2_DIR = DATA_DIR / "v2"
V3_DIR = DATA_DIR / "v3"

# Thresholds
MIN_VIDEOS_FOR_BREAKDOWN = 10  # Need at least 10 videos to suggest sub-niches
MAX_SAMPLE_TITLES = 30  # Sample titles for LLM
MAX_SAMPLE_HASHTAGS = 20  # Top hashtags per niche


def load_v2_taxonomy():
    """Load V2 taxonomy with 234 niches."""
    with open(V2_DIR / "taxonomy.json") as f:
        return json.load(f)


def load_v1_metadata():
    """Load V1 video metadata."""
    with open(V1_DIR / "metadata.json") as f:
        data = json.load(f)
        # Handle both list format and dict format
        if isinstance(data, list):
            return data
        return data.get("videos", [])


def load_v1_clusters():
    """Load V1 cluster assignments to map videos to niches."""
    with open(V1_DIR / "clusters.json") as f:
        return json.load(f)


def build_video_to_niche_map(clusters):
    """Build mapping from video index to niche ID."""
    video_to_niche = {}
    for niche_id, niche_data in clusters.items():
        if "video_indices" in niche_data:
            for idx in niche_data["video_indices"]:
                video_to_niche[idx] = niche_id
    return video_to_niche


def analyze_niches():
    """Analyze each niche to prepare for sub-niche discovery."""
    print("Loading V2 taxonomy...")
    taxonomy = load_v2_taxonomy()

    print("Loading V1 metadata...")
    videos = load_v1_metadata()

    print("Loading V1 clusters...")
    clusters = load_v1_clusters()

    print(f"Total videos: {len(videos)}")
    print(f"Total V2 niches: {len(taxonomy['niches'])}")

    # Build video to niche mapping from clusters
    video_to_niche = build_video_to_niche_map(clusters)
    print(f"Videos with niche assignments: {len(video_to_niche)}")

    # Group videos by niche
    niche_videos = defaultdict(list)
    for idx, video in enumerate(videos):
        niche_id = video_to_niche.get(idx)
        if niche_id:
            niche_videos[niche_id].append(video)

    # Analyze each niche
    analysis = {
        "version": "3.0",
        "source": "v2_taxonomy",
        "niches_analyzed": 0,
        "niches_for_breakdown": 0,
        "niches": {}
    }

    for niche_id, niche_data in taxonomy["niches"].items():
        videos_in_niche = niche_videos.get(niche_id, [])

        # Also check if this is a hashtag-discovered niche (no direct video mapping)
        is_hashtag_niche = niche_data.get("source") == "hashtag_discovered"

        # Extract sample titles
        sample_titles = [v.get("title", "") for v in videos_in_niche[:MAX_SAMPLE_TITLES]]

        # Extract and count hashtags
        hashtag_counts = defaultdict(int)
        for video in videos_in_niche:
            tags = video.get("tags", [])
            for tag in tags:
                hashtag_counts[tag.lower()] += 1

        # Get top hashtags
        top_hashtags = sorted(hashtag_counts.items(), key=lambda x: -x[1])[:MAX_SAMPLE_HASHTAGS]

        # Use niche's own hashtags if available
        niche_hashtags = niche_data.get("top_hashtags", [])

        # Determine if this niche is a good candidate for breakdown
        video_count = niche_data.get("video_count", len(videos_in_niche))
        is_candidate = video_count >= MIN_VIDEOS_FOR_BREAKDOWN

        # Skip very specific niches that are already narrow
        niche_name = niche_data.get("name", "")
        is_already_specific = any(word in niche_name.lower() for word in [
            "beginner", "advanced", "for ", "over ", "under ", "challenge"
        ])

        niche_analysis = {
            "name": niche_name,
            "description": niche_data.get("description", ""),
            "category": niche_data.get("category_name", ""),
            "subcategory": niche_data.get("subcategory_name", ""),
            "source": niche_data.get("source", "embedding_clustered"),
            "video_count": video_count,
            "sample_titles": sample_titles,
            "top_hashtags": [h[0] for h in top_hashtags],
            "hashtag_counts": dict(top_hashtags),
            "niche_hashtags": niche_hashtags,
            "keywords": niche_data.get("keywords", []),
            "is_candidate_for_breakdown": is_candidate and not is_already_specific,
            "reason": "Sufficient videos and not already specific" if (is_candidate and not is_already_specific) else (
                "Already specific niche" if is_already_specific else f"Too few videos ({video_count})"
            )
        }

        analysis["niches"][niche_id] = niche_analysis
        analysis["niches_analyzed"] += 1

        if niche_analysis["is_candidate_for_breakdown"]:
            analysis["niches_for_breakdown"] += 1

    return analysis


def main():
    print("=" * 60)
    print("V3 Step 1: Analyze Niches for Sub-Niche Discovery")
    print("=" * 60)

    # Ensure output directory exists
    V3_DIR.mkdir(parents=True, exist_ok=True)

    # Run analysis
    analysis = analyze_niches()

    # Save results
    output_path = V3_DIR / "niche_analysis.json"
    with open(output_path, "w") as f:
        json.dump(analysis, f, indent=2)

    print(f"\nResults:")
    print(f"  Niches analyzed: {analysis['niches_analyzed']}")
    print(f"  Candidates for breakdown: {analysis['niches_for_breakdown']}")
    print(f"\nSaved to: {output_path}")

    # Show some examples
    print(f"\nExample candidates:")
    count = 0
    for niche_id, data in analysis["niches"].items():
        if data["is_candidate_for_breakdown"] and count < 5:
            print(f"  - {data['name']} ({data['video_count']} videos)")
            count += 1


if __name__ == "__main__":
    main()
