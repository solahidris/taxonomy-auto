#!/usr/bin/env python3
"""V2 Step 4: Create unified taxonomy from embedding + hashtag approaches.

Combines:
1. V1 embedding-based niches (with validation status)
2. New niches discovered via hashtag communities
3. Enriched metadata (top hashtags per niche)

Output: Enhanced taxonomy with confidence scores and hashtag signals.
"""

import json
from pathlib import Path
from collections import defaultdict
from openai import OpenAI
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

PROJECT_ROOT = Path(__file__).parent.parent.parent
V1_TAXONOMY = PROJECT_ROOT / "data/v1/taxonomy.json"
V2_MERGED = PROJECT_ROOT / "data/v2/merged_analysis.json"
V2_COMMUNITIES = PROJECT_ROOT / "data/v2/communities.json"
OUT_TAXONOMY = PROJECT_ROOT / "data/v2/taxonomy.json"

client = OpenAI()


def load_data():
    """Load V1 taxonomy and V2 analysis."""
    v1 = json.loads(V1_TAXONOMY.read_text())
    v2_merged = json.loads(V2_MERGED.read_text())
    v2_communities = json.loads(V2_COMMUNITIES.read_text())
    return v1, v2_merged, v2_communities


def name_new_niche(hashtags: list[str], top_v1_niches: list[dict]) -> dict:
    """Use LLM to name a new niche discovered via hashtags."""
    v1_context = ""
    if top_v1_niches:
        v1_names = [n['niche_name'] for n in top_v1_niches[:3]]
        v1_context = f"\nRelated existing niches: {', '.join(v1_names)}"

    prompt = f"""You are naming micro-niches for a short-form video taxonomy.

Top hashtags in this community:
{', '.join(f'#{t}' for t in hashtags[:15])}
{v1_context}

This appears to be a NEW niche not well-captured by existing categories.
Name this content niche specifically.

Return JSON only:
{{
  "name": "2-4 word specific niche name",
  "description": "One sentence: who creates this content and what it covers",
  "keywords": ["5", "example", "hashtags"]
}}"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print(f"    LLM error: {e}")
        return {
            "name": f"#{hashtags[0]} Community",
            "description": f"Content featuring #{hashtags[0]} and related hashtags",
            "keywords": hashtags[:5]
        }


def enrich_v1_niches(v1_taxonomy: dict, v2_merged: dict) -> dict:
    """
    Enrich V1 niches with hashtag validation and top hashtags.
    """
    validation = v2_merged['validation']['niche_validation']
    enriched_niches = {}

    for niche_id, niche_data in v1_taxonomy.get('niches', {}).items():
        val_info = validation.get(niche_id, {})

        # Get top hashtags from supporting communities
        top_hashtags = []
        if val_info.get('supporting_communities'):
            for comm in val_info['supporting_communities']:
                top_hashtags.extend(comm.get('top_hashtags', []))
            # Dedupe while preserving order
            seen = set()
            top_hashtags = [t for t in top_hashtags if not (t in seen or seen.add(t))][:10]

        enriched_niches[niche_id] = {
            **niche_data,
            'source': 'embedding_clustered',
            'hashtag_validated': val_info.get('confirmed_by_hashtags', False),
            'confidence': 'high' if val_info.get('confirmed_by_hashtags') else 'medium',
            'top_hashtags': top_hashtags,
            'supporting_communities': len(val_info.get('supporting_communities', [])),
        }

    return enriched_niches


def create_new_niches(new_candidates: list[dict], v1_taxonomy: dict) -> list[dict]:
    """
    Create new niche entries from hashtag-discovered candidates.
    """
    if not new_candidates:
        return []

    print(f"\nNaming {len(new_candidates)} new hashtag-discovered niches...")

    new_niches = []
    for candidate in tqdm(new_candidates, desc="Naming new niches"):
        # Name the new niche
        naming = name_new_niche(
            candidate['top_hashtags'],
            candidate.get('top_v1_niches', [])
        )

        # Determine parent category based on top V1 niche overlap
        parent_category = "Hashtag Discovered"
        parent_subcategory = "Cross-Niche Content"
        if candidate.get('top_v1_niches'):
            top_v1 = candidate['top_v1_niches'][0]
            parent_category = top_v1.get('category', parent_category)
            parent_subcategory = top_v1.get('subcategory', parent_subcategory)

        new_niche = {
            'id': f"v2_hashtag_{candidate['community_id']}",
            'name': naming['name'],
            'description': naming['description'],
            'source': 'hashtag_discovered',  # Important: tag as hashtag-discovered
            'confidence': 'hashtag_only',
            'hashtag_validated': True,
            'top_hashtags': candidate['top_hashtags'][:10],
            'keywords': naming.get('keywords', candidate['top_hashtags'][:5]),
            'video_count': candidate['video_count'],
            'category_name': parent_category,
            'subcategory_name': parent_subcategory,
            'discovery_reason': candidate['reason'],
            'cohesion_score': candidate.get('cohesion_score', 0),
        }
        new_niches.append(new_niche)

    return new_niches


def build_unified_taxonomy(
    enriched_v1_niches: dict,
    new_niches: list[dict],
    v1_taxonomy: dict
) -> dict:
    """
    Build the final unified taxonomy.
    """
    # Start with V1 structure
    taxonomy = {
        'version': '2.0',
        'approach': 'hybrid_embedding_hashtag',
        'categories': v1_taxonomy.get('categories', {}),
        'subcategories': v1_taxonomy.get('subcategories', {}),
        'niches': {},
        'stats': {},
    }

    # Add enriched V1 niches
    for niche_id, niche_data in enriched_v1_niches.items():
        taxonomy['niches'][niche_id] = niche_data

    # Add new hashtag-discovered niches
    for new_niche in new_niches:
        niche_id = new_niche['id']
        taxonomy['niches'][niche_id] = new_niche

        # Add to "Hashtag Discovered" category if not exists
        if new_niche['category_name'] == "Hashtag Discovered":
            cat_id = "cat_hashtag"
            if cat_id not in taxonomy['categories']:
                taxonomy['categories'][cat_id] = {
                    'name': 'Hashtag Discovered',
                    'description': 'Niches discovered via hashtag co-occurrence analysis',
                }

    # Compute stats
    total_niches = len(taxonomy['niches'])
    v1_niches = sum(1 for n in taxonomy['niches'].values() if n['source'] == 'embedding_clustered')
    new_niches_count = sum(1 for n in taxonomy['niches'].values() if n['source'] == 'hashtag_discovered')
    hashtag_validated = sum(1 for n in taxonomy['niches'].values() if n.get('hashtag_validated'))
    high_confidence = sum(1 for n in taxonomy['niches'].values() if n.get('confidence') == 'high')

    taxonomy['stats'] = {
        'total_niches': total_niches,
        'v1_embedding_niches': v1_niches,
        'v2_hashtag_niches': new_niches_count,
        'hashtag_validated': hashtag_validated,
        'high_confidence': high_confidence,
        'total_categories': len(taxonomy['categories']),
        'total_subcategories': len(taxonomy['subcategories']),
    }

    return taxonomy


def main():
    print("=" * 60)
    print("V2 Step 4: Build Unified Taxonomy")
    print("=" * 60)

    # Load data
    print("\nLoading data...")
    v1_taxonomy, v2_merged, v2_communities = load_data()

    print(f"  V1 niches: {len(v1_taxonomy.get('niches', {}))}")
    print(f"  New niche candidates: {len(v2_merged.get('new_niche_candidates', []))}")

    # Enrich V1 niches with hashtag validation
    print("\nEnriching V1 niches with hashtag validation...")
    enriched_v1 = enrich_v1_niches(v1_taxonomy, v2_merged)

    validated = sum(1 for n in enriched_v1.values() if n['hashtag_validated'])
    print(f"  V1 niches validated by hashtags: {validated}/{len(enriched_v1)}")

    # Create new niches from hashtag discoveries
    new_candidates = v2_merged.get('new_niche_candidates', [])
    new_niches = create_new_niches(new_candidates, v1_taxonomy)

    print(f"\n  New niches created: {len(new_niches)}")

    # Build unified taxonomy
    print("\nBuilding unified taxonomy...")
    taxonomy = build_unified_taxonomy(enriched_v1, new_niches, v1_taxonomy)

    # Summary
    print(f"\n--- V2 Taxonomy Summary ---")
    print(f"  Total niches: {taxonomy['stats']['total_niches']}")
    print(f"  From V1 (embedding): {taxonomy['stats']['v1_embedding_niches']}")
    print(f"  New (hashtag): {taxonomy['stats']['v2_hashtag_niches']}")
    print(f"  Hashtag validated: {taxonomy['stats']['hashtag_validated']}")
    print(f"  High confidence: {taxonomy['stats']['high_confidence']}")

    # Show some new niches
    if new_niches:
        print(f"\n  Sample new niches:")
        for n in new_niches[:5]:
            print(f"    - {n['name']}: {n['description'][:60]}...")

    # Save
    OUT_TAXONOMY.write_text(json.dumps(taxonomy, indent=2))
    print(f"\n  Taxonomy saved -> {OUT_TAXONOMY}")


if __name__ == "__main__":
    main()
