#!/usr/bin/env python3
"""Step 5: Evaluate taxonomy quality and print report."""

import json
import random
import numpy as np
from pathlib import Path

IN_TAXONOMY = Path("data/taxonomy.json")
IN_EMB = Path("data/embeddings.npy")


def main():
    if not IN_TAXONOMY.exists():
        print("taxonomy.json not found — run step 4 first")
        return

    taxonomy = json.loads(IN_TAXONOMY.read_text())
    total_videos = len(np.load(IN_EMB)) if IN_EMB.exists() else "?"

    all_niches = [n for cat in taxonomy["tree"] for n in cat["children"]]
    sizes = [n["video_count"] for n in all_niches]

    print("=" * 50)
    print("TAXONOMY EVALUATION REPORT")
    print("=" * 50)
    print(f"Generated      : {taxonomy['generated_at']}")
    print(f"Top categories : {len(taxonomy['tree'])}")
    print(f"Leaf niches    : {len(all_niches)}")
    print(f"Videos indexed : {total_videos}")

    classified = sum(sizes)
    if isinstance(total_videos, int):
        print(f"\nCOVERAGE: {classified}/{total_videos} = {classified/total_videos:.1%}")
        if classified / total_videos >= 0.85:
            print("  PASS (target >85%)")
        else:
            print("  WARN (below 85% target)")

    print(f"\nGRANULARITY:")
    print(f"  Max    : {max(sizes)} videos")
    print(f"  Median : {np.median(sizes):.0f} videos")
    print(f"  Min    : {min(sizes)} videos")
    print(f"  >10 videos : {sum(1 for s in sizes if s > 10)} niches")
    print(f"  >5  videos : {sum(1 for s in sizes if s > 5)} niches")
    ratio = max(sizes) / (np.median(sizes) + 1)
    print(f"  Max/median ratio: {ratio:.1f}x  ({'power-law — good' if ratio > 3 else 'even distribution'})")

    print(f"\nCATEGORY BREAKDOWN:")
    for cat in taxonomy["tree"]:
        n_videos = sum(c["video_count"] for c in cat["children"])
        print(f"  {cat['name']:<35} {len(cat['children']):>3} niches  {n_videos:>4} videos")

    print(f"\nSAMPLE NICHES (random 8):")
    for niche in random.sample(all_niches, min(8, len(all_niches))):
        print(f"  [{niche['video_count']:>3}v] {niche['name']}")
        if niche.get("description"):
            print(f"         {niche['description'][:80]}")

    print("=" * 50)


if __name__ == "__main__":
    main()
