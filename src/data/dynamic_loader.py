"""
Dynamic Data Loader - Handles both static and user-uploaded data
Auto-detects channels, columns, and maps them to the standard schema.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Column alias maps — order matters: first match wins
# Keys are the standard internal names; values are lists of source aliases.
# ---------------------------------------------------------------------------
DATE_ALIASES       = ['date', 'segments_date', 'date_start', 'TimePeriod',
                      'Date', 'day', 'Day', 'timestamp', 'Timestamp', 'dt', 'week']
REVENUE_ALIASES    = ['revenue', 'Revenue', 'metrics_conversions_value',
                      'conversions_value', 'conversion_value',
                      'conversion', 'Conversion', 'sales', 'Sales',
                      'total_revenue', 'net_revenue', 'gross_revenue',
                      'amount', 'value', 'income', 'earnings']
SPEND_ALIASES      = ['spend', 'Spend', 'metrics_cost_micros',
                      'cost', 'Cost', 'investment', 'DailyBudget', 'budget']
CLICKS_ALIASES     = ['clicks', 'Clicks', 'metrics_clicks', 'click']
IMPRESSIONS_ALIASES= ['impressions', 'Impressions', 'metrics_impressions',
                      'impr', 'views']
CONVERSIONS_ALIASES= ['conversions', 'Conversions', 'metrics_conversions',
                      'conversion_count', 'converted']
CAMPAIGN_ALIASES   = ['campaign_name', 'CampaignName', 'campaign', 'Campaign',
                      'Campaign_Name']
CAMPAIGN_TYPE_ALIASES = ['campaign_type', 'CampaignType',
                         'campaign_advertising_channel_type',
                         'ad_type', 'channel_type']
CHANNEL_ALIASES    = ['channel', 'Channel', 'source', 'Source',
                      'platform', 'Platform', 'media_source']


def _find_col(df: pd.DataFrame, aliases: list) -> str | None:
    """Return the first column in df that matches any alias (case-insensitive)."""
    lower_map = {c.lower(): c for c in df.columns}
    for alias in aliases:
        if alias in df.columns:
            return alias
        if alias.lower() in lower_map:
            return lower_map[alias.lower()]
    return None


def _normalise_file(df: pd.DataFrame, channel: str, filename: str) -> pd.DataFrame:
    """
    Map arbitrary CSV columns to the standard internal schema:
        date, channel, revenue, spend, clicks, impressions,
        conversions, campaign_name, campaign_type

    Handles unit conversions (e.g. Google cost in micros → dollars).
    """
    out = pd.DataFrame()

    # ── date ──────────────────────────────────────────────────────────────
    date_col = _find_col(df, DATE_ALIASES)
    if date_col is None:
        raise ValueError(
            f"Cannot find a date column in '{filename}'. "
            f"Columns present: {list(df.columns)}"
        )
    out['date'] = pd.to_datetime(df[date_col], errors='coerce')

    # ── revenue ───────────────────────────────────────────────────────────
    rev_col = _find_col(df, REVENUE_ALIASES)
    if rev_col is None:
        raise ValueError(
            f"Cannot find a revenue column in '{filename}'. "
            f"Columns present: {list(df.columns)}"
        )
    out['revenue'] = pd.to_numeric(df[rev_col], errors='coerce').fillna(0)

    # ── spend ─────────────────────────────────────────────────────────────
    spend_col = _find_col(df, SPEND_ALIASES)
    if spend_col:
        out['spend'] = pd.to_numeric(df[spend_col], errors='coerce').fillna(0)
        # Google Ads API returns cost in micros (millionths of a dollar)
        if spend_col == 'metrics_cost_micros' or (
            out['spend'].max() > 1_000_000 and out['revenue'].max() < out['spend'].max() / 100
        ):
            logger.info(f"  Detected cost-in-micros for '{filename}', dividing by 1,000,000")
            out['spend'] = out['spend'] / 1_000_000
    else:
        out['spend'] = 0.0

    # ── clicks ────────────────────────────────────────────────────────────
    clicks_col = _find_col(df, CLICKS_ALIASES)
    out['clicks'] = pd.to_numeric(df[clicks_col], errors='coerce').fillna(0) if clicks_col else 0.0

    # ── impressions ───────────────────────────────────────────────────────
    impr_col = _find_col(df, IMPRESSIONS_ALIASES)
    out['impressions'] = pd.to_numeric(df[impr_col], errors='coerce').fillna(0) if impr_col else 0.0

    # ── conversions ───────────────────────────────────────────────────────
    conv_col = _find_col(df, CONVERSIONS_ALIASES)
    out['conversions'] = pd.to_numeric(df[conv_col], errors='coerce').fillna(0) if conv_col else 0.0

    # ── campaign_name ─────────────────────────────────────────────────────
    camp_col = _find_col(df, CAMPAIGN_ALIASES)
    out['campaign_name'] = df[camp_col].astype(str) if camp_col else 'unknown'

    # ── campaign_type ─────────────────────────────────────────────────────
    ct_col = _find_col(df, CAMPAIGN_TYPE_ALIASES)
    out['campaign_type'] = df[ct_col].astype(str) if ct_col else 'unknown'

    # ── channel ───────────────────────────────────────────────────────────
    out['channel'] = channel

    # Drop rows with unparseable dates
    bad_dates = out['date'].isna().sum()
    if bad_dates:
        logger.warning(f"  Dropping {bad_dates} rows with unparseable dates in '{filename}'")
    out = out.dropna(subset=['date'])

    return out


def _detect_channel(file_path: Path, df: pd.DataFrame) -> str:
    """Detect channel name from filename; fall back to filename stem."""
    filename = file_path.stem.lower()
    patterns = {
        'google': ['google', 'adwords', 'gads', 'gad'],
        'meta':   ['meta', 'facebook', 'fb', 'instagram'],
        'bing':   ['bing', 'microsoft', 'msads'],
        'tiktok': ['tiktok', 'tik_tok'],
        'linkedin': ['linkedin', 'li_ads'],
        'twitter': ['twitter', 'x_ads'],
        'snapchat': ['snapchat', 'snap'],
        'pinterest': ['pinterest', 'pin'],
    }
    for channel, keywords in patterns.items():
        if any(kw in filename for kw in keywords):
            return channel
    # fallback: clean up filename
    return (filename
            .replace('_ads', '').replace('_campaign', '')
            .replace('_stats', '').replace('_data', '').strip('_'))


class DynamicDataLoader:
    """
    Flexible data loader:
    1. Uses static files by default (google, meta, bing)
    2. Accepts user-uploaded CSV files
    3. Auto-detects and maps columns to standard schema
    """

    DEFAULT_FILES = {
        'google': 'google_ads_campaign_stats.csv',
        'meta':   'meta_ads_campaign_stats.csv',
        'bing':   'bing_campaign_stats.csv',
    }

    def __init__(self, data_dir: str = "./data", upload_dir: str = "./data/uploads"):
        self.data_dir   = Path(data_dir)
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def load_data(self, force_static: bool = False) -> Tuple[pd.DataFrame, Dict]:
        logger.info("=" * 70)
        logger.info("DYNAMIC DATA LOADER")
        logger.info("=" * 70)

        if not force_static and self._has_uploaded_files():
            logger.info("✅ User-uploaded files detected — using custom data")
            df, metadata = self._load_files(self.upload_dir.glob("*.csv"), source='uploaded')
        else:
            logger.info("📁 Using default static files")
            df, metadata = self._load_static_files()

        metadata = self._enrich_metadata(df, metadata)

        logger.info(f"📊 Loaded {len(df):,} records | "
                    f"{len(metadata['channels'])} channels | "
                    f"{metadata['date_range']['start']} → {metadata['date_range']['end']}")
        logger.info("=" * 70)

        return df, metadata

    # ------------------------------------------------------------------
    def _has_uploaded_files(self) -> bool:
        return self.upload_dir.exists() and bool(list(self.upload_dir.glob("*.csv")))

    def _load_static_files(self) -> Tuple[pd.DataFrame, Dict]:
        file_paths = []
        for channel, filename in self.DEFAULT_FILES.items():
            fp = self.data_dir / filename
            if fp.exists():
                file_paths.append(fp)
            else:
                logger.warning(f"⚠️  Static file not found: {fp}")

        if not file_paths:
            raise ValueError("No static files could be loaded!")

        return self._load_files(iter(file_paths), source='static')

    def _load_files(self, file_iter, source: str) -> Tuple[pd.DataFrame, Dict]:
        all_data = []
        detected_channels = []
        file_names = []

        for file_path in file_iter:
            file_path = Path(file_path)
            try:
                raw = pd.read_csv(file_path)
                channel = _detect_channel(file_path, raw)
                normalised = _normalise_file(raw, channel, file_path.name)
                all_data.append(normalised)
                detected_channels.append(channel)
                file_names.append(file_path.name)
                logger.info(f"   ✓ {file_path.name}: {len(normalised):,} rows → channel '{channel}'")
            except Exception as e:
                logger.error(f"   ✗ {file_path.name}: {e}")

        if not all_data:
            raise ValueError("No files could be loaded!")

        combined = pd.concat(all_data, ignore_index=True)
        combined = combined.sort_values(['channel', 'date']).reset_index(drop=True)

        metadata = {
            'source': source,
            'files': file_names,
            'channels': detected_channels,
        }
        return combined, metadata

    # ------------------------------------------------------------------
    def _enrich_metadata(self, df: pd.DataFrame, metadata: Dict) -> Dict:
        metadata['date_range'] = {
            'start': str(df['date'].min().date()),
            'end':   str(df['date'].max().date()),
            'days':  (df['date'].max() - df['date'].min()).days,
        }

        metadata['channels_detail'] = {}
        for channel in df['channel'].unique():
            cdf = df[df['channel'] == channel]
            metadata['channels_detail'][channel] = {
                'records':       len(cdf),
                'total_revenue': float(cdf['revenue'].sum()),
                'total_spend':   float(cdf['spend'].sum()),
                'date_range': {
                    'start': str(cdf['date'].min().date()),
                    'end':   str(cdf['date'].max().date()),
                },
            }

        metadata['filters'] = {
            'channels': sorted(df['channel'].unique().tolist()),
            'date_min': str(df['date'].min().date()),
            'date_max': str(df['date'].max().date()),
            'years':    sorted(df['date'].dt.year.unique().tolist()),
            'months':   list(range(1, 13)),
        }
        if 'campaign_name' in df.columns:
            metadata['filters']['campaigns'] = sorted(
                df['campaign_name'].dropna().unique().tolist()[:100]
            )

        metadata['quality'] = {
            'total_records':    len(df),
            'missing_revenue':  int(df['revenue'].isna().sum()),
            'missing_spend':    int(df['spend'].isna().sum()),
            'zero_revenue_days':int((df['revenue'] == 0).sum()),
            'completeness':     f"{(1 - df['revenue'].isna().sum() / len(df)) * 100:.1f}%",
        }

        return metadata

    # ------------------------------------------------------------------
    def get_uploaded_files(self) -> List[Dict]:
        files = []
        if self.upload_dir.exists():
            for fp in self.upload_dir.glob("*.csv"):
                try:
                    df = pd.read_csv(fp)
                    files.append({
                        'filename':    fp.name,
                        'size_kb':     fp.stat().st_size / 1024,
                        'records':     len(df),
                        'uploaded_at': fp.stat().st_mtime,
                    })
                except Exception:
                    pass
        return files

    def clear_uploads(self):
        if self.upload_dir.exists():
            for fp in self.upload_dir.glob("*.csv"):
                fp.unlink()
            logger.info("Cleared all uploaded files")
