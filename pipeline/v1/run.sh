#!/bin/bash
# V1 Pipeline Runner
# Generates the enhanced hierarchical taxonomy with 500-1000 niches

set -e  # Exit on any error

echo "========================================"
echo "V1 Short-Form Creator Taxonomy Pipeline"
echo "========================================"
echo ""

# Check for required environment variables
if [ ! -f "../../.env.local" ]; then
    echo "Error: .env.local not found. Please create it with:"
    echo "  YOUTUBE_API_KEY=your_key"
    echo "  OPENAI_API_KEY=your_key"
    exit 1
fi

# Create data directory
mkdir -p ../../data/v1

echo "[1/6] Collecting videos from YouTube API..."
echo "      Target: 20-30K videos from 200+ keywords"
echo "      This may take 10-15 minutes..."
python3 1_collect.py
echo ""

echo "[2/6] Generating embeddings with OpenAI..."
echo "      Model: text-embedding-3-small"
python3 2_embed.py
echo ""

echo "[3/6] Recursive hierarchical clustering..."
echo "      Level 1: K-Means (k=20) for categories"
echo "      Level 2: K-Means (k=5-8) for subcategories"
echo "      Level 3: HDBSCAN for micro-niches"
echo "      Level 4: Split large niches"
python3 3_cluster.py
echo ""

echo "[4/6] Naming hierarchy with LLM..."
echo "      Naming categories, subcategories, and niches"
echo "      Extracting exemplar creators per niche"
python3 4_name.py
echo ""

echo "[5/6] Building classification endpoints..."
echo "      Multi-label classifier ready"
echo ""

echo "[6/6] Running evaluation..."
echo "      Stability testing across random seeds"
echo "      Clustering quality metrics"
python3 6_evaluate.py
echo ""

echo "========================================"
echo "V1 Pipeline Complete!"
echo "========================================"
echo ""
echo "Output files:"
echo "  data/v1/raw_videos.jsonl   - Raw video metadata"
echo "  data/v1/embeddings.npy     - Video embeddings"
echo "  data/v1/metadata.json      - Video metadata"
echo "  data/v1/clusters.json      - Cluster assignments"
echo "  data/v1/taxonomy.json      - Final taxonomy"
echo "  data/v1/evaluation.json    - Quality metrics"
echo ""
echo "Next steps:"
echo "  1. Start the web server: npm run dev"
echo "  2. Switch to V1 tab in the UI"
echo "  3. Try the multi-label classifier"
echo ""
