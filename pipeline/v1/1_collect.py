#!/usr/bin/env python3
"""V1 Step 1: Collect short-form video metadata from YouTube Data API v3.

Expanded to ~200+ seed keywords for 20-30K videos.
API cost: ~20K units (may need multiple days or multiple API keys).
"""

import os, json, time, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

API_KEY = os.environ["YOUTUBE_API_KEY"]
BASE = "https://www.googleapis.com/youtube/v3"
PROJECT_ROOT = Path(__file__).parent.parent.parent
OUT = PROJECT_ROOT / "data/v1/raw_videos.jsonl"

# Expanded seed keywords (~200+) organized by vertical
SEED_KEYWORDS = [
    # =========================================================================
    # FITNESS & EXERCISE (40+ keywords)
    # =========================================================================
    # Calisthenics & Bodyweight
    "calisthenics workout", "calisthenics beginner", "pull up progression",
    "push up variations", "muscle up tutorial", "street workout motivation",
    "bodyweight fitness", "calisthenics transformation", "handstand tutorial",
    # Gym & Weightlifting
    "gym motivation", "gym workout routine", "powerlifting tips",
    "bodybuilding natural", "gym transformation", "weightlifting technique",
    "deadlift form", "squat tips", "bench press tutorial",
    # Cardio & Endurance
    "running tips beginner", "marathon training", "5k training plan",
    "hyrox training", "crossfit workout", "hiit workout home",
    "jump rope workout", "cycling tips", "swimming technique",
    # Yoga & Flexibility
    "yoga morning routine", "yoga for beginners", "yoga flow",
    "stretching routine", "mobility workout", "flexibility training",
    "pilates routine", "pilates abs", "yoga challenge",
    # Weight Loss & Transformation
    "weight loss transformation", "fat loss tips", "calorie deficit",
    "weight loss journey", "body recomposition", "cutting diet",
    # Home Fitness
    "home workout no equipment", "apartment workout", "dumbbell workout home",
    "resistance band workout", "kettlebell workout",

    # =========================================================================
    # FOOD & COOKING (35+ keywords)
    # =========================================================================
    # Quick Recipes
    "easy 15 minute recipe", "quick dinner ideas", "5 minute meals",
    "one pot recipe", "sheet pan dinner", "instant pot recipe",
    # Meal Prep
    "meal prep sunday", "meal prep ideas", "weekly meal prep",
    "budget meal prep", "healthy meal prep", "freezer meals",
    # Diet Specific
    "vegan cooking", "vegan recipes easy", "keto recipes",
    "high protein meals", "low carb recipe", "gluten free cooking",
    "vegetarian dinner", "plant based meals",
    # Baking
    "sourdough bread baking", "cookie recipe", "cake decorating",
    "bread baking tips", "dessert recipe easy", "baking hacks",
    # Food Content
    "what i eat in a day", "mukbang eating show", "food review",
    "street food tour", "restaurant review", "trying viral food",
    # Cooking Skills
    "cooking hack viral", "knife skills", "cooking tips beginner",
    "chef techniques", "cooking mistakes",

    # =========================================================================
    # BEAUTY & FASHION (35+ keywords)
    # =========================================================================
    # Makeup
    "makeup tutorial beginner", "makeup routine daily", "glam makeup look",
    "natural makeup tutorial", "eyeshadow tutorial", "lipstick hacks",
    "makeup transformation", "drugstore makeup", "makeup dupes",
    # Skincare
    "skincare routine morning", "skincare routine night", "acne skincare",
    "anti aging skincare", "korean skincare", "skincare tips",
    "glass skin routine", "retinol tips", "sunscreen review",
    # Hair
    "hair transformation short", "hair styling tutorial", "curly hair routine",
    "hair growth tips", "hair color transformation", "haircut transformation",
    # Fashion
    "outfit of the day", "fashion haul try on", "thrift flip fashion",
    "capsule wardrobe", "style tips", "outfit ideas",
    "grwm get ready with me", "fashion trends", "streetwear fashion",
    # Nails
    "nail art tutorial", "nail design ideas", "gel nails at home",

    # =========================================================================
    # GAMING (30+ keywords)
    # =========================================================================
    # General Gaming
    "gaming highlights moments", "gaming tips tricks", "gaming setup tour",
    "gaming room tour", "gaming montage", "clutch moments gaming",
    # Specific Games
    "minecraft build tutorial", "minecraft survival", "fortnite tips",
    "valorant tips", "call of duty clips", "gta moments",
    "elden ring boss", "zelda tips", "pokemon challenge",
    # Game Types
    "fps tips tricks", "speedrun world record", "indie game review",
    "horror game reaction", "retro gaming nostalgia", "mobile gaming",
    # Esports & Competitive
    "esports highlights", "pro player settings", "ranked gameplay",
    # Gaming Culture
    "game review short", "gaming memes", "gamer rage moments",

    # =========================================================================
    # TRAVEL & ADVENTURE (25+ keywords)
    # =========================================================================
    "solo travel vlog", "budget travel tips", "travel hacks packing",
    "hidden gems city", "backpacking adventure", "van life daily",
    "road trip vlog", "travel itinerary", "hotel room tour",
    "flight tips", "airport hacks", "travel photography tips",
    "europe travel", "asia travel vlog", "beach destination",
    "mountain hiking", "national park tour", "digital nomad life",
    "travel on budget", "luxury travel", "adventure travel",
    "solo female travel", "couple travel vlog", "family travel tips",

    # =========================================================================
    # COMEDY & ENTERTAINMENT (25+ keywords)
    # =========================================================================
    "funny fails compilation", "prank video", "comedy skit",
    "storytime drama", "embarrassing story", "dating storytime",
    "day in my life aesthetic", "relatable content", "gen z humor",
    "satisfying video oddly", "asmr satisfying", "slime video",
    "life hack actually works", "expectation vs reality", "things that just make sense",
    "trend challenge", "viral challenge", "duet reaction",
    "celebrity impression", "voice impression", "parody video",
    "dark humor", "dad jokes", "pun compilation",

    # =========================================================================
    # EDUCATION & LEARNING (30+ keywords)
    # =========================================================================
    # Programming & Tech
    "learn python programming", "coding tutorial beginner", "web development tips",
    "javascript tutorial", "programming tips", "coding project ideas",
    # Academic
    "history explained short", "science experiment home", "math trick mental",
    "physics explained", "chemistry experiment", "biology facts",
    # Study & Productivity
    "study with me pomodoro", "study tips exam", "productivity tips study",
    "note taking methods", "study motivation", "time management tips",
    # Language Learning
    "language learning daily", "learn spanish", "learn japanese",
    "english tips", "pronunciation tips", "vocabulary tips",
    # General Knowledge
    "book summary 5 minutes", "psychology facts", "interesting facts",
    "did you know", "things you didnt know", "mind blowing facts",

    # =========================================================================
    # FINANCE & BUSINESS (25+ keywords)
    # =========================================================================
    "personal finance tips", "investing for beginners", "stock market explained",
    "passive income ideas", "side hustle ideas", "make money online",
    "budgeting tips", "saving money tips", "frugal living",
    "credit score tips", "debt payoff", "financial freedom",
    "crypto explained", "real estate investing", "index fund investing",
    "entrepreneur tips", "small business tips", "startup advice",
    "career advice", "job interview tips", "salary negotiation",
    "money mistakes", "rich vs poor habits", "millionaire habits",

    # =========================================================================
    # LIFESTYLE & WELLNESS (30+ keywords)
    # =========================================================================
    # Morning/Daily Routines
    "morning routine productive", "night routine", "sunday reset routine",
    "5am routine", "daily routine aesthetic", "self care routine",
    # Mental Health
    "mental health tips", "anxiety tips", "meditation anxiety",
    "therapy tips", "self improvement", "confidence tips",
    "motivation daily", "discipline tips", "mindset shift",
    # Home & Organization
    "minimalism declutter", "organization hacks", "clean with me satisfying",
    "home organization", "closet organization", "room makeover",
    "apartment tour", "home decor ideas", "aesthetic room",
    # Journaling & Self Care
    "journaling habit", "gratitude journal", "bullet journal",
    "self care ideas", "pamper routine", "relaxation tips",

    # =========================================================================
    # PETS & ANIMALS (20+ keywords)
    # =========================================================================
    "dog training tricks", "puppy training tips", "dog behavior explained",
    "cat behavior funny", "cat training", "kitten videos",
    "pet transformation rescue", "pet adoption story", "pet routine",
    "aquarium fish", "reptile care", "bird training",
    "cute pet moments", "pet fails funny", "animals being derps",
    "exotic pets", "pet product review", "pet diy",
    "dog breed comparison", "cat breed guide",

    # =========================================================================
    # TECH & GADGETS (25+ keywords)
    # =========================================================================
    "tech review unboxing", "iphone tips hidden features", "android tips",
    "ai tools productivity", "chatgpt tips", "ai art tutorial",
    "gadget review", "tech deals", "best tech under 50",
    "smart home setup", "desk setup tour", "tech accessories",
    "app recommendations", "productivity apps", "photo editing tips",
    "video editing tips", "camera tips beginner", "drone footage",
    "3d printing", "mechanical keyboard", "headphone review",
    "laptop review", "tablet comparison", "smartwatch tips",

    # =========================================================================
    # ARTS & CRAFTS (20+ keywords)
    # =========================================================================
    "art tutorial beginner", "drawing tips", "digital art tutorial",
    "painting tutorial", "watercolor tutorial", "sketch tips",
    "diy craft ideas", "diy home decor", "upcycling ideas",
    "crochet tutorial", "knitting beginner", "sewing tips",
    "pottery making", "resin art", "calligraphy tutorial",
    "art process video", "artist vlog", "art supplies review",
    "bullet journal ideas", "scrapbooking",

    # =========================================================================
    # MUSIC & DANCE (20+ keywords)
    # =========================================================================
    "guitar tutorial beginner", "piano tutorial", "singing tips",
    "music production tips", "beat making tutorial", "songwriting tips",
    "dance tutorial", "hip hop dance", "kpop dance cover",
    "choreography tutorial", "dance challenge", "shuffle dance",
    "music cover", "street performance", "musician vlog",
    "instrument review", "music theory basics", "vocal warmup",
    "concert vlog", "music reaction",

    # =========================================================================
    # PARENTING & FAMILY (15+ keywords)
    # =========================================================================
    "parenting tips", "mom life vlog", "dad life",
    "baby tips newborn", "toddler activities", "kids educational",
    "pregnancy tips", "postpartum tips", "breastfeeding tips",
    "family vlog", "sibling moments", "family routine",
    "homeschool tips", "kids crafts", "baby products review",

    # =========================================================================
    # AUTOMOTIVE (15+ keywords)
    # =========================================================================
    "car review", "car tips maintenance", "car detailing",
    "car modification", "car wash satisfying", "driving tips",
    "motorcycle vlog", "car comparison", "new car tour",
    "electric car review", "car shopping tips", "car cleaning hacks",
    "project car", "car sounds", "supercar",

    # =========================================================================
    # SPORTS (15+ keywords)
    # =========================================================================
    "basketball tips", "soccer skills tutorial", "football highlights",
    "tennis tips", "golf tips beginner", "boxing training",
    "mma training", "skateboarding tricks", "surfing tutorial",
    "skiing tips", "snowboarding tricks", "rock climbing",
    "sports motivation", "athlete day in life", "sports fails",
]

