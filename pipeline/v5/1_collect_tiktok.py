#!/usr/bin/env python3
"""
V5 Step 1a: Collect TikTok videos using Apify
Budget: ~$1 (~5 CU)
Target: 3,000-5,000 videos
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
# TikTok scraper uses ~0.001-0.005 CU per video
# Conservative estimate: 3,000 videos for $1
MAX_RESULTS_PER_KEYWORD = 100  # Stay conservative
MAX_TOTAL_VIDEOS = 3000

# Keywords derived from V4 taxonomy categories
SEARCH_KEYWORDS = [
    # Fitness
    "calisthenics", "homeworkout", "gymtok", "fitnesstransformation",
    "hiit", "yogaflow", "strengthtraining", "runningtips",
    # Food
    "easycooking", "mealprep", "healthyrecipes", "foodtok",
    "whatieatinaday", "veganrecipes", "quickmeals",
    # Beauty
    "makeuptutorial", "skincareroutine", "grwm", "beautytok",
    "drugstoremakeup", "nailart",
    # Lifestyle
    "morningroutine", "productivity", "minimalism", "dayinmylife",
    # Additional niches
    "sourdough", "hyrox", "swimming", "marathontraining",
]

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "v5"
OUTPUT_FILE = DATA_DIR / "tiktok_raw.jsonl"


def collect_tiktok():
    """Collect TikTok videos via Apify."""
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

    print(f"Collecting TikTok videos for {len(SEARCH_KEYWORDS)} keywords...")
    print(f"Budget: ~$1 (max {MAX_TOTAL_VIDEOS} videos)")
    print()

    for i, keyword in enumerate(SEARCH_KEYWORDS):
        if len(all_videos) >= MAX_TOTAL_VIDEOS:
            print(f"\nReached max videos ({MAX_TOTAL_VIDEOS}), stopping.")
            break

        print(f"[{i+1}/{len(SEARCH_KEYWORDS)}] Searching: #{keyword}...")

        try:
            # Use clockworks/tiktok-scraper (popular, reliable)
            run_input = {
                "hashtags": [keyword],
                "resultsPerPage": min(MAX_RESULTS_PER_KEYWORD, MAX_TOTAL_VIDEOS - len(all_videos)),
                "shouldDownloadVideos": False,
                "shouldDownloadCovers": False,
            }

            run = client.actor("clockworks/tiktok-scraper").call(run_input=run_input)

            # Get results from dataset
            dataset_items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

            new_count = 0
            for item in dataset_items:
                video_id = item.get("id") or item.get("videoId")
                if video_id and video_id not in seen_ids:
                    seen_ids.add(video_id)

                    # Extract hashtags (TikTok returns them as dicts)
                    raw_hashtags = item.get("hashtags", []) or []
                    hashtags = []
                    for h in raw_hashtags:
                        if isinstance(h, dict):
                            hashtags.append(h.get("name", "").lower())
                        elif isinstance(h, str):
                            hashtags.append(h.lower())

                    # Normalize to our format
                    video = {
                        "id": video_id,
                        "platform": "tiktok",
                        "title": item.get("text", ""),  # TikTok caption
                        "description": item.get("text", ""),
                        "hashtags": hashtags,
                        "author": item.get("authorMeta", {}).get("name", ""),
                        "author_id": item.get("authorMeta", {}).get("id", ""),
                        "stats": {
                            "views": item.get("playCount", 0),
                            "likes": item.get("diggCount", 0),
                            "comments": item.get("commentCount", 0),
                            "shares": item.get("shareCount", 0),
                        },
                        "seed_keyword": keyword,
                        "collected_at": item.get("createTimeISO", ""),
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

    print(f"\nDone! Saved {len(all_videos)} TikTok videos to {OUTPUT_FILE}")

    # Save stats
    stats = {
        "platform": "tiktok",
        "total_videos": len(all_videos),
        "unique_hashtags": len(set(h for v in all_videos for h in v.get("hashtags", []))),
        "unique_authors": len(set(v.get("author_id") for v in all_videos if v.get("author_id"))),
        "keywords_searched": len(SEARCH_KEYWORDS),
    }
    with open(DATA_DIR / "tiktok_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    return all_videos


if __name__ == "__main__":
    collect_tiktok()
