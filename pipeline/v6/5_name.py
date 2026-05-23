#!/usr/bin/env python3
"""V6 Step 5: Hierarchical LLM naming for the V6 taxonomy.

Names niches → subcategories → categories bottom-up.
Extracts exemplar creators per niche.
Uses GPT-4o-mini for cost efficiency.
"""

import json
from pathlib import Path
from collections import defaultdict
from openai import OpenAI
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

client = OpenAI()
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "v6"
IN_CLUSTERS = DATA_DIR / "clusters.json"
IN_META = DATA_DIR / "metadata.json"
OUT = DATA_DIR / "taxonomy.json"
MODEL = "gpt-4o-mini"


def call_llm(prompt: str) -> dict:
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            if attempt == 2:
                return {}
    return {}


def name_niche(niche_data: dict) -> dict:
    titles = niche_data.get("sample_titles", [])[:15]
    tags = list(set(niche_data.get("sample_tags", [])))[:20]
    channels = list(set(niche_data.get("sample_channels", [])))[:8]

    prompt = f"""Name a SHORT-FORM video creator niche (TikTok/Reels/Shorts style).

Video titles in this cluster:
{chr(10).join(f'- {t}' for t in titles)}

Common hashtags: {', '.join(f'#{t}' for t in tags[:15])}
Channels: {', '.join(channels[:6])}

Be SPECIFIC, not generic. Good examples: "Beginner Calisthenics Progressions", "Sourdough & Artisan Baking", "Budget Solo Travel Asia".
Bad examples: "Fitness Videos", "Cooking Content", "Travel Vlogs".

Return JSON only:
{{
  "name": "2-5 word specific niche name",
  "description": "One sentence: who creates this content and what it covers",
  "keywords": ["5", "relevant", "hashtag", "keywords"]
}}"""

    result = call_llm(prompt)
    return {
        "name": result.get("name", "Unnamed Niche"),
        "description": result.get("description", ""),
        "keywords": result.get("keywords", []),
    }


def name_subcategory(subcat_id: int, niche_names: list[str]) -> dict:
    prompt = f"""Name a SUBCATEGORY that groups these short-form content niches:
{chr(10).join(f'- {n}' for n in niche_names[:12])}

2-4 word subcategory name that covers all of them.
Return JSON: {{"name": "Subcategory Name", "description": "one sentence"}}"""

    result = call_llm(prompt)
    return {
        "name": result.get("name", f"Subcategory {subcat_id}"),
        "description": result.get("description", ""),
    }


def name_category(cat_id: int, subcat_names: list[str], niche_sample: list[str]) -> dict:
    prompt = f"""Name a broad TOP-LEVEL CATEGORY for these short-form content subcategories:
{chr(10).join(f'- {n}' for n in subcat_names[:10])}

Sample niches: {', '.join(niche_sample[:8])}

1-3 word category name (e.g., "Fitness & Health", "Food & Cooking", "Gaming").
Return JSON: {{"name": "Category Name", "description": "one sentence"}}"""

    result = call_llm(prompt)
    return {
        "name": result.get("name", f"Category {cat_id}"),
        "description": result.get("description", ""),
    }


def get_exemplars(niche_data: dict, metadata: list, top_n: int = 10) -> list[dict]:
    counts: dict[str, int] = defaultdict(int)
    info: dict[str, str] = {}
    for idx in niche_data.get("indices", []):
        if idx < len(metadata):
            aid = metadata[idx].get("author_id", "")
            aname = metadata[idx].get("author", "")
            if aid and aname:
                counts[aid] += 1
                info[aid] = aname
    top = sorted(counts.items(), key=lambda x: -x[1])[:top_n]
    return [{"author_id": aid, "author": info[aid], "video_count": cnt} for aid, cnt in top]


