"""
Improved Prophet Model with Channel-Specific Configs and Log Transform
Addresses accuracy issues on Bing, Meta, and longer forecast horizons
"""
import pandas as pd
import numpy as np
from prophet import Prophet
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


def get_prophet_config(channel: str) -> Dict:
    """
    Get channel-specific Prophet configuration

    Args:
        channel: 'google', 'bing', or 'meta'

    Returns:
        Dictionary of Prophet parameters
    """
    configs = {
        'google': {
            'changepoint_prior_scale': 0.05,      # stable, don't overfit
            'seasonality_prior_scale': 10.0,      # strong seasonality
            'seasonality_mode': 'multiplicative', # percentage-based
            'interval_width': 0.80,               # P10-P90
            'weekly_seasonality': True,
            'yearly_seasonality': True,
            'daily_seasonality': False
        },
        'bing': {
            'changepoint_prior_scale': 0.30,      # HIGH - revenue is volatile
            'seasonality_prior_scale': 5.0,       # LOWER - less seasonal signal
            'seasonality_mode': 'additive',       # better for sparse data
            'interval_width': 0.90,               # WIDER - honest uncertainty
            'weekly_seasonality': True,
            'yearly_seasonality': False,          # not enough history
            'daily_seasonality': False
        },
        'meta': {
            'changepoint_prior_scale': 0.15,      # moderate flexibility
            'seasonality_prior_scale': 8.0,       # moderate seasonality
            'seasonality_mode': 'multiplicative',
            'interval_width': 0.85,               # slightly wider
            'weekly_seasonality': True,
            'yearly_seasonality': False,          # not enough history
            'daily_seasonality': False
        }
    }

    return configs.get(channel, configs['google'])


