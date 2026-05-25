#!/usr/bin/env python3
"""V7 Pipeline Step 5: Embed video texts using text-embedding-3-small.

Creates embeddings from title + hashtags + transcript for clustering.
Cost estimate: ~240 videos × 300 tokens = 72K tokens × $0.02/1M ≈ $0.001
"""

import json
import numpy as np
from pathlib import Path
from openai import OpenAI
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

client = OpenAI()
PROJECT_ROOT = Path(__file__).parent.parent.parent
IN = PROJECT_ROOT / "data/v7/3r_seasonal_classification.json"
OUT_EMB = PROJECT_ROOT / "data/v7/embeddings.npy"
OUT_META = PROJECT_ROOT / "data/v7/metadata.json"
MODEL = "text-embedding-3-small"
BATCH = 100


def make_text(v: dict) -> str:
    """Combine video metadata into a single text for embedding."""
    hashtags = " ".join(f"#{t}" for t in v.get("hashtags", [])[:15])
    title = v.get("title", "")[:200]

    # Include transcript if available
    transcript = ""
    if v.get("subtitle") and v["subtitle"].get("transcript"):
        transcript = v["subtitle"]["transcript"][:500]

    # Include 3R classification info
    classification = v.get("classification_3r", {})
    core_topic = classification.get("relatable", {}).get("core_topic", "")
    format_type = classification.get("reproducible", {}).get("format_type", "")

    text = f"{title}. {transcript}. {hashtags}"
    if core_topic:
        text += f" Topic: {core_topic}."
    if format_type:
        text += f" Format: {format_type}."

    return text.strip()


def main():
    print("=" * 60)
    print("V7 Pipeline: Embedding Videos")
    print("=" * 60)

    # Load data
    data = json.loads(IN.read_text())
    videos = data.get("videos", [])
    print(f"Loaded {len(videos)} videos")

    texts = [make_text(v) for v in videos]
    embeddings: list[list[float]] = []

    print(f"\nEmbedding {len(texts)} videos in batches of {BATCH}...")
    for i in tqdm(range(0, len(texts), BATCH), desc="Embedding"):
        batch = texts[i : i + BATCH]
        resp = client.embeddings.create(model=MODEL, input=batch)
        batch_vecs = [e.embedding for e in sorted(resp.data, key=lambda x: x.index)]
        embeddings.extend(batch_vecs)

    arr = np.array(embeddings, dtype=np.float32)
    np.save(OUT_EMB, arr)

    # Save metadata for clustering
    metadata = []
    for v in videos:
        classification = v.get("classification_3r", {})
        seasonal = v.get("seasonal", {})

        metadata.append({
            "video_id": v.get("video_id"),
            "title": v.get("title", ""),
            "author": v.get("author", ""),
            "hashtags": v.get("hashtags", []),
            "views": v.get("engagement", {}).get("views", 0),
            "follower_count": v.get("follower_count", 0),
            "is_outlier": v.get("is_outlier", False),
            "view_multiplier": v.get("view_multiplier", 1.0),
            "r1_score": classification.get("reproducible", {}).get("score", 0),
            "r2_score": classification.get("relatable", {}).get("score", 0),
            "r3_score": classification.get("repeatable", {}).get("score", 0),
            "core_topic": classification.get("relatable", {}).get("core_topic", ""),
            "format_type": classification.get("reproducible", {}).get("format_type", ""),
            "seasonal_type": seasonal.get("seasonal_type", "UNKNOWN") if seasonal else "UNKNOWN",
            "transcript_preview": v.get("subtitle", {}).get("transcript", "")[:150] if v.get("subtitle") else "",
        })

    OUT_META.write_text(json.dumps(metadata, indent=2))

    token_estimate = sum(len(t.split()) * 1.3 for t in texts)
    cost = token_estimate / 1_000_000 * 0.02

    print(f"\n{'=' * 60}")
    print("RESULTS")
    print("=" * 60)
    print(f"Saved {arr.shape} embeddings → {OUT_EMB}")
    print(f"Saved metadata → {OUT_META}")
    print(f"Estimated cost: ~${cost:.4f}")


if __name__ == "__main__":
    main()
