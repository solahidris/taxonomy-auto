#!/usr/bin/env python3
"""Step 1: Collect short-form video metadata from YouTube Data API v3.

Uses ~60 seed keywords × 50 results = ~3,000 videos.
API cost: ~6,060 units (well within 10K/day free tier).
"""

import os, json, time, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env.local")

API_KEY = os.environ["YOUTUBE_API_KEY"]
BASE = "https://www.googleapis.com/youtube/v3"
OUT = Path("data/raw_videos.jsonl")

SEED_KEYWORDS = [
    # Fitness
    "calisthenics workout", "gym motivation", "yoga morning routine", "hyrox training",
    "running tips beginner", "weight loss transformation", "bodybuilding natural",
    "crossfit workout", "pilates routine", "home workout no equipment",
    # Food & Cooking
    "easy 15 minute recipe", "what i eat in a day", "meal prep sunday",
    "vegan cooking", "sourdough bread baking", "street food tour",
    "mukbang eating show", "cooking hack viral",
    # Beauty & Fashion
    "makeup tutorial beginner", "skincare routine morning", "outfit of the day",
    "hair transformation short", "thrift flip fashion", "nail art tutorial",
    "grwm get ready with me", "fashion haul try on",
    # Gaming
    "gaming highlights moments", "minecraft build tutorial", "fps tips tricks",
    "speedrun world record", "indie game review", "retro gaming nostalgia",
    "gaming setup tour", "esports highlights",
    # Travel
    "solo travel vlog", "budget travel tips europe", "hidden gems city",
    "van life daily", "backpacking southeast asia", "travel hacks packing",
    # Comedy & Entertainment
    "funny fails compilation", "prank video gone wrong", "storytime drama",
    "day in my life aesthetic", "satisfying video oddly", "life hack actually works",
    # Education
    "learn python programming", "history explained short", "science experiment home",
    "study with me pomodoro", "language learning daily", "math trick mental",
    "productivity tips study", "book summary 5 minutes",
    # Finance
    "personal finance tips beginner", "investing index funds", "side hustle 2024",
    "passive income ideas", "frugal living saving", "stock market explained simple",
    # Lifestyle & Wellness
    "morning routine productive", "minimalism declutter", "meditation anxiety",
    "mental health tips", "journaling habit", "clean with me satisfying",
    # Pets
    "dog training tricks", "cat behavior funny", "pet transformation rescue",
    # Tech
    "tech review unboxing", "ai tools productivity", "iphone tips hidden features",
]


def fetch_videos(keyword: str, max_results: int = 50) -> list[dict]:
    search_resp = requests.get(f"{BASE}/search", params={
        "part": "id",
        "q": keyword,
        "type": "video",
        "videoDuration": "short",
        "maxResults": max_results,
        "relevanceLanguage": "en",
        "regionCode": "US",
        "key": API_KEY,
    }, timeout=10)

    data = search_resp.json()
    if "error" in data:
        print(f"  API error: {data['error']['message']}")
        return []

    ids = [item["id"]["videoId"] for item in data.get("items", [])]
    if not ids:
        return []

    detail_resp = requests.get(f"{BASE}/videos", params={
        "part": "snippet",
        "id": ",".join(ids),
        "key": API_KEY,
    }, timeout=10)

    videos = []
    for item in detail_resp.json().get("items", []):
        s = item["snippet"]
        videos.append({
            "id": item["id"],
            "seed_keyword": keyword,
            "title": s.get("title", ""),
            "description": s.get("description", "")[:400],
            "tags": s.get("tags", [])[:20],
            "channel_title": s.get("channelTitle", ""),
            "category_id": s.get("categoryId", ""),
        })
    return videos


def main():
    OUT.parent.mkdir(exist_ok=True)
    seen_ids: set[str] = set()
    total = 0

    with open(OUT, "w") as f:
        for kw in SEED_KEYWORDS:
            print(f"Collecting: '{kw}'...")
            try:
                videos = fetch_videos(kw)
                new = 0
                for v in videos:
                    if v["id"] not in seen_ids:
                        seen_ids.add(v["id"])
                        f.write(json.dumps(v) + "\n")
                        new += 1
                total += new
                print(f"  +{new} new videos (total: {total})")
                time.sleep(0.3)
            except Exception as e:
                print(f"  Error on '{kw}': {e}")
                time.sleep(2)

    print(f"\nDone. {total} unique videos saved to {OUT}")


if __name__ == "__main__":
    main()
