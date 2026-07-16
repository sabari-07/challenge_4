"""
Single model artifact that holds all channel × horizon Prophet models.
This is what gets saved as pickle/model.pkl and loaded by predict.py.
"""
import logging
import pandas as pd

from src.models.prophet_final import FinalProphetForecaster

logger = logging.getLogger(__name__)

CHANNELS = ["google", "bing", "meta"]
HORIZONS = [30, 60, 90]


class MultiHorizonForecaster:
    """
    Wraps one FinalProphetForecaster per (channel, horizon) pair.
    Fit once on aggregated channel data; predict for all horizons at once.
    """

    def __init__(self):
        self.models = {}  # key: (channel, horizon)
        self.is_fitted = False

    def fit(self, df_agg: pd.DataFrame) -> "MultiHorizonForecaster":
        """Train one model per channel × horizon on df_agg (daily aggregated)."""
        for channel in CHANNELS:
            channel_data = df_agg[df_agg["channel"] == channel].copy()
            if channel_data.empty:
                logger.warning(f"No data for {channel}, skipping")
                continue
            for horizon in HORIZONS:
                logger.info(f"Training {channel} / {horizon}d ...")
                model = FinalProphetForecaster(channel=channel, forecast_horizon=horizon)
                model.fit(channel_data)
                self.models[(channel, horizon)] = model

        self.is_fitted = True
        return self

    def predict(self, df_agg: pd.DataFrame) -> pd.DataFrame:
        """
        Re-fit each sub-model on df_agg (so predictions reflect test data),
        then generate forecasts for all channels and horizons.

        Returns a DataFrame with columns:
            horizon_days, channel, predicted_revenue, lower_bound, upper_bound,
            daily_avg, uncertainty
        """
        rows = []

        for horizon in HORIZONS:
            total_revenue = total_lower = total_upper = 0.0

            for channel in CHANNELS:
                channel_data = df_agg[df_agg["channel"] == channel].copy()
                if channel_data.empty:
                    logger.warning(f"No data for {channel} at horizon {horizon}, skipping")
                    continue

                key = (channel, horizon)
                if key in self.models:
                    model = self.models[key]
                else:
                    logger.warning(f"No pre-trained model for {key}, training on the fly")
                    model = FinalProphetForecaster(channel=channel, forecast_horizon=horizon)

                model.fit(channel_data)
                forecast = model.predict(periods=horizon)
                summary = model.get_forecast_summary(forecast, periods=horizon)

                lower = summary.get("lower_bound", summary["total_revenue"] * 0.85)
                upper = summary.get("upper_bound", summary["total_revenue"] * 1.15)

                rows.append({
                    "horizon_days": horizon,
                    "channel": channel,
                    "predicted_revenue": round(summary["total_revenue"], 2),
                    "lower_bound": round(lower, 2),
                    "upper_bound": round(upper, 2),
                    "daily_avg": round(summary["total_revenue"] / horizon, 2),
                    "uncertainty": round(upper - lower, 2),
                })

                total_revenue += summary["total_revenue"]
                total_lower += lower
                total_upper += upper

            rows.append({
                "horizon_days": horizon,
                "channel": "aggregate",
                "predicted_revenue": round(total_revenue, 2),
                "lower_bound": round(total_lower, 2),
                "upper_bound": round(total_upper, 2),
                "daily_avg": round(total_revenue / horizon, 2),
                "uncertainty": round(total_upper - total_lower, 2),
            })

        return pd.DataFrame(rows)
