#!/bin/bash
# V6 Pipeline: Combined multi-platform data + new YouTube categories
# Run from project root: bash pipeline/v6/run.sh
set -e
cd "$(dirname "$0")/../.."

echo "=== V6 Taxonomy Pipeline ==="
echo "Combining all datasets + new YouTube categories"
echo "=============================================="

echo ""
echo "[1/6] Collecting new YouTube data (underrepresented categories)..."
python3 pipeline/v6/1_collect_youtube.py

echo ""
echo "[2/6] Combining all datasets (V5 + V6 new YouTube)..."
python3 pipeline/v6/2_combine_datasets.py

echo ""
echo "[3/6] Generating embeddings..."
python3 pipeline/v6/3_embed.py

echo ""
echo "[4/6] Clustering into niches..."
python3 pipeline/v6/4_cluster.py

echo ""
echo "[5/6] Naming clusters with GPT-4o-mini..."
python3 pipeline/v6/5_name.py

echo ""
echo "[6/6] Evaluating taxonomy quality..."
python3 pipeline/v6/6_evaluate.py

echo ""
echo "=============================================="
echo "V6 Pipeline complete!"
echo "  Taxonomy: data/v6/taxonomy.json"
echo "  Evaluation: data/v6/evaluation.json"
echo "  Run 'npm run dev' and visit http://localhost:3000"
