# Taxonomy Pipeline Analysis: V7 Current State & Full Workflow

## Executive Summary

The V7 pipeline is currently **incomplete** and focuses on **fitness video classification** (TikTok data). It has 4 scripts dealing with seasonal/3R classification but is **missing the core taxonomy generation steps** that exist in V1.

**Current Status**: Partial feature classification (seasonal, 3R framework) - NOT a complete taxonomy pipeline yet.

---

## 1. V7 Pipeline Scripts (Current)

### Files in `/pipeline/v7/`

| Script | Status | Purpose | Input | Output |
|--------|--------|---------|-------|--------|
| `1_classify_seasonal.py` | Complete ✓ | Classify videos as EVERGREEN/TREND/CALENDAR/MOMENT | `data/v5/tiktok_raw.jsonl` (100K+ views) | `data/v7/seasonal_classification.json` |
| `2_fetch_subtitles.py` | Complete ✓ | Fetch WebVTT subtitles from TikTok videos | `sample_data/fitness_short_all.jsonl`, `fitness_super_short_all.jsonl` | `data/v7/videos_with_subtitles.jsonl` |
| `3_classify_3r.py` | Complete ✓ | Apply 3R Framework (Reproducible, Relatable, Repeatable) | `data/v7/raw_videos.jsonl` | `data/v7/3r_classification.json` |
| `4_classify_seasonal.py` | Duplicate | Alternative seasonal classifier | Same as #1 | Same as #1 |

**Key Insight**: V7 is NOT building a taxonomy. It's classifying existing videos into categorical systems (seasonal, 3R scores).

---

## 2. Full Taxonomy Pipeline Workflow (From V1)

### The Complete 6-Step Process

V1 shows the **complete pattern** for building taxonomies. After seasonal classification, you need:

```
Step 1: Collect          → Raw video metadata from YouTube API (20K-30K videos)
         ↓
Step 2: Embed            → Convert text to vectors using OpenAI embeddings
         ↓
Step 3: Cluster          → Hierarchical clustering (K-Means → HDBSCAN)
         ↓
Step 4: Name/Categorize  → Use LLM to name clusters (categories, subcategories, niches)
         ↓
Step 5: Classify*        → Build multi-label classifier for new items
         ↓
Step 6: Evaluate         → Compute quality metrics (coverage, balance, coherence)
```

*Step 5 is optional (runtime classification) and not always run during pipeline.

---

## 3. V1 Pipeline: Detailed Workflow

### Step 1: Collect (`1_collect.py`)
- **Purpose**: Gather video metadata from YouTube API
- **Input**: ~200 seed keywords organized by vertical
- **Process**:
  - Search YouTube for each keyword
  - Collect title, description, tags, channel info, view counts
  - Filter for quality (minimum views, proper channels)
- **Output**: `data/v1/raw_videos.jsonl`
  - Each line: `{"id": "...", "title": "...", "description": "...", "tags": [], "seed_keyword": "...", ...}`
  - Target: 20-30K videos

### Step 2: Embed (`2_embed.py`)
- **Purpose**: Convert video metadata to vector embeddings
- **Input**: `data/v1/raw_videos.jsonl`
- **Process**:
  - Combine title + description + tags into single text
  - Call `text-embedding-3-small` (OpenAI)
  - Batch request (~100 videos per request) for efficiency
- **Output**: 
  - `data/v1/embeddings.npy` - NumPy array of shape (N_videos, 1536)
  - `data/v1/metadata.json` - Video metadata (id, title, channel, tags)
- **Cost**: ~$0.08 for 20K videos

### Step 3: Cluster (`3_cluster.py`)
- **Purpose**: Organize videos into hierarchical niche structure
- **Process**: Recursive clustering at 4 levels:

  ```
  Level 1 (K-Means, k=20)
  ├─ Category 1
  │  ├─ Level 2 (K-Means, k=5-8)
  │  │  ├─ Subcategory 1.1
  │  │  │  ├─ Level 3 (HDBSCAN, min_size=5)
  │  │  │  │  ├─ Micro-niche 1.1.1
  │  │  │  │  └─ Micro-niche 1.1.2
  │  │  │  └─ Subcategory 1.2
  │  │  └─ Subcategory 1.3
  │  └─ Level 2 continues...
  └─ Category 2...
  ```

- **Inputs**: 
  - `embeddings.npy` - Video embeddings
  - `metadata.json` - Video info