def fetch_videos(keyword: str, max_results: int = 50) -> list[dict]:
    """Fetch videos for a keyword from YouTube API."""
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
            print(f"  API error: {data['error']['message']}")
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
            videos.append({
                "id": item["id"],
                "seed_keyword": keyword,
                "title": s.get("title", ""),
                "description": s.get("description", "")[:500],  # Increased from 400
                "tags": s.get("tags", [])[:25],  # Increased from 20
                "channel_id": s.get("channelId", ""),
                "channel_title": s.get("channelTitle", ""),
                "category_id": s.get("categoryId", ""),
            })
        return videos
    except Exception as e:
        print(f"  Request error: {e}")
        return []


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    seen_ids: set[str] = set()
    seen_channels: dict[str, int] = {}  # Track videos per channel
    total = 0

    print(f"V1 Collection: {len(SEED_KEYWORDS)} keywords")
    print("=" * 50)

    with open(OUT, "w") as f:
        for i, kw in enumerate(SEED_KEYWORDS):
            print(f"[{i+1}/{len(SEED_KEYWORDS)}] '{kw}'...")
            try:
                videos = fetch_videos(kw)
                new = 0
                for v in videos:
                    # Skip if already seen
                    if v["id"] in seen_ids:
                        continue
                    # Limit videos per channel to avoid single-creator dominance
                    ch = v["channel_id"]
                    if seen_channels.get(ch, 0) >= 10:
                        continue

                    seen_ids.add(v["id"])
                    seen_channels[ch] = seen_channels.get(ch, 0) + 1
                    f.write(json.dumps(v) + "\n")
                    new += 1

                total += new
                print(f"  +{new} new (total: {total}, channels: {len(seen_channels)})")
                time.sleep(0.4)  # Slightly slower to avoid rate limits

            except Exception as e:
                print(f"  Error: {e}")
                time.sleep(2)

            # Progress checkpoint every 50 keywords
            if (i + 1) % 50 == 0:
                print(f"\n--- Checkpoint: {total} videos from {len(seen_channels)} channels ---\n")

    print("=" * 50)
    print(f"Done. {total} unique videos from {len(seen_channels)} channels")
    print(f"Saved to {OUT}")


if __name__ == "__main__":
    main()
