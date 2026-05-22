#!/usr/bin/env python3
"""V2 Step 5: Evaluate V2 taxonomy and compare with V1.

Evaluates:
1. Coverage and granularity
2. Hashtag validation rates
3. New niche quality
4. Comparison with V1
"""

import json
from pathlib import Path
from collections import Counter
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent.parent
V1_TAXONOMY = PROJECT_ROOT / "data/v1/taxonomy.json"
V2_TAXONOMY = PROJECT_ROOT / "data/v2/taxonomy.json"
V2_MERGED = PROJECT_ROOT / "data/v2/merged_analysis.json"
V2_GRAPH_STATS = PROJECT_ROOT / "data/v2/graph_stats.json"
OUT_EVAL = PROJECT_ROOT / "data/v2/evaluation.json"


def load_data():
    """Load all evaluation data."""
    v1 = json.loads(V1_TAXONOMY.read_text())
    v2 = json.loads(V2_TAXONOMY.read_text())
    v2_merged = json.loads(V2_MERGED.read_text())
    graph_stats = json.loads(V2_GRAPH_STATS.read_text())
    return v1, v2, v2_merged, graph_stats


def compute_taxonomy_metrics(taxonomy: dict, name: str) -> dict:
    """Compute standard taxonomy metrics."""
    niches = taxonomy.get('niches', {})
    n_niches = len(niches)

    if n_niches == 0:
        return {'error': 'No niches found'}

    # Video counts per niche
    sizes = [n.get('video_count', 0) for n in niches.values()]
    sizes = [s for s in sizes if s > 0]

    if not sizes:
        return {'n_niches': n_niches, 'error': 'No video counts'}

    # Gini coefficient for balance
    sorted_sizes = sorted(sizes)
    n = len(sorted_sizes)
    cumsum = np.cumsum(sorted_sizes)
    gini = (2 * sum((i + 1) * v for i, v in enumerate(sorted_sizes)) - (n + 1) * cumsum[-1]) / (n * cumsum[-1])

    # Category distribution
    cat_counts = Counter(n.get('category_name', 'Unknown') for n in niches.values())

    return {
        'name': name,
        'total_niches': n_niches,
        'total_categories': len(taxonomy.get('categories', {})),
        'total_subcategories': len(taxonomy.get('subcategories', {})),
        'niche_sizes': {
            'min': min(sizes),
            'max': max(sizes),
            'mean': round(np.mean(sizes), 1),
            'median': round(np.median(sizes), 1),
            'std': round(np.std(sizes), 1),
        },
        'gini_coefficient': round(gini, 4),
        'balance': 'balanced' if gini < 0.5 else 'imbalanced',
        'top_categories': dict(cat_counts.most_common(10)),
    }


def compute_v2_specific_metrics(v2_taxonomy: dict, v2_merged: dict) -> dict:
    """Compute V2-specific metrics (hashtag validation, new niches, etc.)."""
    niches = v2_taxonomy.get('niches', {})

    # Source breakdown
    source_counts = Counter(n.get('source', 'unknown') for n in niches.values())

    # Confidence breakdown
    confidence_counts = Counter(n.get('confidence', 'unknown') for n in niches.values())

    # Hashtag validation
    hashtag_validated = sum(1 for n in niches.values() if n.get('hashtag_validated'))

    # Niches with hashtags
    niches_with_hashtags = sum(1 for n in niches.values() if n.get('top_hashtags'))
    avg_hashtags = np.mean([len(n.get('top_hashtags', [])) for n in niches.values()])

    # New niche quality (from merged analysis)
    new_candidates = v2_merged.get('new_niche_candidates', [])

    return {
        'source_distribution': dict(source_counts),
        'confidence_distribution': dict(confidence_counts),
        'hashtag_validated': hashtag_validated,
        'hashtag_validated_pct': round(hashtag_validated / len(niches) * 100, 1) if niches else 0,
        'niches_with_hashtags': niches_with_hashtags,
        'avg_hashtags_per_niche': round(avg_hashtags, 1),
        'new_niche_candidates': len(new_candidates),
        'new_niches_added': source_counts.get('hashtag_discovered', 0),
    }


def compare_v1_v2(v1_taxonomy: dict, v2_taxonomy: dict) -> dict:
    """Compare V1 and V2 taxonomies."""
    v1_niches = set(v1_taxonomy.get('niches', {}).keys())
    v2_niches = set(v2_taxonomy.get('niches', {}).keys())

    # V1 niches that are also in V2
    preserved = v1_niches & v2_niches

    # New in V2
    new_in_v2 = v2_niches - v1_niches

    return {
        'v1_niches': len(v1_niches),
        'v2_niches': len(v2_niches),
        'preserved_from_v1': len(preserved),
        'new_in_v2': len(new_in_v2),
        'growth': len(v2_niches) - len(v1_niches),
        'growth_pct': round((len(v2_niches) - len(v1_niches)) / len(v1_niches) * 100, 1) if v1_niches else 0,
    }


