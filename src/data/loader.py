"""
Data Loading Module
Loads campaign data from Google Ads, Bing Ads, and Meta Ads
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataLoader:
    """Load and minimally process campaign data from multiple channels"""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)

    def load_all_channels(self) -> pd.DataFrame:
        """Load data from all three channels and combine"""
        logger.info("Loading data from all channels...")

        # Load individual channels
        google_df = self.load_google_ads()
        bing_df = self.load_bing_ads()
        meta_df = self.load_meta_ads()

        # Combine all channels
        combined_df = pd.concat([google_df, bing_df, meta_df], ignore_index=True)

        # Sort by date
        combined_df = combined_df.sort_values('date').reset_index(drop=True)

        logger.info(f"Total records loaded: {len(combined_df)}")
        logger.info(f"Date range: {combined_df['date'].min()} to {combined_df['date'].max()}")

        return combined_df

    def load_google_ads(self) -> pd.DataFrame:
        """Load Google Ads data"""
        file_path = self.data_dir / "google_ads_campaign_stats.csv"
        logger.info(f"Loading Google Ads from {file_path}")

        df = pd.read_csv(file_path)

        # Convert micros to dollars
        df['spend'] = df['metrics_cost_micros'] / 1_000_000
        df['revenue'] = df['metrics_conversions_value']

        # Standardize columns
        df = df.rename(columns={
            'segments_date': 'date',
            'campaign_id': 'campaign_id',
            'campaign_name': 'campaign_name',
            'metrics_clicks': 'clicks',
            'metrics_impressions': 'impressions',
            'metrics_conversions': 'conversions',
            'campaign_advertising_channel_type': 'campaign_type',
            'campaign_budget_amount': 'daily_budget'
        })

        # Add channel identifier
        df['channel'] = 'google'

        # Select relevant columns
        columns = ['date', 'channel', 'campaign_id', 'campaign_name', 'campaign_type',
                  'revenue', 'spend', 'conversions', 'clicks', 'impressions', 'daily_budget']

        return df[columns].copy()

    def load_bing_ads(self) -> pd.DataFrame:
        """Load Bing/Microsoft Ads data"""
        file_path = self.data_dir / "bing_campaign_stats.csv"
        logger.info(f"Loading Bing Ads from {file_path}")

        df = pd.read_csv(file_path)

        # Standardize columns
        df = df.rename(columns={
            'TimePeriod': 'date',
            'CampaignId': 'campaign_id',
            'CampaignName': 'campaign_name',
            'Revenue': 'revenue',
            'Spend': 'spend',
            'Clicks': 'clicks',
            'Impressions': 'impressions',
            'Conversions': 'conversions',
            'CampaignType': 'campaign_type',
            'DailyBudget': 'daily_budget'
        })

        # Add channel identifier
        df['channel'] = 'bing'

        # Select relevant columns
        columns = ['date', 'channel', 'campaign_id', 'campaign_name', 'campaign_type',
                  'revenue', 'spend', 'conversions', 'clicks', 'impressions', 'daily_budget']

        return df[columns].copy()

    def load_meta_ads(self) -> pd.DataFrame:
        """Load Meta Ads data"""
        file_path = self.data_dir / "meta_ads_campaign_stats.csv"
        logger.info(f"Loading Meta Ads from {file_path}")

        df = pd.read_csv(file_path)

        # 'conversion' is already a dollar revenue value (median implied ROAS 7.6x).
        df = df.rename(columns={
            'date_start': 'date',
            'campaign_id': 'campaign_id',
            'campaign_name': 'campaign_name',
            'conversion': 'revenue',
            'spend': 'spend',
            'clicks': 'clicks',
            'impressions': 'impressions',
            'daily_budget': 'daily_budget'
        })

        # Meta doesn't have explicit conversions count, estimate from revenue
        # Assume average order value of ~$50 for estimation
        df['conversions'] = df['revenue'] / 50.0
        df['conversions'] = df['conversions'].fillna(0)

        # Extract campaign type from campaign name
        def extract_campaign_type(name):
            if pd.isna(name):
                return 'Unknown'
            name_lower = str(name).lower()
            if 'shopping' in name_lower or 'dpa' in name_lower:
                return 'Shopping'
            elif 'search' in name_lower or 'brand' in name_lower:
                return 'Search'
            elif 'prospecting' in name_lower:
                return 'Prospecting'
            elif 'remarketing' in name_lower or 'retargeting' in name_lower:
                return 'Remarketing'
            else:
                return 'Display'

        df['campaign_type'] = df['campaign_name'].apply(extract_campaign_type)

        # Add channel identifier
        df['channel'] = 'meta'

        # Select relevant columns
        columns = ['date', 'channel', 'campaign_id', 'campaign_name', 'campaign_type',
                  'revenue', 'spend', 'conversions', 'clicks', 'impressions', 'daily_budget']

        return df[columns].copy()

    def get_data_summary(self, df: pd.DataFrame) -> Dict:
        """Generate data summary statistics"""
        summary = {
            'total_records': len(df),
            'date_range': {
                'start': str(df['date'].min()),
                'end': str(df['date'].max()),
                'days': (pd.to_datetime(df['date'].max()) - pd.to_datetime(df['date'].min())).days
            },
            'channels': {
                channel: {
                    'records': len(df[df['channel'] == channel]),
                    'campaigns': df[df['channel'] == channel]['campaign_id'].nunique(),
                    'total_revenue': float(df[df['channel'] == channel]['revenue'].sum()),
                    'total_spend': float(df[df['channel'] == channel]['spend'].sum()),
                    'avg_roas': float(df[df['channel'] == channel]['revenue'].sum() /
                                    df[df['channel'] == channel]['spend'].sum()) if df[df['channel'] == channel]['spend'].sum() > 0 else 0
                }
                for channel in df['channel'].unique()
            },
            'campaign_types': df.groupby('campaign_type').agg({
                'revenue': 'sum',
                'spend': 'sum',
                'conversions': 'sum'
            }).to_dict()
        }

        return summary


if __name__ == "__main__":
    # Test the loader
    loader = DataLoader("./data")
    df = loader.load_all_channels()
    print(df.head())
    print(f"\nShape: {df.shape}")
    print(f"\nColumns: {df.columns.tolist()}")

    summary = loader.get_data_summary(df)
    print(f"\nData Summary:")
    print(f"Total Records: {summary['total_records']}")
    print(f"Date Range: {summary['date_range']}")
    print(f"\nChannel Statistics:")
    for channel, stats in summary['channels'].items():
        print(f"  {channel.upper()}: {stats}")
