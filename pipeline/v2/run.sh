#!/bin/bash
# V2 Pipeline: Hashtag Co-occurrence Graph
# Adds Approach A (hashtag analysis) to complement V1's Approach B (embeddings)

set -e

echo "=========================================="
echo "V2 Pipeline: Hashtag Co-occurrence"
echo "=========================================="
echo ""

cd "$(dirname "$0")"

echo "[1/5] Building hashtag co-occurrence graph..."
python3 1_build_hashtag_graph.py
echo ""

echo "[2/5] Running community detection (Louvain)..."
python3 2_community_detection.py
echo ""

echo "[3/5] Cross-validating with V1 embeddings..."
python3 3_merge_with_embeddings.py
echo ""

echo "[4/5] Building unified taxonomy..."
python3 4_unified_taxonomy.py
echo ""

echo "[5/5] Evaluating V2 vs V1..."
python3 5_evaluate.py
echo ""

echo "=========================================="
echo "V2 Pipeline Complete!"
echo "=========================================="
echo ""
echo "Output files:"
echo "  data/v2/hashtag_graph.pkl    - Hashtag co-occurrence graph"
echo "  data/v2/communities.json     - Louvain community detection results"
echo "  data/v2/merged_analysis.json - Cross-validation with V1"
echo "  data/v2/taxonomy.json        - Unified V2 taxonomy"
echo "  data/v2/evaluation.json      - V2 vs V1 comparison"
