"""
Feature generation script for prediction pipeline
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import pandas as pd
import logging

from src.data.dynamic_loader import DynamicDataLoader
from src.data.preprocessor_improved import ImprovedDataPreprocessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Generate features for forecasting")
    parser.add_argument("--data-dir", default="./data", help="Input data directory")
    parser.add_argument("--out", default="features.parquet", help="Output features file")

    args = parser.parse_args()

    logger.info(f"Loading data from {args.data_dir}")

    # DynamicDataLoader scans all CSVs in data_dir and detects the channel from each
    # filename. Setting upload_dir=data_dir means _has_uploaded_files() finds the CSVs
    # and load_data() uses the dynamic scan path — no hardcoded filenames.
    loader = DynamicDataLoader(data_dir=args.data_dir, upload_dir=args.data_dir)
    df, _ = loader.load_data(force_static=False)

    preprocessor = ImprovedDataPreprocessor()
    df_agg = preprocessor.prepare_all_channels(df)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True) if os.path.dirname(args.out) else None
    df_agg.to_parquet(args.out, index=False)

    logger.info(f"Features saved to {args.out} ({len(df_agg)} records)")


if __name__ == "__main__":
    main()
