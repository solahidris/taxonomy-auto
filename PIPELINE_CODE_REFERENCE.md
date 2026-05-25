# Pipeline Code Reference Guide

## Quick Reference: What Each V1 Step Does

### Step 1: Collect (`1_collect.py`)
```python
# Input: 200+ seed keywords
# Process: YouTube API search for each keyword
# Output: raw_videos.jsonl (JSONL format, one video per line)

Output format:
{
  "id": "abc123xyz",
  "title": "How to Build Muscle Fast",
  "description": "Learn the best techniques for muscle growth...",
  "tags": ["fitness", "gym", "workout", "muscle"],
  "seed_keyword": "gym motivation",
  "channel_id": "UCabc123",
  "channel_title": "Fitness Channel",
  "view_count": 1500000,
  ...
}
```

### Step 2: Embed (`2_embed.py`)
```python
# Input: raw_videos.jsonl (20-30K videos)
# Process: Combine fields and embed with OpenAI
# Output: Two files

# embeddings.npy - NumPy array
# Shape: (N_videos, 1536)
# Contains the vector representation of each video

# metadata.json - Lightweight metadata for reference
[
  {
    "id": "abc123xyz",
    "title": "How to Build Muscle Fast",
    "seed_keyword": "gym motivation",
    "tags": ["fitness", "gym"],
    "channel_id": "UCabc123",
    "channel_title": "Fitness Channel"
  },
  ...
]
```

### Step 3: Cluster (`3_cluster.py`)
```python
# Input: embeddings.npy + metadata.json
# Process: Hierarchical clustering

# Level 1: K-Means (k=20) finds 20 broad categories
#   "Fitness", "Cooking", "Tech", "Business", etc.

# Level 2: For EACH category, K-Means (k=5-8) finds subcategories
#   Fitness → "Strength", "Cardio", "Yoga", "Nutrition"

# Level 3: For EACH subcategory, HDBSCAN finds micro-niches
#   Strength → "Calisthenics Beginner", "Powerlifting Intermediate", ...

# Output: clusters.json
{
  "niche_0": {
    "category_id": 0,
    "category_name": "Fitness",
    "subcategory_id": 0,
    "subcategory_name": "Strength Training",
    "indices": [14, 28, 45, 67, ...],  # Video indices in this niche
    "count": 127,
    "sample_titles": [
      "Beginner Push-Up Progressions",
      "Perfect Your Pull-Up Form",
      "Building Strength at Home"
    ],
    "sample_tags": ["pushup", "pullup", "strength", "calisthenics"],
    "sample_channels": ["Calisthenics Movement", "Strength Academy"],
    "centroid": [0.142, -0.087, 0.293, ...],  # 1536-dim embedding
  },
  "niche_1": { ... },
  ...
}
```

### Step 4: Name (`4_name.py`)
```python
# Input: clusters.json + metadata.json
# Process: For EACH cluster, send to GPT-4o-mini:

PROMPT = """
Here are sample videos from a cluster:
1. "Beginner Push-Up Progressions" (calisthenics, workout)
2. "Perfect Your Pull-Up Form" (strength, tutorial)
3. "Building Strength at Home" (no equipment, training)

Based on these samples:
1. Name this cluster/niche
2. What category does it belong to?
3. What subcategory?
4. Who are the top 10 creators?
"""

# Output: taxonomy.json
{
  "categories": [
    {
      "id": 0,
      "name": "Fitness",
      "description": "Physical fitness and exercise content",
      "niche_count": 127
    },
    ...
  ],
  "stats": {
    "total_categories": 20,
    "total_subcategories": 150,
    "total_niches": 500,
    "total_videos": 23450,
    "coverage_percent": 95.2
  },
  "niches": {
    "niche_0": {
      "id": "niche_0",
      "name": "Calisthenics for Beginners",
      "category": "Fitness",
      "category_id": 0,
      "subcategory": "Strength Training",
      "subcategory_id": 0,
      "description": "Bodyweight strength training tutorials focusing on fundamentals",
      "centroid": [...],
      "video_count": 127,
      "exemplar_creators": [
        {
          "channel_id": "UCabc123",
          "channel_title": "Calisthenics Movement",
          "video_count": 24
        },
        ...
      ]
    },
    ...
  }
}
```

