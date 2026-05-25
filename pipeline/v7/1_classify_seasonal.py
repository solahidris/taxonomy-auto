#!/usr/bin/env python3
"""
V7 Step 1: Classify TikTok videos as Seasonal or Evergreen using LLM

This script analyzes video captions and hashtags to determine if content is:
- EVERGREEN: Relevant year-round (e.g., "how to meal prep", "morning routine")
- SEASONAL: Tied to specific time/event (e.g., "Christmas gift ideas", "summer outfit")

Cost estimate: ~$0.20 for 2K videos using GPT-4o-mini
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import time

# Load environment
load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY not found in .env.local")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
INPUT_FILE = DATA_DIR / "v5" / "tiktok_raw.jsonl"
OUTPUT_FILE = DATA_DIR / "v7" / "seasonal_classification.json"

# Filter threshold
MIN_VIEWS = 100_000  # Only analyze videos with 100K+ views


def load_videos():
    """Load TikTok videos with 100K+ views."""
    videos = []
    with open(INPUT_FILE) as f:
        for line in f:
            video = json.loads(line)
            views = video.get("stats", {}).get("views", 0)
            if views >= MIN_VIEWS:
                videos.append(video)
    return videos


def classify_batch(videos_batch: list[dict]) -> list[dict]:
    """Classify a batch of videos using GPT-4o-mini with 4 categories."""

    # Build the prompt with all videos in the batch
    video_texts = []
    for i, video in enumerate(videos_batch):
        hashtags = video.get("hashtags", [])
        if isinstance(hashtags, list) and len(hashtags) > 0:
            if isinstance(hashtags[0], dict):
                hashtag_str = " ".join([f"#{h.get('name', '')}" for h in hashtags[:10]])
            else:
                hashtag_str = " ".join([f"#{h}" for h in hashtags[:10]])
        else:
            hashtag_str = ""

        title = video.get("title", "")[:200]  # Truncate long captions
        video_texts.append(f"{i+1}. {title} {hashtag_str}")

    prompt = f"""Classify each video into one of 4 categories:

EVERGREEN = Timeless content relevant year-round (tutorials, how-tos, routines, general tips, educational content)
TREND = Based on a TikTok trend or viral challenge that may have peaked (winterarc, 75hard, 30 day challenges, viral sounds/dances, trending hashtag movements)
CALENDAR = Tied to seasons or holidays (summer body, Christmas gifts, Valentine's, back to school, New Year resolutions, holiday recipes)
MOMENT = Tied to a specific news event or moment in time (lockdown, pandemic, specific year like "2024 goals", news events, one-time occurrences)

Videos:
{chr(10).join(video_texts)}

Return a JSON object with a "classifications" array: {{"classifications": [{{"index": 1, "type": "EVERGREEN", "reason": "brief reason"}}, ...]}}

Type must be exactly one of: EVERGREEN, TREND, CALENDAR, MOMENT"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        # Try multiple keys that the LLM might use
        for key in ["classifications", "results", "videos", "data", "items"]:
            if key in result and isinstance(result[key], list):
                return result[key]

        # If it's a direct array wrapped in something else
        if isinstance(result, dict):
            for value in result.values():
                if isinstance(value, list) and len(value) > 0:
                    return value

        return []
    except Exception as e:
        print(f"  Error in batch: {e}")
        return []


def main():
    print("V7 Step 1: Seasonal/Evergreen Classification")
    print("=" * 50)

    # Load videos
    print(f"\nLoading videos with >= {MIN_VIEWS:,} views...")
    videos = load_videos()
    print(f"Found {len(videos):,} videos to classify")

    # Classify in batches
    BATCH_SIZE = 20
    results = []

    print(f"\nClassifying in batches of {BATCH_SIZE}...")

    for i in range(0, len(videos), BATCH_SIZE):
        batch = videos[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(videos) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"  Batch {batch_num}/{total_batches}...", end=" ", flush=True)

        classifications = classify_batch(batch)

        # Merge classifications with video data
        for j, video in enumerate(batch):
            classification = next(
                (c for c in classifications if c.get("index") == j + 1),
                {"type": "UNKNOWN", "reason": "Classification failed"}
            )

            results.append({
                "id": video["id"],
                "title": video.get("title", "")[:200],
                "hashtags": video.get("hashtags", [])[:10],
                "author": video.get("author", ""),
                "views": video.get("stats", {}).get("views", 0),
                "likes": video.get("stats", {}).get("likes", 0),
                "seed_keyword": video.get("seed_keyword", ""),
                "classification": classification.get("type", "UNKNOWN"),
                "reason": classification.get("reason", "")
            })

        print(f"done ({len(classifications)} classified)")

        # Small delay to avoid rate limits
        time.sleep(0.5)

    # Calculate stats for 4 categories
    evergreen_count = len([r for r in results if r["classification"] == "EVERGREEN"])
    trend_count = len([r for r in results if r["classification"] == "TREND"])
    calendar_count = len([r for r in results if r["classification"] == "CALENDAR"])
    moment_count = len([r for r in results if r["classification"] == "MOMENT"])
    unknown_count = len([r for r in results if r["classification"] not in ["EVERGREEN", "TREND", "CALENDAR", "MOMENT"]])

    total = len(results)
    output = {
        "metadata": {
            "total_videos": total,
            "min_views_threshold": MIN_VIEWS,
            "evergreen_count": evergreen_count,
            "trend_count": trend_count,
            "calendar_count": calendar_count,
            "moment_count": moment_count,
            "unknown_count": unknown_count,
            "evergreen_pct": round(evergreen_count / total * 100, 1) if total else 0,
            "trend_pct": round(trend_count / total * 100, 1) if total else 0,
            "calendar_pct": round(calendar_count / total * 100, 1) if total else 0,
            "moment_pct": round(moment_count / total * 100, 1) if total else 0,
        },
        "videos": results
    }

    # Save results
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n" + "=" * 50)
    print("Results:")
    print(f"  Evergreen: {evergreen_count:,} ({output['metadata']['evergreen_pct']}%) - Safe to make anytime")
    print(f"  Trend:     {trend_count:,} ({output['metadata']['trend_pct']}%) - Check if trend is still active")
    print(f"  Calendar:  {calendar_count:,} ({output['metadata']['calendar_pct']}%) - Plan for next season/holiday")
    print(f"  Moment:    {moment_count:,} ({output['metadata']['moment_pct']}%) - Too late, moment passed")
    print(f"  Unknown:   {unknown_count:,}")
    print(f"\nSaved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