class ImprovedProphetForecaster:
    """
    Prophet model with improvements:
    - Channel-specific configurations
    - Log transform for longer horizons
    - Better handling of sparse data
    """

    def __init__(self, channel: str = 'google', use_log_transform: bool = False):
        """
        Initialize improved Prophet forecaster

        Args:
            channel: Channel name for config lookup
            use_log_transform: Use log transform for longer forecast horizons
        """
        self.channel = channel
        self.use_log_transform = use_log_transform
        self.config = get_prophet_config(channel)
        self.model = None
        self.is_fitted = False
        self.has_spend_regressor = False
        self.historical_spend = None

    def prepare_data(self, df: pd.DataFrame, target_col: str = 'revenue') -> pd.DataFrame:
        """Prepare data in Prophet format (ds, y)"""
        prophet_df = pd.DataFrame({
            'ds': pd.to_datetime(df['date']),
            'y': df[target_col]
        })

        # Apply log transform if enabled
        if self.use_log_transform:
            prophet_df['y'] = np.log1p(prophet_df['y'])  # log(1 + y) handles zeros

        # Add regressor for spend if available
        if 'spend' in df.columns and target_col == 'revenue':
            prophet_df['spend'] = df['spend']
            if self.use_log_transform:
                prophet_df['spend'] = np.log1p(prophet_df['spend'])

        return prophet_df

    def fit(self, df: pd.DataFrame, target_col: str = 'revenue',
            include_spend: bool = True) -> 'ImprovedProphetForecaster':
        """Train Prophet model with channel-specific config"""
        logger.info(f"Training Improved Prophet for {self.channel} (log_transform={self.use_log_transform})")

        prophet_df = self.prepare_data(df, target_col)

        # Initialize Prophet with channel-specific config
        self.model = Prophet(
            interval_width=self.config['interval_width'],
            changepoint_prior_scale=self.config['changepoint_prior_scale'],
            seasonality_prior_scale=self.config['seasonality_prior_scale'],
            seasonality_mode=self.config['seasonality_mode'],
            daily_seasonality=self.config['daily_seasonality'],
            weekly_seasonality=self.config['weekly_seasonality'],
            yearly_seasonality=self.config['yearly_seasonality']
        )

        # Add spend as regressor if available
        if include_spend and 'spend' in prophet_df.columns:
            self.model.add_regressor('spend')
            self.has_spend_regressor = True
            self.historical_spend = prophet_df['spend'].values

        # Add custom seasonalities for channels with enough history
        if self.channel == 'google':
            self.model.add_seasonality(name='monthly', period=30.5, fourier_order=5)
            self.model.add_seasonality(name='quarterly', period=91.25, fourier_order=8)

        # Fit model
        self.model.fit(prophet_df)
        self.is_fitted = True

        logger.info(f"Prophet training completed for {self.channel}")
        return self

    def predict(self, periods: int, future_spend: pd.Series = None) -> pd.DataFrame:
        """Generate forecast for future periods"""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")

        # Create future dataframe
        future = self.model.make_future_dataframe(periods=periods, freq='D')

        # Add spend values if regressor was used during training
        if self.has_spend_regressor:
            if future_spend is not None:
                # Use provided future spend
                spend_extended = pd.concat([
                    pd.Series(self.historical_spend),
                    future_spend
                ]).reset_index(drop=True)
            else:
                # Use historical average for future periods
                avg_spend = np.mean(self.historical_spend[-30:])  # Last 30 days average
                future_spend_values = np.full(periods, avg_spend)
                spend_extended = pd.concat([
                    pd.Series(self.historical_spend),
                    pd.Series(future_spend_values)
                ]).reset_index(drop=True)

            future['spend'] = spend_extended.values[:len(future)]

        # Generate predictions
        forecast = self.model.predict(future)

        # Reverse log transform if it was used
        if self.use_log_transform:
            forecast['yhat'] = np.expm1(forecast['yhat'])
            forecast['yhat_lower'] = np.expm1(forecast['yhat_lower'])
            forecast['yhat_upper'] = np.expm1(forecast['yhat_upper'])

        return forecast

    def predict_with_custom_spend(self, periods: int, daily_spend: float) -> pd.DataFrame:
        """Forecast with custom daily spend (budget simulation)"""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")

        # Create future dataframe
        future = self.model.make_future_dataframe(periods=periods, freq='D')

        # Set custom spend
        if self.has_spend_regressor:
            spend_value = daily_spend
            if self.use_log_transform:
                spend_value = np.log1p(daily_spend)

            # Historical spend + future custom spend
            future_spend_values = np.full(periods, spend_value)
            spend_extended = pd.concat([
                pd.Series(self.historical_spend),
                pd.Series(future_spend_values)
            ]).reset_index(drop=True)

            future['spend'] = spend_extended.values[:len(future)]

        # Generate forecast
        forecast = self.model.predict(future)

        # Reverse log transform if it was used
        if self.use_log_transform:
            forecast['yhat'] = np.expm1(forecast['yhat'])
            forecast['yhat_lower'] = np.expm1(forecast['yhat_lower'])
            forecast['yhat_upper'] = np.expm1(forecast['yhat_upper'])

        return forecast

    def get_forecast_summary(self, forecast: pd.DataFrame, periods: int = None) -> Dict:
        """Extract summary statistics from forecast"""
        if periods is not None:
            forecast = forecast.tail(periods)

        summary = {
            'mean_daily': float(forecast['yhat'].mean()),
            'total': float(forecast['yhat'].sum()),
            'lower_bound': float(forecast['yhat_lower'].sum()),
            'upper_bound': float(forecast['yhat_upper'].sum()),
            'uncertainty_range': float(forecast['yhat_upper'].sum() - forecast['yhat_lower'].sum()),
            'p10': float(forecast['yhat_lower'].sum()),
            'p50': float(forecast['yhat'].sum()),
            'p90': float(forecast['yhat_upper'].sum()),
        }

        return summary

    def evaluate_backtest(self, df: pd.DataFrame, test_days: int = 30) -> Dict:
        """Backtest on historical data"""
        # Split data
        train_df = df.iloc[:-test_days].copy()
        test_df = df.iloc[-test_days:].copy()

        # Fit on train
        self.fit(train_df, include_spend='spend' in df.columns)

        # Predict on test period
        forecast = self.predict(periods=test_days)
        forecast_test = forecast.tail(test_days).reset_index(drop=True)
        test_df_reset = test_df.reset_index(drop=True)

        # Calculate metrics
        actual = test_df_reset['revenue'].values
        predicted = forecast_test['yhat'].values

        mae = np.mean(np.abs(actual - predicted))
        rmse = np.sqrt(np.mean((actual - predicted) ** 2))
        mape = np.mean(np.abs((actual - predicted) / (actual + 1e-10))) * 100

        # Check if actual falls within prediction intervals
        within_interval = np.sum(
            (actual >= forecast_test['yhat_lower'].values) &
            (actual <= forecast_test['yhat_upper'].values)
        ) / len(actual) * 100

        metrics = {
            'mae': float(mae),
            'rmse': float(rmse),
            'mape': float(mape),
            'within_interval_pct': float(within_interval),
            'actual_total': float(actual.sum()),
            'predicted_total': float(predicted.sum()),
            'total_error_pct': float(abs(actual.sum() - predicted.sum()) / actual.sum() * 100)
        }

        return metrics


