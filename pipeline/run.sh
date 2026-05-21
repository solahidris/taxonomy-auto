#!/bin/bash
# One-command pipeline: YouTube data → embeddings → clusters → taxonomy
set -e

cd "$(dirname "$0")/.."

echo ""
echo "=== Short-Form Creator Taxonomy Pipeline ==="
echo ""

echo "[1/5] Collecting videos from YouTube..."
python pipeline/1_collect.py

echo ""
echo "[2/5] Generating OpenAI embeddings..."
python pipeline/2_embed.py

echo ""
echo "[3/5] Clustering into niches..."
python pipeline/3_cluster.py

echo ""
echo "[4/5] Naming clusters with GPT-4o-mini..."
python pipeline/4_name.py

echo ""
echo "[5/5] Evaluating taxonomy..."
python pipeline/5_evaluate.py

echo ""
echo "All done. taxonomy.json and centroids.json saved to data/"
echo "Run 'npm run dev' and open http://localhost:3000 for the demo."
