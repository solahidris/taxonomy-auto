#!/usr/bin/env python3
"""
V3 Step 2: LLM-Driven Sub-Niche Breakdown

This script uses GPT-4o-mini to suggest specific sub-niches for each candidate niche.
For example: "Calisthenics Training" -> ["Calisthenics for Beginners Over 40",
"Advanced Muscle-Up Progressions", "Calisthenics for Tall People"]

Key features:
- Uses sample titles and hashtags to inform suggestions
- Asks for demographic-specific and skill-level sub-niches
- Tags all suggestions as source: "llm_generated"
- Includes validation keywords for matching videos

Output: data/v3/llm_suggestions.json
"""

import json
import os
import time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

# Paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
V3_DIR = DATA_DIR / "v3"

# Config
MODEL = "gpt-4o-mini"
MAX_NICHES_TO_PROCESS = 100  # Limit for cost control
SUGGESTIONS_PER_NICHE = 4  # Target sub-niches per parent

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def load_niche_analysis():
    """Load niche analysis from step 1."""
    with open(V3_DIR / "niche_analysis.json") as f:
        return json.load(f)


def generate_sub_niches(niche_id: str, niche_data: dict) -> dict:
    """Use LLM to suggest sub-niches for a given niche."""

    name = niche_data["name"]
    description = niche_data.get("description", "")
    sample_titles = niche_data.get("sample_titles", [])[:20]
    top_hashtags = niche_data.get("top_hashtags", [])[:15]
    niche_hashtags = niche_data.get("niche_hashtags", [])[:10]

    # Combine hashtags
    all_hashtags = list(set(top_hashtags + niche_hashtags))[:15]

    prompt = f"""You are helping build a creator niche taxonomy for short-form video content (TikTok, Reels, Shorts).

CURRENT NICHE: "{name}"
Description: {description}

SAMPLE VIDEO TITLES FROM THIS NICHE:
{chr(10).join(f'- {t}' for t in sample_titles[:15])}

COMMON HASHTAGS:
{', '.join(f'#{h}' for h in all_hashtags)}

---

Your task: Suggest {SUGGESTIONS_PER_NICHE} SPECIFIC sub-niches within "{name}".

Guidelines:
1. Be VERY specific - not "Fitness Tips" but "Fitness Tips for Office Workers with Bad Posture"
2. Consider different AUDIENCES: beginners vs advanced, age groups, body types, goals
3. Consider different FORMATS: tutorials, transformations, challenges, day-in-life
4. Each sub-niche should be distinct and targetable
5. Include validation keywords that would appear in video titles of this sub-niche

Return ONLY valid JSON (no markdown):
{{
  "parent_niche": "{name}",
  "sub_niches": [
    {{
      "name": "Specific Sub-Niche Name",
      "description": "One sentence describing who creates this and what it covers",
      "target_audience": "Who this is for (e.g., beginners over 40, busy professionals)",
      "validation_keywords": ["keyword1", "keyword2", "keyword3"],
      "expected_hashtags": ["hashtag1", "hashtag2"]
    }}
  ]
}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        # Tag each sub-niche as LLM-generated
        for sub in result.get("sub_niches", []):
            sub["source"] = "llm_generated"
            sub["parent_niche_id"] = niche_id
            sub["confidence"] = "inferred"
            sub["validation_status"] = "unvalidated"

        return result

    except Exception as e:
        print(f"    Error generating sub-niches for {name}: {e}")
        return {"parent_niche": name, "sub_niches": [], "error": str(e)}


def main():
    print("=" * 60)
    print("V3 Step 2: LLM-Driven Sub-Niche Breakdown")
    print("=" * 60)

    # Load analysis
    print("\nLoading niche analysis...")
    analysis = load_niche_analysis()

    # Filter to candidates only
    candidates = {
        niche_id: data
        for niche_id, data in analysis["niches"].items()
        if data.get("is_candidate_for_breakdown", False)
    }

    print(f"Found {len(candidates)} candidates for breakdown")

    # Limit for cost control
    if len(candidates) > MAX_NICHES_TO_PROCESS:
        print(f"Limiting to {MAX_NICHES_TO_PROCESS} niches for cost control")
        # Prioritize by video count
        sorted_candidates = sorted(
            candidates.items(),
            key=lambda x: x[1].get("video_count", 0),
            reverse=True
        )[:MAX_NICHES_TO_PROCESS]
        candidates = dict(sorted_candidates)

    # Generate sub-niches
    all_suggestions = {
        "version": "3.0",
        "model": MODEL,
        "niches_processed": 0,
        "total_sub_niches_suggested": 0,
        "suggestions": {}
    }

    print(f"\nGenerating sub-niches for {len(candidates)} niches...")

    for i, (niche_id, niche_data) in enumerate(candidates.items()):
        print(f"  [{i+1}/{len(candidates)}] {niche_data['name']}...", end=" ", flush=True)

        result = generate_sub_niches(niche_id, niche_data)

        sub_count = len(result.get("sub_niches", []))
        print(f"{sub_count} sub-niches")

        all_suggestions["suggestions"][niche_id] = result
        all_suggestions["niches_processed"] += 1
        all_suggestions["total_sub_niches_suggested"] += sub_count

        # Rate limiting
        time.sleep(0.3)

    # Save results
    output_path = V3_DIR / "llm_suggestions.json"
    with open(output_path, "w") as f:
        json.dump(all_suggestions, f, indent=2)

    print(f"\nResults:")
    print(f"  Niches processed: {all_suggestions['niches_processed']}")
    print(f"  Total sub-niches suggested: {all_suggestions['total_sub_niches_suggested']}")
    print(f"\nSaved to: {output_path}")

    # Show examples
    print(f"\nExample suggestions:")
    count = 0
    for niche_id, result in all_suggestions["suggestions"].items():
        if count >= 3:
            break
        parent = result.get("parent_niche", "Unknown")
        subs = result.get("sub_niches", [])
        if subs:
            print(f"\n  {parent}:")
            for sub in subs[:3]:
                print(f"    - {sub.get('name', 'Unknown')}")
            count += 1


if __name__ == "__main__":
    main()
