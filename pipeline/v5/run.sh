#!/bin/bash
# V5 Pipeline Runner: Cross-Platform Taxonomy
# Budget: $5 ($1 TikTok + $1 Instagram + $1 YouTube + $2 buffer)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."

echo "=========================================="
echo "V5: Cross-Platform Taxonomy Pipeline"
echo "=========================================="
echo ""
echo "Budget allocation:"
echo "  - TikTok:    ~\$1"
echo "  - Instagram: ~\$1"
echo "  - YouTube:   ~\$1"
echo "  - Buffer:    ~\$2"
echo ""
read -p "Continue with data collection? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "[1/7] Collecting TikTok videos..."
echo "--------------------------------------"
python3 pipeline/v5/1_collect_tiktok.py

echo ""
echo "[2/7] Collecting Instagram Reels..."
echo "--------------------------------------"
python3 pipeline/v5/2_collect_instagram.py

echo ""
echo "[3/7] Collecting YouTube Shorts..."
echo "--------------------------------------"
python3 pipeline/v5/3_collect_youtube.py

echo ""
echo "[4/7] Merging cross-platform data..."
echo "--------------------------------------"
python3 pipeline/v5/4_merge_crossplatform.py

echo ""
echo "[5/7] Generating embeddings..."
echo "--------------------------------------"
python3 pipeline/v5/5_embed.py

echo ""
echo "[6/7] Building unified taxonomy..."
echo "--------------------------------------"
python3 pipeline/v5/6_build_taxonomy.py

echo ""
echo "[7/7] Evaluating taxonomy..."
echo "--------------------------------------"
python3 pipeline/v5/7_evaluate.py

echo ""
echo "=========================================="
echo "V5 Pipeline Complete!"
echo "=========================================="
echo ""
echo "Output files:"
echo "  data/v5/taxonomy.json"
echo "  data/v5/evaluation.json"
echo ""
echo "Run 'npm run dev' to see the results."
