#!/usr/bin/env python3
"""
V5 Step 2: Merge cross-platform data
Combines: TikTok + Instagram + YouTube (new) + YouTube (V1 existing)
Output: Unified dataset ready for embedding
"""

import json
from pathlib import Path
from collections import Counter

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "v5"
V1_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "v1"
OUTPUT_FILE = DATA_DIR / "merged_videos.jsonl"


def load_jsonl(filepath):
    """Load JSONL file."""
    videos = []
    if filepath.exists():
        with open(filepath) as f:
            for line in f:
                if line.strip():
                    videos.append(json.loads(line))
    return videos


def normalize_hashtags(hashtags):
    """Convert hashtags to list of strings (handles dict format from TikTok)."""
    if not hashtags:
        return []
    result = []
    for h in hashtags:
        if isinstance(h, dict):
            name = h.get("name") or h.get("title") or ""
            if name:
                result.append(name.lower().strip("#"))
        elif isinstance(h, str):
            result.append(h.lower().strip("#"))
    return result


def normalize_video(video, platform=None):
    """Normalize video to consistent format."""
    # Handle V1 YouTube data format
    if "seed_keyword" not in video and "tags" in video:
        # V1 format
        return {
            "id": video.get("id"),
            "platform": "youtube",
            "title": video.get("title", ""),
            "description": video.get("description", "")[:500],
            "hashtags": [t.lower() for t in video.get("tags", [])[:15]],
            "author": video.get("channel_title", ""),
            "author_id": video.get("channel_id", ""),
            "stats": {
                "views": video.get("view_count", 0),
                "likes": video.get("like_count", 0),
                "comments": video.get("comment_count", 0),
            },
            "seed_keyword": video.get("seed_keyword", "unknown"),
            "source": "v1_existing",
        }

    # Already normalized (V5 format)
    video["source"] = "v5_new"
    return video


def merge_all():
    """Merge all platform data."""
    print("=== V5: Merging Cross-Platform Data ===\n")

    all_videos = []
    seen_ids = set()
    platform_counts = Counter()

    # 1. Load existing V1 YouTube data
    v1_file = V1_DATA_DIR / "raw_videos.jsonl"
    if v1_file.exists():
        v1_videos = load_jsonl(v1_file)
        for video in v1_videos:
            vid = video.get("id")
            if vid and vid not in seen_ids:
                seen_ids.add(vid)
                normalized = normalize_video(video)
                all_videos.append(normalized)
                platform_counts["youtube_v1"] += 1
        print(f"Loaded {platform_counts['youtube_v1']} existing YouTube videos from V1")
    else:
        print("No V1 data found")

    # 2. Load new YouTube Shorts (from Apify)
    youtube_file = DATA_DIR / "youtube_new_raw.jsonl"
    if youtube_file.exists():
        yt_videos = load_jsonl(youtube_file)
        for video in yt_videos:
            vid = video.get("id")
            if vid and vid not in seen_ids:
                seen_ids.add(vid)
                video["source"] = "v5_new"
                all_videos.append(video)
                platform_counts["youtube_new"] += 1
        print(f"Loaded {platform_counts['youtube_new']} new YouTube Shorts")

    # 3. Load TikTok videos
    tiktok_file = DATA_DIR / "tiktok_raw.jsonl"
    if tiktok_file.exists():
        tt_videos = load_jsonl(tiktok_file)
        for video in tt_videos:
            vid = f"tt_{video.get('id')}"  # Prefix to avoid ID collision
            if vid not in seen_ids:
                seen_ids.add(vid)
                video["id"] = vid
                video["source"] = "v5_new"
                # Normalize hashtags (TikTok returns dicts)
                video["hashtags"] = normalize_hashtags(video.get("hashtags", []))
                all_videos.append(video)
                platform_counts["tiktok"] += 1
        print(f"Loaded {platform_counts['tiktok']} TikTok videos")

    # 4. Load Instagram Reels
    instagram_file = DATA_DIR / "instagram_raw.jsonl"
    if instagram_file.exists():
        ig_videos = load_jsonl(instagram_file)
        for video in ig_videos:
            vid = f"ig_{video.get('id')}"  # Prefix to avoid ID collision
            if vid not in seen_ids:
                seen_ids.add(vid)
                video["id"] = vid
                video["source"] = "v5_new"
                all_videos.append(video)
                platform_counts["instagram"] += 1
        print(f"Loaded {platform_counts['instagram']} Instagram Reels")

    # Save merged dataset
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        for video in all_videos:
            f.write(json.dumps(video) + "\n")

    # Calculate stats
    all_hashtags = set()
    all_authors = set()
    for video in all_videos:
        # Normalize hashtags in case any weren't processed
        normalized = normalize_hashtags(video.get("hashtags", []))
        all_hashtags.update(normalized)
        if video.get("author_id"):
            all_authors.add(video.get("author_id"))

    stats = {
        "total_videos": len(all_videos),
        "platform_breakdown": dict(platform_counts),
        "unique_hashtags": len(all_hashtags),
        "unique_authors": len(all_authors),
        "v1_existing": platform_counts.get("youtube_v1", 0),
        "v5_new": sum(v for k, v in platform_counts.items() if k != "youtube_v1"),
    }

    with open(DATA_DIR / "merge_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print(f"\n=== Merge Complete ===")
    print(f"Total videos: {stats['total_videos']}")
    print(f"  - YouTube (V1): {platform_counts.get('youtube_v1', 0)}")
    print(f"  - YouTube (new): {platform_counts.get('youtube_new', 0)}")
    print(f"  - TikTok: {platform_counts.get('tiktok', 0)}")
    print(f"  - Instagram: {platform_counts.get('instagram', 0)}")
    print(f"Unique hashtags: {stats['unique_hashtags']}")
    print(f"Unique authors: {stats['unique_authors']}")
    print(f"\nSaved to: {OUTPUT_FILE}")

    return all_videos


if __name__ == "__main__":
    merge_all()
