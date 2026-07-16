"""
Final Prophet Model with All Optimizations
- Q4 conditional seasonality for Bing and Meta
- Higher fourier orders for Meta
- Horizon-specific interval widths
- spend_rolling_7 regressor for Meta 60/90d horizons
  (rev_rolling_7 removed: diverges when frozen at prediction time)
"""
import pandas as pd
import numpy as np
from prophet import Prophet
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


def get_prophet_config_by_horizon(channel: str, periods: int = 30) -> Dict:
    """
    Get channel and horizon-specific Prophet configuration

    Args:
        channel: 'google', 'bing', or 'meta'
        periods: Forecast horizon (30, 60, 90 days)

    Returns:
        Dictionary of Prophet parameters
    """
    # Horizon-scaled interval widths.
    # Google's observed MAPE roughly doubles each tier (2.8% → 14.7% → 25.8%).
    # Widening the intervals proportionally prevents overconfident probabilistic
    # outputs at 60d and 90d where uncertainty compounds significantly.
    interval_map = {
        30: 0.80,  # ~±5% calibrated error — tight band is appropriate
        60: 0.90,  # ~±15% calibrated error — widened from 0.85
        90: 0.95   # ~±30% calibrated error — kept wide
    }

    interval_width = interval_map.get(periods, 0.80)

    channel_cps = {
        'google': {30: 0.08, 60: 0.04, 90: 0.02},
        'bing':   {30: 0.05, 60: 0.08, 90: 0.10},
        'meta':   {30: 0.10, 60: 0.15, 90: 0.20},
    }
    changepoint_prior = channel_cps.get(channel, {}).get(periods, 0.05)

    configs = {
        'google': {
            'changepoint_prior_scale': changepoint_prior,
            # Lowered from 10.0 → 3.0. High seasonality prior lets Prophet fit
            # very large Q4 multipliers which then produce extreme predictions
            # when those multipliers are applied to non-Q4 holdout windows.
            'seasonality_prior_scale': 3.0,
            'seasonality_mode': 'multiplicative',
            'interval_width': interval_width,
            'weekly_seasonality': False,  # Will add custom
            'yearly_seasonality': False,  # Will add custom
            'daily_seasonality': False
        },
        'bing': {
            'changepoint_prior_scale': changepoint_prior,
            # Lowered from 5.0 → 2.0. Bing has only 18 months of data;
            # a high prior allows seasonal components to dominate the trend.
            'seasonality_prior_scale': 2.0,
            'seasonality_mode': 'additive',
            'interval_width': interval_width,
            'weekly_seasonality': False,  # Will add custom
            'yearly_seasonality': False,  # Will add custom
            'daily_seasonality': False
        },
        'meta': {
            'changepoint_prior_scale': changepoint_prior,
            # Lowered from 8.0 → 2.0. Meta has a sharp Q4 spike on only 582 days;
            # high prior causes catastrophic over/under-prediction outside Q4.
            'seasonality_prior_scale': 2.0,
            # Additive mode prevents negative predictions on short/volatile data.
            'seasonality_mode': 'additive',
            # flat growth: Meta revenue has no clear long-run trend — it's driven
            # by budget allocation and campaign mix, not organic growth. Linear
            # trend extrapolation produces strongly negative yhat when the model
            # fits a downward slope on the tail of the training window.
            'growth': 'flat',
            'interval_width': interval_width,
            'weekly_seasonality': False,  # Will add custom
            'yearly_seasonality': False,  # Will add custom
            'daily_seasonality': False
        }
    }

    return configs.get(channel, configs['google'])


def add_bing_seasonalities(model: Prophet, has_history: bool = True) -> Prophet:
    """
    Add Bing-specific seasonalities.
    Fourier orders kept low — Bing has only ~18 months of data.
    High fourier orders on short series over-fit seasonal patterns.
    """
    model.add_seasonality(name='weekly', period=7, fourier_order=3)

    if has_history:
        model.add_seasonality(name='yearly', period=365.25, fourier_order=5)

        # Conditional Q4 spike — kept low order to avoid over-fitting
        model.add_seasonality(
            name='q4_holiday',
            period=365.25,
            fourier_order=3,
            condition_name='is_q4'
        )

    return model