- **Output**: `data/v1/clusters.json`
  ```json
  {
    "niche_0": {
      "category_id": 0,
      "category_name": "Fitness",
      "indices": [0, 1, 2, ...],
      "sample_titles": ["..."],
      "centroid": [0.1, 0.2, ...],
      "count": 450
    }
  }
  ```

### Step 4: Name (`4_name.py`)
- **Purpose**: Use LLM to assign meaningful names to clusters
- **Input**: 
  - `data/v1/clusters.json` - Cluster data with sample videos
  - `data/v1/metadata.json` - Full metadata
- **Process**:
  - For each cluster, extract top sample videos
  - Send to GPT-4o-mini with context: "Here are sample videos from a cluster. Name this cluster. Extract top 10 creators."
  - Get back: cluster name, subcategory, niche name, top creators
- **Output**: `data/v1/taxonomy.json`
  ```json
  {
    "categories": [...],
    "stats": {
      "total_categories": 20,
      "total_subcategories": 150,
      "total_niches": 500
    },
    "niches": {
      "niche_0": {
        "id": "niche_0",
        "category": "Fitness",
        "subcategory": "Strength Training",
        "name": "Calisthenics for Beginners",
        "description": "...",
        "centroid": [...],
        "video_count": 450,
        "exemplar_creators": [
          {"id": "channel_123", "name": "FitnessPro", "video_count": 45}
        ]
      }
    }
  }
  ```

### Step 5: Classify (`5_classify.py`)
- **Purpose**: Built-in multi-label classifier for new creators/content
- **Input**: User text (creator bio or content description)
- **Process**:
  - Embed user text using same `text-embedding-3-small` model
  - Compute cosine similarity to all niche centroids
  - Return top-5 matches with confidence scores
  - Flag unknown items (open-set detection)
- **Output**: JSON response
  ```json
  {
    "matches": [
      {
        "niche": "Calisthenics for Beginners",
        "confidence": 92.5,
        "category": "Fitness",
        "exemplar_creators": [...]
      }
    ],
    "unknown_niche_flag": false
  }
  ```

### Step 6: Evaluate (`6_evaluate.py`)
- **Purpose**: Assess taxonomy quality
- **Metrics Computed**:
  - **Coverage**: % of videos successfully assigned
  - **Balance**: Gini coefficient, entropy (how evenly distributed)
  - **Hierarchy**: Avg niches per category, depth stats
  - **Clustering Quality**: Silhouette score, Calinski-Harabasz index
  - **Stability**: Re-run clustering with different seeds, measure consistency
- **Output**: Console report
  ```
  Total niches: 500
  Total categories: 20
  Coverage: 95%
  Gini coefficient: 0.48 (balanced)
  Avg niches per category: 25
  ```

---

## 4. Missing Steps for V7 to Become a Complete Taxonomy Pipeline

V7 currently has **feature classification** but is missing the **taxonomic structure**. To complete it:

### Missing: Step 3 - Hierarchical Clustering
**Status**: NOT IMPLEMENTED

**Purpose**: Build the niche hierarchy from embeddings

**What's needed**:
- Load the 62 fitness videos with their embeddings
- Run K-Means (k=5-8) for fitness categories (e.g., cardio, strength, yoga, nutrition, motivation)
- For each category, run HDBSCAN to find micro-niches
- Output: `data/v7/fitness_clusters.json`

**Why this matters**: Right now V7 classifies videos individually (3R scores, seasonal). It doesn't organize them into a structured taxonomy.

### Missing: Step 4 - Taxonomy Generation
**Status**: NOT IMPLEMENTED

**Purpose**: Name clusters and create final taxonomy structure

**What's needed**:
- Read clusters from Step 3
- Use GPT-4o-mini to name each cluster based on sample videos
- Create final taxonomy: `data/v7/fitness_taxonomy.json`
- Include exemplar creators per niche

### Missing: Step 5 - Classification API
**Status**: PARTIALLY DONE (exists at `pages/api/v7/3r.ts`)

**What's needed**:
- Extend API to serve the taxonomy (not just 3R scores)
- Add endpoint to classify new fitness videos into the taxonomy
- Could combine 3R scores + taxonomy classification

### Missing: Step 6 - Evaluation
**Status**: NOT IMPLEMENTED

