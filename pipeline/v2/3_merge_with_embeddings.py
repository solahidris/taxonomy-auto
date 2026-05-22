#!/usr/bin/env python3
"""V2 Step 3: Cross-validate hashtag communities with V1 embedding clusters.

Compares:
1. Hashtag-based communities (Approach A)
2. Embedding-based clusters (Approach B from V1)

Identifies:
- High-confidence niches (found by BOTH methods)
- Hashtag-only niches (new discoveries)
- Embedding-only niches (semantic clusters without hashtag signal)
"""

import json
import pickle
from pathlib import Path
from collections import defaultdict
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent.parent
V1_TAXONOMY = PROJECT_ROOT / "data/v1/taxonomy.json"
V1_METADATA = PROJECT_ROOT / "data/v1/metadata.json"
V2_COMMUNITIES = PROJECT_ROOT / "data/v2/communities.json"
V2_GRAPH = PROJECT_ROOT / "data/v2/hashtag_graph.pkl"
OUT_MERGED = PROJECT_ROOT / "data/v2/merged_analysis.json"


def load_v1_taxonomy() -> dict:
    """Load V1 embedding-based taxonomy."""
    return json.loads(V1_TAXONOMY.read_text())


def load_v1_metadata() -> list[dict]:
    """Load V1 video metadata."""
    return json.loads(V1_METADATA.read_text())


def load_v2_communities() -> dict:
    """Load V2 hashtag communities."""
    return json.loads(V2_COMMUNITIES.read_text())


def load_v2_graph() -> dict:
    """Load hashtag graph with tag->video mappings."""
    with open(V2_GRAPH, 'rb') as f:
        return pickle.load(f)


def map_videos_to_v1_niches(v1_taxonomy: dict) -> dict[str, str]:
    """
    Map video IDs to their V1 niche.

    Returns: {video_id: niche_id}
    """
    video_to_niche = {}

    for niche_id, niche_data in v1_taxonomy.get('niches', {}).items():
        for video_id in niche_data.get('video_ids', []):
            video_to_niche[video_id] = niche_id

    return video_to_niche


def compute_community_niche_overlap(
    communities: list[dict],
    tag_to_videos: dict,
    video_to_niche: dict,
    v1_taxonomy: dict
) -> list[dict]:
    """
    For each hashtag community, find which V1 niches its videos belong to.

    Returns enriched community data with niche overlap info.
    """
    enriched = []

    for comm in communities:
        # Get all videos in this community via its hashtags
        community_videos = set()
        for tag in comm['all_hashtags']:
            for vid in tag_to_videos.get(tag, []):
                community_videos.add(vid)

        # Count which V1 niches these videos belong to
        niche_counts = defaultdict(int)
        for vid in community_videos:
            niche_id = video_to_niche.get(vid)
            if niche_id:
                niche_counts[niche_id] += 1

        # Sort by count
        top_niches = sorted(niche_counts.items(), key=lambda x: -x[1])

        # Get niche names
        top_niches_named = []
        for niche_id, count in top_niches[:5]:
            niche_data = v1_taxonomy.get('niches', {}).get(niche_id, {})
            top_niches_named.append({
                'niche_id': niche_id,
                'niche_name': niche_data.get('name', 'Unknown'),
                'category': niche_data.get('category_name', ''),
                'subcategory': niche_data.get('subcategory_name', ''),
                'video_overlap': count,
            })

        # Calculate overlap metrics
        total_community_videos = len(community_videos)
        top_niche_overlap = top_niches[0][1] if top_niches else 0
        concentration = top_niche_overlap / total_community_videos if total_community_videos > 0 else 0

        enriched.append({
            **comm,
            'video_count': total_community_videos,
            'niche_distribution': top_niches_named,
            'top_niche_concentration': round(concentration, 3),
            'num_niches_covered': len(niche_counts),
            'is_focused': concentration > 0.5,  # >50% in single V1 niche
            'is_multi_niche': len(niche_counts) >= 3 and concentration < 0.4,
        })

    return enriched


def find_new_niches(
    enriched_communities: list[dict],
    v1_taxonomy: dict,
    min_videos: int = 10
) -> list[dict]:
    """
    Find hashtag communities that might represent NEW niches not in V1.

    Criteria:
    - Community has enough videos (min_videos)
    - Low concentration in any single V1 niche
    - OR high internal cohesion but spread across V1 niches
    """
    new_niche_candidates = []

    for comm in enriched_communities:
        if comm['video_count'] < min_videos:
            continue

        # Check if this community is NOT well-represented by a single V1 niche
        is_new = False
        reason = ""

        if comm['top_niche_concentration'] < 0.3:
            # Videos are spread across many V1 niches - might be a cross-cutting niche
            is_new = True
            reason = "Cross-cutting: spans multiple V1 niches"

        elif comm['is_multi_niche'] and comm['internal_edge_weight'] > 20:
            # High internal cohesion but multi-niche - might be a bridge niche
            is_new = True
            reason = "Bridge niche: cohesive hashtags spanning V1 boundaries"

        if is_new:
            new_niche_candidates.append({
                'community_id': comm['id'],
                'top_hashtags': comm['top_hashtags'][:10],
                'video_count': comm['video_count'],
                'reason': reason,
                'top_v1_niches': comm['niche_distribution'][:3],
                'cohesion_score': comm['internal_edge_weight'],
            })

    return new_niche_candidates