def add_google_seasonalities(model: Prophet) -> Prophet:
    """
    Add Google-specific seasonalities.
    Google has 886 days of clean data — can support moderate fourier orders.
    Quarterly reduced from 8→4 to prevent over-fitting mid-year volatility.
    """
    model.add_seasonality(name='weekly', period=7, fourier_order=3)
    model.add_seasonality(name='yearly', period=365.25, fourier_order=8)
    model.add_seasonality(name='monthly', period=30.5, fourier_order=4)
    model.add_seasonality(name='quarterly', period=91.25, fourier_order=4)

    return model


def add_meta_seasonalities(model: Prophet, has_history: bool = True) -> Prophet:
    """
    Add Meta-specific seasonalities.
    Fourier orders are intentionally conservative (weekly=3, yearly=6) to prevent
    the sharp Q4 spike from over-fitting and producing extreme predictions when
    those seasonal components are applied to non-Q4 windows.
    """
    model.add_seasonality(name='weekly', period=7, fourier_order=3)

    if has_history:
        # Lower fourier order (was 15) — prevents Q4 over-fit bleeding into other months
        model.add_seasonality(name='yearly', period=365.25, fourier_order=6)

        # Conditional holiday spike: only active Nov-Dec
        model.add_seasonality(
            name='holiday_shopping',
            period=365.25,
            fourier_order=5,
            condition_name='is_holiday_season'
        )

    return model


