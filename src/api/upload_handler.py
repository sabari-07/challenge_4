"""
File Upload Handler for Dynamic Data Loading
"""
from fastapi import UploadFile, HTTPException
from pathlib import Path
import pandas as pd
import logging
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)


class UploadHandler:
    """Handles CSV file uploads and validation"""

    def __init__(self, upload_dir: str = "./data/uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def handle_upload(self, files: List[UploadFile]) -> Dict:
        """
        Handle multiple CSV file uploads

        Args:
            files: List of uploaded files

        Returns:
            Dict with upload results and validation info
        """
        results = {
            'success': [],
            'failed': [],
            'total_records': 0,
            'channels_detected': []
        }

        for file in files:
            try:
                # Validate file type
                if not file.filename.endswith('.csv'):
                    results['failed'].append({
                        'filename': file.filename,
                        'error': 'Only CSV files are supported'
                    })
                    continue

                # Detect channel from filename — required for correct routing and deduplication
                stem = Path(file.filename).stem
                channel = self._detect_channel_from_filename(Path(file.filename))

                if channel is None:
                    results['failed'].append({
                        'filename': file.filename,
                        'error': (
                            f"'{file.filename}' must start with google, bing, or meta "
                            f"(e.g. google_ads.csv, bing_campaign_stats.csv, meta_ads_2026.csv)."
                        )
                    })
                    continue

                # Save with timestamp suffix so same-named uploads are never silently overwritten
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                saved_name = f"{stem}_{ts}.csv"
                file_path = self.upload_dir / saved_name
                content = await file.read()

                with open(file_path, 'wb') as f:
                    f.write(content)

                # Validate CSV structure
                validation = self._validate_csv(file_path)

                if validation['valid']:
                    # Remove all older files for the same channel so only the newest is used
                    self._remove_older_channel_files(channel, keep=file_path)

                    results['success'].append({
                        'filename': file.filename,
                        'saved_as': saved_name,
                        'records': validation['records'],
                        'columns': validation['columns'],
                        'channel': validation['channel']
                    })
                    results['total_records'] += validation['records']
                    results['channels_detected'].append(validation['channel'])
                else:
                    results['failed'].append({
                        'filename': file.filename,
                        'error': validation['error']
                    })
                    # Remove invalid file
                    file_path.unlink()

            except Exception as e:
                logger.error(f"Error processing {file.filename}: {e}")
                results['failed'].append({
                    'filename': file.filename,
                    'error': str(e)
                })

        return results

    def _validate_csv(self, file_path: Path) -> Dict:
        """
        Validate CSV file structure

        Returns:
            Dict with validation results
        """
        try:
            df = pd.read_csv(file_path)

            # All known aliases for date and revenue — same as dynamic_loader
            required = {
                'date': [
                    'date', 'segments_date', 'date_start', 'TimePeriod',
                    'Date', 'day', 'Day', 'timestamp', 'Timestamp', 'dt', 'week',
                    'time', 'period', 'month',
                ],
                'revenue': [
                    'revenue', 'Revenue', 'metrics_conversions_value',
                    'conversions_value', 'conversion_value',
                    'conversion', 'Conversion', 'Conversions', 'sales', 'Sales',
                    'total_revenue', 'net_revenue', 'gross_revenue',
                    'amount', 'value', 'income', 'earnings',
                ],
            }

            col_lower_map = {col.lower(): col for col in df.columns}

            found_columns = {}
            for standard_name, variants in required.items():
                found = False
                # 1. exact match (case-insensitive)
                for variant in variants:
                    if variant in df.columns:
                        found_columns[standard_name] = variant
                        found = True
                        break
                    if variant.lower() in col_lower_map:
                        found_columns[standard_name] = col_lower_map[variant.lower()]
                        found = True
                        break
                # 2. substring fallback
                if not found:
                    for col_lower, col_orig in col_lower_map.items():
                        if any(v.lower() in col_lower for v in variants):
                            found_columns[standard_name] = col_orig
                            found = True
                            break

                if not found:
                    return {
                        'valid': False,
                        'error': (
                            f"Missing required column '{standard_name}'. "
                            f"Columns in file: {list(df.columns)}. "
                            f"Expected one of: {variants[:8]}…"
                        )
                    }

            # Detect channel name — already validated before reaching here
            channel_name = self._detect_channel_from_filename(file_path) or 'unknown'

            return {
                'valid': True,
                'records': len(df),
                'columns': list(df.columns),
                'channel': channel_name,
                'date_range': {
                    'start': str(pd.to_datetime(df[found_columns['date']]).min().date()),
                    'end': str(pd.to_datetime(df[found_columns['date']]).max().date())
                }
            }

        except Exception as e:
            return {
                'valid': False,
                'error': f"Failed to parse CSV: {str(e)}"
            }

    # Only these three channels are supported — filename must start with one of them
    KNOWN_CHANNELS = ['google', 'bing', 'meta']

    def _detect_channel_from_filename(self, file_path: Path) -> str:
        """Return channel name if the filename stem starts with google, bing, or meta. Else None."""
        stem = file_path.stem.lower()
        for channel in self.KNOWN_CHANNELS:
            if stem.startswith(channel):
                return channel
        return None  # unrecognised — caller must reject
        return filename.replace('_ads', '').replace('_campaign', '').replace('_stats', '')

    def _remove_older_channel_files(self, channel: str, keep: Path):
        """Delete all uploaded CSVs for a given channel except the one just saved."""
        for existing in self.upload_dir.glob("*.csv"):
            if existing == keep:
                continue
            if self._detect_channel_from_filename(existing) == channel:
                existing.unlink()
                logger.info(f"Removed superseded upload: {existing.name}")

    def clear_uploads(self):
        """Clear all uploaded files"""
        if self.upload_dir.exists():
            for file in self.upload_dir.glob("*.csv"):
                file.unlink()
            logger.info("Cleared all uploaded files")

    def get_uploaded_files(self) -> List[Dict]:
        """Get list of currently uploaded files"""
        files = []
        if self.upload_dir.exists():
            for file in self.upload_dir.glob("*.csv"):
                try:
                    df = pd.read_csv(file)
                    files.append({
                        'filename': file.name,
                        'size_kb': file.stat().st_size / 1024,
                        'records': len(df),
                        'uploaded_at': file.stat().st_mtime
                    })
                except:
                    pass
        return files
