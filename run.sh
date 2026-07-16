#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${1:-./data}"
MODEL_PATH="${2:-./pickle/model.pkl}"
OUTPUT_PATH="${3:-./output/predictions.csv}"

mkdir -p "$(dirname "$OUTPUT_PATH")"

echo "=== AIgnition Forecasting Pipeline ==="
echo "Data dir:    $DATA_DIR"
echo "Model path:  $MODEL_PATH"
echo "Output path: $OUTPUT_PATH"
echo "======================================="

# Step 1: Generate features from data/
python src/generate_features.py \
    --data-dir "$DATA_DIR" \
    --out features.parquet

# Step 2: Load models and produce predictions
python src/predict.py \
    --features features.parquet \
    --model "$MODEL_PATH" \
    --output "$OUTPUT_PATH"

echo "Done. Predictions written to $OUTPUT_PATH"
