#!/usr/bin/env python3
"""
V7 Pipeline Step 3: Classify Videos with 3R Framework

Uses OpenAI GPT-4 to classify each video on:
- R1: Reproducible (can a business make this?)
- R2: Relatable (will their audience care?)
- R3: Repeatable (can they do this weekly?)

Usage:
    python3 pipeline/v7/3_classify_3r.py
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
INPUT_FILE = PROJECT_ROOT / "data" / "v7" / "raw_videos.jsonl"
OUTPUT_FILE = PROJECT_ROOT / "data" / "v7" / "3r_classification.json"

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Classification prompt
CLASSIFICATION_PROMPT = """You are analyzing TikTok fitness videos to help businesses identify content ideas they can pitch to clients.

Analyze this video and classify it on three dimensions. Each score is 1-5 (1=poor fit, 5=excellent fit).

## Video Information
- Title/Description: {title}
- Hashtags: {hashtags}
- Duration: {duration} seconds ({bucket} format)
- Views: {views:,}
- Transcript: {transcript}

## Classification Dimensions

### R1: REPRODUCIBLE (Can a typical fitness business make this?)
Consider:
- Production complexity (equipment, editing, effects needed)
- Does it require special access (celebrities, exotic locations, expensive gear)?
- Is the format template-able (can be replicated with different content)?
- Could a small gym/trainer/fitness brand do this with basic equipment?

### R2: RELATABLE (Will a fitness business's audience care about this topic?)
Consider:
- What core problem or topic does this address?
- Is the appeal personality-driven (needs the specific creator) or topic-driven (anyone could present)?
- Which industries/businesses could use this? (gyms, trainers, supplement brands, activewear, etc.)
- Does it address universal fitness concerns?

### R3: REPEATABLE (Can they make this into a regular series?)
Consider:
- Does the creator likely have multiple similar videos?
- Is this format commonly used by other creators?
- Is it trend-dependent (specific sound, challenge, meme)?
- Could you make 10+ variations of this content?

