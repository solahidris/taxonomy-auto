#!/usr/bin/env python3
"""
V7 Pipeline Step 2: Fetch Subtitles from TikTok Videos

Reads fitness_short_all.jsonl and fitness_super_short_all.jsonl, extracts subtitle URLs,
fetches WebVTT content, and outputs enriched video data with transcripts.

For videos missing subtitle info, uses Apify to re-scrape them.

Usage:
    python3 pipeline/v7/2_fetch_subtitles.py [--apify] [--limit N]

    --apify   Use Apify to fetch missing subtitles (costs ~$5-10 for 10K videos)
    --limit N Only process first N videos (for testing)
"""

from __future__ import annotations
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import requests
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
SAMPLE_DATA = PROJECT_ROOT / "sample_data"
OUTPUT_DIR = PROJECT_ROOT / "data" / "v7"

INPUT_FILES = [
    SAMPLE_DATA / "fitness_short_all.jsonl",
    SAMPLE_DATA / "fitness_super_short_all.jsonl",
]

OUTPUT_FILE = OUTPUT_DIR / "videos_with_subtitles.jsonl"
PROGRESS_FILE = OUTPUT_DIR / "subtitle_progress.json"


def parse_webvtt(content: str) -> str:
    """
    Parse WebVTT content and extract plain text transcript.
    Removes timestamps, cue identifiers, and formatting.
    """
    lines = content.strip().split('\n')
    transcript_lines = []

    for line in lines:
        line = line.strip()

        # Skip header
        if line.startswith('WEBVTT'):
            continue

        # Skip empty lines
        if not line:
            continue

        # Skip timestamp lines (00:00:00.000 --> 00:00:00.000)
        if '-->' in line:
            continue

        # Skip cue identifiers (numeric or alphanumeric IDs)
        if re.match(r'^[\d\w-]+$', line) and len(line) < 20:
            continue

        # Skip NOTE and STYLE blocks
        if line.startswith('NOTE') or line.startswith('STYLE'):
            continue

        # Remove HTML-like tags
        line = re.sub(r'<[^>]+>', '', line)

        # Add to transcript if we have content
        if line:
            transcript_lines.append(line)

    return ' '.join(transcript_lines)


def fetch_subtitle(url: str, timeout: int = 10) -> Optional[str]:
    """
    Fetch WebVTT content from URL and return parsed transcript.
    """
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return parse_webvtt(response.text)
    except requests.RequestException as e:
        print(f"    Failed to fetch subtitle: {e}")
        return None


def get_best_subtitle_url(subtitle_info: list) -> Tuple[Optional[str], str]:
    """
    Select the best subtitle URL from available options.
    Priority:
    1. English (eng-US) original caption
    2. Any English caption
    3. Any original caption
    4. First available

    Returns (url, language)
    """
    if not subtitle_info:
        return None, ""

    # Filter for webvtt format
    webvtt_subs = [s for s in subtitle_info if s.get('caption_format') == 'webvtt']
    if not webvtt_subs:
        webvtt_subs = subtitle_info

    # Priority 1: English original
    for sub in webvtt_subs:
        if sub.get('language_code') == 'en' and sub.get('is_original_caption'):
            return sub.get('url'), sub.get('lang', 'en')

    # Priority 2: Any English
    for sub in webvtt_subs:
        if sub.get('language_code') == 'en':
            return sub.get('url'), sub.get('lang', 'en')

    # Priority 3: Any original
    for sub in webvtt_subs:
        if sub.get('is_original_caption'):
            return sub.get('url'), sub.get('lang', 'unknown')

    # Priority 4: First available
    if webvtt_subs:
        return webvtt_subs[0].get('url'), webvtt_subs[0].get('lang', 'unknown')

    return None, ""


def load_progress() -> dict:
    """Load progress from previous runs for resume capability."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"completed_ids": [], "failed_ids": []}


def save_progress(progress: dict):
    """Save progress for resume capability."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f)


def load_videos() -> list[dict]:
    """Load all videos from input JSONL files."""
    videos = []

    for input_file in INPUT_FILES:
        if not input_file.exists():
            print(f"Warning: {input_file} not found, skipping...")
            continue

        print(f"Loading {input_file.name}...")
        with open(input_file, 'r') as f:
            for line in f:
                if line.strip():
                    videos.append(json.loads(line))

    return videos


