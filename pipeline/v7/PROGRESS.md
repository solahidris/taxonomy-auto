# V7 Pipeline Progress: 3R Framework Classification

## Overview
Building a classification system for post-ingest video data using the **3R Framework**:
- **R1: Reproducible** - Can a business make this content?
- **R2: Relatable** - Will their audience care?
- **R3: Repeatable** - Can they do this weekly/monthly?

Plus existing **Seasonal** classification.

## Data Sources
| File | Bucket | Duration | Count |
|------|--------|----------|-------|
| `sample_data/fitness_short.jsonl` | short | 31-90 seconds | 25 videos |
| `sample_data/fitness_super_short.jsonl` | super_short | ≤30 seconds | 37 videos |
| **Total** | | | **62 videos** |

## Pipeline Steps

### Step 1: Fetch Subtitles
**Status:** NOT STARTED
**Script:** `pipeline/v7/2_fetch_subtitles.py`

Some videos have `subtitleInformation` with URLs to WebVTT subtitle files.
We need to:
1. Read both JSONL files
2. Extract subtitle URLs (prefer English `eng-US`)
3. Fetch and parse WebVTT content
4. Save enriched data with transcripts

**Output:** `data/v7/videos_with_subtitles.json`

### Step 2: Classify with 3R Framework
**Status:** NOT STARTED
**Script:** `pipeline/v7/3_classify_3r.py`

Use LLM (GPT-4) to classify each video on:

#### R1: Reproducible (1-5 score)
- `production_complexity`: LOW / MEDIUM / HIGH
- `requires_special_access`: boolean (celebrity, location, equipment)
- `format_type`: string (tutorial, listicle, montage, story, etc.)
- `reason`: string

#### R2: Relatable (1-5 score)
- `core_topic`: string (the problem/topic addressed)
- `appeal_type`: PERSONALITY_DRIVEN / TOPIC_DRIVEN
- `target_industries`: string[] (fitness studio, supplement brand, etc.)
- `reason`: string

#### R3: Repeatable (1-5 score)
- `creator_has_similar`: number (inferred from format)
- `format_is_common`: boolean
- `trend_dependent`: boolean
- `reason`: string

**Input:** Video title, description, hashtags, subtitles (if available), duration
**Output:** `data/v7/3r_classification.json`

### Step 3: API Endpoint
**Status:** NOT STARTED
**File:** `pages/api/v7/3r.ts`

Serve the classification data to the frontend.

### Step 4: Update V7 UI
**Status:** NOT STARTED

Add:
- Duration bucket selector (short vs super_short)
- 3R filter cards with scores
- Video list with 3R badges

---

## Current Progress

### 2026-05-25 - Session Start
- [x] Analyzed sample data structure
- [x] Added 3R framework types to V7 UI
- [x] Added 3R overview cards to V7 Demo
- [x] Created subtitle fetcher (`2_fetch_subtitles.py`)
  - Fetched subtitles for 62 videos
  - Only 3 had subtitles available (all super_short)
- [x] Created 3R classifier (`3_classify_3r.py`)
  - Classified all 62 videos using GPT-4o-mini
  - Average scores: R1=4.23, R2=4.85, R3=4.13
- [x] Created API endpoint (`/api/v7/3r`)
- [x] Updated V7Demo UI with full 3R display
  - Shows average scores by bucket
  - Distribution charts (format types, complexity, appeal)
  - Filterable video list with scores
  - Links to original TikTok videos

### Results Summary
| Metric | Short (31-90s) | Super Short (≤30s) |
|--------|---------------|-------------------|
| Count | 25 | 37 |
| Avg Reproducible | 4.04 | 4.35 |
| Avg Relatable | 4.96 | 4.78 |
| Avg Repeatable | 4.08 | 4.16 |

---

## Notes

### Subtitle URL Structure
From the data, subtitles are available at:
```
raw_apify.subtitleInformation[].url
```

Prefer:
- `is_original_caption: true`
- `lang: "eng-US"` or `language_code: "en"`
- `caption_format: "webvtt"`

### Video Fields Available for Classification
- `text.description` - The caption/description
- `text.hashtags[]` - Array of hashtag strings
- `video.duration_seconds` - Video length
- `engagement.*` - View/like/comment counts
- `author.handle` - Creator username
- Subtitles (if fetched) - Spoken content

### LLM Prompt Strategy
Feed the model:
1. Video description
2. Hashtags
3. Subtitle transcript (if available)
4. Duration bucket

Ask for structured JSON output with all 3R scores and reasons.
