#!/usr/bin/env python3
"""V2 Step 2: Run community detection on hashtag co-occurrence graph.

Uses Louvain algorithm to find communities of related hashtags.
Each community represents a potential content niche.

Resolution parameter controls granularity:
- Lower resolution = fewer, larger communities
- Higher resolution = more, smaller communities
"""

import json
import pickle
from pathlib import Path
from collections import defaultdict

import networkx as nx
from networkx.algorithms import community as nx_community

PROJECT_ROOT = Path(__file__).parent.parent.parent
IN_GRAPH = PROJECT_ROOT / "data/v2/hashtag_graph.pkl"
OUT_COMMUNITIES = PROJECT_ROOT / "data/v2/communities.json"

# Resolution parameter for Louvain (higher = more communities)
# We'll run at multiple resolutions to build hierarchy
RESOLUTIONS = [0.5, 1.0, 2.0]


def load_graph() -> tuple[nx.Graph, dict]:
    """Load the hashtag graph from pickle."""
    with open(IN_GRAPH, 'rb') as f:
        data = pickle.load(f)

    G = nx.Graph()

    # Add nodes with counts
    for tag in data['nodes']:
        G.add_node(tag, count=data['tag_counts'].get(tag, 0))

    # Add weighted edges
    for (tag1, tag2), weight in data['edges'].items():
        G.add_edge(tag1, tag2, weight=weight)

    return G, data


def run_louvain(G: nx.Graph, resolution: float) -> dict[str, int]:
    """
    Run Louvain community detection.

    Returns: {node: community_id}
    """
    # Use networkx's louvain_communities
    communities = nx_community.louvain_communities(
        G,
        weight='weight',
        resolution=resolution,
        seed=42
    )

    # Convert to node -> community mapping
    node_to_community = {}
    for i, comm in enumerate(communities):
        for node in comm:
            node_to_community[node] = i

    return node_to_community


def analyze_communities(G: nx.Graph, node_to_comm: dict, tag_counts: dict) -> list[dict]:
    """
    Analyze each community.

    Returns list of community info dicts.
    """
    # Group nodes by community
    comm_nodes = defaultdict(list)
    for node, comm in node_to_comm.items():
        comm_nodes[comm].append(node)

    communities = []
    for comm_id, nodes in sorted(comm_nodes.items()):
        # Sort nodes by count (popularity)
        nodes_sorted = sorted(nodes, key=lambda x: -tag_counts.get(x, 0))

        # Calculate community stats
        total_count = sum(tag_counts.get(n, 0) for n in nodes)

        # Get internal edge weight (cohesion)
        internal_weight = 0
        for n1 in nodes:
            for n2 in G.neighbors(n1):
                if n2 in nodes and n1 < n2:  # Avoid double counting
                    internal_weight += G[n1][n2].get('weight', 1)

        communities.append({
            'id': comm_id,
            'size': len(nodes),
            'total_video_count': total_count,
            'internal_edge_weight': internal_weight,
            'top_hashtags': nodes_sorted[:15],
            'all_hashtags': nodes_sorted,
        })

    return sorted(communities, key=lambda x: -x['total_video_count'])


def build_hierarchy(results: dict[float, list[dict]], tag_counts: dict) -> dict:
    """
    Build a hierarchical structure from multi-resolution communities.

    Lower resolution (0.5) = categories (broad)
    Medium resolution (1.0) = subcategories
    Higher resolution (2.0) = niches (specific)
    """
    # Map tags to their community at each level
    tag_to_level = {res: {} for res in results.keys()}

    for res, communities in results.items():
        for comm in communities:
            for tag in comm['all_hashtags']:
                tag_to_level[res][tag] = comm['id']

    # Build hierarchy: find parent-child relationships
    resolutions = sorted(results.keys())

    hierarchy = {
        'levels': {},
        'parent_child': {},
    }

    for i, res in enumerate(resolutions):
        level_name = ['categories', 'subcategories', 'niches'][i] if i < 3 else f'level_{i}'
        hierarchy['levels'][level_name] = {
            'resolution': res,
            'communities': results[res],
        }

        # Find parent relationships (coarser level -> finer level)
        if i > 0:
            parent_res = resolutions[i - 1]
            child_parent = defaultdict(lambda: defaultdict(int))

            # For each tag, map child community to parent community
            for tag in tag_to_level[res]:
                child_comm = tag_to_level[res][tag]
                parent_comm = tag_to_level[parent_res].get(tag)
                if parent_comm is not None:
                    child_parent[child_comm][parent_comm] += tag_counts.get(tag, 1)

            # Assign each child to its dominant parent
            parent_mapping = {}
            for child, parents in child_parent.items():
                if parents:
                    parent_mapping[child] = max(parents.keys(), key=lambda p: parents[p])

            hierarchy['parent_child'][f'{resolutions[i-1]}_to_{res}'] = parent_mapping

    return hierarchy


def main():
    print("=" * 60)
    print("V2 Step 2: Community Detection (Louvain)")
    print("=" * 60)

    # Load graph
    print("\nLoading hashtag graph...")
    G, graph_data = load_graph()
    tag_counts = graph_data['tag_counts']

    print(f"  Nodes: {G.number_of_nodes()}")
    print(f"  Edges: {G.number_of_edges()}")

    # Run community detection at multiple resolutions
    results = {}

    for res in RESOLUTIONS:
        print(f"\n--- Resolution {res} ---")
        node_to_comm = run_louvain(G, res)
        communities = analyze_communities(G, node_to_comm, tag_counts)

        results[res] = communities

        print(f"  Communities found: {len(communities)}")
        print(f"  Largest community: {communities[0]['size']} hashtags")
        print(f"  Smallest community: {communities[-1]['size']} hashtags")

        # Show top 5 communities
        print(f"  Top 5 by video count:")
        for comm in communities[:5]:
            top_tags = ', '.join(f'#{t}' for t in comm['top_hashtags'][:5])
            print(f"    [{comm['id']}] {comm['size']} tags, {comm['total_video_count']} videos: {top_tags}")

    # Build hierarchy
    print("\n--- Building Hierarchy ---")
    hierarchy = build_hierarchy(results, tag_counts)

    # Summary
    print(f"\nHierarchy Summary:")
    for level_name, level_data in hierarchy['levels'].items():
        n_comms = len(level_data['communities'])
        print(f"  {level_name}: {n_comms} communities (resolution={level_data['resolution']})")

    # Save results
    output = {
        'resolutions': RESOLUTIONS,
        'results': {str(k): v for k, v in results.items()},
        'hierarchy': {
            'levels': {
                name: {
                    'resolution': data['resolution'],
                    'num_communities': len(data['communities']),
                    'communities': data['communities'],
                }
                for name, data in hierarchy['levels'].items()
            },
            'parent_child': {
                k: {str(ck): cv for ck, cv in v.items()}
                for k, v in hierarchy['parent_child'].items()
            },
        },
        'graph_stats': {
            'nodes': G.number_of_nodes(),
            'edges': G.number_of_edges(),
        }
    }

    OUT_COMMUNITIES.write_text(json.dumps(output, indent=2))
    print(f"\n  Communities saved -> {OUT_COMMUNITIES}")


if __name__ == "__main__":
    main()