def fetch_subtitles_via_apify(video_urls: list[str]) -> dict:
    """
    Fetch subtitles for videos that don't have subtitle info using Apify.
    Returns dict mapping video_id to subtitle info.
    """
    APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
    if not APIFY_TOKEN:
        print("WARNING: APIFY_API_TOKEN not found, cannot fetch missing subtitles")
        return {}

    try:
        from apify_client import ApifyClient
    except ImportError:
        print("Installing apify-client...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "apify-client", "-q"])
        from apify_client import ApifyClient

    client = ApifyClient(APIFY_TOKEN)

    run_input = {
        "postURLs": video_urls,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": True,
        "shouldDownloadSlideshowImages": False,
    }

    try:
        print(f"    Running Apify for {len(video_urls)} videos...")
        run = client.actor("clockworks/tiktok-scraper").call(run_input=run_input)

        results = {}
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            video_id = item.get("id") or item.get("videoId")
            if video_id:
                results[video_id] = item.get("subtitleInformation")

        return results
    except Exception as e:
        print(f"    Apify error: {e}")
        return {}


def process_videos(videos: list[dict], use_apify: bool = False) -> Tuple[list, dict]:
    """
    Process all videos, fetching subtitles where available.
    Returns (list of enriched videos, metadata dict).
    """
    # Load progress for resume
    progress = load_progress()
    completed_ids = set(progress["completed_ids"])

    metadata = {
        "total_videos": len(videos),
        "with_subtitles": 0,
        "without_subtitles": 0,
        "fetch_errors": 0,
        "apify_fetched": 0,
        "by_bucket": {"short": 0, "super_short": 0},
        "by_bucket_with_subs": {"short": 0, "super_short": 0}
    }

    # Load existing results if resuming
    enriched_videos = []
    if OUTPUT_FILE.exists():
        print("Loading existing results for resume...")
        with open(OUTPUT_FILE) as f:
            for line in f:
                if line.strip():
                    v = json.loads(line)
                    enriched_videos.append(v)
                    # Update metadata
                    if v.get("subtitle", {}).get("transcript"):
                        metadata["with_subtitles"] += 1
                    else:
                        metadata["without_subtitles"] += 1
        print(f"  Loaded {len(enriched_videos)} existing results")

    # Filter to videos not yet processed
    videos_to_process = [v for v in videos if v["video_id"] not in completed_ids]
    print(f"Videos to process: {len(videos_to_process)} (skipping {len(completed_ids)} already done)")

    if not videos_to_process:
        print("All videos already processed!")
        return enriched_videos, metadata

    # Separate videos with/without existing subtitle info
    videos_with_subs = []
    videos_without_subs = []

    for video in videos_to_process:
        subtitle_info = video.get('raw_apify', {}).get('subtitleInformation')
        if subtitle_info:
            videos_with_subs.append(video)
        else:
            videos_without_subs.append(video)

    print(f"  With existing subtitle info: {len(videos_with_subs)}")
    print(f"  Missing subtitle info: {len(videos_without_subs)}")

    # If using Apify, batch-fetch missing subtitles
    apify_results = {}
    if use_apify and videos_without_subs:
        print(f"\nFetching {len(videos_without_subs)} missing subtitles via Apify...")
        BATCH_SIZE = 50

        for i in range(0, len(videos_without_subs), BATCH_SIZE):
            batch = videos_without_subs[i:i + BATCH_SIZE]
            urls = [v["url"] for v in batch]
            print(f"  Batch {i // BATCH_SIZE + 1}/{(len(videos_without_subs) + BATCH_SIZE - 1) // BATCH_SIZE}...")
            batch_results = fetch_subtitles_via_apify(urls)
            apify_results.update(batch_results)
            metadata["apify_fetched"] += len(batch_results)
            time.sleep(2)  # Rate limit between batches

    # Process all videos
    all_to_process = videos_with_subs + videos_without_subs
    print(f"\nFetching WebVTT transcripts for {len(all_to_process)} videos...")

    for i, video in enumerate(all_to_process):
        video_id = video.get('video_id', 'unknown')
        bucket = video.get('bucket', 'unknown')

        if (i + 1) % 100 == 0:
            print(f"  Progress: {i + 1}/{len(all_to_process)}")

        # Count by bucket
        if bucket in metadata["by_bucket"]:
            metadata["by_bucket"][bucket] += 1

        # Get subtitle info (from original data or Apify results)
        subtitle_info = video.get('raw_apify', {}).get('subtitleInformation')
        if not subtitle_info and video_id in apify_results:
            subtitle_info = apify_results[video_id]

        subtitle_url, subtitle_lang = get_best_subtitle_url(subtitle_info)

        # Build enriched video object
        enriched = {
            "video_id": video_id,
            "url": video.get('url'),
            "bucket": bucket,
            "duration_seconds": video.get('video', {}).get('duration_seconds'),
            "title": video.get('text', {}).get('description', ''),
            "hashtags": video.get('text', {}).get('hashtags', []),
            "author": video.get('author', {}).get('handle', ''),
            "engagement": {
                "views": video.get('engagement', {}).get('play_count', 0),
                "likes": video.get('engagement', {}).get('like_count', 0),
                "comments": video.get('engagement', {}).get('comment_count', 0),
                "shares": video.get('engagement', {}).get('share_count', 0),
            },
            "subtitle": {
                "available": subtitle_url is not None,
                "language": subtitle_lang,
                "transcript": None,
            }
        }

        # Fetch subtitle if available
        if subtitle_url:
            transcript = fetch_subtitle(subtitle_url)

            if transcript:
                enriched["subtitle"]["transcript"] = transcript
                metadata["with_subtitles"] += 1
                if bucket in metadata["by_bucket_with_subs"]:
                    metadata["by_bucket_with_subs"][bucket] += 1
            else:
                metadata["fetch_errors"] += 1
                metadata["without_subtitles"] += 1
        else:
            metadata["without_subtitles"] += 1

        enriched_videos.append(enriched)
        completed_ids.add(video_id)

        # Save progress every 100 videos
        if (i + 1) % 100 == 0:
            progress["completed_ids"] = list(completed_ids)
            save_progress(progress)
            # Also save results incrementally
            with open(OUTPUT_FILE, "w") as f:
                for v in enriched_videos:
                    f.write(json.dumps(v) + "\n")

        # Small delay to be nice to TikTok CDN
        if subtitle_url:
            time.sleep(0.1)

    # Final save
    progress["completed_ids"] = list(completed_ids)
    save_progress(progress)

    return enriched_videos, metadata


def main():
    print("=" * 60)
    print("V7 Pipeline: Fetch Subtitles")
    print("=" * 60)

    # Parse arguments
    use_apify = "--apify" in sys.argv
    limit = None
    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    if use_apify:
        print("Mode: Apify enabled (will fetch missing subtitles)")
    else:
        print("Mode: Local only (use --apify to fetch missing subtitles)")

    if limit:
        print(f"Limit: {limit} videos")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load videos
    videos = load_videos()
    print(f"\nLoaded {len(videos)} videos total")

    if limit:
        videos = videos[:limit]
        print(f"Limited to {len(videos)} videos")

    if not videos:
        print("No videos to process!")
        return

    # Process videos
    enriched_videos, metadata = process_videos(videos, use_apify=use_apify)

    # Save final results
    print(f"\nSaving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w') as f:
        for v in enriched_videos:
            f.write(json.dumps(v) + "\n")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total videos:      {metadata['total_videos']}")
    print(f"With subtitles:    {metadata['with_subtitles']} ({metadata['with_subtitles']/len(enriched_videos)*100:.1f}%)")
    print(f"Without subtitles: {metadata['without_subtitles']}")
    print(f"Fetch errors:      {metadata['fetch_errors']}")
    if use_apify:
        print(f"Apify fetched:     {metadata['apify_fetched']}")
    print(f"\nBy bucket:")
    for bucket, count in metadata['by_bucket'].items():
        subs = metadata['by_bucket_with_subs'].get(bucket, 0)
        pct = subs / count * 100 if count > 0 else 0
        print(f"  {bucket}: {count} videos ({subs} with subs, {pct:.1f}%)")
    print(f"\nOutput saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
