#!/usr/bin/env python3
"""V6 Step 2: Combine all datasets into one unified collection.

Sources:
  - V5 merged (6,976 videos): YouTube V1 + TikTok + Instagram + some YouTube V5
  - V6 new YouTube (step 1): fresh YouTube data for underrepresented categories

Output: data/v6/raw_videos.jsonl (unified, deduplicated, normalized)
"""

import json
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "v6"
OUT = DATA_DIR / "raw_videos.jsonl"


def load_jsonl(fp: Path) -> list[dict]:
    videos = []
    if fp.exists():
        with open(fp) as f:
            for line in f:
                line = line.strip()
                if line:
                    videos.append(json.loads(line))
    return videos


def normalize(video: dict) -> dict:
    """Normalize to V6 format: {id, platform, title, description, hashtags, author, author_id, source}"""
    # Already normalized (V5/V6 format) — has hashtags field
    if "hashtags" in video:
        return {
            "id": video.get("id", ""),
            "platform": video.get("platform", "youtube"),
            "title": video.get("title", ""),
            "description": (video.get("description", "") or "")[:500],
            "hashtags": [h.lower().strip("#") for h in (video.get("hashtags") or [])[:25]],
            "author": video.get("author", "") or video.get("channel_title", ""),
            "author_id": video.get("author_id", "") or video.get("channel_id", ""),
            "seed_keyword": video.get("seed_keyword", ""),
            "source": video.get("source", "unknown"),
        }

    # V1 format: has tags field instead of hashtags
    tags = video.get("tags", []) or []
    title = video.get("title", "")
    hashtags_in_title = [
        w[1:].lower() for w in title.split()
        if w.startswith("#") and len(w) > 1
    ]
    return {
        "id": video.get("id", ""),
        "platform": "youtube",
        "title": title,
        "description": (video.get("description", "") or "")[:500],
        "hashtags": list(set(hashtags_in_title + [t.lower() for t in tags[:15]]))[:25],
        "author": video.get("channel_title", ""),
        "author_id": video.get("channel_id", ""),
        "seed_keyword": video.get("seed_keyword", ""),
        "source": video.get("source", "v1_existing"),
    }


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    all_videos: list[dict] = []
    seen_ids: set[str] = set()
    source_counts = Counter()

    # 1. V5 merged — already includes V1 + TikTok + Instagram + some V5 YouTube
    v5_merged = PROJECT_ROOT / "data" / "v5" / "merged_videos.jsonl"
    v5_videos = load_jsonl(v5_merged)
    for v in v5_videos:
        vid = v.get("id", "")
        if vid and vid not in seen_ids:
            seen_ids.add(vid)
            norm = normalize(v)
            all_videos.append(norm)
            source_counts[v.get("source", "unknown")] += 1
    print(f"Loaded {len(v5_videos)} videos from V5 merged ({len(all_videos)} unique so far)")

    # 2. V6 new YouTube data
    v6_youtube = DATA_DIR / "youtube_raw.jsonl"
    v6_videos = load_jsonl(v6_youtube)
    v6_added = 0
    for v in v6_videos:
        vid = v.get("id", "")
        if vid and vid not in seen_ids:
            seen_ids.add(vid)
            norm = normalize(v)
            all_videos.append(norm)
            source_counts["v6_new"] += 1
            v6_added += 1
    print(f"Loaded {len(v6_videos)} V6 YouTube videos (+{v6_added} unique)")

    # Write combined output
    with open(OUT, "w") as f:
        for v in all_videos:
            f.write(json.dumps(v) + "\n")

    # Stats
    platform_counts = Counter(v["platform"] for v in all_videos)
    all_hashtags = set(h for v in all_videos for h in v.get("hashtags", []))
    unique_authors = set(v["author_id"] for v in all_videos if v.get("author_id"))

    stats = {
        "total_videos": len(all_videos),
        "source_breakdown": dict(source_counts),
        "platform_breakdown": dict(platform_counts),
        "unique_hashtags": len(all_hashtags),
        "unique_authors": len(unique_authors),
    }

    with open(DATA_DIR / "combine_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print(f"\n=== V6 Combined Dataset ===")
    print(f"Total videos:    {stats['total_videos']}")
    for platform, count in sorted(platform_counts.items()):
        print(f"  {platform}: {count}")
    print(f"Unique hashtags: {stats['unique_hashtags']}")
    print(f"Unique authors:  {stats['unique_authors']}")
    print(f"\nSaved → {OUT}")


if __name__ == "__main__":
    main()
