#!/usr/bin/env python3
"""Step 4: Name clusters with GPT-4o-mini, build taxonomy.json and centroids.json.

Cost estimate: ~200 clusters × 300 tokens = 60K tokens × $0.15/1M ≈ $0.01
"""

import json
from datetime import date
from pathlib import Path
from openai import OpenAI
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env.local")

client = OpenAI()
IN = Path("data/clusters.json")
OUT_TAXONOMY = Path("data/taxonomy.json")
OUT_CENTROIDS = Path("data/centroids.json")

NICHE_PROMPT = """You are naming micro-niches for a short-form video taxonomy (TikTok/Reels/Shorts).

Video titles from this cluster:
{titles}

Hashtags seen:
{tags}

Name this content niche specifically. Not "fitness" — more like "Calisthenics Bodyweight Training" or "Hyrox Race Prep".

Return JSON only:
{{
  "name": "2-4 word specific niche name",
  "description": "One sentence: who creates this content and what it covers",
  "keywords": ["5", "example", "hashtags"]
}}"""

CATEGORY_PROMPT = """These micro-niches all belong together:
{niches}

What is the best 1-3 word parent category for all of them?
Return JSON: {{"name": "Category Name", "description": "one sentence about this category"}}"""


def name_niche(titles: list[str], tags: list[str]) -> dict:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": NICHE_PROMPT.format(
            titles="\n".join(f"- {t}" for t in titles[:10]),
            tags=", ".join(f"#{t}" for t in tags[:15]) or "none",
        )}],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    return json.loads(resp.choices[0].message.content)


def name_category(micro_names: list[str]) -> dict:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": CATEGORY_PROMPT.format(
            niches="\n".join(f"- {n}" for n in micro_names),
        )}],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return json.loads(resp.choices[0].message.content)


def main():
    clusters = json.loads(IN.read_text())
    print(f"Naming {len(clusters)} clusters...")

    named: dict[str, dict] = {}
    for key, cluster in tqdm(clusters.items(), desc="Naming niches"):
        try:
            info = name_niche(cluster["sample_titles"], cluster["sample_tags"])
        except Exception as e:
            print(f"  Error on {key}: {e}")
            info = {"name": f"Niche {key}", "description": "", "keywords": []}
        named[key] = {**cluster, **info}

    # Group by coarse cluster
    by_coarse: dict[int, list[tuple[str, dict]]] = {}
    for key, n in named.items():
        by_coarse.setdefault(n["coarse_id"], []).append((key, n))

    print("\nNaming top-level categories...")
    tree = []
    centroids = []

    for cid in sorted(by_coarse.keys()):
        items = by_coarse[cid]
        micro_names = [n["name"] for _, n in items]
        try:
            cat_info = name_category(micro_names)
        except Exception as e:
            print(f"  Error naming category {cid}: {e}")
            cat_info = {"name": f"Category {cid}", "description": ""}

        children = []
        for key, n in sorted(items, key=lambda x: -len(x[1]["indices"])):
            children.append({
                "id": key,
                "name": n["name"],
                "description": n["description"],
                "keywords": n.get("keywords", []),
                "video_count": len(n["indices"]),
                "sample_titles": n["sample_titles"][:5],
            })
            centroids.append({
                "id": key,
                "name": n["name"],
                "description": n["description"],
                "path": [cat_info["name"], n["name"]],
                "keywords": n.get("keywords", []),
                "centroid": n["centroid"],
            })

        tree.append({
            "id": f"cat_{cid}",
            "name": cat_info["name"],
            "description": cat_info.get("description", ""),
            "children": children,
        })

    taxonomy = {
        "version": "1.0",
        "generated_at": date.today().isoformat(),
        "total_niches": len(centroids),
        "tree": tree,
    }

    OUT_TAXONOMY.write_text(json.dumps(taxonomy, indent=2))
    OUT_CENTROIDS.write_text(json.dumps(centroids, indent=2))

    print(f"\nTaxonomy: {len(tree)} categories, {len(centroids)} niches")
    print(f"  → {OUT_TAXONOMY}")
    print(f"  → {OUT_CENTROIDS}")


if __name__ == "__main__":
    main()