class MultiChannelImprovedForecaster:
    """Improved multi-channel forecaster with channel-specific configs"""

    def __init__(self, use_log_transform: bool = False):
        self.use_log_transform = use_log_transform
        self.models = {}

    def fit(self, df: pd.DataFrame, channels: List[str] = None):
        """Fit separate Prophet models for each channel with optimal configs"""
        if channels is None:
            channels = df['channel'].unique()

        for channel in channels:
            logger.info(f"Training Improved Prophet for channel: {channel}")
            channel_data = df[df['channel'] == channel].copy()

            model = ImprovedProphetForecaster(
                channel=channel,
                use_log_transform=self.use_log_transform
            )
            model.fit(channel_data, include_spend_regressor=True)

            self.models[channel] = model

        logger.info(f"Trained improved models for {len(self.models)} channels")
        return self

    def predict(self, periods: int = 30, channel_budgets: Dict[str, float] = None) -> Dict[str, pd.DataFrame]:
        """Predict for all channels"""
        forecasts = {}

        for channel, model in self.models.items():
            if channel_budgets and channel in channel_budgets:
                forecast = model.predict_with_custom_spend(
                    periods=periods,
                    daily_spend=channel_budgets[channel]
                )
            else:
                forecast = model.predict(periods=periods)

            forecasts[channel] = forecast

        return forecasts

    def evaluate_all_channels(self, df: pd.DataFrame, test_days: int = 30) -> Dict[str, Dict]:
        """Backtest all channels"""
        results = {}

        for channel in df['channel'].unique():
            logger.info(f"Evaluating Improved Prophet for channel: {channel}")
            channel_data = df[df['channel'] == channel].copy()

            model = ImprovedProphetForecaster(
                channel=channel,
                use_log_transform=self.use_log_transform
            )
            metrics = model.evaluate_backtest(channel_data, test_days=test_days)

            results[channel] = metrics

        return results


if __name__ == "__main__":
    from src.data.loader import DataLoader
    from src.data.preprocessor_improved import ImprovedDataPreprocessor

    # Load and preprocess data
    loader = DataLoader("./data")
    df = loader.load_all_channels()

    preprocessor = ImprovedDataPreprocessor()
    df_clean = preprocessor.prepare_all_channels(df)

    # Test single channel
    google_data = df_clean[df_clean['channel'] == 'google'].copy()

    # Compare with and without log transform
    print("\n" + "="*70)
    print("TESTING: Google with standard config")
    print("="*70)

    forecaster = ImprovedProphetForecaster(channel='google', use_log_transform=False)
    metrics_standard = forecaster.evaluate_backtest(google_data, test_days=30)

    print(f"MAE: ${metrics_standard['mae']:,.2f}")
    print(f"Total Error: {metrics_standard['total_error_pct']:.2f}%")
    print(f"Coverage: {metrics_standard['within_interval_pct']:.1f}%")

    print("\n" + "="*70)
    print("TESTING: Google with log transform")
    print("="*70)

    forecaster_log = ImprovedProphetForecaster(channel='google', use_log_transform=True)
    metrics_log = forecaster_log.evaluate_backtest(google_data, test_days=30)

    print(f"MAE: ${metrics_log['mae']:,.2f}")
    print(f"Total Error: {metrics_log['total_error_pct']:.2f}%")
    print(f"Coverage: {metrics_log['within_interval_pct']:.1f}%")
