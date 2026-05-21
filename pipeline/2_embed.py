#!/usr/bin/env python3
"""Step 2: Embed video texts using text-embedding-3-small.

Cost estimate: ~3000 videos × 200 tokens = 600K tokens × $0.02/1M ≈ $0.01
"""

import json
import numpy as np
from pathlib import Path
from openai import OpenAI
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env.local")

client = OpenAI()
IN = Path("data/raw_videos.jsonl")
OUT_EMB = Path("data/embeddings.npy")
OUT_META = Path("data/metadata.json")
MODEL = "text-embedding-3-small"
BATCH = 100


def make_text(v: dict) -> str:
    tags = " ".join(f"#{t}" for t in v.get("tags", [])[:15])
    return f"{v['title']}. {v.get('description', '')[:300]}. {tags}".strip()


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
            "channel_title": v.get("channel_title", ""),
        }
        for v in videos
    ]
    OUT_META.write_text(json.dumps(metadata, indent=2))

    token_estimate = sum(len(t.split()) * 1.3 for t in texts)
    cost = token_estimate / 1_000_000 * 0.02
    print(f"\nSaved {arr.shape} embeddings → {OUT_EMB}")
    print(f"Estimated cost: ~${cost:.4f}")


if __name__ == "__main__":
    main()