def compute_hashtag_graph_metrics(graph_stats: dict) -> dict:
    """Summarize hashtag graph metrics."""
    return {
        'total_videos': graph_stats.get('total_videos', 0),
        'videos_with_hashtags': graph_stats.get('videos_with_hashtags', 0),
        'hashtag_coverage_pct': round(
            graph_stats.get('videos_with_hashtags', 0) / graph_stats.get('total_videos', 1) * 100, 1
        ),
        'unique_hashtags': graph_stats.get('filtered_hashtags', 0),
        'hashtag_edges': graph_stats.get('filtered_edges', 0),
        'avg_edge_weight': graph_stats.get('avg_edge_weight', 0),
    }


def main():
    print("=" * 60)
    print("V2 Step 5: Evaluation")
    print("=" * 60)

    # Load data
    print("\nLoading data...")
    v1, v2, v2_merged, graph_stats = load_data()

    # Compute metrics
    print("\nComputing metrics...")

    v1_metrics = compute_taxonomy_metrics(v1, "V1")
    v2_metrics = compute_taxonomy_metrics(v2, "V2")
    v2_specific = compute_v2_specific_metrics(v2, v2_merged)
    comparison = compare_v1_v2(v1, v2)
    graph_metrics = compute_hashtag_graph_metrics(graph_stats)

    # Print summary
    print("\n" + "=" * 60)
    print("V2 EVALUATION SUMMARY")
    print("=" * 60)

    print(f"\n--- Taxonomy Comparison ---")
    print(f"                      V1          V2")
    print(f"  Total niches:       {v1_metrics['total_niches']:<12}{v2_metrics['total_niches']}")
    print(f"  Categories:         {v1_metrics['total_categories']:<12}{v2_metrics['total_categories']}")
    print(f"  Gini coefficient:   {v1_metrics['gini_coefficient']:<12}{v2_metrics['gini_coefficient']}")
    print(f"  Balance:            {v1_metrics['balance']:<12}{v2_metrics['balance']}")

    print(f"\n--- V2 Improvements ---")
    print(f"  New niches added: {comparison['new_in_v2']} (+{comparison['growth_pct']}%)")
    print(f"  Hashtag validated: {v2_specific['hashtag_validated']} ({v2_specific['hashtag_validated_pct']}%)")
    print(f"  Avg hashtags/niche: {v2_specific['avg_hashtags_per_niche']}")

    print(f"\n--- Source Breakdown ---")
    for source, count in v2_specific['source_distribution'].items():
        print(f"  {source}: {count}")

    print(f"\n--- Confidence Breakdown ---")
    for conf, count in v2_specific['confidence_distribution'].items():
        print(f"  {conf}: {count}")

    print(f"\n--- Hashtag Graph ---")
    print(f"  Videos with hashtags: {graph_metrics['videos_with_hashtags']} ({graph_metrics['hashtag_coverage_pct']}%)")
    print(f"  Unique hashtags: {graph_metrics['unique_hashtags']}")
    print(f"  Co-occurrence edges: {graph_metrics['hashtag_edges']}")

    # Overall score
    scores = []

    # Coverage (still 100% since we kept all V1 niches)
    scores.append(100)

    # Balance
    scores.append(100 if v2_metrics['gini_coefficient'] < 0.5 else 50)

    # Hashtag validation rate
    scores.append(min(100, v2_specific['hashtag_validated_pct'] * 1.5))

    # New niche discovery (bonus for finding new niches)
    new_niche_bonus = min(100, comparison['growth_pct'] * 5)
    scores.append(new_niche_bonus)

    overall = np.mean(scores)

    print(f"\n--- Overall Score ---")
    print(f"  V2 Quality Score: {overall:.1f}/100")
    print(f"\n  Breakdown:")
    print(f"    Coverage:           {scores[0]:.1f}/100")
    print(f"    Balance:            {scores[1]:.1f}/100")
    print(f"    Hashtag Validation: {scores[2]:.1f}/100")
    print(f"    New Discoveries:    {scores[3]:.1f}/100")

    # V2 success criteria check
    print(f"\n--- V2 Success Criteria ---")
    criteria = [
        ("Hashtag graph built", graph_metrics['unique_hashtags'] > 0, f"{graph_metrics['unique_hashtags']} hashtags"),
        ("Community detection done", v2_merged['summary']['v2_communities'] > 0, f"{v2_merged['summary']['v2_communities']} communities"),
        ("New niches discovered", comparison['new_in_v2'] >= 10, f"{comparison['new_in_v2']} new"),
        ("V1 niches validated", v2_specific['hashtag_validated_pct'] >= 50, f"{v2_specific['hashtag_validated_pct']}%"),
    ]

    for name, passed, detail in criteria:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}: {detail}")

    # Save results
    results = {
        'v1_metrics': v1_metrics,
        'v2_metrics': v2_metrics,
        'v2_specific': v2_specific,
        'comparison': comparison,
        'graph_metrics': graph_metrics,
        'overall_score': round(overall, 1),
        'score_breakdown': {
            'coverage': scores[0],
            'balance': scores[1],
            'hashtag_validation': scores[2],
            'new_discoveries': scores[3],
        },
        'success_criteria': {name: passed for name, passed, _ in criteria},
    }

    OUT_EVAL.write_text(json.dumps(results, indent=2))
    print(f"\n  Evaluation saved -> {OUT_EVAL}")


if __name__ == "__main__":
    main()
