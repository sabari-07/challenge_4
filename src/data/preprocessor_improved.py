"""
Improved Data Preprocessor for Prophet
Fixes data quality issues that cause poor forecast accuracy
"""
import pandas as pd
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ImprovedDataPreprocessor:
    """Enhanced preprocessor with channel-specific fixes"""

    def __init__(self):
        pass

    def prepare_bing(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fix Bing data issues:
        - High proportion of zero-revenue rows
        - Fill zero-revenue active days using conversion × derived AOV
        """
        logger.info("Preprocessing Bing data with fixes...")

        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])

        logger.info(f"  Using all campaign types: {df['campaign_type'].unique().tolist()}")

        # Aggregate by date across all campaign types
        daily = df.groupby('date').agg({
            'revenue': 'sum',
            'spend': 'sum',
            'conversions': 'sum',
            'clicks': 'sum',
            'impressions': 'sum'
        }).reset_index()

        # Discard the leading tail of the series where revenue has not yet started.
        # Find the first date that has at least one non-zero revenue day within
        # the following 14 days — this is the point where the channel became active.
        # Using a rolling window avoids trimming at the first isolated spike.
        daily = daily.sort_values('date').reset_index(drop=True)
        rev_rolling = daily['revenue'].rolling(14, min_periods=1).sum()
        first_active_idx = (rev_rolling > 0).idxmax()
        first_active_date = daily.loc[first_active_idx, 'date']
        daily = daily[daily['date'] >= first_active_date].copy()
        logger.info(f"  Trimmed to first active revenue date: {first_active_date.date()} ({len(daily)} days)")

        # Filter to active days only (spend > 0).
        pre_filter = len(daily)
        daily = daily[daily['spend'] > 0].copy()
        logger.info(f"  Filtered to spend > 0 days: {len(daily)}/{pre_filter}")

        # Derive AOV from the data itself: mean(revenue / conversions) on days
        # where both are positive. Falls back to median revenue if no conversions.
        active = daily[(daily['revenue'] > 0) & (daily['conversions'] > 0)].copy()
        if len(active) >= 10:
            median_order_value = float((active['revenue'] / active['conversions']).median())
        else:
            median_order_value = float(daily.loc[daily['revenue'] > 0, 'revenue'].median())
        logger.info(f"  Derived AOV from data: ${median_order_value:.2f}")

        # Compute a floor: median of non-zero revenue days
        nonzero_rev = daily.loc[daily['revenue'] > 0, 'revenue']
        revenue_floor = float(nonzero_rev.median()) if len(nonzero_rev) > 0 else median_order_value

        # Fill zero revenue using conversions × AOV, floor at revenue_floor
        zero_count = (daily['revenue'] == 0).sum()
        filled = daily.loc[daily['revenue'] == 0, 'conversions'] * median_order_value
        filled = filled.where(filled > 0, revenue_floor)
        daily.loc[daily['revenue'] == 0, 'revenue'] = filled

        logger.info(f"  Filled {zero_count} zero-revenue days "
                    f"(floor=${revenue_floor:.2f})")

        # Flag the structural break where new campaign types were added.
        # Detected as the first month where a campaign type appears that was
        # absent in the first half of the training data.
        daily['new_campaigns_active'] = 0
        if 'campaign_type' in df.columns:
            midpoint = daily['date'].median()
            early_types = set(df[df['date'] <= midpoint]['campaign_type'].unique())
            late_types   = set(df[df['date'] >  midpoint]['campaign_type'].unique())
            new_types = late_types - early_types
            if new_types:
                first_new = df[df['campaign_type'].isin(new_types)]['date'].min()
                daily['new_campaigns_active'] = (daily['date'] >= first_new).astype(int)
                logger.info(f"  New campaign types detected {new_types} from {first_new.date()}")

        daily['roas'] = daily['revenue'] / (daily['spend'] + 1e-10)
        return daily

    @staticmethod
    def _clean_meta_daily(daily: pd.DataFrame) -> pd.DataFrame:
        """
        Apply gap-fill, outlier cap, floor, and leading-gap cutoff to a
        date-aggregated Meta DataFrame. All thresholds are derived from the
        data itself so this works for any advertiser's Meta export.
        """
        daily = daily.copy()
        daily['date'] = pd.to_datetime(daily['date'])
        daily = daily.sort_values('date').reset_index(drop=True)

        # Expand to a full daily date range and note which dates were missing
        # BEFORE interpolating — we use this to detect the largest data gap.
        full_range = pd.date_range(start=daily['date'].min(),
                                   end=daily['date'].max(), freq='D')
        numeric_cols = ['revenue', 'spend', 'conversions', 'clicks', 'impressions']
        daily = daily.set_index('date').reindex(full_range)
        was_missing = daily['revenue'].isna()  # True for imputed dates

        if 'meta_type' in daily.columns:
            daily['meta_type'] = daily['meta_type'].ffill().bfill()
        daily[numeric_cols] = daily[numeric_cols].interpolate(
            method='time', limit_direction='both'
        )
        daily = daily.reset_index().rename(columns={'index': 'date'})
        was_missing = was_missing.reset_index(drop=True)

        # Find the end of the longest contiguous missing-data gap.
        # If a gap exists (e.g. Jun–Oct with no real observations), training on
        # the imputed flat-line before it introduces a false seasonal baseline.
        # Starting from the day after the gap end gives Prophet clean real data.
        if was_missing.any():
            # Identify run lengths of consecutive missing dates
            gap_end_idx = None
            max_gap = 0
            run_len = 0
            run_end = 0
            for i, missing in enumerate(was_missing):
                if missing:
                    run_len += 1
                    run_end = i
                else:
                    if run_len > max_gap:
                        max_gap = run_len
                        gap_end_idx = run_end
                    run_len = 0
            # Only cut at the gap end if it's long enough to be meaningful (>= 30 days)
            if max_gap >= 30 and gap_end_idx is not None:
                daily = daily.iloc[gap_end_idx + 1:].copy()
                logger.info(f"    Skipped {max_gap}-day data gap, training from "
                            f"{daily['date'].iloc[0].date()}")

        revenue_99 = daily['revenue'].quantile(0.99)
        daily['revenue'] = daily['revenue'].clip(upper=revenue_99)

        nonzero = daily.loc[daily['revenue'] > 0, 'revenue']
        revenue_floor = float(nonzero.quantile(0.10)) if len(nonzero) > 10 else 0.0
        if revenue_floor > 0:
            daily.loc[daily['revenue'] < revenue_floor, 'revenue'] = revenue_floor

        logger.info(f"    Cleaned → {len(daily)} days "
                    f"({daily['date'].min().date()} to {daily['date'].max().date()})")
        return daily

    def prepare_meta(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fix Meta data issues:
        - 168 missing dates (gaps of entire months, Jun-Oct 2024)
        - Extreme outliers ($26K single day)
        - High variance campaigns

        Outputs a daily DataFrame that includes a 'meta_type' column
        ('Remarketing' or 'Prospecting') so FinalProphetForecaster can train
        separate sub-models per campaign segment and sum the forecasts.

        Note: the 'conversion' column in meta_ads_campaign_stats.csv is already a
        dollar revenue value (median implied ROAS = 7.6x, consistent with DTC Meta).
        The DataLoader correctly renames it to 'revenue' — no AOV scaling needed.
        """
        logger.info("Preprocessing Meta data with fixes...")

        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])

        # Tag each row as 'Remarketing' or 'Prospecting' based on campaign name.
        # Detection is keyword-based so it works for any advertiser's naming convention,
        # not just the specific names in the bundled dataset.
        if 'campaign_name' in df.columns:
            name_lower = df['campaign_name'].str.lower().fillna('')
            remarketing_keywords = ['remarketing', 'retargeting', 'remarket', 'retarget']
            is_remarketing = name_lower.str.contains('|'.join(remarketing_keywords), regex=True)
            df['meta_type'] = np.where(is_remarketing, 'Remarketing', 'Prospecting')
            n_rem = is_remarketing.sum()
            n_pro = (~is_remarketing).sum()
            logger.info(f"  Meta campaign split: {n_rem} remarketing rows, {n_pro} prospecting rows")
        else:
            df['meta_type'] = 'Prospecting'  # safe default when name not available

        # Build per-type daily series and clean each one independently.
        # This preserves the remarketing/prospecting distinction through gap-fill
        # and outlier capping, so the forecaster receives split-ready data.
        type_dfs = []
        for mtype, group in df.groupby('meta_type'):
            agg = group.groupby('date').agg({
                'revenue': 'sum', 'spend': 'sum', 'conversions': 'sum',
                'clicks': 'sum', 'impressions': 'sum'
            }).reset_index()
            agg['meta_type'] = mtype
            cleaned = self._clean_meta_daily(agg)
            type_dfs.append(cleaned)
            logger.info(f"  Meta {mtype}: {len(cleaned)} days after cleaning")

        daily = pd.concat(type_dfs, ignore_index=True).sort_values(['meta_type', 'date'])

        # Calculate ROAS on the combined series
        daily['roas'] = daily['revenue'] / (daily['spend'] + 1e-10)

        logger.info(f"  Meta total rows (with meta_type split): {len(daily)}")
        return daily

    def prepare_google(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare Google data (already clean, just aggregate)
        """
        logger.info("Preprocessing Google data...")

        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])

        # Aggregate by date
        daily = df.groupby('date').agg({
            'revenue': 'sum',
            'spend': 'sum',
            'conversions': 'sum',
            'clicks': 'sum',
            'impressions': 'sum'
        }).reset_index()

        # Calculate ROAS
        daily['roas'] = daily['revenue'] / (daily['spend'] + 1e-10)

        logger.info(f"  Google data: {len(daily)} days")

        return daily

    def prepare_for_prophet(self, df: pd.DataFrame, channel: str) -> pd.DataFrame:
        """
        Prepare data for Prophet with channel-specific fixes

        Args:
            df: Raw dataframe from loader
            channel: 'google', 'bing', or 'meta'

        Returns:
            Clean daily dataframe ready for Prophet
        """
        if channel == 'bing':
            return self.prepare_bing(df)
        elif channel == 'meta':
            return self.prepare_meta(df)
        elif channel == 'google':
            return self.prepare_google(df)
        else:
            raise ValueError(f"Unknown channel: {channel}")

    def prepare_all_channels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare all channels at once

        Args:
            df: Combined dataframe with 'channel' column

        Returns:
            Clean dataframe with all channels
        """
        logger.info("Preparing all channels with improved preprocessing...")

        result_dfs = []

        for channel in df['channel'].unique():
            channel_df = df[df['channel'] == channel].copy()
            clean_df = self.prepare_for_prophet(channel_df, channel)
            clean_df['channel'] = channel
            result_dfs.append(clean_df)

        combined = pd.concat(result_dfs, ignore_index=True)
        combined = combined.sort_values(['channel', 'date']).reset_index(drop=True)

        logger.info(f"Total records after preprocessing: {len(combined)}")

        return combined


if __name__ == "__main__":
    from src.data.loader import DataLoader

    # Load data
    loader = DataLoader("./data")
    df = loader.load_all_channels()

    # Apply improved preprocessing
    preprocessor = ImprovedDataPreprocessor()

    print("\n" + "="*70)
    print("BEFORE PREPROCESSING")
    print("="*70)
    for channel in ['google', 'bing', 'meta']:
        channel_df = df[df['channel'] == channel]
        print(f"\n{channel.upper()}:")
        print(f"  Records: {len(channel_df)}")
        print(f"  Date range: {channel_df['date'].min()} to {channel_df['date'].max()}")
        print(f"  Zero revenue: {(channel_df['revenue'] == 0).sum()} / {len(channel_df)}")
        print(f"  Total revenue: ${channel_df['revenue'].sum():,.2f}")

    print("\n" + "="*70)
    print("AFTER PREPROCESSING")
    print("="*70)

    clean_df = preprocessor.prepare_all_channels(df)

    for channel in ['google', 'bing', 'meta']:
        channel_df = clean_df[clean_df['channel'] == channel]
        print(f"\n{channel.upper()}:")
        print(f"  Records: {len(channel_df)}")
        print(f"  Date range: {channel_df['date'].min()} to {channel_df['date'].max()}")
        print(f"  Zero revenue: {(channel_df['revenue'] == 0).sum()} / {len(channel_df)}")
        print(f"  Total revenue: ${channel_df['revenue'].sum():,.2f}")
        print(f"  Avg daily revenue: ${channel_df['revenue'].mean():,.2f}")
