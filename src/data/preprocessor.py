"""
Data Preprocessing and Feature Engineering
"""
import pandas as pd
import numpy as np
from typing import Tuple, List
import logging

logger = logging.getLogger(__name__)


class DataPreprocessor:
    """Preprocess and engineer features for forecasting"""

    def __init__(self):
        self.feature_columns = []
        self.validation_report = None

    def validate_campaign_consistency(self, df: pd.DataFrame) -> dict:
        """Validate campaign data consistency and quality"""
        logger.info("Validating campaign consistency...")

        validation_report = {
            "status": "valid",
            "issues": [],
            "warnings": [],
            "statistics": {}
        }

        # Check for duplicate campaigns on same date
        duplicates = df.groupby(['channel', 'campaign_id', 'date']).size()
        duplicate_count = (duplicates > 1).sum()
        if duplicate_count > 0:
            validation_report["issues"].append(f"Found {duplicate_count} duplicate campaign-date combinations")
            validation_report["status"] = "warning"

        # Check for date gaps per campaign
        for channel in df['channel'].unique():
            for campaign_id in df[df['channel'] == channel]['campaign_id'].unique():
                campaign_data = df[(df['channel'] == channel) & (df['campaign_id'] == campaign_id)].copy()
                campaign_data['date'] = pd.to_datetime(campaign_data['date'])
                campaign_data = campaign_data.sort_values('date')

                if len(campaign_data) > 1:
                    date_diffs = campaign_data['date'].diff()
                    large_gaps = date_diffs[date_diffs > pd.Timedelta(days=7)]
                    if len(large_gaps) > 0:
                        validation_report["warnings"].append(
                            f"Campaign {campaign_id} ({channel}) has {len(large_gaps)} gaps > 7 days"
                        )

        # Check for spend/revenue anomalies
        for col in ['spend', 'revenue']:
            if col in df.columns:
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 3 * iqr
                upper_bound = q3 + 3 * iqr

                outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)]
                if len(outliers) > 0:
                    validation_report["warnings"].append(
                        f"Found {len(outliers)} potential {col} anomalies (3x IQR)"
                    )

        # Check for missing critical fields
        critical_fields = ['date', 'channel', 'campaign_id', 'spend', 'revenue']
        for field in critical_fields:
            if field in df.columns:
                missing_count = df[field].isnull().sum()
                if missing_count > 0:
                    validation_report["issues"].append(f"Missing {missing_count} values in {field}")
                    validation_report["status"] = "warning"

        # Statistics
        validation_report["statistics"] = {
            "total_records": len(df),
            "channels": df['channel'].nunique(),
            "campaigns": df['campaign_id'].nunique(),
            "date_range": {
                "start": str(df['date'].min()),
                "end": str(df['date'].max())
            },
            "total_spend": float(df['spend'].sum()),
            "total_revenue": float(df['revenue'].sum()),
            "overall_roas": float(df['revenue'].sum() / df['spend'].sum()) if df['spend'].sum() > 0 else 0
        }

        logger.info(f"Validation complete: {validation_report['status']}")
        logger.info(f"Issues: {len(validation_report['issues'])}, Warnings: {len(validation_report['warnings'])}")

        self.validation_report = validation_report
        return validation_report

    def prepare_for_forecasting(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare data for time series forecasting"""
        df = df.copy()

        # Convert date to datetime
        df['date'] = pd.to_datetime(df['date'])

        # Calculate ROAS
        df['roas'] = df['revenue'] / df['spend']
        df['roas'] = df['roas'].replace([np.inf, -np.inf], 0).fillna(0)

        # Add temporal features
        df['day_of_week'] = df['date'].dt.dayofweek
        df['day_of_month'] = df['date'].dt.day
        df['month'] = df['date'].dt.month
        df['quarter'] = df['date'].dt.quarter
        df['week_of_year'] = df['date'].dt.isocalendar().week
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)

        # Add lag features (7-day and 30-day rolling)
        for col in ['revenue', 'spend', 'roas']:
            df[f'{col}_7d_avg'] = df.groupby(['channel', 'campaign_id'])[col].transform(
                lambda x: x.rolling(window=7, min_periods=1).mean()
            )
            df[f'{col}_30d_avg'] = df.groupby(['channel', 'campaign_id'])[col].transform(
                lambda x: x.rolling(window=30, min_periods=1).mean()
            )

        # Campaign performance metrics
        df['ctr'] = df['clicks'] / df['impressions']
        df['ctr'] = df['ctr'].replace([np.inf, -np.inf], 0).fillna(0)

        df['conversion_rate'] = df['conversions'] / df['clicks']
        df['conversion_rate'] = df['conversion_rate'].replace([np.inf, -np.inf], 0).fillna(0)

        df['cpc'] = df['spend'] / df['clicks']
        df['cpc'] = df['cpc'].replace([np.inf, -np.inf], 0).fillna(0)

        df['cpa'] = df['spend'] / df['conversions']
        df['cpa'] = df['cpa'].replace([np.inf, -np.inf], 0).fillna(0)

        return df

    def aggregate_by_channel(self, df: pd.DataFrame, freq: str = 'D') -> pd.DataFrame:
        """Aggregate data by channel and time period"""
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])

        # Group by channel and date
        agg_dict = {
            'revenue': 'sum',
            'spend': 'sum',
            'conversions': 'sum',
            'clicks': 'sum',
            'impressions': 'sum'
        }

        grouped = df.groupby(['channel', pd.Grouper(key='date', freq=freq)]).agg(agg_dict).reset_index()

        # Recalculate ROAS
        grouped['roas'] = grouped['revenue'] / grouped['spend']
        grouped['roas'] = grouped['roas'].replace([np.inf, -np.inf], 0).fillna(0)

        return grouped

    def aggregate_by_campaign_type(self, df: pd.DataFrame, freq: str = 'D') -> pd.DataFrame:
        """Aggregate data by campaign type and time period"""
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])

        agg_dict = {
            'revenue': 'sum',
            'spend': 'sum',
            'conversions': 'sum',
            'clicks': 'sum',
            'impressions': 'sum'
        }

        grouped = df.groupby(['channel', 'campaign_type', pd.Grouper(key='date', freq=freq)]).agg(agg_dict).reset_index()

        grouped['roas'] = grouped['revenue'] / grouped['spend']
        grouped['roas'] = grouped['roas'].replace([np.inf, -np.inf], 0).fillna(0)

        return grouped

    def split_train_test(self, df: pd.DataFrame, test_days: int = 30) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Split data into train and test sets"""
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        split_date = df['date'].max() - pd.Timedelta(days=test_days)

        train = df[df['date'] <= split_date].copy()
        test = df[df['date'] > split_date].copy()

        logger.info(f"Train: {len(train)} records, {train['date'].min()} to {train['date'].max()}")
        logger.info(f"Test: {len(test)} records, {test['date'].min()} to {test['date'].max()}")

        return train, test


if __name__ == "__main__":
    from loader import DataLoader

    # Test preprocessing
    loader = DataLoader("./data")
    df = loader.load_all_channels()

    preprocessor = DataPreprocessor()
    df_processed = preprocessor.prepare_for_forecasting(df)

    print(df_processed.head())
    print(f"\nProcessed columns: {df_processed.columns.tolist()}")
    print(f"\nShape: {df_processed.shape}")
