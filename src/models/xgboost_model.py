"""
XGBoost Model with Quantile Regression for Probabilistic Forecasting
"""
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class XGBoostForecaster:
    """XGBoost model for revenue forecasting with uncertainty"""

    def __init__(self, quantiles: List[float] = [0.1, 0.5, 0.9]):
        self.quantiles = quantiles
        self.models = {}  # One model per quantile
        self.feature_columns = []
        self.is_fitted = False

    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create features for XGBoost"""
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])

        # Temporal features
        df['day_of_week'] = df['date'].dt.dayofweek
        df['day_of_month'] = df['date'].dt.day
        df['month'] = df['date'].dt.month
        df['quarter'] = df['date'].dt.quarter
        df['week_of_year'] = df['date'].dt.isocalendar().week
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)

        # Lag features
        for lag in [1, 7, 14, 30]:
            df[f'revenue_lag_{lag}'] = df.groupby('channel')['revenue'].shift(lag)
            df[f'spend_lag_{lag}'] = df.groupby('channel')['spend'].shift(lag)
            df[f'roas_lag_{lag}'] = df.groupby('channel')['roas'].shift(lag)

        # Rolling features
        for window in [7, 14, 30]:
            df[f'revenue_roll_{window}'] = df.groupby('channel')['revenue'].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )
            df[f'spend_roll_{window}'] = df.groupby('channel')['spend'].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )
            df[f'roas_roll_{window}'] = df.groupby('channel')['roas'].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )

        # Fill NaN values
        df = df.fillna(0)

        return df

    def fit(self, df: pd.DataFrame, target_col: str = 'revenue'):
        """Train XGBoost models for each quantile"""
        logger.info(f"Training XGBoost quantile models for {target_col}")

        # Create features
        df = self.create_features(df)

        # Define feature columns (exclude target and metadata)
        exclude_cols = ['date', 'revenue', 'channel', 'campaign_id', 'campaign_name', 'campaign_type']
        self.feature_columns = [col for col in df.columns if col not in exclude_cols]

        X = df[self.feature_columns]
        y = df[target_col]

        # Train model for each quantile
        for quantile in self.quantiles:
            logger.info(f"Training model for quantile {quantile}")

            params = {
                'objective': 'reg:quantileerror',
                'quantile_alpha': quantile,
                'max_depth': 6,
                'learning_rate': 0.1,
                'n_estimators': 100,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'random_state': 42
            }

            model = xgb.XGBRegressor(**params)
            model.fit(X, y, verbose=False)

            self.models[quantile] = model

        self.is_fitted = True
        logger.info("XGBoost training completed")
        return self

    def predict(self, df: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Generate predictions for all quantiles"""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")

        # Create features
        df = self.create_features(df)
        X = df[self.feature_columns]

        predictions = {}
        for quantile, model in self.models.items():
            pred = model.predict(X)
            predictions[f'q{int(quantile*100)}'] = pred

        return predictions

    def get_forecast_summary(self, predictions: Dict[str, np.ndarray]) -> Dict:
        """Calculate summary statistics from predictions"""
        median = predictions.get('q50', predictions.get('q45', list(predictions.values())[0]))

        summary = {
            'mean': float(np.mean(median)),
            'total': float(np.sum(median)),
            'lower_bound': float(np.sum(predictions[f'q{int(min(self.quantiles)*100)}'])),
            'upper_bound': float(np.sum(predictions[f'q{int(max(self.quantiles)*100)}'])),
            'uncertainty': float(np.sum(predictions[f'q{int(max(self.quantiles)*100)}']) -
                               np.sum(predictions[f'q{int(min(self.quantiles)*100)}']))
        }

        return summary

    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance from median model"""
        if not self.is_fitted:
            raise ValueError("Model must be fitted first")

        median_model = self.models[0.5]
        importance = pd.DataFrame({
            'feature': self.feature_columns,
            'importance': median_model.feature_importances_
        }).sort_values('importance', ascending=False)

        return importance


class MultiChannelXGBoostForecaster:
    """XGBoost forecaster for multiple channels"""

    def __init__(self, quantiles: List[float] = [0.1, 0.5, 0.9]):
        self.quantiles = quantiles
        self.models = {}

    def fit(self, df: pd.DataFrame, channels: List[str] = None):
        """Fit separate models for each channel"""
        if channels is None:
            channels = df['channel'].unique()

        for channel in channels:
            logger.info(f"Training XGBoost model for channel: {channel}")
            channel_data = df[df['channel'] == channel].copy()

            model = XGBoostForecaster(quantiles=self.quantiles)
            model.fit(channel_data, target_col='revenue')

            self.models[channel] = model

        return self

    def predict(self, df: pd.DataFrame) -> Dict[str, Dict[str, np.ndarray]]:
        """Predict for all channels"""
        forecasts = {}

        for channel, model in self.models.items():
            channel_data = df[df['channel'] == channel].copy()
            if len(channel_data) > 0:
                forecast = model.predict(channel_data)
                forecasts[channel] = forecast

        return forecasts


if __name__ == "__main__":
    from src.data.loader import DataLoader
    from src.data.preprocessor import DataPreprocessor

    loader = DataLoader("./data")
    df = loader.load_all_channels()

    preprocessor = DataPreprocessor()
    df = preprocessor.prepare_for_forecasting(df)
    df_agg = preprocessor.aggregate_by_channel(df, freq='D')

    # Train model
    google_data = df_agg[df_agg['channel'] == 'google'].copy()

    forecaster = XGBoostForecaster()
    forecaster.fit(google_data)

    # Predict on same data (for testing)
    predictions = forecaster.predict(google_data.tail(30))
    summary = forecaster.get_forecast_summary(predictions)

    print("Forecast Summary:")
    print(summary)

    print("\nFeature Importance:")
    print(forecaster.get_feature_importance().head(10))
