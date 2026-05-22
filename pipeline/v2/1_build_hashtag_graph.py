#!/usr/bin/env python3
"""V2 Step 1: Build hashtag co-occurrence graph from V1 video data.

Extracts hashtags from:
1. YouTube API tags field
2. Hashtags in video titles (#tag)
3. Hashtags in video descriptions (#tag)

Builds a weighted graph where:
- Nodes = hashtags (lowercased, normalized)
- Edges = co-occurrence count (how often two hashtags appear together)
"""

import json
import re
from pathlib import Path
from collections import defaultdict
import pickle

PROJECT_ROOT = Path(__file__).parent.parent.parent
V1_DATA = PROJECT_ROOT / "data/v1/raw_videos.jsonl"
OUT_DIR = PROJECT_ROOT / "data/v2"
OUT_GRAPH = OUT_DIR / "hashtag_graph.pkl"
OUT_STATS = OUT_DIR / "graph_stats.json"

# Minimum occurrences for a hashtag to be included
MIN_TAG_COUNT = 3
# Minimum co-occurrence count for an edge
MIN_EDGE_WEIGHT = 2


def normalize_tag(tag: str) -> str:
    """Normalize a hashtag: lowercase, strip non-alphanumeric."""
    tag = tag.lower().strip()
    tag = re.sub(r'[^a-z0-9]', '', tag)
    return tag


def extract_hashtags_from_text(text: str) -> list[str]:
    """Extract #hashtags from text."""
    pattern = re.compile(r'#(\w+)')
    return [normalize_tag(t) for t in pattern.findall(text)]


def extract_all_hashtags(video: dict) -> list[str]:
    """Extract all hashtags from a video (tags + title + description)."""
    tags = set()

    # From YouTube API tags field
    for t in video.get('tags', []):
        normalized = normalize_tag(t)
        if normalized and len(normalized) >= 2:
            tags.add(normalized)

    # From title hashtags
    for t in extract_hashtags_from_text(video.get('title', '')):
        if t and len(t) >= 2:
            tags.add(t)

    # From description hashtags
    for t in extract_hashtags_from_text(video.get('description', '')):
        if t and len(t) >= 2:
            tags.add(t)

    return list(tags)


def build_cooccurrence_graph(videos: list[dict]) -> tuple[dict, dict, dict]:
    """
    Build hashtag co-occurrence data.

    Returns:
        tag_counts: {tag: count} - how many videos each tag appears in
        cooccurrence: {(tag1, tag2): count} - co-occurrence counts
        tag_to_videos: {tag: [video_ids]} - which videos contain each tag
    """
    tag_counts = defaultdict(int)
    cooccurrence = defaultdict(int)
    tag_to_videos = defaultdict(list)

    for video in videos:
        video_id = video['id']
        tags = extract_all_hashtags(video)

        # Count tag occurrences
        for tag in tags:
            tag_counts[tag] += 1
            tag_to_videos[tag].append(video_id)

        # Count co-occurrences (pairs of tags in same video)
        tags_sorted = sorted(tags)  # Sort for consistent edge naming
        for i, tag1 in enumerate(tags_sorted):
            for tag2 in tags_sorted[i+1:]:
                edge = (tag1, tag2)
                cooccurrence[edge] += 1

    return dict(tag_counts), dict(cooccurrence), dict(tag_to_videos)


