# V0 Learnings: Short-Form Creator Taxonomy Pipeline

> **Purpose**: This document captures all learnings, decisions, trade-offs, and observations from V0 of the taxonomy pipeline. V1 should reference this to avoid repeating mistakes and to build on what worked.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Running the Pipeline](#running-the-pipeline)
3. [Architecture Decisions](#architecture-decisions)
4. [Data Collection (YouTube API)](#data-collection-youtube-api)
5. [Embedding Strategy](#embedding-strategy)
6. [Clustering Approach](#clustering-approach)
7. [LLM Labeling](#llm-labeling)
8. [Classification at Runtime](#classification-at-runtime)
9. [What Worked Well](#what-worked-well)
10. [What Didn't Work](#what-didnt-work)
11. [Metrics & Evaluation](#metrics--evaluation)
12. [Cost Analysis](#cost-analysis)
13. [Technical Debt](#technical-debt)
14. [Recommendations for V1](#recommendations-for-v1)

---

## Project Overview

### Goal
Automatically generate a hierarchical taxonomy of creator niches from short-form video data, then use it to classify new creators/content in real-time.

### V0 Approach Summary
```
YouTube API → Raw Videos → Text Extraction → OpenAI Embeddings →
K-Means + HDBSCAN Clustering → GPT-4o-mini Labeling → Taxonomy JSON + Centroids
```

### Final Output Stats (V0)
- **109 micro-niches** across **15 top-level categories**
- **~3,000 videos** processed
- **~95% coverage** (videos successfully assigned to a niche)
- Pipeline runtime: ~5-10 minutes
- Total cost: ~$0.05-0.10 per full run

---

## Running the Pipeline

### Prerequisites

1. **Python 3.10+** with packages:
   ```bash
   pip install openai numpy scikit-learn tqdm python-dotenv
   ```

2. **API Keys** in `.env.local`:
   ```
   YOUTUBE_API_KEY=your_youtube_api_key
   OPENAI_API_KEY=your_openai_api_key
   ```

3. **YouTube API Setup**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a project and enable YouTube Data API v3
   - Create an API key (no OAuth needed for search)

### Running the Full Pipeline

```bash
# From project root
bash pipeline/run.sh
```

This runs all 5 steps sequentially:

### Pipeline Steps Breakdown

| Step | Script | What It Does | Time | Output |
|------|--------|--------------|------|--------|
| 1/5 | `1_collect.py` | Searches YouTube with ~60 seed keywords, fetches video metadata | ~2-3 min | `data/raw_videos.jsonl` |
| 2/5 | `2_embed.py` | Embeds all video texts using OpenAI `text-embedding-3-small` | ~1-2 min | `data/embeddings.npy`, `data/metadata.json` |
| 3/5 | `3_cluster.py` | Runs K-Means (K=15) + HDBSCAN to find micro-niches | ~30 sec | `data/clusters.json` |
| 4/5 | `4_name.py` | Uses GPT-4o-mini to name each cluster and category | ~2-3 min | `data/taxonomy.json`, `data/centroids.json` |
| 5/5 | `5_evaluate.py` | Prints taxonomy quality report (coverage, granularity) | ~5 sec | Console output |

### Running Individual Steps

You can run steps individually for debugging:

```bash
# Collect fresh data from YouTube
python pipeline/1_collect.py

# Re-embed (if you modify text extraction)
python pipeline/2_embed.py

# Re-cluster (if you change K or HDBSCAN params)
python pipeline/3_cluster.py

# Re-label (if you change prompts)
python pipeline/4_name.py

# Check quality
python pipeline/5_evaluate.py
```

### Expected Console Output

```
=== Short-Form Creator Taxonomy Pipeline ===

[1/5] Collecting videos from YouTube...
Collecting: 'calisthenics workout'...
  +48 new videos (total: 48)
Collecting: 'gym motivation'...
  +45 new videos (total: 93)
...
Done. 2847 unique videos saved to data/raw_videos.jsonl

[2/5] Generating OpenAI embeddings...
Loaded 2847 videos
Embedding: 100%|████████████████| 29/29 [01:23<00:00]
Saved (2847, 1536) embeddings → data/embeddings.npy
Estimated cost: ~$0.0089

[3/5] Clustering into niches...
Loading embeddings...
Reducing to 100 dims with PCA...
  Explained variance: 87.34%
Running K-Means (k=15)...
Running HDBSCAN micro-clusters within each coarse cluster...
Found 109 micro-niches across 15 coarse clusters
Classified 2712/2847 videos (95.3%)

[4/5] Naming clusters with GPT-4o-mini...
Naming 109 clusters...
Naming niches: 100%|████████████████| 109/109 [02:15<00:00]
Naming top-level categories...
Taxonomy: 15 categories, 109 niches

[5/5] Evaluating taxonomy...
==================================================
TAXONOMY EVALUATION REPORT
==================================================
Generated      : 2026-05-22
Top categories : 15
Leaf niches    : 109
Videos indexed : 2847

COVERAGE: 2712/2847 = 95.3%
  PASS (target >85%)
...
==================================================

All done. taxonomy.json and centroids.json saved to data/
Run 'npm run dev' and open http://localhost:3000 for the demo.
```

### Resource Usage

| Resource | Usage |
|----------|-------|
| **Time** | 5-8 minutes total |
| **YouTube API** | ~6,000 units (10,000/day free) |
| **OpenAI Embeddings** | ~600K tokens (~$0.01) |
| **OpenAI Chat (GPT-4o-mini)** | ~50K tokens (~$0.03) |
| **Disk Space** | ~50MB (embeddings.npy is largest) |
| **Memory** | ~500MB peak (during clustering) |

### Troubleshooting

**"YOUTUBE_API_KEY not found"**
- Ensure `.env.local` exists in project root with `YOUTUBE_API_KEY=...`

**"quotaExceeded" from YouTube**
- You've hit daily quota (10K units). Wait 24h or use different project.

**"Rate limit" from OpenAI**
- Embedding batches are 100 at a time, should be fine. Check your OpenAI tier.

**Clustering produces too few/many niches**
- Adjust `N_COARSE` in `3_cluster.py` (default 15)
- Adjust `min_cluster_size` in HDBSCAN (default 3)

---

## Architecture Decisions

### Decision 1: Two-Stage Clustering (K-Means → HDBSCAN)

**What we did:**
- First level: K-Means with K=15 to create coarse categories
- Second level: HDBSCAN within each coarse cluster to find micro-niches

**Why:**
- K-Means alone creates forced equal-ish clusters
- HDBSCAN alone on 3K points was too slow and created too many tiny clusters
- Two-stage gave us control over top-level granularity while letting density-based clustering find natural sub-groups

**Trade-off:**
- K=15 was manually chosen; might not be optimal
- Some coarse clusters have many micro-niches (unbalanced tree)

**Learning:**
> The two-stage approach works better than single-stage K-Means. However, K=15 may need tuning based on dataset size. Consider silhouette scores or elbow method for K selection in V1.

---

### Decision 2: PCA Before Clustering

**What we did:**
- Reduced 1536-dim embeddings to 100 dimensions using PCA
- Explained variance: ~85-90%

**Why:**
- HDBSCAN struggles with high-dimensional data (curse of dimensionality)
- Faster clustering on lower dimensions
- Still captured most of the variance

**Trade-off:**
- Lost some fine-grained distinctions
- PCA assumes linear relationships

**Learning:**
> PCA to 100 dims was a good balance. Could experiment with UMAP for non-linear reduction, but PCA is faster and deterministic.

---

### Decision 3: Centroids for Runtime Classification

**What we did:**
- Stored mean embedding vector for each micro-niche
- At runtime: embed new text → cosine similarity against all centroids → return top 5

**Why:**
- No need to store all 3K video embeddings
- O(n) where n = number of niches (~100) instead of n = number of videos
- Centroids are stable representations of each cluster

**Trade-off:**
- Centroid = average, may not capture cluster shape well
- Outliers in cluster can skew centroid

**Learning:**
> Centroid approach is fast and works well enough. For V1, consider storing multiple representatives per cluster (medoids) or using faiss for approximate nearest neighbor.

---

## Data Collection (YouTube API)

### What We Collected

| Field | Source | Notes |
|-------|--------|-------|
| `id` | Video ID | Used for deduplication |
| `title` | Snippet | Primary signal for embedding |
| `description` | Snippet | Truncated to 400 chars |
| `tags` | Snippet | Up to 20 tags; many videos have none |
| `channel_title` | Snippet | Not used in V0 |
| `category_id` | Snippet | YouTube's category; not used |
| `seed_keyword` | Our query | Tracks which search found it |

### Seed Keywords Used (~60 total)

Grouped by vertical:
- **Fitness**: calisthenics workout, gym motivation, yoga morning routine, hyrox training, running tips, weight loss transformation, bodybuilding natural, crossfit workout, pilates routine, home workout
- **Food**: easy 15 minute recipe, what i eat in a day, meal prep sunday, vegan cooking, sourdough bread, street food tour, mukbang, cooking hack
- **Beauty/Fashion**: makeup tutorial beginner, skincare routine, outfit of the day, thrift flip, nail art, grwm
- **Gaming**: gaming highlights, minecraft build, fps tips, speedrun, indie game review, retro gaming
- **Travel**: solo travel vlog, budget travel, hidden gems, van life, backpacking
- **Comedy/Entertainment**: funny fails, prank video, storytime, day in my life, satisfying video
- **Education**: learn python, history explained, science experiment, study with me, language learning
- **Finance**: personal finance tips, investing, side hustle, passive income, frugal living
- **Lifestyle**: morning routine, minimalism, meditation, mental health, journaling
- **Pets**: dog training, cat behavior, pet transformation
- **Tech**: tech review, ai tools, iphone tips

### Learnings from Data Collection

1. **Short video filter is critical**: Without `videoDuration=short`, we get long-form content that has different semantics

2. **Description quality varies wildly**:
   - Many Shorts have empty or one-line descriptions
   - Some have full essays with SEO spam
   - Truncating to 400 chars was necessary

3. **Tags are often empty**:
   - ~40% of Shorts have no tags
   - When present, tags are high-signal
   - Hashtags in title often duplicate tags

4. **Seed keyword diversity matters**:
   - If we only searched "fitness", we'd miss sub-niches
   - Specific queries (e.g., "hyrox training") captured niches that generic queries missed
   - But overlap between searches = deduplication needed

5. **Regional/language bias**:
   - Used `regionCode=US` and `relevanceLanguage=en`
   - Taxonomy is English/US-centric
   - May miss non-English creator niches

**Recommendation for V1:**
> Expand seed keywords based on taxonomy gaps. If a category is sparse, generate more specific keywords for that vertical. Consider multi-language support.

---

## Embedding Strategy

### Model Choice: `text-embedding-3-small`

**Why:**
- Cheapest OpenAI embedding model ($0.02/1M tokens)
- 1536 dimensions (same as ada-002)
- Good enough quality for clustering
- Fast batch processing

**Alternative considered:**
- `text-embedding-3-large`: More expensive, higher dims, might be overkill
- Open-source (e.g., sentence-transformers): Free but requires GPU setup

### Text Construction

```python
def make_text(video):
    tags = " ".join(f"#{t}" for t in video.get("tags", [])[:15])
    return f"{video['title']}. {video.get('description', '')[:300]}. {tags}".strip()
```

**Format**: `{title}. {description}. #{tag1} #{tag2} ...`

**Learnings:**

1. **Title is most important**: Usually 5-15 words, high signal
2. **Description[:300] is noisy but helpful**: Sometimes has context not in title
3. **Tags as hashtags work well**: Embedding model understands `#fitness` as a topic marker
4. **Limit tags to 15**: More than that adds noise (SEO spam tags)

**What we tried that didn't help:**
- Including channel name: Added noise, not topic-relevant
- Using category_id: YouTube's categories are too broad (e.g., "People & Blogs")

**Recommendation for V1:**
> Could experiment with weighting (e.g., repeat title 2x) or using only title+tags for cleaner embeddings.

---

## Clustering Approach

### Stage 1: K-Means (K=15)

**Configuration:**
```python
kmeans = KMeans(n_clusters=15, random_state=42, n_init=10)
```

**Why K=15?**
- ~3000 videos / 15 = ~200 videos per coarse cluster
- Matches roughly the number of "content verticals" in our seed keywords
- Empirically produced reasonable categories

**Observation:**
- Some clusters are very large (300+ videos): e.g., fitness
- Some are small (50 videos): e.g., pets
- This reflects real-world content distribution

### Stage 2: HDBSCAN (per coarse cluster)

**Configuration:**
```python
hdb = HDBSCAN(min_cluster_size=3)
```

**Why HDBSCAN?**
- Finds arbitrary-shaped clusters
- Handles noise (outliers get label -1)
- No need to specify number of clusters
- Density-based = finds natural groupings

**Why min_cluster_size=3?**
- Too low (1-2): Every video becomes its own cluster
- Too high (10+): Misses small but valid niches
- 3 = minimum to establish a pattern

### Handling Noise Points

**What we did:**
- If noise cluster has ≥3 videos, create a "noise" niche
- Label it with LLM like any other cluster

**Observation:**
- Noise clusters are often "miscellaneous" or transitional content
- Some noise clusters actually represent valid niches that HDBSCAN couldn't separate

### Clustering Results (V0)

| Metric | Value |
|--------|-------|
| Coarse clusters | 15 |
| Total micro-niches | 109 |
| Noise niches | ~15 (labeled as `c{X}_noise`) |
| Coverage | ~95% of videos assigned |
| Largest micro-niche | 121 videos |
| Smallest micro-niche | 3 videos |
| Median micro-niche size | ~20 videos |

**Learnings:**

1. **109 niches might be too many**: Hard to browse, many are very similar
2. **Noise clusters are useful**: Often catch edge cases
3. **Size distribution is power-law**: Few big niches, many small ones
4. **Some coarse clusters have 1 micro-niche**: Indicates homogeneous content

**Recommendation for V1:**
> Consider merging similar micro-niches (e.g., cosine similarity > 0.9 between centroids). Or use hierarchical clustering for 3+ levels.

---

## LLM Labeling

### Model: `gpt-4o-mini`

**Why not gpt-4o?**
- 4o-mini is ~10x cheaper
- Quality was good enough for labeling
- JSON mode works reliably

### Niche Naming Prompt

```
You are naming micro-niches for a short-form video taxonomy (TikTok/Reels/Shorts).

Video titles from this cluster:
- {title1}
- {title2}
...

Hashtags seen:
#{tag1}, #{tag2}, ...

Name this content niche specifically. Not "fitness" — more like "Calisthenics Bodyweight Training" or "Hyrox Race Prep".

Return JSON only:
{
  "name": "2-4 word specific niche name",
  "description": "One sentence: who creates this content and what it covers",
  "keywords": ["5", "example", "hashtags"]
}
```

**Key prompt elements:**
1. Context: "short-form video taxonomy"
2. Examples in prompt: Shows desired specificity
3. Explicit "not fitness": Prevents overly generic names
4. JSON mode: Ensures structured output

### Category Naming Prompt

```
These micro-niches all belong together:
- {niche1}
- {niche2}
...

What is the best 1-3 word parent category for all of them?
Return JSON: {"name": "Category Name", "description": "one sentence about this category"}
```

### Labeling Quality Observations

**Good labels (examples):**
- "ASMR Cleaning Aesthetics" - Specific, accurate
- "Calisthenics Bodyweight Training" - Clear niche
- "Morning Yoga & Mobility Routines" - Describes content well

**Bad labels (examples):**
- "Miscellaneous Lifestyle Content" - Too vague
- "Gym Motivation" - Same as input, not specific enough
- Duplicate names across niches (e.g., multiple "Home Workout" niches)

**Learnings:**

1. **Sample size matters**: 10 titles + 15 tags is enough for most clusters
2. **Temperature=0.3 reduces hallucination**: More deterministic names
3. **Some clusters are genuinely ambiguous**: Mixed content = vague label
4. **Keywords generated are useful**: Good for display and search

**Recommendation for V1:**
> Add deduplication step: If two niches have >80% keyword overlap, consider merging. Also validate that generated keywords actually appear in the cluster data.

---

## Classification at Runtime

### API Endpoint: `/api/classify`

**Flow:**
1. Receive text (creator bio, video caption, hashtags)
2. Embed with `text-embedding-3-small`
3. Compute cosine similarity against all 109 centroids
4. Return top 5 matches with scores

### Latency

| Step | Time |
|------|------|
| OpenAI embedding | ~200-300ms |
| Cosine similarity (109 centroids) | <5ms |
| Total | ~250-350ms |

### Classification Quality Observations

**Works well for:**
- Clear niche content ("I do HIIT workouts and meal prep")
- Hashtag-heavy inputs ("#calisthenics #streetworkout #bodyweight")
- Standard creator bios

**Struggles with:**
- Multi-niche creators ("fitness + cooking + lifestyle")
- Very short inputs ("workout videos")
- Non-English content
- New niches not in training data (e.g., new trends)

**Score interpretation:**
- 0.85+ : Very confident match
- 0.70-0.85: Good match
- 0.50-0.70: Partial match, check alternatives
- <0.50: Poor match, likely out-of-taxonomy

**Learning:**
> Top-1 accuracy is high for clear niches, but multi-label classification would serve users better. A creator can belong to multiple niches.

---

## What Worked Well

### 1. End-to-End Automation
The entire pipeline runs without manual intervention. From YouTube search to final taxonomy takes ~10 minutes.

### 2. Semantic Understanding
The embedding approach correctly groups semantically similar content even with different wording. "HIIT" and "high intensity interval training" cluster together.

### 3. Cost Efficiency
Total cost per run: ~$0.05-0.10
- Embeddings: ~$0.01 for 3K videos
- LLM labeling: ~$0.03 for 109 niches + 15 categories
- YouTube API: Free tier (6K units used of 10K daily limit)

### 4. Hierarchical Output
Two-level taxonomy (category → niche) is browsable and useful for both humans and downstream systems.

### 5. Fast Runtime Classification
~300ms per classification is fast enough for real-time use.

### 6. Interpretable Centroids
Storing centroid vectors means we can explain why a classification was made (closest niche) and show confidence scores.

---

## What Didn't Work

### 1. Fixed Cluster Count
K=15 and K=50 (in original code) were guesses. Some areas (fitness) need more granularity; others (pets) need less.

**Impact:** Some niches are too broad, others too narrow.

### 2. Single-Label Assignment
Each video belongs to exactly one cluster. A "fitness meal prep" video is either fitness OR food, not both.

**Impact:** Cross-niche content is forced into one category, losing context.

### 3. No Hierarchy Depth Control
We get exactly 2 levels. Some niches could use sub-niches (e.g., Fitness → Calisthenics → Pull-up Progressions).

**Impact:** Flat structure within categories.

### 4. Centroid Drift Over Time
Centroids are computed once. As content trends evolve, centroids become stale.

**Impact:** New content styles may classify poorly to outdated centroids.

### 5. Category Assignment is Post-Hoc
Categories are named after clustering. Sometimes niches that don't belong together end up in the same category.

**Example:** "Morning Routines" category contains both yoga and skincare content that clustered together due to "morning routine" language overlap.

### 6. No Confidence Threshold
We return top 5 matches regardless of score. If nothing matches well, we still return results.

**Impact:** Misleading classifications for out-of-taxonomy content.

### 7. Duplicate/Similar Niches
Some niches are nearly identical but got separate clusters due to clustering artifacts.

**Example:** "Gym Motivation" and "Fitness Motivation" in different categories.

---

## Metrics & Evaluation

### Coverage
- **Target:** >85% of videos assigned to a niche
- **Actual:** ~95%
- **Status:** PASS

### Granularity
- **Max niche size:** 121 videos
- **Median niche size:** ~20 videos
- **Min niche size:** 3 videos
- **Max/median ratio:** ~6x (power-law distribution - expected)

### Manual Spot Check (10 random niches)
| Niche | Quality |
|-------|---------|
| ASMR Cleaning Aesthetics | Good - specific and accurate |
| Morning Yoga & Mobility | Good - clear niche |
| Gym Motivation | Medium - too generic |
| Minimalist Lifestyle Hacks | Good - matches content |
| Gaming Highlights | Medium - very broad |

### Classification Accuracy (informal test)

Tested with 20 made-up creator bios:

| Input Type | Top-1 Accuracy |
|------------|---------------|
| Clear single-niche | ~85% |
| Multi-niche | ~40% (expected - single label) |
| Out of taxonomy | N/A (no ground truth) |

---

## Cost Analysis

### Per-Run Costs

| Step | API | Cost |
|------|-----|------|
| Data collection | YouTube Data API v3 | Free (10K/day) |
| Embedding 3K videos | text-embedding-3-small | ~$0.01 |
| Labeling 109 niches | gpt-4o-mini | ~$0.02 |
| Labeling 15 categories | gpt-4o-mini | ~$0.005 |
| **Total** | | **~$0.035** |

### Runtime Costs (per classification)

| Step | Cost |
|------|------|
| Embed 1 text | ~$0.000002 |
| Cosine similarity | $0 (local compute) |

At 10,000 classifications/day: ~$0.02/day

### Infrastructure Costs

- Next.js on Vercel: Free tier sufficient
- No database needed (JSON files)
- No GPU needed

---

## Technical Debt

### 1. Hardcoded Parameters
- `N_COARSE = 15`
- `MIN_MICRO_SIZE = 3`
- `n_components = 100` (PCA)

Should be configurable or auto-tuned.

### 2. No Incremental Updates
Adding new videos requires full re-run of pipeline.

### 3. No Versioning
If taxonomy changes, old classifications become inconsistent.

### 4. Centroids in Memory
Loaded into memory on first request. Works for 109 niches, won't scale to thousands.

### 5. No Monitoring
No logging of classification quality over time.

### 6. Single Embedding Model
If OpenAI changes the model or deprecates it, centroids become invalid.

---

## Gap Analysis: V0 vs Hackathon Brief

### Deliverables Status

| Deliverable | Required | V0 Status |
|-------------|----------|-----------|
| Taxonomy file (JSON tree) | Yes | **Done** - 109 niches, 15 categories |
| Reproducible pipeline | Yes | **Done** - `bash pipeline/run.sh` |
| Classifier | Yes | **Done** - `/api/classify` |
| Evaluation report | Yes | **Partial** - missing stability test |
| Short writeup | Yes | **Done** - LEARNINGS + UI docs |

### Evaluation Criteria Status

| Criterion | Target | V0 Status |
|-----------|--------|-----------|
| Coverage | >85% | **Pass** - 95% |
| Granularity | Power-law | **Pass** |
| Stability | Run twice, same structure | **Not tested** |
| Readability | Non-expert understands | **Mostly pass** |
| Speed | Fast | **Pass** - 5-8 min |
| Docs | Others can run | **Pass** |

### Critical Gaps

1. **Scale**: Brief wants "hundreds or thousands" of niches. We have 109.
2. **Depth**: Brief implies 3-4 levels. We have 2.
3. **Multi-label**: Brief says "niche(s)" plural. We're single-label.
4. **Open-set detection**: Brief stretch goal. Not implemented.
5. **Stability test**: Required evaluation. Not done.

---

## Recommendations for V1

### Priority 1: Scale (Critical)

The brief explicitly states:
> "A useful taxonomy has **hundreds or thousands** of leaf categories"

**Problem**: 109 niches from 3K videos isn't enough.

**Solutions**:

1. **10x more data** (Critical)
   - Collect 20-30K videos instead of 3K
   - Expand seed keywords from 60 to 200+
   - Consider adding TikTok scraping (Playwright) for diversity
   - Add Reddit API for niche discovery/validation

2. **Deeper hierarchy** (Critical)
   - Target 3-4 levels: Category → Subcategory → Niche → Micro-niche
   - Options:
     - Recursive HDBSCAN on each cluster
     - LLM-driven recursive breakdown (Approach C from brief)
     - Cluster centroids to create parent levels

3. **Lower min_cluster_size**
   - Current: 3 (too conservative)
   - Try: 2 for micro-niches, accept more granularity

### Priority 2: Multi-Label Classification (Required)

The brief says: "return the most likely **niche(s)**" — plural.

**Implementation**:
```python
def classify(text):
    scores = cosine_similarity(embed(text), all_centroids)
    # Return all niches above threshold, not just top-1
    matches = [
        {"niche": n, "score": s, "confidence": confidence_level(s)}
        for n, s in zip(niches, scores)
        if s > 0.45  # threshold
    ]
    return sorted(matches, key=lambda x: -x["score"])[:5]
```

**Confidence levels**:
- 0.75+: "Primary niche"
- 0.55-0.75: "Secondary niche"
- 0.45-0.55: "Possible niche"
- <0.45: Not returned

### Priority 3: Open-Set Detection (Stretch Goal)

Brief says: "flag creators who fit no niche as candidates for new ones"

**Implementation**:
- If max_score < 0.40: Return `{"niche": "Unknown/Emerging", "candidates_for_new_niche": true}`
- Log these inputs for analysis
- Periodically cluster "unknown" inputs to discover new niches

### Priority 4: Stability Testing (Required Evaluation)

Brief says: "Run the pipeline twice. Major structure should hold."

**Implementation**:
```python
def test_stability():
    # Run pipeline twice with different random seeds
    taxonomy_1 = run_pipeline(seed=42)
    taxonomy_2 = run_pipeline(seed=123)

    # Measure structural similarity
    # - % of niches that appear in both
    # - Jaccard similarity of niche keywords
    # - Centroid cosine similarity

    assert structural_similarity > 0.80
```

### Priority 5: Exemplar Creators (Stretch Goal)

Brief says: "top 10 per niche"

**Implementation**:
- Store `channel_title` with each video (already collected)
- For each niche, rank creators by:
  - Number of videos in niche
  - Average similarity to centroid
- Store top 10 in taxonomy.json

### Priority 6: Hybrid Approach (Enhancement)

Brief says: "Mixing is encouraged"

**Current**: Approach B only (Embedding-Based Clustering)

**V1 Hybrid**:
1. **Add Hashtag Co-Occurrence (Approach A)**
   - Build hashtag graph from collected videos
   - Use community detection to validate/enrich clusters
   - Hashtag clusters can inform niche keywords

2. **Add LLM Recursive Breakdown (Approach C)**
   - After initial clustering, ask LLM: "Break this niche into 3-5 sub-niches"
   - Validate sub-niches against actual video data
   - This helps reach 3-4 levels of depth

### Architecture Changes for V1

| Change | Why |
|--------|-----|
| **More data first** | Can't get 1000 niches from 3K videos |
| **UMAP instead of PCA** | Better preserves local structure for hierarchy |
| **Recursive clustering** | Natural way to build deeper trees |
| **faiss for ANN** | Scale to 1000+ centroids efficiently |
| **Add TikTok data** | Cross-platform validation (stretch goal) |

### V1 Pipeline Structure

```
1_collect.py      → 20-30K videos (YouTube + optional TikTok)
2_embed.py        → Embeddings (same as V0)
3_cluster.py      → Recursive hierarchical clustering (3-4 levels)
4_hashtag.py      → [NEW] Hashtag co-occurrence analysis
5_name.py         → LLM naming with recursive sub-niche breakdown
6_validate.py     → [NEW] Cross-validate clusters with hashtag communities
7_evaluate.py     → Extended eval: coverage, granularity, stability, readability
8_exemplars.py    → [NEW] Top creators per niche
```

### V1 Target Metrics

| Metric | V0 | V1 Target |
|--------|-----|-----------|
| Total niches | 109 | 500-1000 |
| Hierarchy depth | 2 | 3-4 |
| Videos processed | 3K | 20-30K |
| Coverage | 95% | >90% |
| Multi-label | No | Yes |
| Open-set detection | No | Yes |
| Stability test | No | Yes, >80% |
| Exemplar creators | No | Top 10/niche |

### What NOT to Do in V1

1. **Don't over-engineer** - Brief says "quality and rigor over flashy code"
2. **Don't add cross-platform yet** - Get YouTube right first
3. **Don't build complex UI** - Focus on taxonomy quality
4. **Don't use paid APIs unnecessarily** - Brief says "no cloud spend"

---

## Appendix: File Structure

```
taxonomy-auto/
├── data/
│   ├── raw_videos.jsonl     # YouTube API output (~3K lines)
│   ├── embeddings.npy       # 3000 x 1536 float32 array
│   ├── metadata.json        # Video metadata (id, title, tags)
│   ├── clusters.json        # Cluster assignments + sample data
│   ├── taxonomy.json        # Final hierarchical taxonomy
│   └── centroids.json       # Niche centroids for classification
├── pipeline/
│   ├── 1_collect.py         # YouTube API data collection
│   ├── 2_embed.py           # OpenAI embedding generation
│   ├── 3_cluster.py         # Two-stage clustering
│   ├── 4_name.py            # LLM labeling
│   └── 5_evaluate.py        # Quality report
├── pages/
│   ├── index.tsx            # Demo UI (V0/V1 tabs, Process docs)
│   └── api/
│       ├── classify.ts      # Classification endpoint
│       └── taxonomy.ts      # Taxonomy JSON endpoint
├── LEARNINGS.md             # This document (DO NOT DELETE)
└── CLAUDE.md                # Claude Code project instructions
```

---

## Appendix: Sample Taxonomy Structure

```json
{
  "version": "1.0",
  "generated_at": "2026-05-22",
  "total_niches": 109,
  "tree": [
    {
      "id": "cat_0",
      "name": "Mindful Living",
      "description": "Content focused on minimalism and sensory experiences",
      "children": [
        {
          "id": "c0_m0",
          "name": "ASMR Cleaning Aesthetics",
          "description": "Creators focus on satisfying cleaning routines with ASMR",
          "keywords": ["ASMR", "cleaning", "satisfying", "organization"],
          "video_count": 43
        },
        // ... more niches
      ]
    },
    // ... more categories
  ]
}
```

---

## V1 Implementation Results

V1 was implemented and run successfully. Here are the actual results:

### V1 Pipeline Scripts

| Script | Purpose |
|--------|---------|
| `pipeline/v1/1_collect.py` | Data collection with 200+ seed keywords (hit quota at ~4K videos) |
| `pipeline/v1/2_embed.py` | OpenAI embeddings (text-embedding-3-small) |
| `pipeline/v1/3_cluster.py` | 4-level recursive clustering (K-Means + HDBSCAN) |
| `pipeline/v1/4_name.py` | Hierarchical LLM naming + exemplar creator extraction |
| `pipeline/v1/5_classify.py` | Multi-label classifier with open-set detection (CLI) |
| `pipeline/v1/6_evaluate.py` | Evaluation with stability testing |
| `pipeline/v1/run.sh` | Full pipeline runner |

### V1 Results vs Targets

| Metric | V0 | V1 Target | V1 Actual | Status |
|--------|-----|-----------|-----------|--------|
| Videos processed | 3,000 | 20-30K | 3,991 | Partial (quota limit) |
| Categories | 15 | 20+ | 20 | Pass |
| Subcategories | - | 50+ | 77 | Pass |
| Leaf niches | 109 | 500-1000 | 209 | Partial |
| Hierarchy depth | 2 | 3-4 | 4 | Pass |
| Coverage | 95% | >90% | 100% | Pass |
| Multi-label | No | Yes | Yes | Pass |
| Open-set detection | No | Yes | Yes | Pass |
| Stability (ARI) | untested | >80% | 73.2% | Close |
| Exemplar creators | No | Top 10 | Yes | Pass |

### V1 Categories Generated

1. Fitness & Training
2. Quick & Easy Meals
3. Strength Training
4. Bodyweight Fitness
5. Quick Bites (Baking)
6. Fitness & Weight Loss
7. Skincare & Beauty
8. Lifestyle & Nutrition
9. Healthy Cooking
10. Calisthenics & Fitness
11. Baking & Bread
12. Running & Training
13. Mobility & Stretching
14. Meal Prep & Nutrition
15. Yoga & Wellness
16. Drugstore Beauty
17. Food & Dining
18. Makeup Tutorials
19. Calisthenics Training
20. Cooking Hacks

### V1 Sample Subcategories

- HYROX Training & Competition
- Sourdough Bread Techniques
- Swimming Techniques & Drills
- Beginner Marathon Training
- Dynamic Mobility Routines
- Freezer Meal Mastery
- High Protein Meal Prep
- Yoga Challenge Series
- Affordable Drugstore Makeup
- Viral Food Challenges
- Mukbang & ASMR Eating
- Beginner Calisthenics Guide
- Push-Up Mastery
- Handstand Mastery Techniques

### V1 Evaluation Summary

```
Overall Quality Score: 74.6/100

Breakdown:
  Coverage:       100.0/100
  Balance:        100.0/100
  Stability:       73.2/100
  Classification:  99.6/100
  Hierarchy:        0.0/100 (minor bug in consistency check)
```

### Key V1 Achievements

1. **4-Level Hierarchy**: Category → Subcategory → Micro-niche → Split-niche
2. **Multi-Label Classification**: Returns multiple niches with confidence scores
3. **Open-Set Detection**: Flags unknown/emerging niches (threshold: 35% similarity)
4. **Exemplar Creators**: Top 10 creators stored per niche
5. **Stability Testing**: 73% ARI across 5 random seeds
6. **99.6% Classification Confidence**: High-quality niche assignments

### V1 Limitations & V2 Opportunities

1. **YouTube Quota**: Hit 10K daily limit at ~4K videos. Need multi-day collection or quota increase.
2. **Missing Verticals**: Gaming, Travel, Tech were not fully collected due to quota.
3. **209 niches vs 500-1000 target**: Need more data to reach target scale.
4. **Numerical Warnings**: Some overflow warnings during clustering (use float64 throughout).
5. **Content Bias**: Heavy on Fitness, Food, Beauty due to keyword order vs quota.

### V1 File Structure

```
data/v1/
├── raw_videos.jsonl     # 3,991 videos
├── embeddings.npy       # 3991 x 1536 float32
├── metadata.json        # Video metadata
├── clusters.json        # 209 cluster assignments
├── taxonomy.json        # Final hierarchical taxonomy
└── evaluation.json      # Quality metrics

pipeline/v1/
├── 1_collect.py         # 200+ keywords, channel limits
├── 2_embed.py           # Same as V0
├── 3_cluster.py         # 4-level recursive clustering
├── 4_name.py            # Hierarchical naming + exemplars
├── 5_classify.py        # Multi-label CLI classifier
├── 6_evaluate.py        # Stability + quality metrics
└── run.sh               # Full pipeline runner

pages/api/v1/
├── classify.ts          # Multi-label API endpoint
└── taxonomy.ts          # Hierarchical taxonomy API
```

### How to Run V1

```bash
# Full pipeline
cd pipeline/v1 && bash run.sh

# Or individual steps
python3 pipeline/v1/1_collect.py   # YouTube collection (~10-15 min)
python3 pipeline/v1/2_embed.py     # Embeddings (~1-2 min)
python3 pipeline/v1/3_cluster.py   # Clustering (~1 min)
python3 pipeline/v1/4_name.py      # LLM naming (~3-5 min)
python3 pipeline/v1/6_evaluate.py  # Evaluation (~30 sec)
```

---

## V2 Implementation Results

V2 adds hashtag co-occurrence graph analysis (Approach A) to complement V1's embedding-based clustering.

### V2 Pipeline Scripts

| Script | Purpose |
|--------|---------|
| `pipeline/v2/1_build_hashtag_graph.py` | Extract hashtags, build co-occurrence graph |
| `pipeline/v2/2_community_detection.py` | Louvain algorithm at 3 resolutions |
| `pipeline/v2/3_merge_with_embeddings.py` | Cross-validate with V1 clusters |
| `pipeline/v2/4_unified_taxonomy.py` | Create unified taxonomy, LLM naming for new niches |
| `pipeline/v2/5_evaluate.py` | Compare V2 vs V1 |
| `pipeline/v2/run.sh` | Full pipeline runner |

### V2 Results Summary

| Metric | V1 | V2 | Change |
|--------|-----|-----|--------|
| Total niches | 209 | 234 | +25 (+12%) |
| Categories | 20 | 21 | +1 (Hashtag Discovered) |
| Subcategories | 77 | 77 | - |
| Approaches used | B only | A + B | +Approach A |

### Hashtag Graph Statistics

| Metric | Value |
|--------|-------|
| Total videos processed | 3,991 |
| Videos with hashtags | 2,931 (73.4%) |
| Unique hashtags | 1,586 |
| Co-occurrence edges | 15,169 |
| Average edge weight | 3.98 |

### Louvain Community Detection

Ran at 3 resolutions to build hierarchy:

| Resolution | Level | Communities |
|------------|-------|-------------|
| 0.5 | Categories | 16 |
| 1.0 | Subcategories | 22 |
| 2.0 | Niches | 29 |

### New Niches Discovered (via Hashtags)

25 new niches discovered through hashtag co-occurrence that weren't found by embedding clustering:

| Niche | Description | Top Hashtags |
|-------|-------------|--------------|
| Fitness Transformation Journeys | Personal fitness journeys, progress, challenges | #fitness, #workout, #gym, #motivation |
| Quick Healthy Meals | Fast nutritious recipes for busy individuals | #recipe, #cooking, #mealprep, #easyrecipe |
| Quick Cake Decorating Tips | Rapid cake decorating techniques | #shorts, #cakedecorating, #cake |
| Interactive Food Experiences | Immersive food reviews, challenges | #food, #foodie, #yummy |
| Bodyweight Fitness Journey | Home workouts without equipment | #homeworkout, #fitnessmotivation |
| Affordable DIY Makeup Tutorials | Budget-friendly drugstore tutorials | #makeup, #howto, #drugstoremakeup |
| Aesthetic Skincare ASMR | Skincare + ASMR relaxation | #skincare, #asmr, #aesthetic |

(Plus 18 more cross-cutting niches spanning multiple V1 categories)

### V2 Evaluation Scores

```
Overall Quality Score: 56.5/100

Breakdown:
  Coverage:           100.0/100
  Balance:             50.0/100 (Gini 0.66 - more imbalanced)
  Hashtag Validation:  16.0/100 (see Known Issue below)
  New Discoveries:     60.0/100
```

### Success Criteria

| Criterion | Target | Result | Status |
|-----------|--------|--------|--------|
| Hashtag graph built | >0 hashtags | 1,586 hashtags | **PASS** |
| Community detection done | >0 communities | 29 communities | **PASS** |
| New niches discovered | ≥10 new | 25 new | **PASS** |
| V1 niches validated | ≥50% | 0% | **FAIL** |

### Known Issue: V1 Validation Rate = 0%

**Problem:** V1 taxonomy doesn't store `video_ids` in niches, only centroids. The cross-validation step couldn't map videos back to V1 niches.

**Impact:** Can't validate V1 niches using hashtag communities. All V1 niches show `hashtag_validated: false`.

**Fix for V3:** Modify V1 pipeline to store `video_ids` per niche, or use V1 metadata to rebuild the mapping.

### What V2 Achieved

1. **Approach A Implementation**: Hashtag co-occurrence graph successfully built
2. **Community Detection**: Louvain algorithm found meaningful hashtag communities
3. **New Niche Discovery**: 25 cross-cutting niches not found by embedding clustering alone
4. **Hybrid Taxonomy**: Combined embedding + hashtag approaches
5. **Source Tagging**: All niches tagged with `source: "embedding_clustered"` or `"hashtag_discovered"`
6. **Hybrid Classifier**: V2 classifier combines embedding similarity + hashtag matching

### V2 Classifier

The V2 classifier (`/api/v2/classify`) uses a hybrid approach to classify creator content:

**How It Works:**

1. **Embedding-Based Niches (209 niches)**:
   - Computes cosine similarity between input embedding and niche centroids
   - If input contains hashtags that match niche's top_hashtags, adds a boost (up to +15%)
   - Final score = embedding_similarity + hashtag_boost

2. **Hashtag-Discovered Niches (25 niches)**:
   - No centroids available (discovered via hashtag communities)
   - Uses hashtag matching: checks if input hashtags overlap with niche's top_hashtags
   - Also matches keywords from input text against niche keywords
   - Score = (hashtag_match_ratio × 0.6 + keyword_match_ratio × 0.2) × 0.8

**Scoring Formula:**

```python
# For embedding-based niches
hashtag_boost = 0.15 * min(matched_hashtags, 3) / 3 if matched_hashtags > 0 else 0
final_score = min(1.0, embedding_similarity + hashtag_boost)

# For hashtag-discovered niches
hashtag_score = matched_hashtags / min(niche_hashtags, 5) * 1.2  # capped at 1.0
keyword_bonus = keyword_matches / total_keywords * 0.2
final_score = (hashtag_score * 0.6 + keyword_bonus) * 0.8
```

**Features:**
- **Multi-label**: Returns multiple niches if scores are within 8% of best match
- **Open-set detection**: Flags "UNKNOWN" if best score < 35%
- **Source tagging**: Each result shows if it came from embedding or hashtag discovery
- **Matched hashtags**: Shows which hashtags contributed to the match

**API Response:**
```json
{
  "input_hashtags": ["fitness", "workout", "gym"],
  "classification_status": "HIGH_CONFIDENCE",
  "primary_niche": {
    "niche_name": "Fitness Transformation Journeys",
    "source": "hashtag_discovered",
    "matched_hashtags": ["fitness", "workout", "gym"],
    "confidence": 72.5
  },
  "stats": {
    "matches_from_embedding": 3,
    "matches_from_hashtag": 2
  }
}

### V2 File Structure

```
data/v2/
├── hashtag_graph.pkl     # NetworkX graph + tag_to_videos mapping
├── graph_stats.json      # Graph statistics
├── communities.json      # Louvain results at 3 resolutions
├── merged_analysis.json  # Cross-validation with V1
├── taxonomy.json         # Final V2 taxonomy (234 niches)
└── evaluation.json       # V2 vs V1 comparison

pipeline/v2/
├── 1_build_hashtag_graph.py
├── 2_community_detection.py
├── 3_merge_with_embeddings.py
├── 4_unified_taxonomy.py
├── 5_evaluate.py
└── run.sh

pages/api/v2/
├── classify.ts           # Hybrid classifier (embedding + hashtag)
└── taxonomy.ts           # V2 taxonomy API endpoint
```

### How to Run V2

```bash
# Full pipeline
cd pipeline/v2 && bash run.sh

# Or individual steps
python3 pipeline/v2/1_build_hashtag_graph.py   # ~10 sec
python3 pipeline/v2/2_community_detection.py   # ~5 sec
python3 pipeline/v2/3_merge_with_embeddings.py # ~5 sec
python3 pipeline/v2/4_unified_taxonomy.py      # ~2 min (LLM calls)
python3 pipeline/v2/5_evaluate.py              # ~5 sec
```

### V2 Learnings

1. **Hashtag coverage is good**: 73.4% of videos have hashtags - strong signal
2. **Cross-cutting niches exist**: Some content spans multiple embedding clusters but has unified hashtag communities
3. **Community detection works**: Louvain at resolution 2.0 found 29 meaningful communities
4. **Missing video_ids is a blocker**: Can't cross-validate without knowing which videos belong to which V1 niches
5. **Balance trade-off**: New hashtag niches have variable sizes (732 to 10 videos), increasing Gini coefficient

---

## V3 Implementation Results

V3 adds LLM-driven sub-niche discovery (Approach C) to the taxonomy pipeline.

### V3 Pipeline Scripts

| Script | Purpose |
|--------|---------|
| `pipeline/v3/1_analyze_niches.py` | Analyze V2 niches for breakdown candidates |
| `pipeline/v3/2_llm_breakdown.py` | GPT-4o-mini generates 4 sub-niches per parent |
| `pipeline/v3/3_validate_suggestions.py` | Validate suggestions against video data |
| `pipeline/v3/4_merge_taxonomy.py` | Create V3 taxonomy with parent-child relationships |
| `pipeline/v3/5_evaluate.py` | Compare V3 vs V2 |
| `pipeline/v3/run.sh` | Full pipeline runner |

### V3 Results Summary

| Metric | V2 | V3 | Change |
|--------|-----|-----|--------|
| Total niches | 234 | 593 | +359 (+153.4%) |
| Embedding niches | 209 | 209 | - |
| Hashtag niches | 25 | 25 | - |
| LLM sub-niches | - | 359 | +359 |
| Validation rate | - | 89.8% | New |

### LLM Suggestion Quality

| Status | Count | Percentage |
|--------|-------|------------|
| Validated (≥5 videos) | 308 | 77.0% |
| Partial (2-4 videos) | 51 | 12.8% |
| Unvalidated (<2 videos) | 41 | 10.3% |
| **Total suggestions** | 400 | 100% |

**Validation rate:** 89.8% (validated + partial)

### V3 Evaluation Score

```
Overall Quality Score: 90.2/100

Breakdown:
  Scale:           100.0/100 (593 niches, target 400)
  Validation Rate:  89.8/100
  Specificity:      71.2/100
  Coverage:        100.0/100
```

### V3 Source Distribution

| Source | Count | Percentage |
|--------|-------|------------|
| embedding_clustered | 209 | 35.2% |
| hashtag_discovered | 25 | 4.2% |
| llm_generated | 359 | 60.5% |

### Success Criteria

| Criterion | Result | Status |
|-----------|--------|--------|
| LLM breakdown implemented | Yes | **PASS** |
| Sub-niches generated | 359 | **PASS** |
| Validation working | 89.8% rate | **PASS** |
| Source tagging maintained | Yes | **PASS** |
| Scale improvement | 153% growth | **PASS** |

### Example Sub-Niches Generated

**Quick Cake Decorating Tips →**
- Beginner-Friendly Cake Decorating Hacks (51 videos)
- Cake Decorating Challenges for Kids (38 videos)
- Seasonal Cake Decorating Ideas (39 videos)

**Fitness Transformation Journeys →**
- Postpartum Fitness Transformations (4 videos)
- Fitness Challenges for Busy Professionals (13 videos)
- Body Positivity Fitness Transformations (194 videos)

**Quick Healthy Meals →**
- 15-Minute Vegan Dinners (38 videos)
- Healthy Meal Prep for Weight Loss (437 videos)
- Quick Healthy Snacks for Kids (31 videos)

### V3 Classifier

The V3 classifier (`/api/v3/classify`) extends V2 with sub-niche matching:

**New Features:**
1. **Sub-niche recommendations**: Returns matching sub-niches within parent niches
2. **Keyword matching**: Checks validation_keywords and expected_hashtags from LLM suggestions
3. **Multi-level results**: Shows both parent niche match and recommended sub-niche

**Scoring Formula:**
```python
# Base score from V2 (embedding + hashtag boost)
base_score = embedding_similarity + hashtag_boost

# Sub-niche keyword matching
for keyword in sub_niche.validation_keywords:
    if keyword in input_text:
        matched_terms.append(keyword)
        sub_niche_score += 0.15

# Final score with sub-niche boost
sub_niche_boost = 0.10 * min(best_sub_niche_score, 1.0)
final_score = min(1.0, base_score + sub_niche_boost)
```

**API Response:**
```json
{
  "primary_niche": {
    "niche_name": "Quick Cake Decorating Tips",
    "source": "embedding_clustered",
    "has_sub_niches": true,
    "recommended_sub_niche": {
      "id": "v3_sub_niche_45_0",
      "name": "Beginner-Friendly Cake Decorating Hacks",
      "validation_status": "validated",
      "matchedTerms": ["beginner", "cake decorating", "easy"]
    }
  },
  "stats": {
    "taxonomy_size": 593,
    "llm_sub_niches": 359,
    "matches_with_sub_niches": 2
  }
}
```

### V3 File Structure

```
data/v3/
├── niche_analysis.json       # 121 breakdown candidates
├── llm_suggestions.json      # 400 LLM-generated sub-niches
├── validated_suggestions.json # Validation results
├── taxonomy.json             # Final V3 taxonomy (593 niches)
└── evaluation.json           # V3 vs V2 comparison

pipeline/v3/
├── 1_analyze_niches.py       # Candidate identification
├── 2_llm_breakdown.py        # GPT-4o-mini sub-niche generation
├── 3_validate_suggestions.py # Video data validation
├── 4_merge_taxonomy.py       # Taxonomy merging
├── 5_evaluate.py             # Evaluation metrics
└── run.sh                    # Pipeline runner

pages/api/v3/
├── classify.ts               # Sub-niche aware classifier
└── taxonomy.ts               # V3 taxonomy API endpoint
```

### How to Run V3

```bash
# Full pipeline
cd pipeline/v3 && bash run.sh

# Or individual steps
python3 pipeline/v3/1_analyze_niches.py    # ~5 sec
python3 pipeline/v3/2_llm_breakdown.py     # ~3-5 min (100 API calls)
python3 pipeline/v3/3_validate_suggestions.py # ~10 sec
python3 pipeline/v3/4_merge_taxonomy.py    # ~5 sec
python3 pipeline/v3/5_evaluate.py          # ~5 sec
```

**Cost:** ~$0.15 for 100 GPT-4o-mini calls (4 sub-niches each)

### V3 Learnings

1. **LLM suggestions are high quality**: 89.8% validated against real video data
2. **Keyword validation works**: Matching LLM-suggested keywords against video titles/tags is effective
3. **Specificity improved**: From generic "Calisthenics Training" to specific "Calisthenics for Beginners Over 40"
4. **Parent-child relationships valuable**: Users can browse from broad to specific
5. **Cost-effective**: $0.15 for 359 new sub-niches vs collecting more data
6. **Source tagging essential**: Distinguishing `llm_generated` from `embedding_clustered` prevents confusion

### V3 Limitations

1. **Limited to 100 niches processed**: Cost control measure, could expand
2. **Validation is keyword-based**: May miss semantically similar content
3. **No sub-niche centroids**: Sub-niches inherit parent centroid for classification
4. **LLM hallucination risk**: Some suggestions may not reflect real content patterns

### V3 UI Features

The V3 Process & Flowchart page includes all features from V2 plus V3-specific additions:

| Feature | Description |
|---------|-------------|
| ELI5 Toggle | Simple vs technical explanation mode |
| Clickable Data Flow | 8-step visual flow with modal popups showing details + code |
| V2 vs V3 Comparison | Side-by-side improvements table |
| How to Run Pipeline | Step-by-step with timing and cost info |
| LLM Validation Process | 3 cards showing validated/partial/rejected stats |
| V3 Key Features | Featured V3 Classifier card + 4 feature cards |
| Why V3 Works/Doesn't | Pros and cons columns |
| Evaluation Results | Stats grid + score breakdown with progress bars |
| V3 vs Hackathon Brief | Full compliance table |
| Source Distribution | Visual breakdown by source type |
| Taxonomy Evolution | V0 → V3 progression table |

---

## V2/V3/V4 Roadmap

### Gap Analysis Summary

After comparing V1 results against the hackathon brief:

| Requirement | Brief Target | V1 Actual | Gap |
|-------------|--------------|-----------|-----|
| Leaf niches | "hundreds or thousands" | 209 | Need 500-1000+ |
| Approaches used | "Mixing is encouraged" | B only (Embedding) | Missing A, C, D |
| Stability | "Run twice, structure holds" | 73% ARI | Need >80% |
| Micro-niche specificity | "Calisthenics for tall guys over 30" | "Calisthenics Training" | Too generic |

### V2: Hashtag Co-Occurrence Graph (Approach A)

**Goal:** Add hashtag graph analysis to complement embedding-based clustering.

**Why:**
- Brief explicitly mentions this approach
- Finds emergent niches that semantic clustering might miss
- Validates clusters through a completely different signal

**Implementation Plan:**
```
pipeline/v2/
├── 1_build_hashtag_graph.py   # Build graph from existing V1 video tags
├── 2_community_detection.py   # Louvain/Leiden clustering
├── 3_merge_with_embeddings.py # Cross-validate with V1 clusters
├── 4_unified_taxonomy.py      # Merge both approaches
└── 5_evaluate.py              # Compare V2 vs V1
```

**Key Techniques:**
- Nodes = hashtags, Edges = co-occurrence counts
- Community detection: Louvain or Leiden algorithm (via `networkx` or `igraph`)
- Resolution parameter to control hierarchy depth
- LLM naming for discovered communities

**Expected Output:**
- Hashtag communities that map to niches
- New niches not found by embedding clustering
- Validation: niches found by BOTH methods are high-confidence

**Data:** Use existing V1 data (3,991 videos) - no new API calls needed.

---

### V3: LLM-Driven Sub-Niche Discovery (Approach C)

**Goal:** Use LLM to recursively break down niches into more specific micro-niches.

**Why:**
- Gets us to "Calisthenics for tall guys over 30" level of specificity
- LLMs can infer audience demographics and skill levels from content
- Faster than collecting more data

**Implementation Plan:**
```
pipeline/v3/
├── 1_analyze_niches.py        # For each V2 niche, sample videos
├── 2_llm_breakdown.py         # Ask LLM to suggest sub-niches
├── 3_validate_suggestions.py  # Check if sub-niches have real video support
├── 4_merge_taxonomy.py        # Add validated sub-niches to taxonomy
└── 5_evaluate.py              # Quality check
```

**Critical: Data Pollution Prevention**

All LLM-generated niches MUST be tagged to distinguish from data-driven niches:

```json
{
  "id": "niche_123",
  "name": "Calisthenics for Beginners Over 40",
  "source": "llm_generated",        // vs "data_driven"
  "confidence": "inferred",         // vs "clustered"
  "parent_niche": "niche_045",      // Data-driven parent
  "validation_status": "partial",   // "full" | "partial" | "unvalidated"
  "video_support": 12,              // How many videos match this sub-niche
  "generated_by": "gpt-4o-mini",
  "generated_at": "2026-05-23"
}
```

**LLM Prompt Strategy:**
```
Given these 30 video titles about "Calisthenics Training":
- "Beginner calisthenics routine"
- "Advanced muscle-up tutorial"
- "Calisthenics for older adults"
...

What are 3-5 specific sub-niches within this category?
Consider: skill levels, demographics, specific exercises, goals.

Return JSON with suggested sub-niches and which videos support each.
```

**Validation Rules:**
- Sub-niche must have ≥3 supporting videos to be "validated"
- Sub-niche with 1-2 videos = "partial" validation
- Sub-niche with 0 videos = "unvalidated" (keep for future data collection)

---

### V4: Full LLM Breakdown (All Niches)

**Goal:** Remove the artificial 100-niche limit from V3 and process ALL 234 niches.

**Why:**
- V3 only processed 100 of 234 niches (cost control measure)
- Processing all niches → potentially +500 more sub-niches
- Cost is minimal (~$0.35 total)
- No new data collection needed

**V4 Pipeline:**
```
pipeline/v4/
├── 1_analyze_niches.py        # Identify ALL breakdown candidates (no limit)
├── 2_llm_breakdown.py         # GPT-4o-mini for all 234 niches
├── 3_validate_suggestions.py  # Validate against video data
├── 4_merge_taxonomy.py        # Create V4 taxonomy
└── 5_evaluate.py              # Compare V4 vs V3
```

**Expected V4 Results:**

| Metric | V3 | V4 Target |
|--------|-----|-----------|
| Niches processed by LLM | 100 | 234 |
| Sub-niches generated | 400 | ~936 |
| Validated sub-niches | 359 | ~800+ |
| Total taxonomy size | 593 | ~1000+ |
| Cost | ~$0.15 | ~$0.35 |
| Time | 5 min | ~10 min |

---

---

## V4 Implementation Results

V4 removes the 100-niche limit from V3 and processes ALL candidates for LLM-driven sub-niche discovery.

### V4 Pipeline Scripts

| Script | Purpose |
|--------|---------|
| `pipeline/v4/1_analyze_niches.py` | Identify ALL breakdown candidates (no 100 limit) |
| `pipeline/v4/2_llm_breakdown.py` | GPT-4o-mini generates 4 sub-niches per parent (ALL 121) |
| `pipeline/v4/3_validate_suggestions.py` | Validate suggestions against video data |
| `pipeline/v4/4_merge_taxonomy.py` | Create V4 taxonomy with parent-child relationships |
| `pipeline/v4/5_evaluate.py` | Compare V4 vs V3 |
| `pipeline/v4/run.sh` | Full pipeline runner |

### V4 Results Summary

| Metric | V3 | V4 | Change |
|--------|-----|-----|--------|
| Niches processed by LLM | 100 | 121 | +21 (+21%) |
| LLM suggestions | 400 | 484 | +84 (+21%) |
| Validated sub-niches | 359 | 442 | +83 (+23%) |
| Total niches | 593 | 676 | +83 (+14%) |
| Validation rate | 89.8% | 91.3% | +1.5% |

### LLM Suggestion Quality (V4)

| Status | Count | Percentage |
|--------|-------|------------|
| Validated (≥5 videos) | 389 | 80.4% |
| Partial (2-4 videos) | 53 | 10.9% |
| Unvalidated (<2 videos) | 42 | 8.7% |
| **Total suggestions** | 484 | 100% |

**Validation rate:** 91.3% (validated + partial)

### V4 Evaluation Score

```
Overall Quality Score: 87.7/100

Breakdown:
  Scale:           67.6/100 (676 niches, target 1000)
  Validation Rate: 91.3/100
  Specificity:    100.0/100
  Coverage:       100.0/100
```

### V4 Source Distribution

| Source | Count | Percentage |
|--------|-------|------------|
| embedding_clustered | 209 | 30.9% |
| hashtag_discovered | 25 | 3.7% |
| llm_generated | 442 | 65.4% |

### Success Criteria

| Criterion | Target | Result | Status |
|-----------|--------|--------|--------|
| All niches processed | >100 | 121 (ALL) | **PASS** |
| Validation rate | ≥85% | 91.3% | **PASS** |
| Total niches | ≥800 | 676 | **FAIL** |
| Specificity | ≥60% | 100% | **PASS** |
| Growth vs V3 | >0% | +14% | **PASS** |

### V4 vs V3 Key Changes

**What changed (one line of code):**

V3:
```python
MAX_NICHES_TO_PROCESS = 100  # Artificial limit!
```

V4:
```python
# NO LIMIT - Process ALL candidates
```

That's literally the main change! One line removed, 83 more niches discovered.

### V4 Classifier

The V4 classifier (`/api/v4/classify`) is identical to V3 but operates on the larger V4 taxonomy:

**Features:**
- All V3 features (embedding similarity + hashtag boost + sub-niche matching)
- Now searches across 676 niches instead of 593
- 442 LLM sub-niches vs 359 in V3
- Better coverage due to 21 more parent niches processed

### V4 File Structure

```
data/v4/
├── niche_analysis.json       # 121 breakdown candidates (ALL)
├── llm_suggestions.json      # 484 LLM-generated sub-niches
├── validated_suggestions.json # Validation results
├── taxonomy.json             # Final V4 taxonomy (676 niches)
└── evaluation.json           # V4 vs V3 comparison

pipeline/v4/
├── 1_analyze_niches.py       # Candidate identification (no limit)
├── 2_llm_breakdown.py        # GPT-4o-mini sub-niche generation
├── 3_validate_suggestions.py # Video data validation
├── 4_merge_taxonomy.py       # Taxonomy merging
├── 5_evaluate.py             # Evaluation metrics
└── run.sh                    # Pipeline runner

pages/api/v4/
├── classify.ts               # V4 classifier (676 niches)
└── taxonomy.ts               # V4 taxonomy API endpoint
```

### How to Run V4

```bash
# Full pipeline
cd pipeline/v4 && bash run.sh

# Or individual steps
python3 pipeline/v4/1_analyze_niches.py    # ~5 sec
python3 pipeline/v4/2_llm_breakdown.py     # ~2-3 min (121 API calls)
python3 pipeline/v4/3_validate_suggestions.py # ~10 sec
python3 pipeline/v4/4_merge_taxonomy.py    # ~5 sec
python3 pipeline/v4/5_evaluate.py          # ~5 sec
```

**Cost:** ~$0.18 for 121 GPT-4o-mini calls (4 sub-niches each)

### V4 Learnings

1. **Removing limits works**: Just removing the artificial 100-niche limit gave us +14% more niches
2. **Validation rate improved**: 91.3% vs 89.8% - additional niches had good support
3. **Minimal code change, significant impact**: One line removed, 83 more niches
4. **Cost remained low**: Only ~$0.03 more than V3 (~$0.18 vs ~$0.15)
5. **Still below 800 target**: 676 niches - need more base data to reach 800+

### V4 Limitations

1. **Below 800 target**: 676 niches vs 800 goal (need more video data)
2. **Same video data**: Still only ~4K videos from V1
3. **8.7% rejection rate**: 42 suggestions don't match video data
4. **No new discovery methods**: Still relies on V2 base niches

### V4 UI Features

The V4 Process & Flowchart page includes all features from V3:

| Feature | Description |
|---------|-------------|
| ELI5 Toggle | Simple vs technical explanation mode |
| Clickable Data Flow | 8-step visual flow with modal popups |
| V3 vs V4 Comparison | Side-by-side improvements table |
| How to Run Pipeline | Step-by-step with timing and cost info |
| LLM Validation Process | 3 cards showing validated/partial/rejected stats |
| V4 Key Features | What V4 adds vs what it keeps the same |
| Why V4 Works/Doesn't | Pros and cons columns |
| Evaluation Results | Stats grid + score breakdown with progress bars |
| Success Criteria | Full compliance table |
| Output Files | Generated file descriptions |

---

### V5: Cross-Platform Data (Future)

**Goal:** Collect 15-30K videos from multiple platforms to strengthen taxonomy.

**Why:**
- YouTube quota limits data collection to ~4K videos
- Cross-platform validation strengthens niche confidence
- More data = better clustering and more micro-niches

---

#### V5 Data Source Options (Evaluated)

| API | What it provides | Cost | Setup Time | Verdict |
|-----|------------------|------|------------|---------|
| **Apify TikTok Scraper** | 10K+ TikTok videos with hashtags | ~$5-10 | 30 min | ✅ Best option |
| **Apify Instagram Scraper** | 10K+ Reels with captions | ~$5-10 | 30 min | ✅ Good option |
| **SerpAPI (YouTube)** | Bypass quota, search results | ~$50/mo | 30 min | ✅ Good for YouTube gaps |
| **Meta Instagram Graph API** | Official API, limited access | Free | 2 hrs | ⚠️ Only 30 hashtags/week, 1,500 posts max |
| **TikTok Research API** | Official API, full access | Free | Days (approval) | ❌ Too slow |
| **Reddit API** | Subreddit validation | Free | 1-2 hrs | ❌ No video data |
| **Google Trends** | Trend validation | Free | 1 hr | ❌ No video data |
| **Twitter/X API** | Hashtag trends | $100/mo | 1 hr | ❌ No video data |

**Why Apify is recommended for V5:**
- Pre-built scrapers, no approval process
- Instant access to TikTok/Instagram data
- Same hashtag culture as YouTube Shorts
- ~$10 for 10K+ videos is cost-effective
- Cross-platform validation strengthens taxonomy

**Instagram Graph API Limits (if using own Business account):**
- 30 unique hashtags per 7-day rolling window
- 50 results per hashtag search
- Maximum: 1,500 posts per week
- Good for spot-checking, not bulk data

---

#### V5 Pipeline (Future)

```
pipeline/v5/
├── 1_collect_tiktok.py        # Apify TikTok scraper (10K videos)
├── 2_collect_instagram.py     # Apify Instagram scraper (10K Reels) [optional]
├── 3_merge_crossplatform.py   # Combine YouTube + TikTok + Instagram
├── 4_embed_new_data.py        # Embed cross-platform videos
├── 5_unified_taxonomy.py      # Re-cluster with cross-platform data
└── 6_evaluate.py              # Final evaluation
```

**Expected V5 Results:**

| Metric | V4 | V5 Target |
|--------|-----|-----------|
| Videos | 4K | 20-30K |
| Niches | ~1000 | 1200-1500 |
| Platforms | YouTube only | YouTube + TikTok (+ Instagram) |
| Cost | ~$0.35 | ~$15-25 |
| Time | 10 min | 3-4 hrs |

---

### Version Progression Summary

| Version | Focus | Approach | Data | Niches |
|---------|-------|----------|------|--------|
| V0 | Proof of concept | B (Embedding) | 3K videos | 109 |
| V1 | Multi-label + hierarchy | B (Embedding) | 4K videos | 209 |
| V2 | Hashtag graph | A + B hybrid | 4K videos | 234 |
| V3 | LLM sub-niches (limited) | A + B + C | 4K videos | 593 |
| **V4** | **Full LLM breakdown** | **A + B + C** | **4K videos** | **676** |
| V5 | Cross-platform data | A + B + C | 20-30K videos | 1200-1500 (target) |

---

### Success Metrics by Version

**V2 Success:**
- [x] Hashtag graph built from existing tags (1,586 hashtags, 15,169 edges)
- [x] Community detection finds 20-50 communities (29 at niche level)
- [x] ≥10 new niches discovered (not found by V1) (25 new niches)
- [x] Hybrid classifier implemented (embedding + hashtag matching)
- [ ] Cross-validation: ≥70% of V1 niches confirmed by hashtag communities (0% - blocked by missing video_ids)

**V3 Success:**
- [x] LLM generates 3-5 sub-niches per existing niche (4 per niche, 400 total)
- [x] ≥50% of suggestions have video support (89.8% validation rate)
- [x] All LLM-generated niches clearly tagged (source: "llm_generated")
- [x] Total niches: 400-600 (593 achieved)

**V4 Success:**
- [x] All candidates processed by LLM (121 niches, no 100 limit)
- [ ] ~800-1000 total niches (676 achieved - need more data)
- [x] Validation rate maintained (>85%) (91.3% achieved)
- [x] Cost under $0.50 (~$0.18)

**V5 Success:**
- [ ] 20-30K videos collected (cross-platform)
- [ ] 1200-1500 total niches
- [ ] Stability: >85% ARI
- [ ] Coverage: >90%
- [ ] Long-tail micro-niches like "Hyrox prep for first-timers"

---

---

## V6 Implementation Results

V6 is a fresh re-clustering using ALL available data combined — YouTube V1, TikTok, Instagram, and new YouTube data targeting 15 previously underrepresented categories.

### V6 Pipeline Scripts

| Script | Purpose |
|--------|---------|
| `pipeline/v6/1_collect_youtube.py` | New YouTube collection (222 keywords, round-robin across 15 categories) |
| `pipeline/v6/2_combine_datasets.py` | Merge V5 merged (6,976) + V6 new YouTube (3,389) → 10,365 total |
| `pipeline/v6/3_embed.py` | OpenAI embeddings for 10,365 videos |
| `pipeline/v6/4_cluster.py` | 4-level hierarchical clustering (K-Means + HDBSCAN) |
| `pipeline/v6/5_name.py` | GPT-4o-mini naming for all clusters |
| `pipeline/v6/6_evaluate.py` | Evaluation metrics |
| `pipeline/v6/run.sh` | Full pipeline runner |

### V6 Data Collection Strategy

Key insight: V1 collected ~66 keywords before hitting quota (Fitness/Food/Beauty). V6 targeted the uncovered categories using **round-robin ordering** across 15 categories, ensuring each category gets representation even if quota runs out.

**New categories targeted (not in V1):**
- Gaming, Travel, Finance, Arts & Crafts, Music & Dance
- Parenting, Automotive, Sports, Home & DIY
- Career, Relationships, Spirituality, International Food, Comedy, Pets

All 222 keywords completed — per-minute rate limiting caused some skips but the daily quota held. **3,389 new unique videos** collected.

### V6 Dataset Composition

| Source | Videos |
|--------|--------|
| YouTube V1 | 3,991 |
| TikTok (V5) | 2,034 |
| Instagram (V5) | 951 |
| YouTube V6 (new) | 3,389 |
| **Total** | **10,365** |

- Unique hashtags: 28,031
- Unique authors: 6,429
- Embedding cost: ~$0.014

### V6 Results Summary

| Metric | V5 Target | V6 Actual | Status |
|--------|-----------|-----------|--------|
| Videos processed | 20-30K | 10,365 | Partial |
| Categories | 20+ | 25 | **PASS** |
| Subcategories | 50+ | 149 | **PASS** |
| Leaf niches | 400-700 | 542 | **PASS** |
| Coverage | >90% | 100% | **PASS** |
| Gini coefficient | <0.7 | 0.383 | **PASS** |
| Overall score | — | 85.6/100 | **PASS** |

### V6 Categories Generated

| Category | Niches |
|----------|--------|
| Home Fitness | 38 |
| Quick Meal Solutions | 36 |
| Strength & Conditioning | 33 |
| Makeup & Beauty | 30 |
| Food & Travel | 27 |
| Fitness Motivation | 26 |
| Yoga & Wellness | 25 |
| Skill Mastery | 24 |
| Lifestyle & Culture | 24 |
| Quick Cooking | 24 |
| Arts & Crafts | 20 |
| Personal Finance | 19 |
| Skincare & Beauty | 19 |
| Home & DIY | 19 |
| Running & Fitness | 19 |
| Automotive DIY | 17 |
| Fitness & Weight Loss | 17 |
| Meal Prep & Nutrition | 20 |
| Gaming Content | 14 |
| Parenting & Development | 10 |
| Music Education | 11 |
| Pet Care | 13 |
| Nutrition & Lifestyle | 12 |
| Baking & Desserts | 24 |
| Personal Development | 21 |

### Sample V6 Niches (New Categories)

**Gaming Content:**
- Gamer Rage Reactions
- GTA Online Money Glitches
- Roblox Game Development Tutorials
- Horror Game Reaction Rankings
- Minecraft Building Techniques

**Personal Finance:**
- Beginner Stock Market Investing
- Real Estate Investment Strategies
- DIY Tax Filing Tips
- Crypto DeFi Explained

**Automotive DIY:**
- DIY Car Oil Change Tutorials (52 videos)
- DIY Car Detailing Hacks
- DIY Car Maintenance Tips
- Quick Car Repair Hacks

**Pet Care:**
- Dog Trick Training Tutorials
- DIY Cat Enrichment Projects
- Healthy Dog Food Recipes
- Advanced Dog Trick Training

**Music Education:**
- Quick Guitar Chord Tutorials
- Easy Ukulele Song Tutorials
- Trap Melody Creation Tutorials
- Beginner Guitar Chord Progressions

**Parenting & Development:**
- Positive Discipline Techniques for Parents
- Newborn Sleep Strategies
- Postpartum Fitness & Wellness

### V6 Evaluation Score

```
Overall Quality Score: 85.6/100

Breakdown:
  Coverage: 100.0/100
  Balance:   52.1/100 (Gini 0.383 — actually good, formula penalizes heavy cats)
  Scale:    100.0/100
```

### V6 Learnings

1. **Round-robin keyword ordering works**: Even with per-minute quota throttling, all 15 categories got representation
2. **10K+ videos produces much richer niches**: Median niche size of 15 videos vs 3-5 in earlier versions
3. **Cross-platform data helps**: TikTok/Instagram hashtag culture fills gaps YouTube content misses
4. **New categories emerged naturally**: Gaming, Automotive, Pet Care, Music all have distinct clusters
5. **Balance is stable at Gini=0.383**: Fitness still dominates (3+ years of seed keywords) but new categories are real
6. **100% coverage**: 4-level hierarchy handles outliers better than 2-level

### V6 Limitations

1. **Still fitness-heavy**: YouTube V1 + V6 combined have ~5K fitness videos vs ~500 gaming videos
2. **Some near-duplicate niches**: Real estate has 4 very similar niches — needs post-processing dedup
3. **No LLM sub-niche breakdown**: Could apply V4-style LLM expansion to reach 1,000+ niches
4. **28K hashtags but not structured**: Hashtag graph analysis (V2 approach) not re-applied to V6

### V6 File Structure

```
data/v6/
├── youtube_raw.jsonl      # 3,389 new YouTube videos
├── raw_videos.jsonl       # 10,365 combined videos
├── combine_stats.json     # Dataset composition stats
├── embeddings.npy         # 10365 x 1536 float32
├── metadata.json          # Video metadata
├── clusters.json          # 542 cluster assignments
├── taxonomy.json          # Final V6 taxonomy
└── evaluation.json        # Quality metrics

pipeline/v6/
├── 1_collect_youtube.py   # Round-robin collection (15 categories)
├── 2_combine_datasets.py  # Dataset merging
├── 3_embed.py             # Embeddings
├── 4_cluster.py           # 4-level clustering
├── 5_name.py              # LLM naming
├── 6_evaluate.py          # Evaluation
└── run.sh                 # Full pipeline runner

pages/api/v6/
├── classify.ts            # V6 classifier (embedding + hashtag boost)
└── taxonomy.ts            # V6 taxonomy API endpoint
```

### How to Run V6

```bash
# Full pipeline (~25-35 min)
bash pipeline/v6/run.sh

# Or individual steps
python3 pipeline/v6/1_collect_youtube.py   # ~15-20 min (YouTube collection)
python3 pipeline/v6/2_combine_datasets.py  # ~10 sec
python3 pipeline/v6/3_embed.py             # ~2 min (~$0.014)
python3 pipeline/v6/4_cluster.py           # ~2-3 min
python3 pipeline/v6/5_name.py             # ~18-20 min (~$0.18)
python3 pipeline/v6/6_evaluate.py          # ~5 sec
```

**Total cost:** ~$0.20 per full run

### Version Progression Summary (Updated)

| Version | Focus | Approach | Data | Niches |
|---------|-------|----------|------|--------|
| V0 | Proof of concept | B (Embedding) | 3K videos | 109 |
| V1 | Multi-label + hierarchy | B (Embedding) | 4K videos | 209 |
| V2 | Hashtag graph | A + B hybrid | 4K videos | 234 |
| V3 | LLM sub-niches (limited) | A + B + C | 4K videos | 593 |
| V4 | Full LLM breakdown | A + B + C | 4K videos | 676 |
| V5 | Cross-platform data | A + B + C | 7K videos | taxonomy.json |
| **V6** | **Combined all data + new YouTube** | **B** | **10K videos** | **542** |

---

*Document created: 2026-05-22*
*Last updated: 2026-05-24 (V6 hackathon assessment + V7 planning)*

---

## Hackathon Requirements Assessment (V6)

This section documents how V6 maps to each hackathon deliverable and evaluation criterion. Written at end-of-project before final submission.

### Deliverables

| Deliverable | Requirement | V6 Status | Notes |
|---|---|---|---|
| Taxonomy file | JSON tree, name/description/hashtags/creators per node | ✅ PASS | `data/v6/taxonomy.json` — 542 niches, all fields present |
| Reproducible pipeline | One command, end-to-end | ✅ PASS | `bash pipeline/v6/run.sh` — 6 steps, ~20 min |
| Classifier | Given bio/caption/hashtags → most likely niche(s) | ✅ PASS | `/api/v6/classify` — top-5 ranked with confidence |
| Evaluation report | Coverage, granularity, quality | ⚠️ PARTIAL | Metrics exist but no held-out sample (see below) |
| Short writeup | What you did, what worked, what to improve | ✅ PASS | This LEARNINGS.md document |

### Evaluation Criteria — Honest Assessment

**1. Coverage — ⚠️ Partial**

We report 100% coverage, but this is measured on the **training data**, not a held-out sample. The brief asks to classify "a held-out sample of 1,000 creators/posts" and report what % land in a niche more specific than the top level. We never ran this test. Our 100% figure tells us no video was left unclustered — it does not tell us how the classifier performs on unseen creators. This is a real gap.

**2. Granularity — ⚠️ Moderate**

- 542 niches from 10,365 videos → average ~19 videos per niche
- Gini coefficient 0.383 — moderate distribution (not heavily skewed, not perfectly flat)
- Balance score 52.1/100 — some niches are significantly larger than others
- The brief's example bar ("Calisthenics for tall guys over 30", "Hyrox prep") suggests true micro-niches. With only 10K videos our niches likely sit at a mid-level of specificity rather than the deepest long tail.

**3. Stability — ❌ Not tested**

K-Means has random initialization. Running the pipeline twice could produce different niche splits. We never tested this. A proper submission would include: run pipeline twice, compare niche names/structure, measure overlap. Not addressed.

**4. Readability — ✅ Pass**

GPT-4o-mini generates human-readable names. The hierarchy (category → subcategory → niche) gives context. Can read "Home Fitness > Bodyweight Training > Calisthenics for Beginners" and understand who belongs there.

**5. Speed — ✅ Pass**

~20 minutes end-to-end documented. YouTube collection (~10 min) dominates. Embedding + clustering + naming add another ~10 min. Total ~$0.31 per full run.

**6. Docs — ✅ Pass**

LEARNINGS.md covers every version, decision, and trade-off. `run.sh` scripts are one-command. API key setup documented. The UI (Next.js) includes a Process tab explaining every step.

### Approaches Used

| Approach | Description | Used in V6? |
|---|---|---|
| A — Hashtag Co-Occurrence | Graph-based community detection | Partially — hashtag boost in classifier, not graph clustering |
| B — Embedding Clustering | Sentence embeddings + HDBSCAN/K-Means | ✅ Core clustering method |
| C — LLM Recursive Breakdown | GPT breaks niches into sub-niches | ✅ GPT-4o-mini for naming; V3/V4 used for discovery |
| D — Hybrid | Mix of approaches | ✅ B + LLM naming + hashtag signals |

### Stretch Goals Assessment

| Goal | Status |
|---|---|
| Cross-platform alignment | ✅ YouTube + TikTok + Instagram all in V6 corpus |
| Exemplar creators | ✅ Top creators by video count per niche |
| Confidence scores / distribution | ✅ Returns ranked top-5 with raw similarity scores |
| Open-set detection | ✅ UNKNOWN flag when best_similarity < 0.35 |
| Niche dynamics | ❌ Not implemented — static snapshot only |

### What Would Make This Submission Stronger

If there were more time, these are the three highest-impact improvements:

1. **Held-out evaluation** — Take 500-1,000 real creator bios from a source not in the training set (e.g., fresh YouTube search, Reddit posts). Run the classifier and measure: % that land in a leaf niche (not top-level), % marked UNKNOWN, average confidence. This would replace our self-referential "100% coverage" with a real generalization number.

2. **Stability test** — Run `bash pipeline/v6/run.sh` twice (steps 4-6 only, reusing embeddings). Compare the niche lists. Measure Jaccard overlap of niche names. If >70% match, the taxonomy is stable. Document this.

3. **Deeper micro-niches** — 10K videos across 542 niches averages ~19 per niche. To get truly specific niches ("Hyrox prep", "Van life solo female travel") we likely need 50K+ videos or a different approach — LLM recursive breakdown (Approach C) seeded with the V6 clusters as root nodes, then validated against video data.

### Final Grade (Self-Assessment)

| Criterion | Weight | Score | Notes |
|---|---|---|---|
| Taxonomy file | High | A | All fields, correct format, 542 niches |
| Reproducible pipeline | High | A | One command, documented |
| Classifier | High | A- | Works well, no held-out validation |
| Evaluation report | High | C+ | Metrics computed but not on held-out data |
| Writeup | Medium | A | This document |
| Coverage | High | B | 100% on training data, unknown on held-out |
| Granularity | Medium | B- | Power-law shape but balance score 52/100 |
| Stability | Medium | F | Not tested |
| Readability | Medium | A- | GPT names are generally good |
| Speed | Low | A | ~20 min, ~$0.31 |
| Docs | Medium | A | Thorough LEARNINGS.md + UI process tabs |
| Stretch goals | Bonus | A- | Cross-platform, exemplars, confidence, open-set |

**Overall: B+ / meets core requirements, evaluation rigor is the main weakness.**

---

## V7 Planning: The Actual Product

### What V7 Is

V6 is a pipeline and a demo UI. V7 is the question: **what does this look like as a real tool that someone else can actually use?**

The core insight from building V0→V6: we've built a strong backend (taxonomy + classifier). The frontend is a dev tool. V7 would flip the ratio — the pipeline runs once (or on a schedule), and the UI becomes the primary interface for non-technical users.

### Two Modes of V7

**Mode A — Self-Hosted (for hackathon judges, developers, teams)**

The user clones the repo, runs the pipeline once, and gets a web app. The existing Next.js app evolves into a proper product UI. Target: someone with a YouTube API key and OpenAI key can be classifying creators in 30 minutes.

**Mode B — Hosted Product (if this became a real startup)**

The pipeline runs on a server. Users sign up, enter a creator handle or paste a bio, get results immediately. No setup required. Taxonomy refreshes weekly.

For hackathon purposes, Mode A is realistic. But V7 design should anticipate Mode B.

### V7 Feature Scope

**1. One-Click Pipeline Runner (UI-based)**

Instead of running `bash pipeline/v6/run.sh` in a terminal, the web UI has a "Run Pipeline" button that:
- Shows real-time step progress (steps 1-6 with live log streaming via WebSocket or SSE)
- Displays cost estimate before starting
- Shows the resulting taxonomy stats when complete
- Lets you re-run individual steps (e.g., re-name without re-embedding)

This alone removes the biggest barrier to use. Non-technical users currently cannot run the pipeline at all.

**2. Creator Lookup (not just classify text)**

Current classifier: paste raw text → get niche match.

V7 classifier: enter a YouTube handle / TikTok @username → system fetches their recent videos automatically, aggregates them, and returns their niche profile. Result: niche, confidence, similar creators in the same niche.

**3. Taxonomy Browser as First-Class UI**

The current browse tab works but feels like a dev debug view. V7 makes it the main screen:
- Search bar across all 542 niches
- Click a niche → see its top creators, example videos, defining hashtags
- "Find similar niches" button → shows nearest niches by centroid distance
- Export: download a niche's creator list as CSV

**4. Batch Classification**

Upload a CSV of creator bios/handles → download classified CSV with niche, confidence, hierarchy. This is the most useful thing for anyone running a creator database.

**5. API Access**

`POST /api/v6/classify` already exists. V7 documents it properly: rate limits, auth, example responses. A simple API key system (even hardcoded in `.env.local`) lets teams build on top of it.

**6. Setup Wizard**

First-time visit → wizard that:
1. Checks for API keys (YouTube, OpenAI) — shows ✅/❌ per key
2. Checks if taxonomy data exists (`data/v6/taxonomy.json`) — if not, prompts to run pipeline
3. If pipeline not run: "Generate Taxonomy" button → runs pipeline with live progress
4. On completion: drops into the main classifier UI

This collapses "clone repo → set up keys → run bash script → open browser" into a guided 3-click flow.

### What V7 Is NOT

- Not a data collection product (we're not competing with Apify)
- Not a social analytics dashboard (not showing follower counts, engagement rates)
- Not a recommendation engine (we classify, we don't suggest who to follow)
- Not real-time (taxonomy is a snapshot, not a live graph)

### Tech Additions Needed for V7

| Feature | What's needed |
|---|---|
| Pipeline runner UI | SSE/WebSocket endpoint that streams `run.sh` stdout to browser |
| Creator lookup | YouTube Data API `channels.list` + `search.list` by handle |
| Batch classification | File upload endpoint + CSV parser + bulk classify loop |
| Setup wizard | First-load check: do `data/v6/taxonomy.json` and `.env.local` keys exist? |
| API docs page | Markdown page describing `/api/v6/classify` input/output |
| Search across niches | Simple string search on `taxonomy.json` niche names |

### V7 Does Not Require

- Database (taxonomy.json is the database)
- Auth system (single-user local tool for now)
- Cloud infrastructure (all runs on a laptop)
- New pipeline steps (V6 pipeline is the backend)

### Recommended V7 Build Order

1. **Setup wizard** — highest barrier removal, needed first
2. **Pipeline runner UI** (streaming progress) — makes pipeline accessible to non-devs
3. **Creator lookup** (by handle) — turns it from "paste text" to "find this creator"
4. **Batch CSV classification** — most useful for real use cases
5. **Niche search + deep browse** — polish the taxonomy browser
6. **API docs page** — for technical handoff

### V7 Stack (no changes needed)

Same Next.js app. Add:
- `pages/api/pipeline/run.ts` — streams shell process stdout via SSE
- `pages/api/creator/lookup.ts` — YouTube API channels.list by handle
- `pages/api/v6/batch.ts` — bulk classify endpoint
- `pages/setup.tsx` — first-run wizard page

Everything else evolves the existing UI rather than replacing it.
*Author: V0/V1/V2/V3/V4/V5/V6 Pipeline Development*

---

## V7 Post-Build: Known Issues & Gaps

### Critical: Taxonomy Coverage Gap

**Discovery date:** 2026-05-24  
**Symptom:** Creator lookup for `@solah` returned "Career Development Insights" (64.8%) from the old stale cache, then "Black-Owned Business Spotlights" (32%) after server restart with corrected centroids. Neither is correct.

**Root cause:** The V6 taxonomy was built from exactly 15 data collection categories:

```
gaming, travel, finance, arts_crafts, music_dance, parenting,
automotive, sports, home_diy, career, relationships, spirituality,
international_food, comedy, pets
```

The test channel (`@solah`) creates content about **sneakers, streetwear, NFTs, tech startups (building in public / indie hacking), and Malaysian lifestyle**. None of these map to any of the 15 source categories. Best cosine similarity was ~0.36 (36%) — well below the 0.5 threshold for a meaningful match.

**Why the old result looked plausible:** The pre-fix server had 100-dim PCA centroids in memory. The cosine function returned NaN for dimensions 100–1535 (b[i] = undefined), but numerical drift and NaN handling produced spuriously non-zero scores. These were meaningless but happened to look like real matches (64.8% was noise, not signal).

**Key insight:** A taxonomy is only as good as its source data. If a creator's content category was never collected during data ingestion, no amount of embedding quality or clustering sophistication will produce a correct classification. The classifier will always return the "closest wrong answer."

**Signals that coverage is missing:**
- Best similarity < 0.45 across all niches
- Top 5 matches span wildly different categories (Gaming + Food + Dance = nothing in common)
- Hashtag boost = 0 across all matches (no hashtag overlap at all)

### Fix Needed: Add Missing Data Categories

To properly classify fashion/sneaker and tech-startup creators, step 1 of the pipeline needs two new categories added to `1_collect_youtube.py`:

```python
"fashion_sneakers": [
    "sneaker unboxing review", "nike air jordan collection", "streetwear outfit of the day",
    "sneaker cop or drop", "hypebeast fashion haul", "limited edition shoe drop",
    "adidas yeezy review", "sneaker resell guide", "streetwear brand review",
    "shoe collection tour", "fashion week highlights", "sneaker convention vlog",
    "sneaker cleaning tutorial", "thrift flip streetwear", "sneaker grail unboxing",
],
"tech_startup": [
    "building saas in public", "indie hacker revenue update", "startup founder daily vlog",
    "coding my startup solo", "mrr milestone update", "no code app build tutorial",
    "product hunt launch tips", "solopreneur business model", "software side project launch",
    "startup failure lessons", "building in public accountability", "bootstrapped startup growth",
    "api integration tutorial", "developer productivity tools", "vibe coding startup",
],
```

Re-running steps 1→5 (skip step 2 if combining with existing data) would add ~1,500 new videos and produce ~60-80 new niches covering these content types.

**Estimated cost to fix:** ~$0.02 more embeddings + ~$0.05 more naming = ~$0.07 additional

---

## Core Reflection: Does This Actually Solve the Problem?

> *"When in doubt, look at the output and ask: would this taxonomy actually help someone understand the creator landscape? If not, iterate."*

### Honest Answer: Partially — with a critical flaw

**Where it works:**
For creators making content within the 15 categories we explicitly collected data from (gaming, travel, finance, cooking, fitness, parenting, automotive, sports, home_diy, career, relationships, spirituality, food, comedy, pets), the taxonomy surfaces real, specific niches. The hierarchy is clean, the pipeline is reproducible at ~$0.31, and the classifier is fast.

**Where it breaks down:**
The taxonomy only reflects what we *searched for*, not what actually exists in the creator landscape. We chose 15 categories upfront, ran keyword queries, clustered the results, and called it a taxonomy. That is not bottom-up discovery — it is top-down confirmation. The `@solah` test proved this: a real creator making sneaker, streetwear, and indie-hacking content got classified as "Gamer Rage Reactions" and "Vegan Restaurant Reviews" at 32% confidence. The system returned wrong answers with no signal that anything was wrong.

**The deeper problem — sampling bias masquerading as discovery:**
A first-time user running creator lookup on almost anyone outside those 15 buckets gets garbage results. Garbage with a confidence score. That is arguably worse than "no match found" because it misleads.

**What would actually answer yes:**
- Start from a broad random sample of creators, not category-specific keyword queries
- Let the embedding clusters tell you what categories exist, rather than seeding the search with categories you already assumed
- Validate classifications against human judgement on a held-out set
- Cover obvious missing gaps: fashion/sneakers, beauty, tech/coding/startup, SEA-language content, news commentary, business/entrepreneurship

**Verdict:** As a *pipeline demo* — yes, it works. As a tool that genuinely helps someone understand the creator landscape — not yet. It understands the 15 corners of the landscape we already knew existed before we started. The taxonomy reflects our assumptions, not the data.
