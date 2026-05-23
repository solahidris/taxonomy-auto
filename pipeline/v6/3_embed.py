#!/usr/bin/env python3
"""V6 Step 3: Generate embeddings for the combined V6 dataset.

Uses OpenAI text-embedding-3-small (same model as V1-V5 for consistency).
"""

import json, os, sys
import numpy as np
from pathlib import Path
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "v6"
IN = DATA_DIR / "raw_videos.jsonl"
OUT_EMB = DATA_DIR / "embeddings.npy"
OUT_META = DATA_DIR / "metadata.json"
MODEL = "text-embedding-3-small"
BATCH_SIZE = 100


def make_text(video: dict) -> str:
    title = video.get("title", "") or ""
    description = video.get("description", "") or ""
    hashtags = video.get("hashtags", []) or []
    tags_str = " ".join(f"#{h}" for h in hashtags[:15])
    return f"{title}. {description[:300]}. {tags_str}".strip()


def main():
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    print("Loading V6 combined videos...")
    videos = []
    with open(IN) as f:
        for line in f:
            line = line.strip()
            if line:
                videos.append(json.loads(line))
    print(f"Loaded {len(videos)} videos")

    texts = [make_text(v) for v in videos]

    print(f"\nEmbedding with {MODEL}...")
    all_embeddings = []
    for i in tqdm(range(0, len(texts), BATCH_SIZE)):
        batch = texts[i:i + BATCH_SIZE]
        try:
            resp = client.embeddings.create(model=MODEL, input=batch)
            all_embeddings.extend([e.embedding for e in resp.data])
        except Exception as e:
            print(f"\nError at batch {i}: {e}")
            all_embeddings.extend([[0.0] * 1536] * len(batch))

    embeddings = np.array(all_embeddings, dtype=np.float32)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.save(OUT_EMB, embeddings)
    print(f"\nSaved embeddings: {embeddings.shape} → {OUT_EMB}")

    metadata = []
    for i, v in enumerate(videos):
        metadata.append({
            "idx": i,
            "id": v.get("id", ""),
            "platform": v.get("platform", "youtube"),
            "title": (v.get("title", "") or "")[:120],
            "hashtags": (v.get("hashtags", []) or [])[:10],
            "author": v.get("author", ""),
            "author_id": v.get("author_id", ""),
            "source": v.get("source", "unknown"),
        })

    with open(OUT_META, "w") as f:
        json.dump(metadata, f)
    print(f"Saved metadata → {OUT_META}")

    total_tokens = sum(len(t.split()) * 1.3 for t in texts)
    cost = (total_tokens / 1_000_000) * 0.02
    print(f"Estimated embedding cost: ${cost:.4f}")

    platform_counts: dict = {}
    for v in videos:
        p = v.get("platform", "unknown")
        platform_counts[p] = platform_counts.get(p, 0) + 1
    for p, c in sorted(platform_counts.items()):
        print(f"  {p}: {c}")


if __name__ == "__main__":
    main()
