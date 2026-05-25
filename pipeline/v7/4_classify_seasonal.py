#!/usr/bin/env python3
"""
V7 Pipeline Step 4: Classify Videos as Seasonal vs Evergreen

Uses OpenAI GPT-4 to classify each video on seasonality.

Usage:
    python3 pipeline/v7/4_classify_seasonal.py
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = PROJECT_ROOT / "data" / "v7" / "3r_classification.json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "v7" / "3r_seasonal_classification.json"

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Classification prompt
CLASSIFICATION_PROMPT = """Classify this TikTok video's seasonality for content planning purposes.

## Video Information
- Title/Description: {title}
- Hashtags: {hashtags}
- Core Topic: {core_topic}
- Format: {format_type}

## Classification Categories

**EVERGREEN** - Content that works year-round
- General fitness tips, workout routines
- Motivational content, transformation stories
- Exercise tutorials, form guides
- No time-specific references

**SEASONAL** - Content tied to specific times
- Holiday workouts (Christmas, New Year, Halloween)
- Summer body, beach season prep
- Back-to-school fitness
- Specific month/season references

**TREND** - Content tied to viral moments
- Specific TikTok sounds/challenges
- Celebrity references, current events
- Meme formats that will date quickly

## Output Format
Respond with ONLY valid JSON (no markdown):
{{
  "seasonal_type": "<EVERGREEN|SEASONAL|TREND>",
  "confidence": <0.0-1.0>,
  "reason": "<1 sentence explanation>",
  "time_relevance": "<always|specific_season|short_window>"
}}"""


def classify_video(video: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Send video to GPT-4 for seasonal classification.
    """
    classification_3r = video.get("classification_3r", {})

    prompt = CLASSIFICATION_PROMPT.format(
        title=video.get("title", "")[:500],
        hashtags=", ".join(video.get("hashtags", [])[:15]),
        core_topic=classification_3r.get("relatable", {}).get("core_topic", "unknown"),
        format_type=classification_3r.get("reproducible", {}).get("format_type", "unknown"),
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a content strategist analyzing video seasonality for business planning."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=200,
        )

        content = response.choices[0].message.content.strip()

        # Handle potential markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        return json.loads(content)

    except json.JSONDecodeError as e:
        print(f"    JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"    API error: {e}")
        return None


def main():
    print("=" * 60)
    print("V7 Pipeline: Seasonal Classification")
    print("=" * 60)

    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not found in .env.local")
        return

    # Load input data
    if not INPUT_FILE.exists():
        print(f"ERROR: Input file not found: {INPUT_FILE}")
        print("Run 3_classify_3r.py first!")
        return

    with open(INPUT_FILE, 'r') as f:
        data = json.load(f)

    videos = data.get("videos", [])
    print(f"\nLoaded {len(videos)} videos\n")

    # Track stats
    stats = {
        "total": len(videos),
        "classified": 0,
        "errors": 0,
        "by_type": {"EVERGREEN": 0, "SEASONAL": 0, "TREND": 0}
    }

    # Process each video
    enriched_videos = []

    for i, video in enumerate(videos):
        video_id = video.get("video_id", "unknown")

        print(f"[{i+1}/{len(videos)}] Classifying {video_id}...")

        seasonal = classify_video(video)

        if seasonal:
            video["seasonal"] = seasonal
            stats["classified"] += 1
            seasonal_type = seasonal.get("seasonal_type", "UNKNOWN")
            if seasonal_type in stats["by_type"]:
                stats["by_type"][seasonal_type] += 1
            print(f"    {seasonal_type} ({seasonal.get('confidence', 0):.0%})")
        else:
            video["seasonal"] = None
            stats["errors"] += 1

        enriched_videos.append(video)

        # Rate limiting
        time.sleep(0.3)

    # Update metadata
    data["videos"] = enriched_videos
    data["metadata"]["seasonal_stats"] = stats

    # Save results
    print(f"\nSaving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total videos:    {stats['total']}")
    print(f"Classified:      {stats['classified']}")
    print(f"Errors:          {stats['errors']}")
    print(f"\nBy Type:")
    for t, count in stats["by_type"].items():
        pct = (count / stats["classified"] * 100) if stats["classified"] > 0 else 0
        print(f"  {t}: {count} ({pct:.1f}%)")
    print(f"\nOutput saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
