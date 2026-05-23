#!/usr/bin/env python3
"""
V5 Step 5: Evaluate V5 taxonomy
Metrics: scale, cross-platform coverage, validation rate, new discoveries
"""

import json
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "v5"
V4_DIR = Path(__file__).parent.parent.parent / "data" / "v4"


def load_json(filepath):
    """Load JSON file."""
    if filepath.exists():
        with open(filepath) as f:
            return json.load(f)
    return None


def evaluate():
    print("=== V5 Taxonomy Evaluation ===\n")

    # Load taxonomies
    v5_taxonomy = load_json(DATA_DIR / "taxonomy.json")
    v4_taxonomy = load_json(V4_DIR / "taxonomy.json")
    merge_stats = load_json(DATA_DIR / "merge_stats.json")

    if not v5_taxonomy:
        print("ERROR: No V5 taxonomy found. Run pipeline first.")
        return

    # Basic stats
    print("=" * 50)
    print("SCALE METRICS")
    print("=" * 50)

    v5_total = v5_taxonomy.get("total_niches", 0)
    v4_total = v4_taxonomy.get("total_niches", 0) if v4_taxonomy else 0
    growth = ((v5_total - v4_total) / v4_total * 100) if v4_total > 0 else 0

    print(f"V5 total niches:     {v5_total}")
    print(f"V4 total niches:     {v4_total}")
    print(f"Growth:              {growth:+.1f}%")
    print(f"Target (1000+):      {'PASS' if v5_total >= 1000 else 'PARTIAL' if v5_total >= 800 else 'FAIL'}")

    # Platform coverage
    print("\n" + "=" * 50)
    print("CROSS-PLATFORM COVERAGE")
    print("=" * 50)

    if merge_stats:
        platform_breakdown = merge_stats.get("platform_breakdown", {})
        total_videos = merge_stats.get("total_videos", 0)

        print(f"Total videos:        {total_videos}")
        for platform, count in sorted(platform_breakdown.items()):
            pct = (count / total_videos * 100) if total_videos > 0 else 0
            print(f"  - {platform:15} {count:5} ({pct:.1f}%)")

        # Check multi-platform
        platforms = [p for p in platform_breakdown.keys() if platform_breakdown[p] > 0]
        print(f"\nPlatforms covered:   {len(platforms)}")
        print(f"Target (3):          {'PASS' if len(platforms) >= 3 else 'PARTIAL' if len(platforms) >= 2 else 'FAIL'}")

    # Cross-platform validation
    print("\n" + "=" * 50)
    print("CROSS-PLATFORM VALIDATION")
    print("=" * 50)

    validated_count = 0
    multi_platform_niches = 0

    for category in v5_taxonomy.get("categories", []):
        for child in category.get("children", []):
            if child.get("cross_platform_validated"):
                validated_count += 1
                platforms = child.get("validation_platforms", [])
                if len(platforms) > 1:
                    multi_platform_niches += 1

    print(f"Niches validated by new data: {validated_count}")
    print(f"Multi-platform niches:        {multi_platform_niches}")
    validation_rate = (validated_count / v5_total * 100) if v5_total > 0 else 0
    print(f"Validation rate:              {validation_rate:.1f}%")

    # New discoveries
    print("\n" + "=" * 50)
    print("NEW DISCOVERIES")
    print("=" * 50)

    new_niches = v5_taxonomy.get("stats", {}).get("v5_new_niches", 0)
    print(f"New niches discovered:  {new_niches}")
    print(f"Discovery source:       Cross-platform clustering")

    # List new niches if any
    for category in v5_taxonomy.get("categories", []):
        if category.get("source") == "v5_cross_platform":
            print(f"\nNew category: '{category.get('name')}'")
            for child in category.get("children", [])[:10]:
                platforms = ", ".join(child.get("platforms", []))
                print(f"  - {child.get('name')} ({platforms})")

    # Overall score
    print("\n" + "=" * 50)
    print("OVERALL QUALITY SCORE")
    print("=" * 50)

    # Calculate scores
    scale_score = min(100, (v5_total / 1000) * 100)
    platform_score = min(100, len(platforms) / 3 * 100) if merge_stats else 0
    validation_score = min(100, validation_rate)
    discovery_score = min(100, new_niches * 5)  # 20 new niches = 100

    overall = (scale_score + platform_score + validation_score + discovery_score) / 4

    print(f"Scale (1000 target):     {scale_score:.1f}/100")
    print(f"Platform coverage:       {platform_score:.1f}/100")
    print(f"Validation rate:         {validation_score:.1f}/100")
    print(f"New discoveries:         {discovery_score:.1f}/100")
    print(f"\nOVERALL SCORE:           {overall:.1f}/100")

    # Save evaluation
    evaluation = {
        "version": "5.0",
        "metrics": {
            "scale": {
                "v5_niches": v5_total,
                "v4_niches": v4_total,
                "growth_pct": growth,
                "target": 1000,
                "score": scale_score,
            },
            "platforms": {
                "covered": len(platforms) if merge_stats else 0,
                "target": 3,
                "breakdown": platform_breakdown if merge_stats else {},
                "score": platform_score,
            },
            "validation": {
                "validated_niches": validated_count,
                "multi_platform": multi_platform_niches,
                "rate_pct": validation_rate,
                "score": validation_score,
            },
            "discoveries": {
                "new_niches": new_niches,
                "score": discovery_score,
            },
        },
        "overall_score": overall,
        "success_criteria": {
            "scale_1000": v5_total >= 1000,
            "scale_800": v5_total >= 800,
            "multi_platform": len(platforms) >= 3 if merge_stats else False,
            "validation_50pct": validation_rate >= 50,
            "new_discoveries_10": new_niches >= 10,
        },
    }

    with open(DATA_DIR / "evaluation.json", "w") as f:
        json.dump(evaluation, f, indent=2)

    print(f"\nSaved evaluation -> {DATA_DIR / 'evaluation.json'}")

    # Success criteria summary
    print("\n" + "=" * 50)
    print("SUCCESS CRITERIA")
    print("=" * 50)

    criteria = evaluation["success_criteria"]
    for name, passed in criteria.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name:25} {status}")


if __name__ == "__main__":
    evaluate()