def filter_graph(tag_counts: dict, cooccurrence: dict,
                 min_tag_count: int, min_edge_weight: int) -> tuple[set, dict]:
    """
    Filter graph to remove rare tags and weak edges.

    Returns:
        valid_tags: set of tags that pass the filter
        filtered_edges: {(tag1, tag2): weight}
    """
    # Filter tags by minimum count
    valid_tags = {tag for tag, count in tag_counts.items() if count >= min_tag_count}

    # Filter edges by minimum weight and valid tags
    filtered_edges = {}
    for (tag1, tag2), weight in cooccurrence.items():
        if weight >= min_edge_weight and tag1 in valid_tags and tag2 in valid_tags:
            filtered_edges[(tag1, tag2)] = weight

    # Further filter: only keep tags that have at least one edge
    tags_with_edges = set()
    for tag1, tag2 in filtered_edges.keys():
        tags_with_edges.add(tag1)
        tags_with_edges.add(tag2)

    return tags_with_edges, filtered_edges


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("V2 Step 1: Build Hashtag Co-occurrence Graph")
    print("=" * 60)

    # Load V1 videos
    print("\nLoading V1 video data...")
    videos = [json.loads(l) for l in V1_DATA.read_text().splitlines() if l.strip()]
    print(f"  Loaded {len(videos)} videos")

    # Build co-occurrence graph
    print("\nExtracting hashtags and building graph...")
    tag_counts, cooccurrence, tag_to_videos = build_cooccurrence_graph(videos)

    print(f"  Raw hashtags: {len(tag_counts)}")
    print(f"  Raw edges: {len(cooccurrence)}")

    # Filter graph
    print(f"\nFiltering (min_tag_count={MIN_TAG_COUNT}, min_edge_weight={MIN_EDGE_WEIGHT})...")
    valid_tags, filtered_edges = filter_graph(
        tag_counts, cooccurrence, MIN_TAG_COUNT, MIN_EDGE_WEIGHT
    )

    print(f"  Filtered hashtags: {len(valid_tags)}")
    print(f"  Filtered edges: {len(filtered_edges)}")

    # Compute statistics
    if filtered_edges:
        weights = list(filtered_edges.values())
        avg_weight = sum(weights) / len(weights)
        max_weight = max(weights)

        # Degree distribution
        degree = defaultdict(int)
        for tag1, tag2 in filtered_edges.keys():
            degree[tag1] += 1
            degree[tag2] += 1
        avg_degree = sum(degree.values()) / len(degree) if degree else 0
    else:
        avg_weight = max_weight = avg_degree = 0

    # Top hashtags by count
    top_tags = sorted(
        [(t, tag_counts[t]) for t in valid_tags],
        key=lambda x: -x[1]
    )[:30]

    # Top edges by weight
    top_edges = sorted(filtered_edges.items(), key=lambda x: -x[1])[:20]

    print(f"\n--- Graph Statistics ---")
    print(f"  Nodes (hashtags): {len(valid_tags)}")
    print(f"  Edges (co-occurrences): {len(filtered_edges)}")
    print(f"  Avg edge weight: {avg_weight:.2f}")
    print(f"  Max edge weight: {max_weight}")
    print(f"  Avg node degree: {avg_degree:.2f}")

    print(f"\n--- Top 15 Hashtags ---")
    for tag, count in top_tags[:15]:
        print(f"  #{tag}: {count} videos")

    print(f"\n--- Top 10 Co-occurrences ---")
    for (tag1, tag2), weight in top_edges[:10]:
        print(f"  #{tag1} + #{tag2}: {weight}")

    # Save graph data
    graph_data = {
        'nodes': list(valid_tags),
        'edges': filtered_edges,
        'tag_counts': {t: tag_counts[t] for t in valid_tags},
        'tag_to_videos': {t: tag_to_videos[t] for t in valid_tags},
        'params': {
            'min_tag_count': MIN_TAG_COUNT,
            'min_edge_weight': MIN_EDGE_WEIGHT,
        }
    }

    with open(OUT_GRAPH, 'wb') as f:
        pickle.dump(graph_data, f)
    print(f"\n  Graph saved -> {OUT_GRAPH}")

    # Save stats as JSON
    stats = {
        'total_videos': len(videos),
        'videos_with_hashtags': sum(1 for v in videos if extract_all_hashtags(v)),
        'raw_hashtags': len(tag_counts),
        'raw_edges': len(cooccurrence),
        'filtered_hashtags': len(valid_tags),
        'filtered_edges': len(filtered_edges),
        'avg_edge_weight': round(avg_weight, 2),
        'max_edge_weight': max_weight,
        'avg_node_degree': round(avg_degree, 2),
        'top_hashtags': top_tags[:30],
        'top_cooccurrences': [(list(e), w) for e, w in top_edges[:30]],
    }
    OUT_STATS.write_text(json.dumps(stats, indent=2))
    print(f"  Stats saved -> {OUT_STATS}")


if __name__ == "__main__":
    main()
