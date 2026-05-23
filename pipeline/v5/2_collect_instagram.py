#!/usr/bin/env python3
"""
V5 Step 1b: Collect Instagram Reels using Apify
Budget: ~$1 (~5 CU)
Target: 2,000-3,000 Reels

Uses apify/instagram-reel-scraper which takes profile usernames
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
MAX_REELS_PER_PROFILE = 30  # Get recent reels from each creator
MAX_TOTAL_VIDEOS = 2000

# Popular creators by niche (public profiles with Reels content)
# These are well-known fitness/food/beauty creators on Instagram
CREATOR_PROFILES = [
    # Fitness creators
    "chloeting", "pamaborka", "bloaborka", "kaikifit",
    "whitneyysimmons", "brittanylpilates", "madfit.ig",
    "alexisren", "tammi.dc", "karinapombo",
    # Calisthenics/Strength
    "chrisbarnett", "tikibarber", "chrisheria", "austindunham",
    "simonsterstrength", "daniellaham",
    # Running/Cardio
    "kipaborka", "runwithryan", "therunningcouple",
    # Yoga
    "adrienelouise", "jessicaolie", "yoga_girl",
    # Food/Cooking creators
    "halfbakedharvest", "minimalistbaker", "feelgoodfoodie",
    "budgetbytes", "pinchofyum", "themediterraneandish",
    "skinnytaste", "damndelicious", "ambitiouskitchen",
    # Meal prep
    "workweeklunch", "mealpreponfleek", "themealprepmanual",
    # Beauty/Skincare
    "nikkietutorials", "patrickta", "hudabeauty",
    "jamescharles", "jackieaina", "mannymua733",
    "skincarebyhyram", "doctorly", "labmuffinbeautyscience",
    # Lifestyle/Morning routines
    "matildadjerf", "emmachamberlain", "tinx",
]

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "v5"
OUTPUT_FILE = DATA_DIR / "instagram_raw.jsonl"


def collect_instagram():
    """Collect Instagram Reels via Apify using instagram-reel-scraper."""
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

    print(f"Collecting Instagram Reels from {len(CREATOR_PROFILES)} creator profiles...")
    print(f"Budget: ~$3 (max {MAX_TOTAL_VIDEOS} Reels)")
    print()

    for i, username in enumerate(CREATOR_PROFILES):
        if len(all_videos) >= MAX_TOTAL_VIDEOS:
            print(f"\nReached max videos ({MAX_TOTAL_VIDEOS}), stopping.")
            break

        print(f"[{i+1}/{len(CREATOR_PROFILES)}] Scraping @{username}...")

        try:
            # Use apify/instagram-reel-scraper with username (must be array)
            run_input = {
                "username": [username],
                "resultsLimit": MAX_REELS_PER_PROFILE,
            }

            run = client.actor("apify/instagram-reel-scraper").call(run_input=run_input)

            # Get results from dataset
            dataset_items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

            new_count = 0
            for item in dataset_items:
                video_id = item.get("id") or item.get("shortCode") or item.get("code")
                if video_id and video_id not in seen_ids:
                    seen_ids.add(video_id)

                    # Extract hashtags from caption
                    caption = item.get("caption", "") or item.get("text", "") or ""
                    hashtags = [
                        word[1:].lower()
                        for word in caption.split()
                        if word.startswith("#") and len(word) > 1
                    ]

                    # Normalize to our format
                    video = {
                        "id": video_id,
                        "platform": "instagram",
                        "title": caption[:200] if caption else "",
                        "description": caption,
                        "hashtags": hashtags,
                        "author": item.get("ownerUsername", "") or username,
                        "author_id": item.get("ownerId", ""),
                        "stats": {
                            "views": item.get("videoPlayCount", 0) or item.get("playCount", 0),
                            "likes": item.get("likesCount", 0) or item.get("likeCount", 0),
                            "comments": item.get("commentsCount", 0) or item.get("commentCount", 0),
                        },
                        "seed_keyword": username,  # Track which creator
                        "collected_at": item.get("timestamp", "") or item.get("takenAt", ""),
                    }
                    all_videos.append(video)
                    new_count += 1

            print(f"  +{new_count} Reels (total: {len(all_videos)})")

        except Exception as e:
            print(f"  Error: {e}")
            continue

    # Save results
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        for video in all_videos:
            f.write(json.dumps(video) + "\n")

    print(f"\nDone! Saved {len(all_videos)} Instagram Reels to {OUTPUT_FILE}")

    # Save stats
    stats = {
        "platform": "instagram",
        "total_videos": len(all_videos),
        "unique_hashtags": len(set(h for v in all_videos for h in v.get("hashtags", []))),
        "unique_authors": len(set(v.get("author") for v in all_videos if v.get("author"))),
        "profiles_scraped": len(CREATOR_PROFILES),
    }
    with open(DATA_DIR / "instagram_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    return all_videos


if __name__ == "__main__":
    collect_instagram()