**What's needed**:
- Compute taxonomy metrics (coverage, balance, granularity)
- Test multi-label classification on held-out videos
- Report coherence of the fitness niche taxonomy

---

## 5. Data Flow Comparison: V1 vs V7

### V1 (Full Taxonomy Pipeline)
```
YouTube API (200 keywords)
         ↓
    20-30K videos
         ↓
   OpenAI Embeddings
         ↓
  K-Means (20) + HDBSCAN
         ↓
   500 leaf niches
         ↓
  GPT-4 Naming (multi-level)
         ↓
   Final Taxonomy (500 niches)
         ↓
   Multi-label Classifier
         ↓
   Evaluation Metrics
```

### V7 (Currently: Feature Classification Only)
```
TikTok API (fitness videos)
         ↓
    62 sample videos
         ↓
  WebVTT Subtitles (3/62)
         ↓
   OpenAI Embeddings [MISSING in pipeline]
         ↓
  GPT-4 3R Classification
  GPT-4 Seasonal Classification
         ↓
   3R Scores + Seasonal Labels
         ↓
   [NO HIERARCHY/TAXONOMY]
         ↓
   UI Display of Scores
```

---

## 6. Recommended Next Steps for V7

### Option A: Complete Taxonomy Generation (5-6 hours)
1. Create `5_embed_fitness.py` - Embed the 62 fitness videos
2. Create `6_cluster_fitness.py` - Build 2-3 level hierarchy
3. Create `7_name_fitness_taxonomy.py` - Name the hierarchy
4. Update `pages/api/v7/taxonomy.ts` - Serve taxonomy
5. Update UI to show both 3R scores AND taxonomy membership

### Option B: Lightweight Taxonomy (2-3 hours)
1. Use the 3R scores to create a simple 1-level taxonomy:
   - "High Reproducibility, High Relatability" → B2B Friendly
   - "High Reproducibility, Low Relatability" → Niche
   - etc.
2. Group videos by this taxonomy
3. Name groups manually (don't use LLM)

### Option C: Extend to Full-Scale (20-30 hours)
1. Collect 10K+ fitness videos (not just 62)
2. Run full 6-step V1 pipeline
3. Have a complete, production-ready fitness taxonomy

---

## 7. Key Files to Reference

### V1 Templates
- `/pipeline/v1/1_collect.py` - Video collection pattern
- `/pipeline/v1/2_embed.py` - Embedding strategy
- `/pipeline/v1/3_cluster.py` - Hierarchical clustering code
- `/pipeline/v1/4_name.py` - LLM naming pattern
- `/pipeline/v1/5_classify.py` - Classification logic
- `/pipeline/v1/6_evaluate.py` - Evaluation metrics

### V7 Existing
- `/pipeline/v7/1_classify_seasonal.py` - Feature classification
- `/pipeline/v7/2_fetch_subtitles.py` - Data enrichment
- `/pipeline/v7/3_classify_3r.py` - 3R framework classification
- `/pages/api/v7/3r.ts` - API endpoint for 3R data

### Data Locations
- **V1 Input**: `data/v1/raw_videos.jsonl`
- **V7 Input**: `sample_data/fitness_short_all.jsonl`, `fitness_super_short_all.jsonl`
- **V1 Output**: `data/v1/taxonomy.json`, `data/v1/embeddings.npy`
- **V7 Current Output**: `data/v7/3r_classification.json`

---

## 8. Cost Estimates (if building full V7 taxonomy)

| Step | Task | Cost |
|------|------|------|
| Embed 62 videos | OpenAI embeddings | ~$0.01 |
| 3R Classification | GPT-4o-mini (62 × 1 request) | ~$0.20 |
| Naming | GPT-4o-mini (naming 5-8 clusters) | ~$0.10 |
| **Total** | | **~$0.31** |

---

## Summary Table: V1 vs V7

| Aspect | V1 | V7 |
|--------|----|----|
| **Scope** | Full 6-step pipeline | Partial (feature classification) |
| **Input** | 20-30K YouTube videos | 62 TikTok fitness videos |
| **Clustering** | 4-level hierarchy (K-Means + HDBSCAN) | NONE |
| **Output** | 500 niches in taxonomy.json | 3R scores + seasonal labels |
| **Use Case** | Discover creator niches | Evaluate fitness video properties |
| **Completeness** | 100% (production-ready) | 50% (missing taxonomy steps) |

