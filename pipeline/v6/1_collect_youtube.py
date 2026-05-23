#!/usr/bin/env python3
"""V6 Step 1: Collect YouTube Shorts targeting underrepresented categories.

V1 collected Fitness/Food/Beauty heavily. V5 added some Gaming/Travel/Tech.
V6 targets categories still missing: Finance, Arts, Music, Parenting, Automotive,
Sports, Home/DIY, Career, Relationships, Spirituality, International Food,
Comedy, Pets — plus deeper Gaming and Travel coverage.

Keywords are interleaved round-robin by category so even if quota runs out,
we get broad category coverage.
"""

import os, json, time, requests
from pathlib import Path
from itertools import zip_longest
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

API_KEY = os.environ["YOUTUBE_API_KEY"]
BASE = "https://www.googleapis.com/youtube/v3"
PROJECT_ROOT = Path(__file__).parent.parent.parent
OUT = PROJECT_ROOT / "data/v6/youtube_raw.jsonl"

# Keywords organized by category — round-robin ensures breadth even at quota limit
CATEGORIES = {
    "gaming": [
        "minecraft build tutorial", "fortnite battle royale tips", "valorant aim tips",
        "elden ring boss guide", "pokemon card opening", "roblox tutorial shorts",
        "retro gaming nostalgia", "speedrun world record", "gaming setup tour budget",
        "fps gaming clips", "indie game hidden gem", "horror game jumpscare",
        "gta online money glitch", "esports highlights 2024", "gaming rage funny",
    ],
    "travel": [
        "japan travel guide solo", "italy travel tips cheap", "bali travel vlog",
        "europe on 50 dollars day", "thailand hidden gems", "solo female travel tips",
        "van life daily routine", "national park hiking tips", "flight hacks first class",
        "digital nomad life abroad", "greece island travel", "mexico city travel",
        "road trip america tips", "travel photography composition", "budget hostel tips",
    ],
    "finance": [
        "investing beginner stock market", "etf index fund explained", "roth ira setup",
        "side hustle real money 2024", "budgeting paycheck method", "credit card rewards hack",
        "real estate investing tips", "crypto basics explained simply", "debt payoff strategy",
        "emergency fund building", "salary negotiation script", "dividend investing passive",
        "freelancing income tips", "dropshipping 2024 truth", "financial independence tips",
    ],
    "arts_crafts": [
        "watercolor painting tutorial beginner", "procreate digital art tips", "pottery wheel tutorial",
        "crochet beginner pattern simple", "resin art pouring tutorial", "embroidery beginner tips",
        "oil painting technique beginner", "drawing portrait tips", "candle making tutorial",
        "macrame wall hanging tutorial", "linocut printmaking", "paper quilling tutorial",
        "clay sculpting beginner", "knitting beginner cast on", "upcycle denim jacket diy",
    ],
    "music_dance": [
        "guitar chord progression beginner", "piano ballad tutorial easy", "singing breath control tips",
        "music production fl studio beginner", "beat making tutorial trap", "hip hop choreography tutorial",
        "salsa dance steps beginner", "kpop dance cover tutorial", "shuffle dance beginner",
        "vocal warmup exercises daily", "guitar fingerpicking pattern", "songwriting tips emotional",
        "music theory modal scales", "live looping performance", "ukulele easy songs beginner",
    ],
    "parenting": [
        "newborn baby sleep schedule", "toddler tantrum tips calm", "baby solid food introduction",
        "gentle parenting tips toddler", "positive discipline kids", "breastfeeding tips new mom",
        "dad life funny moments", "homeschool tips beginner", "toddler activity indoor rainy",
        "baby development milestones", "picky eater toddler meals", "postpartum recovery tips",
        "single parent tips morning", "co parenting communication tips", "teen parenting advice",
    ],
    "automotive": [
        "car maintenance diy beginner", "oil change tutorial at home", "car detailing beginner tips",
        "electric vehicle tips charging", "used car buying inspection tips", "motorcycle beginner tips",
        "car modification budget build", "jdm car culture explained", "tire rotation diy tutorial",
        "car audio setup beginner", "dashboard warning light meaning", "brake pad replacement diy",
        "tesla tips hidden features", "off road 4x4 tips", "car wash satisfying technique",
    ],
    "sports": [
        "basketball dribbling moves tutorial", "soccer juggling freestyle skills", "golf swing fix tips",
        "tennis serve technique tips", "boxing combination training", "skateboard kickflip beginner",
        "surfing beginner lesson tips", "snowboard beginner basics", "rock climbing technique wall",
        "table tennis spin serve tips", "badminton smash technique", "mma ground game tips",
        "disc golf beginner tips", "parkour beginner jump tutorial", "swimming flip turn tips",
    ],
    "home_diy": [
        "home renovation diy beginner tips", "ikea hack furniture ideas", "thrift flip furniture transformation",
        "bathroom tile installation diy", "painting walls tips professional", "container garden balcony",
        "indoor plant beginner care", "smart home setup guide", "home organization system",
        "kitchen renovation budget tips", "drywall patch repair tutorial", "closet organization ideas",
        "succulent propagation tips", "herb garden indoor kitchen", "exterior home decor ideas",
    ],
    "career": [
        "job interview tips modern 2024", "resume tips get hired", "linkedin profile optimization",
        "remote work productivity tips", "career change pivot advice", "networking tips introvert",
        "salary negotiation raise tips", "personal branding social media", "work burnout recovery",
        "freelance client tips getting", "side income 2024 skills", "productivity deep work tips",
        "office politics navigate tips", "promotion tips workplace", "skills learn 2024 demand",
    ],
    "relationships": [
        "dating app tips first message", "first date conversation tips", "relationship green flags list",
        "narcissist signs recognize", "healthy boundaries relationship", "long distance relationship tips",
        "breakup recovery self love", "love language acts service", "communication conflict resolve",
        "trust rebuild relationship tips", "attachment style anxious tips", "marriage advice early",
        "self worth after breakup", "making friends as adult", "social skills confidence tips",
    ],
    "spirituality": [
        "meditation beginner 5 minutes", "breathwork anxiety tutorial", "mindfulness present moment",
        "stoicism daily practice tips", "gratitude journaling life change", "manifestation vision board",
        "shadow work journaling prompts", "yoga nidra body scan", "crystal healing beginner",
        "law of attraction evidence", "inner child healing exercise", "prayer manifestation tips",
        "spiritual awakening signs", "chakra balancing beginner", "energy cleansing ritual",
    ],
    "international_food": [
        "japanese ramen from scratch", "korean fried chicken recipe", "thai pad thai tutorial",
        "indian curry authentic recipe", "italian pasta technique carbonara", "mexican tacos birria",
        "vietnamese pho soup recipe", "chinese dumplings jiaozi tutorial", "french croissant technique",
        "sushi roll tutorial beginner", "turkish pide recipe", "ethiopian injera recipe",
        "moroccan tagine recipe", "spanish paella authentic", "greek tzatziki recipe",
    ],
    "comedy": [
        "comedy skit everyday life", "dating life funny shorts", "gym fails compilation",
        "expectation vs reality work", "coworker types funny", "gen z humor explained",
        "influencer satire funny", "relatable morning routine funny", "online dating cringe",
        "boss types funny parody", "social media reality funny", "tourist vs local funny",
    ],
    "pets": [
        "dog tricks advanced training", "puppy first week tips", "cat behavior explained funny",
        "aquarium fish care beginner", "parrot training tips talking", "reptile care beginner",
        "hamster cage setup tour", "rabbit care indoor tips", "bird enrichment ideas diy",
        "exotic pet care tips", "senior dog care tips", "kitten socialization tips",
        "dog separation anxiety tips", "cat enrichment indoor ideas", "pet nutrition tips",
    ],
}


