"""
Train and save forecasting models
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
import joblib
import logging
import pandas as pd
from pathlib import Path

from src.data.loader import DataLoader
from src.data.preprocessor_improved import ImprovedDataPreprocessor
from src.models.multi_horizon_forecaster import MultiHorizonForecaster
from src.simulation.budget_optimizer import BudgetOptimizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Train models and save to pickle directory"""
    logger.info("Starting model training...")

    pickle_dir = Path("./pickle")
    pickle_dir.mkdir(exist_ok=True)

    # Load data
    logger.info("Loading data...")
    loader = DataLoader("./data")
    df = loader.load_all_channels()

    # Preprocess with channel-specific fixes (Search-only Bing, Meta Nov 2024+,
    # outlier capping) — same pipeline used by the API and generate_features.py
    logger.info("Preprocessing data...")
    preprocessor = ImprovedDataPreprocessor()
    df_agg = preprocessor.prepare_all_channels(df)

    # Train single model artifact (all 9 channel × horizon models inside)
    logger.info("Training MultiHorizonForecaster (3 channels x 3 horizons)...")
    model = MultiHorizonForecaster()
    model.fit(df_agg)

    model_path = pickle_dir / "model.pkl"
    joblib.dump(model, model_path)
    logger.info(f"Model saved -> {model_path}")

    # Train budget optimizer on the cleaned, aggregated data
    logger.info("Training budget optimizer...")
    optimizer = BudgetOptimizer()
    for channel in df_agg["channel"].unique():
        optimizer.fit_spend_response_curve(df_agg, channel)

    optimizer_path = pickle_dir / "budget_optimizer.pkl"
    joblib.dump(optimizer, optimizer_path)
    logger.info(f"Budget optimizer saved -> {optimizer_path}")

    # Save preprocessor
    preprocessor_path = pickle_dir / "preprocessor.pkl"
    joblib.dump(preprocessor, preprocessor_path)
    logger.info(f"Preprocessor saved -> {preprocessor_path}")

    # Save metadata
    metadata = {
        "trained_at": pd.Timestamp.now().isoformat(),
        "data_records": len(df),
        "channels": df["channel"].unique().tolist(),
        "date_range": {
            "start": str(df["date"].min()),
            "end": str(df["date"].max()),
        },
        "models": {
            "forecaster": str(model_path),
            "optimizer": str(optimizer_path),
            "preprocessor": str(preprocessor_path),
        },
    }

    metadata_path = pickle_dir / "model_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Metadata saved -> {metadata_path}")

    print("\n" + "=" * 60)
    print("MODEL TRAINING SUMMARY")
    print("=" * 60)
    print(f"Total records:  {len(df)}")
    print(f"Date range:     {df['date'].min()} to {df['date'].max()}")
    print(f"Channels:       {', '.join(df['channel'].unique())}")
    print(f"Model artifact: {model_path.resolve()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