### Step 5: Classify (`5_classify.py`)
```python
# Input: taxonomy.json (with centroids) + user query
# Process: Runtime multi-label classification

INPUT = "I make beginner-friendly calisthenics tutorials"

# 1. Embed the input
user_embedding = embed(INPUT)  # 1536-dim vector

# 2. Compute cosine similarity to all niche centroids
similarities = [
  ("Calisthenics for Beginners", 0.78),
  ("Strength Training Basics", 0.71),
  ("Bodyweight Exercises", 0.68),
  ("Fitness Motivation", 0.45),
  ("Gym Workouts", 0.32)
]

# 3. Return top matches with confidence calibration
OUTPUT = {
  "matches": [
    {
      "niche": "Calisthenics for Beginners",
      "confidence": 92.5,
      "category": "Fitness",
      "similarity": 0.78,
      "exemplar_creators": [
        {"channel_title": "Calisthenics Movement", "video_count": 24}
      ]
    },
    {
      "niche": "Strength Training Basics",
      "confidence": 85.3,
      "category": "Fitness",
      "similarity": 0.71,
      ...
    },
    ...
  ],
  "unknown_niche_flag": false  # Is this a new niche?
}
```

### Step 6: Evaluate (`6_evaluate.py`)
```python
# Input: taxonomy.json + embeddings.npy + metadata.json
# Process: Compute quality metrics

OUTPUT = {
  "coverage": {
    "videos_covered": 22305,
    "videos_total": 23450,
    "coverage_percent": 95.2
  },
  "hierarchy": {
    "total_categories": 20,
    "total_subcategories": 150,
    "total_niches": 500,
    "avg_niches_per_category": 25,
    "avg_niches_per_subcategory": 3.3
  },
  "balance": {
    "gini_coefficient": 0.48,        # 0=perfect balance, 1=all in one
    "entropy": 5.24,                 # Higher = more balanced
    "interpretation": "balanced"
  },
  "niche_sizes": {
    "min": 5,
    "max": 850,
    "mean": 44.6,
    "median": 23,
    "std": 78.4
  },
  "clustering_quality": {
    "silhouette_score": 0.34,
    "calinski_harabasz_score": 12.4
  },
  "stability": {
    "seed_1_ari": 0.91,    # Agreement with seed=1
    "seed_2_ari": 0.89,    # Agreement with seed=2
    "seed_3_ari": 0.87,    # Agreement with seed=3
    "avg_stability": 0.89   # Consistent across runs
  }
}
```

---

## V7 Classification Scripts (Feature-Based)

### Script 1: Seasonal Classification (`1_classify_seasonal.py`)

```python
# Input: TikTok videos with 100K+ views
# Process: Batch classification with LLM

PROMPT = """
Classify each video:
- EVERGREEN: Timeless (how-tos, routines, tutorials)
- TREND: Based on viral TikTok trends (challenges, dances)
- CALENDAR: Tied to seasons/holidays (summer, Christmas)
- MOMENT: Specific news event or moment (lockdown, year goals)

Videos:
1. "Christmas Gift Ideas for Fitness Lovers" #ChristmasGifts
2. "5-Minute Workout You Can Do Anywhere" #fitnesshacks
3. "The 75 Hard Challenge - Day 5 Update" #75hard
...
"""

OUTPUT = {
  "classifications": [
    {
      "index": 1,
      "type": "CALENDAR",
      "reason": "Content is seasonal (Christmas-specific)"
    },
    {
      "index": 2,
      "type": "EVERGREEN",
      "reason": "Workout tips applicable year-round"
    },
    {
      "index": 3,
      "type": "TREND",
      "reason": "Based on viral 75 Hard challenge"
    },
    ...
  ]
}
```

### Script 2: Fetch Subtitles (`2_fetch_subtitles.py`)

```python
# Input: TikTok video data with subtitle URLs
# Process: Download and parse WebVTT files

# Extract from video data:
subtitle_info = {
  "url": "https://...",
  "lang": "eng-US",
  "format": "webvtt",
  "is_original": true
}

# Fetch and parse:
response = requests.get(subtitle_info["url"])
webvtt_content = response.text

# Parse WebVTT:
"""
WEBVTT

00:00:00.000 --> 00:00:05.000
Hey everyone, today I'm showing you

00:00:05.000 --> 00:00:10.000
my favorite 5-minute workout routine
"""

# Output: Plain text transcript
"Hey everyone, today I'm showing you my favorite 5-minute workout routine"

# Save enriched videos:
{
  "id": "video_123",
  "title": "...",
  "description": "...",
  "transcript": "...",  # NEW: Fetched subtitle text
  "duration_seconds": 42,
  "bucket": "super_short"
}
```

### Script 3: 3R Classification (`3_classify_3r.py`)