def interleave_round_robin(categories: dict) -> list[str]:
    """Return keywords interleaved round-robin across all categories."""
    lists = list(categories.values())
    result = []
    for items in zip_longest(*lists):
        for item in items:
            if item is not None:
                result.append(item)
    return result


SEED_KEYWORDS = interleave_round_robin(CATEGORIES)


def fetch_videos(keyword: str, max_results: int = 50) -> list[dict]:
    try:
        search_resp = requests.get(f"{BASE}/search", params={
            "part": "id",
            "q": keyword,
            "type": "video",
            "videoDuration": "short",
            "maxResults": max_results,
            "relevanceLanguage": "en",
            "regionCode": "US",
            "key": API_KEY,
        }, timeout=15)

        data = search_resp.json()
        if "error" in data:
            err = data["error"]["message"]
            print(f"  API error: {err}")
            if "quotaExceeded" in err:
                return None  # Signal quota exhausted
            return []

        ids = [item["id"]["videoId"] for item in data.get("items", [])]
        if not ids:
            return []

        detail_resp = requests.get(f"{BASE}/videos", params={
            "part": "snippet",
            "id": ",".join(ids),
            "key": API_KEY,
        }, timeout=15)

        videos = []
        for item in detail_resp.json().get("items", []):
            s = item["snippet"]
            # Extract hashtags from title
            title = s.get("title", "")
            hashtags_from_title = [
                w[1:].lower() for w in title.split()
                if w.startswith("#") and len(w) > 1
            ]
            tags = s.get("tags", [])[:20]
            all_hashtags = list(set(hashtags_from_title + [t.lower() for t in tags]))

            videos.append({
                "id": item["id"],
                "platform": "youtube",
                "seed_keyword": keyword,
                "title": title,
                "description": s.get("description", "")[:500],
                "hashtags": all_hashtags[:25],
                "author": s.get("channelTitle", ""),
                "author_id": s.get("channelId", ""),
                "category_id": s.get("categoryId", ""),
                "source": "v6_new",
            })
        return videos

    except Exception as e:
        print(f"  Request error: {e}")
        return []


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)

    # Load existing video IDs from V5 merged to avoid duplicates
    seen_ids: set[str] = set()
    v5_merged = PROJECT_ROOT / "data/v5/merged_videos.jsonl"
    if v5_merged.exists():
        with open(v5_merged) as f:
            for line in f:
                vid = json.loads(line)
                if vid.get("id"):
                    seen_ids.add(vid["id"])
        print(f"Loaded {len(seen_ids)} existing IDs from V5 to skip duplicates")

    seen_channels: dict[str, int] = {}
    total = 0
    quota_exceeded = False

    print(f"\nV6 YouTube Collection: {len(SEED_KEYWORDS)} keywords (round-robin by category)")
    print("=" * 60)

    with open(OUT, "w") as f:
        for i, kw in enumerate(SEED_KEYWORDS):
            if quota_exceeded:
                break

            print(f"[{i+1}/{len(SEED_KEYWORDS)}] '{kw}'...")
            videos = fetch_videos(kw)

            if videos is None:
                print("  QUOTA EXCEEDED — stopping collection")
                quota_exceeded = True
                break

            new = 0
            for v in videos:
                if v["id"] in seen_ids:
                    continue
                ch = v["author_id"]
                if seen_channels.get(ch, 0) >= 10:
                    continue
                seen_ids.add(v["id"])
                seen_channels[ch] = seen_channels.get(ch, 0) + 1
                f.write(json.dumps(v) + "\n")
                new += 1

            total += new
            print(f"  +{new} new (total: {total}, channels: {len(seen_channels)})")
            time.sleep(0.5)

            if (i + 1) % 15 == 0:
                print(f"\n--- {i+1} keywords done, {total} videos, {len(seen_channels)} channels ---\n")

    print("=" * 60)
    print(f"Done. {total} unique new videos from {len(seen_channels)} channels")
    print(f"Saved to {OUT}")


if __name__ == "__main__":
    main()