## Output Format
Respond with ONLY valid JSON (no markdown code blocks):
{{
  "reproducible": {{
    "score": <1-5>,
    "production_complexity": "<LOW|MEDIUM|HIGH>",
    "requires_special_access": <true|false>,
    "format_type": "<tutorial|listicle|montage|motivation|transformation|review|challenge|demo|other>",
    "reason": "<1 sentence explanation>"
  }},
  "relatable": {{
    "score": <1-5>,
    "core_topic": "<the main topic/problem addressed>",
    "appeal_type": "<PERSONALITY_DRIVEN|TOPIC_DRIVEN>",
    "target_industries": ["<industry1>", "<industry2>"],
    "reason": "<1 sentence explanation>"
  }},
  "repeatable": {{
    "score": <1-5>,
    "format_is_common": <true|false>,
    "trend_dependent": <true|false>,
    "series_potential": "<1 sentence about series possibilities>",
    "reason": "<1 sentence explanation>"
  }}
}}"""


def classify_video(video: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Send video to GPT-4 for 3R classification.
    """
    # Build transcript string
    transcript = video.get("subtitle", {}).get("transcript")
    if not transcript:
        transcript = "(No transcript available - using title/hashtags only)"

    # Format prompt
    prompt = CLASSIFICATION_PROMPT.format(
        title=video.get("title", ""),
        hashtags=", ".join(video.get("hashtags", [])),
        duration=video.get("duration_seconds", 0),
        bucket=video.get("bucket", "unknown"),
        views=video.get("engagement", {}).get("views", 0),
        transcript=transcript,
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using mini for cost efficiency
            messages=[
                {"role": "system", "content": "You are a content strategy analyst helping businesses find reproducible content ideas."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Low temperature for consistency
            max_tokens=500,
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON response
        # Handle potential markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        return json.loads(content)

    except json.JSONDecodeError as e:
        print(f"    JSON parse error: {e}")
        print(f"    Response was: {content[:200]}...")
        return None
    except Exception as e:
        print(f"    API error: {e}")
        return None


def main():
    print("=" * 60)
    print("V7 Pipeline: 3R Classification")
    print("=" * 60)

    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not found in .env.local")
        return

    # Load input data
    if not INPUT_FILE.exists():
        print(f"ERROR: Input file not found: {INPUT_FILE}")
        print("Run 2_fetch_subtitles.py first!")
        return

    # Load JSONL file
    videos = []
    with open(INPUT_FILE, 'r') as f:
        for line in f:
            if line.strip():
                videos.append(json.loads(line))
    print(f"\nLoaded {len(videos)} videos\n")

    # Process each video
    results = {
        "metadata": {
            "total_videos": len(videos),
            "classified": 0,
            "errors": 0,
            "avg_scores": {
                "reproducible": 0,
                "relatable": 0,
                "repeatable": 0,
            },
            "by_bucket": {
                "short": {"count": 0, "avg_r1": 0, "avg_r2": 0, "avg_r3": 0},
                "super_short": {"count": 0, "avg_r1": 0, "avg_r2": 0, "avg_r3": 0},
            }
        },
        "videos": []
    }

    # Track scores for averaging
    total_scores = {"reproducible": 0, "relatable": 0, "repeatable": 0}
    bucket_scores = {
        "short": {"r1": 0, "r2": 0, "r3": 0, "count": 0},
        "super_short": {"r1": 0, "r2": 0, "r3": 0, "count": 0},
    }

    for i, video in enumerate(videos):
        video_id = video.get("video_id", "unknown")
        bucket = video.get("bucket", "unknown")

        print(f"[{i+1}/{len(videos)}] Classifying {video_id}...")

        classification = classify_video(video)

        if classification:
            # Build enriched video object
            enriched = {
                **video,
                "classification_3r": classification,
            }
            results["videos"].append(enriched)
            results["metadata"]["classified"] += 1

            # Track scores
            r1 = classification.get("reproducible", {}).get("score", 0)
            r2 = classification.get("relatable", {}).get("score", 0)
            r3 = classification.get("repeatable", {}).get("score", 0)

            total_scores["reproducible"] += r1
            total_scores["relatable"] += r2
            total_scores["repeatable"] += r3

            if bucket in bucket_scores:
                bucket_scores[bucket]["r1"] += r1
                bucket_scores[bucket]["r2"] += r2
                bucket_scores[bucket]["r3"] += r3
                bucket_scores[bucket]["count"] += 1

            print(f"    R1={r1} R2={r2} R3={r3}")
        else:
            results["metadata"]["errors"] += 1
            # Still include video but without classification
            enriched = {
                **video,
                "classification_3r": None,
            }
            results["videos"].append(enriched)

        # Rate limiting
        time.sleep(0.5)

    # Calculate averages
    n = results["metadata"]["classified"]
    if n > 0:
        results["metadata"]["avg_scores"]["reproducible"] = round(total_scores["reproducible"] / n, 2)
        results["metadata"]["avg_scores"]["relatable"] = round(total_scores["relatable"] / n, 2)
        results["metadata"]["avg_scores"]["repeatable"] = round(total_scores["repeatable"] / n, 2)

    for bucket, scores in bucket_scores.items():
        if scores["count"] > 0:
            results["metadata"]["by_bucket"][bucket]["count"] = scores["count"]
            results["metadata"]["by_bucket"][bucket]["avg_r1"] = round(scores["r1"] / scores["count"], 2)
            results["metadata"]["by_bucket"][bucket]["avg_r2"] = round(scores["r2"] / scores["count"], 2)
            results["metadata"]["by_bucket"][bucket]["avg_r3"] = round(scores["r3"] / scores["count"], 2)

    # Save results
    print(f"\nSaving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(results, f, indent=2)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total videos:    {results['metadata']['total_videos']}")
    print(f"Classified:      {results['metadata']['classified']}")
    print(f"Errors:          {results['metadata']['errors']}")
    print(f"\nAverage Scores:")
    print(f"  Reproducible: {results['metadata']['avg_scores']['reproducible']}/5")
    print(f"  Relatable:    {results['metadata']['avg_scores']['relatable']}/5")
    print(f"  Repeatable:   {results['metadata']['avg_scores']['repeatable']}/5")
    print(f"\nBy Bucket:")
    for bucket, stats in results["metadata"]["by_bucket"].items():
        print(f"  {bucket}: {stats['count']} videos (R1={stats['avg_r1']}, R2={stats['avg_r2']}, R3={stats['avg_r3']})")
    print(f"\nOutput saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