def _split_meta_series(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split Meta daily data into remarketing and prospecting sub-series.

    Expects the 'meta_type' column produced by ImprovedDataPreprocessor.prepare_meta().
    Remarketing (DPA + Brand) is stable and predictable. Prospecting + Generic
    is volatile and spend-driven. Mixing them drowns the stable signal in noise.

    Returns: (remarketing_daily, prospecting_daily), or (None, None) if the
    meta_type column is absent or either segment has fewer than 30 days.
    """
    if 'meta_type' not in df.columns:
        return None, None

    remarketing = df[df['meta_type'] == 'Remarketing'].copy()
    prospecting = df[df['meta_type'] == 'Prospecting'].copy()

    if len(remarketing) < 30 or len(prospecting) < 30:
        return None, None

    return remarketing, prospecting


class FinalProphetForecaster:
    """
    Final Prophet model with all optimizations.

    For Meta, internally trains two sub-models (remarketing and prospecting)
    and sums their forecasts. The public fit/predict interface is unchanged.
    """

    def __init__(self, channel: str = 'google', forecast_horizon: int = 30):
        self.channel = channel
        self.forecast_horizon = forecast_horizon
        self.config = get_prophet_config_by_horizon(channel, forecast_horizon)
        self.model = None
        self.is_fitted = False
        self.regressors = []
        self.historical_data = None
        # Meta sub-models (None for non-Meta channels)
        self._meta_remarketing_model = None
        self._meta_prospecting_model = None

    def prepare_data(self, df: pd.DataFrame, target_col: str = 'revenue') -> pd.DataFrame:
        """Prepare data with conditional seasonality flags and regressors"""
        # Reset regressors so repeated fit() calls don't accumulate duplicates.
        self.regressors = []

        prophet_df = pd.DataFrame({
            'ds': pd.to_datetime(df['date']),
            'y': df[target_col]
        })

        # Add conditional seasonality flags
        prophet_df['is_q4'] = prophet_df['ds'].dt.month.isin([11, 12]).astype(int)
        prophet_df['is_holiday_season'] = prophet_df['ds'].dt.month.isin([11, 12]).astype(int)

        # Add spend regressor for Google only.
        # Bing spend is highly erratic (swings of 3,000%+ between months) which
        # causes the regressor to mislead the model on longer horizons.
        # Meta spend collapsed sharply in late May/Jun 2026 (~70% drop) while
        # revenue decreased proportionally — the model learns a high positive
        # coefficient and then predicts near-zero when the low spend estimate
        # is applied forward, producing artificially deflated forecasts.
        include_spend = self.channel == 'google'
        if include_spend and 'spend' in df.columns and target_col == 'revenue':
            prophet_df['spend'] = df['spend']
            self.regressors.append('spend')

        # Add Conversions regressor for Bing (0.73 correlation with revenue).
        # This gives the model a signal correlated with revenue that is more
        # stable than spend, allowing it to distinguish active from inactive days.
        if self.channel == 'bing' and 'conversions' in df.columns:
            prophet_df['conversions'] = df['conversions'].values
            self.regressors.append('conversions')
            logger.info("  Added Conversions regressor for Bing (0.73 correlation)")

        # Note: new_campaigns_active (Jan 2026 campaign-type shift) was evaluated
        # as a Bing regressor but consistently degraded 30d accuracy without
        # sufficient benefit at 60d/90d. The structural break is instead handled
        # by including all campaign types in preprocessing (not just Search).

        # spend_rolling_7 for Meta removed: spend is no longer a Meta regressor
        # (see spend exclusion comment above), so the rolling feature cannot be built.

        return prophet_df

    def _fit_single(self, df: pd.DataFrame, target_col: str = 'revenue') -> Prophet:
        """Fit one Prophet model on df and return it. Used internally."""
        prophet_df = self.prepare_data(df, target_col)
        self.historical_data = prophet_df.copy()

        model = Prophet(**self.config)
        for regressor in self.regressors:
            model.add_regressor(regressor)

        has_history = len(df) > 365
        if self.channel == 'google':
            model = add_google_seasonalities(model)
        elif self.channel == 'bing':
            model = add_bing_seasonalities(model, has_history)
        elif self.channel == 'meta':
            model = add_meta_seasonalities(model, has_history)

        model.fit(prophet_df)
        return model

    def fit(self, df: pd.DataFrame, target_col: str = 'revenue') -> 'FinalProphetForecaster':
        """Train Prophet model with all optimizations."""
        logger.info(f"Training Final Prophet for {self.channel} ({self.forecast_horizon}-day horizon)")

        if self.channel == 'meta':
            remarketing, prospecting = _split_meta_series(df)

            if remarketing is not None and len(remarketing) >= 30 and len(prospecting) >= 30:
                logger.info(f"  Meta split: {len(remarketing)} remarketing days, {len(prospecting)} prospecting days")
                self._meta_remarketing_model = self._fit_single(remarketing, target_col)
                # Reset regressors / historical_data before fitting second sub-model
                self._meta_prospecting_model = self._fit_single(prospecting, target_col)
                # Store combined history for predict() reference (dates only needed)
                self.historical_data = self.prepare_data(
                    df.groupby('date').agg({'revenue': 'sum', 'spend': 'sum',
                                           'conversions': 'sum', 'clicks': 'sum',
                                           'impressions': 'sum'}).reset_index(),
                    target_col
                )
                self.model = self._meta_remarketing_model  # fallback for backtest path
            else:
                logger.warning("  Meta split produced insufficient data — falling back to single model")
                # df may have multiple rows per date (one per meta_type); aggregate first
                df_agg = df.groupby('date').agg({'revenue': 'sum', 'spend': 'sum',
                                                  'conversions': 'sum', 'clicks': 'sum',
                                                  'impressions': 'sum'}).reset_index()
                self.model = self._fit_single(df_agg, target_col)
                self._meta_remarketing_model = None
                self._meta_prospecting_model = None
        else:
            self.model = self._fit_single(df, target_col)

        self.is_fitted = True
        logger.info(f"Final Prophet training completed for {self.channel}")
        return self

    def _predict_one(self, model: Prophet, periods: int,
                     future_spend: pd.Series = None) -> pd.DataFrame:
        """Run predict on a single fitted Prophet model."""
        future = model.make_future_dataframe(periods=periods, freq='D')
        future['is_q4'] = future['ds'].dt.month.isin([11, 12]).astype(int)
        future['is_holiday_season'] = future['ds'].dt.month.isin([11, 12]).astype(int)

        for regressor in self.regressors:
            if regressor == 'spend':
                if future_spend is not None:
                    spend_extended = pd.concat([
                        self.historical_data['spend'], future_spend
                    ]).reset_index(drop=True)
                else:
                    spend_series = self.historical_data['spend']
                    est = float(spend_series.iloc[-60:].median())
                    spend_extended = pd.concat([
                        spend_series, pd.Series(np.full(periods, est))
                    ]).reset_index(drop=True)
                future['spend'] = spend_extended.values[:len(future)]

            elif regressor == 'conversions':
                if 'spend' in future.columns:
                    hist = self.historical_data.iloc[-60:]
                    rate = hist['conversions'].sum() / (hist['spend'].sum() + 1e-10)
                    future['conversions'] = future['spend'] * rate
                else:
                    future['conversions'] = float(
                        self.historical_data['conversions'].iloc[-30:].median()
                    )

        forecast = model.predict(future)
        # Do NOT clip here for Meta sub-models: a slightly-negative remarketing day
        # combined with a positive prospecting day should produce a sensible sum.
        # Clipping is applied after summation in predict() for all channels.
        return forecast

    def predict(self, periods: int = None, future_spend: pd.Series = None) -> pd.DataFrame:
        """Generate forecast for future periods."""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")

        if periods is None:
            periods = self.forecast_horizon

        # Meta: sum remarketing + prospecting sub-model forecasts, then clip to zero.
        if (self.channel == 'meta'
                and self._meta_remarketing_model is not None
                and self._meta_prospecting_model is not None):

            fc_r = self._predict_one(self._meta_remarketing_model, periods, future_spend)
            fc_p = self._predict_one(self._meta_prospecting_model, periods, future_spend)

            # Align on date before summing — sub-models may have different history
            # lengths so their future dataframes can be different total sizes.
            fc_r_fut = fc_r.tail(periods).set_index('ds')
            fc_p_fut = fc_p.tail(periods).set_index('ds')
            idx = fc_r_fut.index.union(fc_p_fut.index)
            yhat  = fc_r_fut['yhat'].reindex(idx).fillna(0) + fc_p_fut['yhat'].reindex(idx).fillna(0)
            lower = fc_r_fut['yhat_lower'].reindex(idx).fillna(0) + fc_p_fut['yhat_lower'].reindex(idx).fillna(0)
            upper = fc_r_fut['yhat_upper'].reindex(idx).fillna(0) + fc_p_fut['yhat_upper'].reindex(idx).fillna(0)
            combined = pd.DataFrame({
                'ds': idx,
                'yhat':       yhat.clip(lower=0.0).values,
                'yhat_lower': lower.clip(lower=0.0).values,
                'yhat_upper': upper.clip(lower=0.0).values,
            })
            return combined

        fc = self._predict_one(self.model, periods, future_spend)
        for col in ['yhat', 'yhat_lower', 'yhat_upper']:
            if col in fc.columns:
                fc[col] = fc[col].clip(lower=0.0)
        return fc

    def predict_with_custom_spend(self, periods: int, daily_spend: float) -> pd.DataFrame:
        """Forecast with custom daily spend (budget simulation)"""
        future_spend = pd.Series([daily_spend] * periods)
        return self.predict(periods=periods, future_spend=future_spend)

    def get_forecast_summary(self, forecast: pd.DataFrame, periods: int = None) -> Dict:
        """Extract summary statistics from forecast"""
        if periods is not None:
            forecast = forecast.tail(periods)

        total_revenue = float(forecast['yhat'].sum())
        lower_bound = float(forecast['yhat_lower'].sum())
        upper_bound = float(forecast['yhat_upper'].sum())

        summary = {
            'mean_daily': float(forecast['yhat'].mean()),
            'total_revenue': total_revenue,
            'total': total_revenue,  # Keep for backwards compatibility
            'lower_bound': lower_bound,
            'upper_bound': upper_bound,
            'uncertainty': upper_bound - lower_bound,
            'uncertainty_range': upper_bound - lower_bound,
            'p10': lower_bound,
            'p50': total_revenue,
            'p90': upper_bound,
        }

        return summary

    def evaluate_backtest(self, df: pd.DataFrame, test_days: int = 30) -> Dict:
        """
        Backtest on historical data.

        Key metric is total_error_pct: the % error on the summed period total.
        Splits by unique calendar dates so channels with multiple rows per date
        (e.g. Meta with Remarketing + Prospecting sub-series) are handled correctly.
        """
        # Split by unique dates, not row index, so multi-row-per-date channels
        # (Meta Remarketing + Prospecting) get the right holdout window.
        unique_dates = sorted(df['date'].unique())
        cutoff_date = unique_dates[-test_days]
        train_df = df[df['date'] < cutoff_date].copy()
        test_df = df[df['date'] >= cutoff_date].copy()

        self.fit(train_df)

        forecast = self.predict(periods=test_days)
        forecast_test = forecast.tail(test_days).reset_index(drop=True)

        # Aggregate test actuals by date (sums Remarketing + Prospecting per day)
        test_daily = (test_df.groupby('date')['revenue'].sum()
                      .sort_values().reset_index(drop=True))
        actual = test_daily.values
        predicted = forecast_test['yhat'].values[:len(actual)]
        errors = np.abs(actual - predicted)

        mae = float(np.mean(errors))
        rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))

        actual_sum = float(actual.sum())
        wmape = float(np.sum(errors) / actual_sum * 100) if actual_sum > 0 else 0.0

        predicted_sum = float(predicted.sum())
        total_error_pct = float(abs(actual_sum - predicted_sum) / actual_sum * 100) if actual_sum > 0 else 0.0

        lower = forecast_test['yhat_lower'].values[:len(actual)]
        upper = forecast_test['yhat_upper'].values[:len(actual)]
        within_interval = float(np.sum((actual >= lower) & (actual <= upper)) / len(actual) * 100)

        return {
            'mae': mae,
            'rmse': rmse,
            'wmape': wmape,
            'within_interval_pct': within_interval,
            'actual_total': actual_sum,
            'predicted_total': predicted_sum,
            'total_error_pct': total_error_pct,
        }


class MultichannelFinalForecaster:
    """Final multi-channel forecaster with all optimizations"""

    def __init__(self, forecast_horizon: int = 30):
        self.forecast_horizon = forecast_horizon
        self.models = {}

    def fit(self, df: pd.DataFrame, channels: List[str] = None):
        """Fit separate optimized models for each channel"""
        if channels is None:
            channels = df['channel'].unique()

        for channel in channels:
            logger.info(f"Training Final Prophet for channel: {channel}")
            channel_data = df[df['channel'] == channel].copy()

            model = FinalProphetForecaster(
                channel=channel,
                forecast_horizon=self.forecast_horizon
            )
            model.fit(channel_data)

            self.models[channel] = model

        logger.info(f"Trained final models for {len(self.models)} channels")
        return self

    def predict(self, periods: int = None, channel_budgets: Dict[str, float] = None) -> Dict[str, pd.DataFrame]:
        """Predict for all channels"""
        if periods is None:
            periods = self.forecast_horizon

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
            logger.info(f"Evaluating Final Prophet for channel: {channel}")
            channel_data = df[df['channel'] == channel].copy()

            model = FinalProphetForecaster(
                channel=channel,
                forecast_horizon=test_days
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

    # Test with Google
    google_data = df_clean[df_clean['channel'] == 'google'].copy()

    forecaster = FinalProphetForecaster(channel='google', forecast_horizon=30)
    forecaster.fit(google_data)

    forecast = forecaster.predict(periods=30)
    summary = forecaster.get_forecast_summary(forecast, periods=30)

    print("\n30-Day Forecast Summary (Google):")
    print(f"  Expected (P50): ${summary['p50']:,.2f}")
    print(f"  Range: ${summary['p10']:,.2f} - ${summary['p90']:,.2f}")
