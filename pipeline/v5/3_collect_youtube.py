#!/usr/bin/env python3
"""
V5 Step 1c: Collect YouTube Shorts using Apify (bypasses quota)
Budget: ~$1 (~5 CU)
Target: 3,000-5,000 videos

Note: We already have ~4K YouTube videos from V1. This script collects
additional videos to fill gaps in underrepresented categories.
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
if not APIFY_TOKEN:
    print("ERROR: APIFY_API_TOKEN not found in .env.local")
    sys.exit(1)

# Budget control: ~$1 = 5 CU
MAX_RESULTS_PER_KEYWORD = 100
MAX_TOTAL_VIDEOS = 3000

# Keywords for categories underrepresented in V1 (due to quota limits)
# V1 was heavy on fitness/food/beauty, light on gaming/travel/tech
SEARCH_KEYWORDS = [
    # Gaming (V1 gap)
    "gaming highlights", "minecraft shorts", "fortnite clips", "valorant plays",
    "speedrun", "retro gaming", "indie games",
    # Travel (V1 gap)
    "travel shorts", "hidden gems travel", "solo travel tips", "van life",
    "backpacking tips", "budget travel hacks",
    # Tech (V1 gap)
    "tech review shorts", "iphone tips", "android hacks", "ai tools",
    "coding tips", "tech unboxing",
    # Comedy/Entertainment (V1 gap)
    "funny shorts", "comedy sketches", "prank videos", "satisfying videos",
    "asmr", "life hacks",
    # Education
    "learn in 60 seconds", "science shorts", "history facts", "study tips",
    # Fill existing gaps with more specific queries
    "swimming drills", "marathon tips", "hyrox training", "pilates shorts",
]

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "v5"
OUTPUT_FILE = DATA_DIR / "youtube_new_raw.jsonl"


def collect_youtube():
    """Collect YouTube Shorts via Apify."""
    try:
        from apify_client import ApifyClient
    except ImportError:
        print("Installing apify-client...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "apify-client", "-q"])
        from apify_client import ApifyClient

    client = ApifyClient(APIFY_TOKEN)

    all_videos = []
    seen_ids = set()

    # Load existing V1 video IDs to avoid duplicates
    v1_data_file = DATA_DIR.parent / "v1" / "raw_videos.jsonl"
    if v1_data_file.exists():
        with open(v1_data_file) as f:
            for line in f:
                video = json.loads(line)
                seen_ids.add(video.get("id"))
        print(f"Loaded {len(seen_ids)} existing V1 video IDs to avoid duplicates")

    print(f"\nCollecting YouTube Shorts for {len(SEARCH_KEYWORDS)} keywords...")
    print(f"Budget: ~$1 (max {MAX_TOTAL_VIDEOS} new videos)")
    print()

    for i, keyword in enumerate(SEARCH_KEYWORDS):
        if len(all_videos) >= MAX_TOTAL_VIDEOS:
            print(f"\nReached max videos ({MAX_TOTAL_VIDEOS}), stopping.")
            break

        print(f"[{i+1}/{len(SEARCH_KEYWORDS)}] Searching: '{keyword}'...")

        try:
            # Use bernardo/youtube-scraper or similar
            run_input = {
                "searchKeywords": [keyword],
                "maxResults": min(MAX_RESULTS_PER_KEYWORD, MAX_TOTAL_VIDEOS - len(all_videos)),
                "uploadDate": "month",  # Recent content
                "videoType": "short",  # Shorts only
            }

            run = client.actor("bernardo/youtube-scraper").call(run_input=run_input)

            # Get results from dataset
            dataset_items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

            new_count = 0
            for item in dataset_items:
                video_id = item.get("id") or item.get("videoId")
                if video_id and video_id not in seen_ids:
                    seen_ids.add(video_id)

                    # Extract tags/hashtags
                    tags = item.get("tags", []) or []
                    title = item.get("title", "") or ""
                    # Extract hashtags from title
                    hashtags = [
                        word[1:].lower()
                        for word in title.split()
                        if word.startswith("#") and len(word) > 1
                    ]

                    # Normalize to our format
                    video = {
                        "id": video_id,
                        "platform": "youtube",
                        "title": title,
                        "description": (item.get("description", "") or "")[:500],
                        "hashtags": list(set(hashtags + [t.lower() for t in tags[:10]])),
                        "author": item.get("channelName", "") or item.get("channel", ""),
                        "author_id": item.get("channelId", ""),
                        "stats": {
                            "views": item.get("viewCount", 0),
                            "likes": item.get("likeCount", 0),
                            "comments": item.get("commentCount", 0),
                        },
                        "seed_keyword": keyword,
                        "collected_at": item.get("uploadDate", ""),
                    }
                    all_videos.append(video)
                    new_count += 1

            print(f"  +{new_count} new videos (total: {len(all_videos)})")

        except Exception as e:
            print(f"  Error: {e}")
            continue

    # Save results
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        for video in all_videos:
            f.write(json.dumps(video) + "\n")

    print(f"\nDone! Saved {len(all_videos)} new YouTube Shorts to {OUTPUT_FILE}")

    # Save stats
    stats = {
        "platform": "youtube",
        "total_new_videos": len(all_videos),
        "unique_hashtags": len(set(h for v in all_videos for h in v.get("hashtags", []))),
        "unique_authors": len(set(v.get("author_id") for v in all_videos if v.get("author_id"))),
        "keywords_searched": len(SEARCH_KEYWORDS),
        "skipped_duplicates": len(seen_ids) - len(all_videos),
    }
    with open(DATA_DIR / "youtube_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    return all_videos


if __name__ == "__main__":
    collect_youtube()