def main():
    print("Loading clusters and metadata...")
    clusters = json.loads(IN_CLUSTERS.read_text())
    metadata = json.loads(IN_META.read_text())
    print(f"  {len(clusters)} niches to name")

    # Group niches by category and subcategory
    by_cat_subcat: dict = defaultdict(lambda: defaultdict(list))
    for niche_id, data in clusters.items():
        cat_id = data["category_id"]
        sub_id = data["subcategory_id"]
        by_cat_subcat[cat_id][sub_id].append(niche_id)

    # Step 1: Name all niches
    print("\nNaming niches with GPT-4o-mini...")
    niche_names: dict[str, dict] = {}
    for niche_id, data in tqdm(clusters.items()):
        result = name_niche(data)
        niche_names[niche_id] = result

    # Step 2: Name subcategories
    print("\nNaming subcategories...")
    subcat_names: dict[str, dict] = {}
    subcat_key_to_id: dict[str, str] = {}

    for cat_id, subcats in tqdm(by_cat_subcat.items()):
        for sub_id, niche_ids in subcats.items():
            key = f"sub_{cat_id}_{sub_id}"
            names = [niche_names[nid]["name"] for nid in niche_ids if nid in niche_names]
            result = name_subcategory(sub_id, names)
            subcat_names[key] = {
                **result,
                "category_id": cat_id,
                "niche_ids": niche_ids,
                "niche_count": len(niche_ids),
            }
            subcat_key_to_id[key] = key

    # Step 3: Name categories
    print("\nNaming categories...")
    cat_names: dict[str, dict] = {}

    for cat_id, subcats in tqdm(by_cat_subcat.items()):
        subcat_keys = [f"sub_{cat_id}_{sub_id}" for sub_id in subcats]
        sub_name_list = [subcat_names[k]["name"] for k in subcat_keys if k in subcat_names]
        niche_sample = [
            niche_names[nid]["name"]
            for sub_id, nids in subcats.items()
            for nid in nids[:3]
            if nid in niche_names
        ][:10]
        result = name_category(cat_id, sub_name_list, niche_sample)
        cat_names[str(cat_id)] = {
            **result,
            "niche_count": sum(len(nids) for nids in subcats.values()),
        }

    # Build taxonomy JSON
    print("\nBuilding taxonomy...")

    categories = {}
    for cat_id, data in cat_names.items():
        categories[f"cat_{cat_id}"] = {
            "name": data["name"],
            "description": data.get("description", ""),
            "niche_count": data["niche_count"],
        }

    subcategories = {}
    for key, data in subcat_names.items():
        subcategories[key] = {
            "name": data["name"],
            "description": data.get("description", ""),
            "category_id": data["category_id"],
            "category_name": cat_names.get(str(data["category_id"]), {}).get("name", ""),
            "niche_count": data["niche_count"],
        }

    niches = {}
    for niche_id, data in clusters.items():
        cat_id = data["category_id"]
        sub_id = data["subcategory_id"]
        subcat_key = f"sub_{cat_id}_{sub_id}"
        n = niche_names.get(niche_id, {})

        niches[niche_id] = {
            "name": n.get("name", "Unnamed"),
            "description": n.get("description", ""),
            "keywords": n.get("keywords", []),
            "category_id": cat_id,
            "category_name": cat_names.get(str(cat_id), {}).get("name", ""),
            "subcategory_id": subcat_key,
            "subcategory_name": subcat_names.get(subcat_key, {}).get("name", ""),
            "video_count": data["count"],
            "top_hashtags": data.get("sample_tags", [])[:10],
            "centroid": data["centroid"],
            "exemplar_creators": get_exemplars(data, metadata),
            "source": "embedding_clustered",
        }

    taxonomy = {
        "version": "6.0",
        "generated_at": "2026-05-23",
        "approach": "V6: Combined YouTube+TikTok+Instagram data, 4-level embedding clustering",
        "sources": {
            "youtube_v1": "3991 videos",
            "tiktok": "2034 videos",
            "instagram": "951 videos",
            "youtube_v6": "new videos targeting underrepresented categories",
        },
        "categories": categories,
        "subcategories": subcategories,
        "niches": niches,
        "stats": {
            "total_niches": len(niches),
            "total_categories": len(categories),
            "total_subcategories": len(subcategories),
            "total_videos": sum(c["count"] for c in clusters.values()),
            "approaches": ["Embedding Clustering (V1)", "Cross-Platform Data (V5)", "New YouTube Categories (V6)"],
        },
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(taxonomy, f, indent=2)

    print(f"\nV6 Taxonomy complete:")
    print(f"  Categories:    {len(categories)}")
    print(f"  Subcategories: {len(subcategories)}")
    print(f"  Niches:        {len(niches)}")
    print(f"  Saved → {OUT}")


if __name__ == "__main__":
    main()
