"""
Prediction script - loads model and generates forecasts
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import joblib
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Generate predictions from trained model")
    parser.add_argument("--features", required=True, help="Input features parquet file")
    parser.add_argument("--model", default="./pickle/model.pkl", help="Path to model.pkl")
    parser.add_argument("--output", default="./output/predictions.csv", help="Output predictions CSV")

    args = parser.parse_args()

    logger.info(f"Loading features from {args.features}")
    df_agg = pd.read_parquet(args.features)

    logger.info(f"Loading model from {args.model}")
    model = joblib.load(args.model)

    logger.info("Generating predictions...")
    predictions_df = model.predict(df_agg)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    predictions_df.to_csv(args.output, index=False)

    logger.info(f"Predictions saved to {args.output} ({len(predictions_df)} rows)")
    print(predictions_df.to_string(index=False))


if __name__ == "__main__":
    main()
