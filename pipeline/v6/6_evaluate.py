#!/usr/bin/env python3
"""V6 Step 6: Evaluate the V6 taxonomy quality."""

import json
from pathlib import Path
from collections import Counter

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "v6"


def gini(values: list[int]) -> float:
    if not values or sum(values) == 0:
        return 0
    vals = sorted(values)
    n = len(vals)
    cum = 0
    for i, v in enumerate(vals):
        cum += (2 * (i + 1) - n - 1) * v
    return cum / (n * sum(vals))


def main():
    taxonomy_file = DATA_DIR / "taxonomy.json"
    if not taxonomy_file.exists():
        print("ERROR: Run 5_name.py first")
        return

    taxonomy = json.loads(taxonomy_file.read_text())
    niches = taxonomy["niches"]
    categories = taxonomy["categories"]
    subcategories = taxonomy["subcategories"]
    stats = taxonomy["stats"]

    # Size distribution
    video_counts = [n["video_count"] for n in niches.values()]
    total_assigned = sum(video_counts)
    total_videos = stats.get("total_videos", total_assigned)

    # Category distribution
    cat_niches = Counter(n["category_name"] for n in niches.values())

    print("=" * 60)
    print("V6 TAXONOMY EVALUATION")
    print("=" * 60)
    print(f"Generated:     {taxonomy.get('generated_at', 'N/A')}")
    print(f"Categories:    {len(categories)}")
    print(f"Subcategories: {len(subcategories)}")
    print(f"Niches:        {len(niches)}")
    print(f"Videos total:  {total_videos}")
    print()

    # Coverage
    coverage = total_assigned / total_videos if total_videos > 0 else 0
    status = "PASS" if coverage >= 0.85 else "FAIL"
    print(f"COVERAGE: {total_assigned}/{total_videos} = {coverage*100:.1f}%  [{status}]")

    # Balance
    g = gini(video_counts)
    bal_status = "PASS" if g < 0.7 else "WARN"
    print(f"BALANCE (Gini): {g:.3f}  [{bal_status}] (lower = more balanced)")

    # Niche size distribution
    if video_counts:
        print(f"\nNICHE SIZES:")
        print(f"  Max:    {max(video_counts)}")
        print(f"  Median: {sorted(video_counts)[len(video_counts)//2]}")
        print(f"  Min:    {min(video_counts)}")
        print(f"  Mean:   {total_assigned/len(video_counts):.1f}")

    # Categories
    print(f"\nTOP CATEGORIES BY NICHE COUNT:")
    for cat, count in cat_niches.most_common(10):
        print(f"  {cat}: {count} niches")

    # Scoring
    coverage_score = min(100, coverage * 100 / 0.85 * 100) if coverage < 0.85 else 100
    balance_score = max(0, (0.8 - g) / 0.8 * 100)
    scale_score = min(100, len(niches) / 400 * 100)

    overall = (coverage_score * 0.3 + balance_score * 0.3 + scale_score * 0.4)

    print(f"\nSCORES:")
    print(f"  Coverage:  {coverage_score:.1f}/100")
    print(f"  Balance:   {balance_score:.1f}/100")
    print(f"  Scale:     {scale_score:.1f}/100")
    print(f"  OVERALL:   {overall:.1f}/100")

    evaluation = {
        "version": "v6",
        "total_niches": len(niches),
        "total_categories": len(categories),
        "total_subcategories": len(subcategories),
        "total_videos": total_videos,
        "coverage": coverage,
        "gini_coefficient": g,
        "niche_sizes": {
            "max": max(video_counts) if video_counts else 0,
            "min": min(video_counts) if video_counts else 0,
            "median": sorted(video_counts)[len(video_counts)//2] if video_counts else 0,
            "mean": total_assigned / len(video_counts) if video_counts else 0,
        },
        "category_distribution": dict(cat_niches),
        "scores": {
            "coverage": round(coverage_score, 1),
            "balance": round(balance_score, 1),
            "scale": round(scale_score, 1),
            "overall": round(overall, 1),
        },
    }

    with open(DATA_DIR / "evaluation.json", "w") as f:
        json.dump(evaluation, f, indent=2)

    print(f"\nSaved evaluation → {DATA_DIR / 'evaluation.json'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