def compute_validation_matrix(
    enriched_communities: list[dict],
    v1_taxonomy: dict
) -> dict:
    """
    Create a validation matrix: which V1 niches are confirmed by hashtag communities?
    """
    # For each V1 niche, check if there's a focused hashtag community
    v1_niches = v1_taxonomy.get('niches', {})

    niche_validation = {}
    for niche_id, niche_data in v1_niches.items():
        # Find communities that are focused on this niche
        focused_communities = []
        for comm in enriched_communities:
            for niche_info in comm['niche_distribution']:
                if niche_info['niche_id'] == niche_id:
                    # This community has overlap with this niche
                    overlap_pct = niche_info['video_overlap'] / comm['video_count'] if comm['video_count'] > 0 else 0
                    if overlap_pct > 0.3:  # >30% of community is this niche
                        focused_communities.append({
                            'community_id': comm['id'],
                            'top_hashtags': comm['top_hashtags'][:5],
                            'overlap_videos': niche_info['video_overlap'],
                            'overlap_pct': round(overlap_pct, 3),
                        })

        niche_validation[niche_id] = {
            'niche_name': niche_data.get('name', ''),
            'category': niche_data.get('category_name', ''),
            'v1_video_count': niche_data.get('video_count', 0),
            'confirmed_by_hashtags': len(focused_communities) > 0,
            'supporting_communities': focused_communities[:3],
            'confidence': 'high' if focused_communities else 'embedding_only',
        }

    # Summary stats
    confirmed = sum(1 for v in niche_validation.values() if v['confirmed_by_hashtags'])
    total = len(niche_validation)

    return {
        'niche_validation': niche_validation,
        'summary': {
            'total_v1_niches': total,
            'confirmed_by_hashtags': confirmed,
            'confirmation_rate': round(confirmed / total * 100, 1) if total > 0 else 0,
            'embedding_only': total - confirmed,
        }
    }


def main():
    print("=" * 60)
    print("V2 Step 3: Cross-Validate Hashtags with Embeddings")
    print("=" * 60)

    # Load data
    print("\nLoading data...")
    v1_taxonomy = load_v1_taxonomy()
    v1_metadata = load_v1_metadata()
    v2_communities = load_v2_communities()
    v2_graph = load_v2_graph()

    print(f"  V1 niches: {len(v1_taxonomy.get('niches', {}))}")
    print(f"  V1 videos: {len(v1_metadata)}")
    print(f"  V2 graph hashtags: {len(v2_graph['nodes'])}")

    # Use the finest resolution (niches level) for analysis
    niche_communities = v2_communities['hierarchy']['levels']['niches']['communities']
    print(f"  V2 hashtag communities: {len(niche_communities)}")

    # Map videos to V1 niches
    print("\nMapping videos to V1 niches...")
    video_to_niche = map_videos_to_v1_niches(v1_taxonomy)
    print(f"  Videos mapped: {len(video_to_niche)}")

    # Compute overlap between hashtag communities and V1 niches
    print("\nComputing community-niche overlap...")
    enriched_communities = compute_community_niche_overlap(
        niche_communities,
        v2_graph['tag_to_videos'],
        video_to_niche,
        v1_taxonomy
    )

    # Analyze results
    focused = sum(1 for c in enriched_communities if c['is_focused'])
    multi_niche = sum(1 for c in enriched_communities if c['is_multi_niche'])

    print(f"\n--- Community Analysis ---")
    print(f"  Focused communities (>50% one niche): {focused}")
    print(f"  Multi-niche communities: {multi_niche}")
    print(f"  Other: {len(enriched_communities) - focused - multi_niche}")

    # Find potential new niches
    print("\nFinding new niche candidates...")
    new_niches = find_new_niches(enriched_communities, v1_taxonomy, min_videos=10)
    print(f"  New niche candidates: {len(new_niches)}")

    if new_niches:
        print("\n  Top new niche candidates:")
        for nn in new_niches[:5]:
            tags = ', '.join(f'#{t}' for t in nn['top_hashtags'][:5])
            print(f"    - {tags} ({nn['video_count']} videos)")
            print(f"      Reason: {nn['reason']}")

    # Compute validation matrix
    print("\nValidating V1 niches with hashtag signal...")
    validation = compute_validation_matrix(enriched_communities, v1_taxonomy)

    print(f"\n--- Validation Summary ---")
    print(f"  V1 niches confirmed by hashtags: {validation['summary']['confirmed_by_hashtags']}/{validation['summary']['total_v1_niches']} ({validation['summary']['confirmation_rate']}%)")
    print(f"  Embedding-only niches: {validation['summary']['embedding_only']}")

    # Show some confirmed niches
    confirmed_niches = [
        (nid, v) for nid, v in validation['niche_validation'].items()
        if v['confirmed_by_hashtags']
    ][:5]

    if confirmed_niches:
        print("\n  Sample confirmed niches:")
        for nid, v in confirmed_niches:
            tags = ', '.join(f'#{t}' for t in v['supporting_communities'][0]['top_hashtags']) if v['supporting_communities'] else ''
            print(f"    - {v['niche_name']}: {tags}")

    # Save results
    output = {
        'enriched_communities': enriched_communities,
        'new_niche_candidates': new_niches,
        'validation': validation,
        'summary': {
            'v1_niches': len(v1_taxonomy.get('niches', {})),
            'v2_communities': len(niche_communities),
            'focused_communities': focused,
            'multi_niche_communities': multi_niche,
            'new_niche_candidates': len(new_niches),
            'v1_niches_confirmed': validation['summary']['confirmed_by_hashtags'],
            'confirmation_rate': validation['summary']['confirmation_rate'],
        }
    }

    OUT_MERGED.write_text(json.dumps(output, indent=2))
    print(f"\n  Analysis saved -> {OUT_MERGED}")


if __name__ == "__main__":
    main()
