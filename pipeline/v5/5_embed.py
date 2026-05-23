#!/usr/bin/env python3
"""
V5 Step 3: Generate embeddings for merged cross-platform data
Uses OpenAI text-embedding-3-small (same as V1-V4)
"""

import json
import os
import sys
from pathlib import Path
import numpy as np
from tqdm import tqdm
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY not found in .env.local")
    sys.exit(1)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "v5"
INPUT_FILE = DATA_DIR / "merged_videos.jsonl"
OUTPUT_EMBEDDINGS = DATA_DIR / "embeddings.npy"
OUTPUT_METADATA = DATA_DIR / "metadata.json"

BATCH_SIZE = 100  # OpenAI allows up to 2048, but 100 is safer
MODEL = "text-embedding-3-small"


def make_text(video):
    """Create text representation for embedding."""
    title = video.get("title", "") or ""
    description = video.get("description", "") or ""
    hashtags = video.get("hashtags", []) or []

    # Combine: title + truncated description + hashtags
    tags_str = " ".join(f"#{t}" for t in hashtags[:15])
    text = f"{title}. {description[:300]}. {tags_str}".strip()

    # Add platform context (helps distinguish platform-specific content)
    platform = video.get("platform", "")
    if platform:
        text = f"[{platform}] {text}"

    return text


def embed_videos():
    """Generate embeddings for all videos."""
    try:
        from openai import OpenAI
    except ImportError:
        print("Installing openai...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "openai", "-q"])
        from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)

    # Load merged videos
    print("Loading merged videos...")
    videos = []
    with open(INPUT_FILE) as f:
        for line in f:
            if line.strip():
                videos.append(json.loads(line))

    print(f"Loaded {len(videos)} videos")

    # Create text representations
    texts = [make_text(v) for v in videos]

    # Generate embeddings in batches
    print(f"\nGenerating embeddings with {MODEL}...")
    all_embeddings = []

    for i in tqdm(range(0, len(texts), BATCH_SIZE)):
        batch = texts[i:i + BATCH_SIZE]

        try:
            response = client.embeddings.create(
                model=MODEL,
                input=batch
            )
            batch_embeddings = [e.embedding for e in response.data]
            all_embeddings.extend(batch_embeddings)
        except Exception as e:
            print(f"\nError at batch {i}: {e}")
            # Fill with zeros for failed batch (will be filtered later)
            all_embeddings.extend([[0.0] * 1536] * len(batch))

    # Convert to numpy array
    embeddings = np.array(all_embeddings, dtype=np.float32)

    # Save embeddings
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.save(OUTPUT_EMBEDDINGS, embeddings)
    print(f"\nSaved embeddings: {embeddings.shape} -> {OUTPUT_EMBEDDINGS}")

    # Save metadata (for mapping back to videos)
    metadata = []
    for i, video in enumerate(videos):
        metadata.append({
            "idx": i,
            "id": video.get("id"),
            "platform": video.get("platform"),
            "title": video.get("title", "")[:100],
            "hashtags": video.get("hashtags", [])[:10],
            "author": video.get("author", ""),
            "source": video.get("source", "unknown"),
        })

    with open(OUTPUT_METADATA, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved metadata -> {OUTPUT_METADATA}")

    # Cost estimate
    total_tokens = sum(len(t.split()) * 1.3 for t in texts)  # Rough estimate
    cost = (total_tokens / 1_000_000) * 0.02  # $0.02 per 1M tokens
    print(f"\nEstimated embedding cost: ${cost:.4f}")

    # Stats
    platform_counts = {}
    for v in videos:
        p = v.get("platform", "unknown")
        platform_counts[p] = platform_counts.get(p, 0) + 1

    print(f"\nEmbedding stats:")
    print(f"  Total videos: {len(videos)}")
    print(f"  Embedding dims: {embeddings.shape[1]}")
    for platform, count in sorted(platform_counts.items()):
        print(f"  - {platform}: {count}")

    return embeddings, metadata


if __name__ == "__main__":
    embed_videos()