```python
# Input: Video metadata + optional transcripts
# Process: Score on 3 dimensions

PROMPT = """
Classify this fitness video:

Title: "5-Minute Ab Workout at Home"
Tags: #abs #workout #fitness #shorts
Duration: 47 seconds (short format)
Transcript: "Hey guys, here's my favorite ab routine..."

R1: REPRODUCIBLE (1-5)
- Can a typical fitness business make this?
- Complexity, special access needed?

R2: RELATABLE (1-5)
- Will audience care about this topic?
- Appeal: personality or topic-driven?

R3: REPEATABLE (1-5)
- Can they make 10+ variations?
- Format commonly used?

Respond with JSON only:
{
  "reproducible": {
    "score": 4,
    "production_complexity": "LOW",
    "requires_special_access": false,
    "format_type": "tutorial",
    "reason": "Simple ab exercises, minimal equipment"
  },
  "relatable": {
    "score": 5,
    "core_topic": "Quick home workouts",
    "appeal_type": "TOPIC_DRIVEN",
    "target_industries": ["fitness", "health", "gym"],
    "reason": "Home workouts appeal to broad audience"
  },
  "repeatable": {
    "score": 4,
    "creator_has_similar": 15,
    "format_is_common": true,
    "trend_dependent": false,
    "reason": "Ab exercises are evergreen, format is standard"
  }
}
"""

OUTPUT = {
  "video_id": "video_123",
  "scores": {
    "reproducible": 4,
    "relatable": 5,
    "repeatable": 4,
    "overall": 4.3
  },
  "dimensions": {
    "reproducible": {
      "production_complexity": "LOW",
      "requires_special_access": false,
      "format_type": "tutorial",
      "reason": "..."
    },
    "relatable": { ... },
    "repeatable": { ... }
  }
}
```

---

## Data Structure Reference

### Raw Video Format (V1 Input)
```json
{
  "id": "XY-abc123",
  "title": "How to Build Muscle Fast",
  "description": "Learn the best techniques for muscle growth...",
  "tags": ["fitness", "gym", "workout"],
  "seed_keyword": "gym motivation",
  "channel_id": "UCxyz123",
  "channel_title": "Fitness Pro Channel",
  "view_count": 1500000,
  "like_count": 45000,
  "comment_count": 2300
}
```

### Taxonomy Format (V1 Output)
```json
{
  "categories": [
    {
      "id": 0,
      "name": "Fitness",
      "niche_count": 127
    }
  ],
  "niches": {
    "niche_0": {
      "id": "niche_0",
      "name": "Calisthenics for Beginners",
      "category": "Fitness",
      "subcategory": "Strength Training",
      "centroid": [0.14, -0.09, ...],
      "video_count": 127,
      "exemplar_creators": [
        {
          "channel_id": "UCxyz",
          "channel_title": "Channel Name",
          "video_count": 24
        }
      ]
    }
  },
  "stats": {
    "total_categories": 20,
    "total_subcategories": 150,
    "total_niches": 500
  }
}
```

### Embeddings Format (V1 Step 2 Output)
```python
# embeddings.npy is a NumPy binary file
import numpy as np
embeddings = np.load('data/v1/embeddings.npy')
# Shape: (23450, 1536)
# Each row is a video's embedding vector
# Type: float32

# Access a single video's embedding:
video_0_embedding = embeddings[0]  # Shape: (1536,)
```

---

## Classification Logic (Cosine Similarity)

```python
import numpy as np
from sklearn.preprocessing import normalize

# Load taxonomy centroids
taxonomycentroids = {
  "niche_0": np.array([0.14, -0.09, 0.21, ...]),  # 1536-dim
  "niche_1": np.array([0.05, 0.12, -0.08, ...]),
  ...
}

# Embed user query
user_text = "I make beginner calisthenics tutorials"
user_embedding = embed_with_openai(user_text)  # 1536-dim

# Normalize both
user_embedding_norm = normalize(user_embedding.reshape(1, -1))[0]
centroid_norms = {
  niche_id: normalize(vec.reshape(1, -1))[0]
  for niche_id, vec in taxonomy_centroids.items()
}

# Compute similarities
similarities = {
  niche_id: np.dot(user_embedding_norm, centroid_norm)
  for niche_id, centroid_norm in centroid_norms.items()
}

# Get top-5
top_5 = sorted(similarities.items(), key=lambda x: -x[1])[:5]
# Result: [("niche_0", 0.78), ("niche_5", 0.71), ...]
```

---

## Key Differences: V1 vs V7

| Aspect | V1 (Taxonomy) | V7 (Classification) |
|--------|---------------|-------------------|
| **Purpose** | Build a niche hierarchy | Evaluate video properties |
| **Input** | Raw video metadata | Pre-processed video data |
| **Clustering** | K-Means + HDBSCAN | None |
| **Output** | `taxonomy.json` (500 niches) | `3r_classification.json` (scores) |
| **Use Case** | "What niches exist?" | "Can a business make this?" |
| **Completeness** | 100% | 50% (missing hierarchy) |

