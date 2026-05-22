#!/bin/bash
# V3 Pipeline Runner: LLM-Driven Sub-Niche Discovery
#
# This pipeline adds Approach C (LLM sub-niche breakdown) to the taxonomy.
# Requires V2 to have been run first.
#
# Usage: cd pipeline/v3 && bash run.sh

set -e

echo "=============================================="
echo "V3 Pipeline: LLM-Driven Sub-Niche Discovery"
echo "=============================================="
echo ""
echo "This pipeline will:"
echo "  1. Analyze V2 niches for breakdown candidates"
echo "  2. Use GPT-4o-mini to suggest specific sub-niches"
echo "  3. Validate suggestions against real video data"
echo "  4. Merge validated sub-niches into V3 taxonomy"
echo "  5. Evaluate V3 vs V2"
echo ""
echo "Prerequisites: V2 pipeline must have been run"
echo ""

# Check for V2 taxonomy
if [ ! -f "../../data/v2/taxonomy.json" ]; then
    echo "ERROR: V2 taxonomy not found!"
    echo "Please run the V2 pipeline first: cd pipeline/v2 && bash run.sh"
    exit 1
fi

# Check for V1 metadata (needed for validation)
if [ ! -f "../../data/v1/metadata.json" ]; then
    echo "ERROR: V1 metadata not found!"
    echo "Please run the V1 pipeline first: cd pipeline/v1 && bash run.sh"
    exit 1
fi

echo "Starting V3 pipeline..."
echo ""

# Step 1: Analyze niches
echo "[1/5] Analyzing V2 niches for breakdown candidates..."
python3 1_analyze_niches.py
echo ""

# Step 2: LLM breakdown
echo "[2/5] Generating sub-niche suggestions with LLM..."
python3 2_llm_breakdown.py
echo ""

# Step 3: Validate suggestions
echo "[3/5] Validating suggestions against video data..."
python3 3_validate_suggestions.py
echo ""

# Step 4: Merge taxonomy
echo "[4/5] Creating V3 taxonomy..."
python3 4_merge_taxonomy.py
echo ""

# Step 5: Evaluate
echo "[5/5] Evaluating V3 taxonomy..."
python3 5_evaluate.py
echo ""

echo "=============================================="
echo "V3 Pipeline Complete!"
echo "=============================================="
echo ""
echo "Output files in data/v3/:"
echo "  - niche_analysis.json    (niche breakdown candidates)"
echo "  - llm_suggestions.json   (LLM-generated sub-niches)"
echo "  - validated_suggestions.json (validation results)"
echo "  - taxonomy.json          (final V3 taxonomy)"
echo "  - evaluation.json        (V3 vs V2 comparison)"
echo ""
echo "Run 'npm run dev' to see V3 in the UI"
