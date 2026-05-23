#!/bin/bash
# V4 Pipeline Runner - Full LLM Breakdown (No Limit)

set -e

echo "============================================================"
echo "V4 Pipeline: Full LLM Sub-Niche Breakdown"
echo "============================================================"
echo ""
echo "V4 removes the 100-niche limit from V3 and processes ALL candidates."
echo ""

cd "$(dirname "$0")"

echo "[1/5] Analyzing niches..."
python3 1_analyze_niches.py

echo ""
echo "[2/5] Running LLM breakdown (ALL candidates - this may take a few minutes)..."
python3 2_llm_breakdown.py

echo ""
echo "[3/5] Validating suggestions..."
python3 3_validate_suggestions.py

echo ""
echo "[4/5] Merging taxonomy..."
python3 4_merge_taxonomy.py

echo ""
echo "[5/5] Evaluating results..."
python3 5_evaluate.py

echo ""
echo "============================================================"
echo "V4 Pipeline Complete!"
echo "============================================================"
echo ""
echo "Output files:"
echo "  - data/v4/niche_analysis.json"
echo "  - data/v4/llm_suggestions.json"
echo "  - data/v4/validated_suggestions.json"
echo "  - data/v4/taxonomy.json"
echo "  - data/v4/evaluation.json"
