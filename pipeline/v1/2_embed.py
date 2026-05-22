#!/usr/bin/env python3
"""V1 Step 2: Embed video texts using text-embedding-3-small.

Same as V0 but reads/writes to v1 directory.
Cost estimate: ~20K videos × 200 tokens = 4M tokens × $0.02/1M ≈ $0.08
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
IN = PROJECT_ROOT / "data/v1/raw_videos.jsonl"
OUT_EMB = PROJECT_ROOT / "data/v1/embeddings.npy"
OUT_META = PROJECT_ROOT / "data/v1/metadata.json"
MODEL = "text-embedding-3-small"
BATCH = 100


def make_text(v: dict) -> str:
    """Combine video metadata into a single text for embedding."""
    tags = " ".join(f"#{t}" for t in v.get("tags", [])[:15])
    title = v.get("title", "")
    desc = v.get("description", "")[:300]
    return f"{title}. {desc}. {tags}".strip()


def main():
    videos = [json.loads(l) for l in IN.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(videos)} videos")

    texts = [make_text(v) for v in videos]
    embeddings: list[list[float]] = []

    for i in tqdm(range(0, len(texts), BATCH), desc="Embedding"):
        batch = texts[i : i + BATCH]
        resp = client.embeddings.create(model=MODEL, input=batch)
        batch_vecs = [e.embedding for e in sorted(resp.data, key=lambda x: x.index)]
        embeddings.extend(batch_vecs)

    arr = np.array(embeddings, dtype=np.float32)
    np.save(OUT_EMB, arr)

    metadata = [
        {
            "id": v["id"],
            "title": v["title"],
            "seed_keyword": v["seed_keyword"],
            "tags": v.get("tags", []),
            "channel_id": v.get("channel_id", ""),
            "channel_title": v.get("channel_title", ""),
        }
        for v in videos
    ]
    OUT_META.write_text(json.dumps(metadata, indent=2))

    token_estimate = sum(len(t.split()) * 1.3 for t in texts)
    cost = token_estimate / 1_000_000 * 0.02
    print(f"\nSaved {arr.shape} embeddings → {OUT_EMB}")
    print(f"Saved metadata → {OUT_META}")
    print(f"Estimated cost: ~${cost:.4f}")


if __name__ == "__main__":
    main()
