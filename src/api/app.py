"""
FastAPI Backend for Revenue Forecasting System
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
import os
import pandas as pd
import numpy as np
import json
import logging
import asyncio
from datetime import datetime, timedelta

from src.data.loader import DataLoader
from src.data.preprocessor import DataPreprocessor
from src.data.preprocessor_improved import ImprovedDataPreprocessor
from src.data.dynamic_loader import DynamicDataLoader
from src.models.prophet_final import FinalProphetForecaster
from src.simulation.budget_optimizer import BudgetOptimizer
from src.ai.cohere_client import CohereClient
from src.api.upload_handler import UploadHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="AIgnition - Revenue Forecasting API",
    description="Probabilistic Revenue Forecasting for E-commerce Marketing",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
data_loader = None
preprocessor = None
ensemble_forecaster = None
budget_optimizer = None
ai_client = None
historical_data = None
upload_handler = UploadHandler()
data_metadata = {}


# Helper function to convert DataFrames to JSON-serializable dicts
def dataframe_to_records(df):
    """Convert DataFrame to list of records with Timestamp conversion and NaN/inf sanitisation"""
    if df is None or df.empty:
        return []

    df_copy = df.copy()

    # Convert datetime columns to ISO strings
    for col in df_copy.columns:
        if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
            df_copy[col] = df_copy[col].dt.strftime('%Y-%m-%d')

    # Prophet uses 'ds' for the date column; rename to 'date' for frontend compatibility
    if 'ds' in df_copy.columns:
        df_copy = df_copy.rename(columns={'ds': 'date'})

    # Replace NaN and inf with None so json.dumps produces null (valid JSON)
    df_copy = df_copy.replace([np.inf, -np.inf], np.nan)
    df_copy = df_copy.where(pd.notnull(df_copy), None)

    return df_copy.to_dict('records')


def sanitize_dict(d):
    """Recursively replace NaN/inf in a dict so json.dumps never emits invalid tokens"""
    if isinstance(d, dict):
        return {k: sanitize_dict(v) for k, v in d.items()}
    if isinstance(d, list):
        return [sanitize_dict(v) for v in d]
    if isinstance(d, float):
        if d != d or d == float('inf') or d == float('-inf'):  # NaN or inf
            return None
    return d


OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "output")


def save_forecast_csv(rows: list, forecast_type: str, horizon: int) -> str:
    """Save forecast rows to output/ as a timestamped CSV. Returns the file path."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"forecast_{forecast_type}_{horizon}d_{ts}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)
    pd.DataFrame(rows).to_csv(filepath, index=False)
    logger.info(f"Forecast saved to {filepath}")
    return filepath


# Pydantic models
class ForecastRequest(BaseModel):
    horizon: int = 30  # days
    channels: Optional[List[str]] = None
    future_spends: Optional[Dict[str, float]] = None
    top_n: Optional[int] = None  # For campaign-level: limit to top N campaigns
    min_data_points: Optional[int] = 20  # For campaign-level: minimum historical data
    campaign_ids: Optional[List[int]] = None  # For campaign-level: specific campaign IDs to forecast (integers)


class BudgetOptimizationRequest(BaseModel):
    total_budget: float
    channels: List[str]
    min_roas: Optional[float] = None


class ScenarioSimulationRequest(BaseModel):
    scenario_name: str
    budget_allocation: Dict[str, float]


@app.on_event("startup")
async def startup_event():
    """Initialize models and data on startup"""
    global data_loader, preprocessor, ensemble_forecaster, budget_optimizer, ai_client, historical_data

    logger.info("Initializing forecasting system...")

    try:
        # Load data
        data_loader = DataLoader("./data")
        historical_data = data_loader.load_all_channels()

        # Basic validation using original preprocessor
        preprocessor = DataPreprocessor()
        validation_report = preprocessor.validate_campaign_consistency(historical_data)
        logger.info(f"Campaign validation: {validation_report['status']}")
        if validation_report['issues']:
            logger.warning(f"Validation issues: {validation_report['issues']}")
        if validation_report['warnings']:
            logger.info(f"Validation warnings: {validation_report['warnings']}")

        # Apply improved preprocessing (Search-only Bing, Meta Nov 2024+,
        # outlier capping) — same pipeline used by train_models.py
        improved_preprocessor = ImprovedDataPreprocessor()
        historical_data = improved_preprocessor.prepare_all_channels(historical_data)

        # Initialize AI client
        ai_client = CohereClient()

        # Initialize budget optimizer
        budget_optimizer = BudgetOptimizer()
        for channel in historical_data['channel'].unique():
            budget_optimizer.fit_spend_response_curve(historical_data, channel)

        logger.info("System initialized successfully")

    except Exception as e:
        logger.error(f"Error during initialization: {str(e)}")
        raise


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "AIgnition Revenue Forecasting API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/data/summary")
async def get_data_summary():
    """Get summary of historical data"""
    if historical_data is None:
        raise HTTPException(status_code=500, detail="Data not loaded")

    df = historical_data
    channels_summary = {}
    for channel in df['channel'].unique():
        cdf = df[df['channel'] == channel]
        total_spend = float(cdf['spend'].sum())
        total_revenue = float(cdf['revenue'].sum())
        # campaign count — use campaign_name or campaign_id if present
        if 'campaign_name' in cdf.columns:
            n_campaigns = int(cdf['campaign_name'].nunique())
        elif 'campaign_id' in cdf.columns:
            n_campaigns = int(cdf['campaign_id'].nunique())
        else:
            n_campaigns = 0
        channels_summary[channel] = {
            'records': len(cdf),
            'campaigns': n_campaigns,
            'total_revenue': total_revenue,
            'total_spend': total_spend,
            'avg_roas': total_revenue / total_spend if total_spend > 0 else 0,
        }

    # campaign_type breakdown — column may or may not exist
    campaign_types = {}
    if 'campaign_type' in df.columns:
        try:
            campaign_types = df.groupby('campaign_type').agg(
                revenue=('revenue', 'sum'),
                spend=('spend', 'sum'),
                conversions=('conversions', 'sum') if 'conversions' in df.columns else ('revenue', 'count')
            ).to_dict()
        except Exception:
            campaign_types = {}

    summary = {
        'total_records': len(df),
        'date_range': {
            'start': str(df['date'].min().date() if hasattr(df['date'].min(), 'date') else df['date'].min()),
            'end':   str(df['date'].max().date() if hasattr(df['date'].max(), 'date') else df['date'].max()),
            'days':  int((pd.to_datetime(df['date'].max()) - pd.to_datetime(df['date'].min())).days),
        },
        'channels': channels_summary,
        'campaign_types': campaign_types,
    }

    return {
        "success": True,
        "data": sanitize_dict(summary)
    }


@app.get("/api/data/historical")
async def get_historical_data(
    channel: Optional[str] = None,
    days: int = 90
):
    """Get historical data for visualization"""
    if historical_data is None:
        raise HTTPException(status_code=500, detail="Data not loaded")

    df = historical_data.copy()

    # Filter by channel if provided
    if channel:
        df = df[df['channel'] == channel]

    # Get last N days properly
    max_date = df['date'].max()
    cutoff_date = max_date - pd.Timedelta(days=days)
    df = df[df['date'] > cutoff_date]

    # Aggregate by date and channel
    agg_df = df.groupby(['date', 'channel']).agg({
        'revenue': 'sum',
        'spend': 'sum',
        'conversions': 'sum',
        'clicks': 'sum',
        'impressions': 'sum'
    }).reset_index()

    agg_df['roas'] = agg_df['revenue'] / agg_df['spend']
    agg_df['roas'] = agg_df['roas'].replace([np.inf, -np.inf], 0).fillna(0)

    # Sort by date
    agg_df = agg_df.sort_values('date')

    # Convert to records with timestamp handling
    records = dataframe_to_records(agg_df)

    return {
        "success": True,
        "data": records
    }


@app.get("/api/data/campaigns")
async def get_campaigns_list(
    channel: Optional[str] = None,
    min_data_points: int = 20
):
    """Get list of available campaigns with their metadata"""
    if historical_data is None:
        raise HTTPException(status_code=500, detail="Data not loaded")

    df = historical_data.copy()

    # Filter by channel if provided
    if channel and channel != 'all':
        df = df[df['channel'] == channel]

    # Group by campaign and count data points
    campaign_stats = df.groupby(['campaign_id', 'campaign_name', 'channel', 'campaign_type']).agg({
        'date': 'count',
        'revenue': 'sum',
        'spend': 'sum'
    }).reset_index()

    campaign_stats.columns = ['campaign_id', 'campaign_name', 'channel', 'campaign_type', 'data_points', 'total_revenue', 'total_spend']

    # Calculate ROAS
    campaign_stats['roas'] = campaign_stats['total_revenue'] / campaign_stats['total_spend']
    campaign_stats['roas'] = campaign_stats['roas'].replace([np.inf, -np.inf], 0).fillna(0)

    # Filter by minimum data points
    campaign_stats = campaign_stats[campaign_stats['data_points'] >= min_data_points]

    # Sort by revenue (descending)
    campaign_stats = campaign_stats.sort_values('total_revenue', ascending=False)

    # Convert to records and ensure campaign_id is int
    campaigns = campaign_stats.to_dict('records')

    # Ensure campaign_id is int (not numpy.int64) for JSON serialization
    for campaign in campaigns:
        campaign['campaign_id'] = int(campaign['campaign_id'])
        campaign['data_points'] = int(campaign['data_points'])

    return {
        "success": True,
        "data": {
            "campaigns": campaigns,
            "total_count": len(campaigns)
        }
    }


@app.post("/api/forecast/generate")
async def generate_forecast(request: ForecastRequest):
    """Generate revenue forecast"""
    try:
        logger.info(f"Generating forecast for horizon: {request.horizon} days")

        # Aggregate data by channel
        df_agg = preprocessor.aggregate_by_channel(historical_data, freq='D')

        # Filter channels if specified
        if request.channels:
            df_agg = df_agg[df_agg['channel'].isin(request.channels)]

        # Train Prophet forecasters for each channel
        channels = df_agg['channel'].unique()
        channel_models = {}

        for channel in channels:
            channel_data = df_agg[df_agg['channel'] == channel].copy()
            model = FinalProphetForecaster(channel=channel, forecast_horizon=request.horizon)
            model.fit(channel_data)
            channel_models[channel] = model

        # Generate predictions
        result = {'channels': {}, 'aggregate': {}}
        total_revenue = 0
        total_lower = 0
        total_upper = 0
        total_uncertainty = 0

        for channel, model in channel_models.items():
            # Generate forecast with custom spend if provided (future_spends is total budget → convert to daily)
            if request.future_spends and channel in request.future_spends:
                forecast = model.predict_with_custom_spend(
                    periods=request.horizon,
                    daily_spend=request.future_spends[channel] / request.horizon
                )
            else:
                forecast = model.predict(periods=request.horizon)

            summary = model.get_forecast_summary(forecast, periods=request.horizon)

            result['channels'][channel] = {
                'summary': summary,
                'forecast': forecast
            }

            # Aggregate totals
            total_revenue += summary['total_revenue']
            total_lower += summary.get('lower_bound', summary['total_revenue'] * 0.85)
            total_upper += summary.get('upper_bound', summary['total_revenue'] * 1.15)
            total_uncertainty += summary['uncertainty']

        result['aggregate'] = {
            'total_revenue': total_revenue,
            'lower_bound': total_lower,
            'upper_bound': total_upper,
            'uncertainty': total_uncertainty
        }

        # Calculate aggregate ROAS immediately (before AI analysis)
        if request.future_spends:
            total_spend = sum(request.future_spends.values())
        else:
            # Sum historical spend from each channel (last 30 days per channel)
            total_spend = 0
            for channel in df_agg['channel'].unique():
                channel_hist = df_agg[df_agg['channel'] == channel].tail(30)
                total_spend += float(channel_hist['spend'].sum())

        if total_spend > 0:
            result['aggregate']['blended_roas_expected'] = total_revenue / total_spend
            result['aggregate']['blended_roas_lower'] = total_lower / total_spend
            result['aggregate']['blended_roas_upper'] = total_upper / total_spend
            result['aggregate']['blended_roas_range'] = f"{result['aggregate']['blended_roas_lower']:.2f}x - {result['aggregate']['blended_roas_upper']:.2f}x"
            result['aggregate']['blended_roas'] = result['aggregate']['blended_roas_expected']
            result['aggregate']['total_spend'] = total_spend

        # Prepare all channels data for AI analysis
        all_channels_summary = {}
        for channel, forecast_data in result['channels'].items():
            # Get historical stats
            channel_hist = df_agg[df_agg['channel'] == channel].tail(30)
            hist_revenue = float(channel_hist['revenue'].sum())
            hist_spend = float(channel_hist['spend'].sum())
            hist_roas = hist_revenue / hist_spend if hist_spend > 0 else 0

            forecast_summary = forecast_data['summary']

            # Calculate spend for ROAS calculation
            future_spend = request.future_spends.get(channel, hist_spend) if request.future_spends else hist_spend

            # Revenue bounds
            lower_bound = forecast_summary.get('lower_bound', forecast_summary['total_revenue'] * 0.85)
            upper_bound = forecast_summary.get('upper_bound', forecast_summary['total_revenue'] * 1.15)

            # ROAS calculations (probabilistic ranges)
            roas_lower = lower_bound / future_spend if future_spend > 0 else 0
            roas_expected = forecast_summary['total_revenue'] / future_spend if future_spend > 0 else 0
            roas_upper = upper_bound / future_spend if future_spend > 0 else 0

            all_channels_summary[channel] = {
                'historical': {
                    'revenue': hist_revenue,
                    'spend': hist_spend,
                    'roas': hist_roas,
                    'trend': 'increasing' if channel_hist['revenue'].iloc[-1] > channel_hist['revenue'].iloc[0] else 'decreasing'
                },
                'forecast': {
                    'predicted_revenue': forecast_summary['total_revenue'],
                    'lower_bound': lower_bound,
                    'upper_bound': upper_bound,
                    'predicted_roas': roas_expected,
                    'roas_lower': roas_lower,
                    'roas_upper': roas_upper,
                    'roas_range': f"{roas_lower:.2f}x - {roas_upper:.2f}x",
                    'uncertainty_pct': (forecast_summary['uncertainty'] / forecast_summary['total_revenue'] * 100) if forecast_summary['total_revenue'] > 0 else 0
                }
            }

        # Generate ONE executive summary for all channels with aggregate data
        try:
            logger.info("Generating executive AI summary for all channels")
            # Include aggregate data for AI to use the correct totals
            ai_data = {
                'aggregate': result['aggregate'],
                'channels': all_channels_summary
            }
            executive_summary = ai_client.generate_channel_level_summary(ai_data, request.horizon)
        except Exception as e:
            logger.error(f"Error generating AI executive summary: {str(e)}")
            executive_summary = ""

        # Format response - convert timestamps to ISO format for JSON serialization
        channels_data = {}
        for channel, data in result['channels'].items():
            # Get future spend for this channel
            channel_hist = df_agg[df_agg['channel'] == channel].tail(30)
            hist_spend = float(channel_hist['spend'].sum())
            future_spend = request.future_spends.get(channel, hist_spend) if request.future_spends else hist_spend

            # Calculate ROAS ranges for channel summary
            summary = data['summary'].copy()
            lower_bound = summary.get('lower_bound', summary['total_revenue'] * 0.85)
            upper_bound = summary.get('upper_bound', summary['total_revenue'] * 1.15)

            summary['roas_expected'] = summary['total_revenue'] / future_spend if future_spend > 0 else 0
            summary['roas_lower'] = lower_bound / future_spend if future_spend > 0 else 0
            summary['roas_upper'] = upper_bound / future_spend if future_spend > 0 else 0
            summary['roas_range'] = f"{summary['roas_lower']:.2f}x - {summary['roas_upper']:.2f}x"

            channels_data[channel] = {
                "summary": summary,
                "daily_forecast": dataframe_to_records(data.get('forecast').tail(horizon) if data.get('forecast') is not None and not data.get('forecast').empty else None)
            }

        # Aggregate already has ROAS calculated above
        aggregate = result['aggregate'].copy()

        response = {
            "success": True,
            "forecast": {
                "horizon_days": request.horizon,
                "generated_at": datetime.now().isoformat(),
                "aggregate": aggregate,
                "ai_executive_summary": executive_summary,  # ONE summary for all channels
                "channels": channels_data
            }
        }

        return response

    except Exception as e:
        import traceback
        logger.error(f"Error generating forecast: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/forecast/generate-stream")
async def generate_forecast_stream(request: ForecastRequest):
    """Generate revenue forecast with real-time SSE progress updates"""

    async def event_stream():
        try:
            channel_list = request.channels or ['google', 'bing', 'meta']
            future_spends = request.future_spends or {}
            horizon = request.horizon

            # Step 1: Loading Data
            yield f"data: {json.dumps({'step': 'loading', 'progress': 0, 'message': 'Loading channel data...'})}\n\n"
            await asyncio.sleep(0.01)

            df_agg = preprocessor.aggregate_by_channel(historical_data, freq='D')
            if channel_list:
                df_agg = df_agg[df_agg['channel'].isin(channel_list)]

            yield f"data: {json.dumps({'step': 'loading', 'progress': 100, 'message': 'Data loaded successfully'})}\n\n"
            await asyncio.sleep(0.01)

            # Step 2: Training Models
            yield f"data: {json.dumps({'step': 'training', 'progress': 0, 'message': 'Training forecast models...'})}\n\n"
            await asyncio.sleep(0.01)

            channel_models = {}
            for channel in df_agg['channel'].unique():
                channel_data = df_agg[df_agg['channel'] == channel].copy()
                model = FinalProphetForecaster(channel=channel, forecast_horizon=horizon)
                model.fit(channel_data)
                channel_models[channel] = model

            yield f"data: {json.dumps({'step': 'training', 'progress': 100, 'message': 'Models trained successfully'})}\n\n"
            await asyncio.sleep(0.01)

            # Step 3: Generating Forecasts (using custom spend if provided)
            yield f"data: {json.dumps({'step': 'forecasting', 'progress': 0, 'message': 'Generating revenue forecasts...'})}\n\n"
            await asyncio.sleep(0.01)

            result = {'channels': {}, 'aggregate': {}}
            total_revenue = 0
            total_lower = 0
            total_upper = 0
            total_uncertainty = 0

            for channel, model in channel_models.items():
                if channel in future_spends:
                    forecast = model.predict_with_custom_spend(periods=horizon, daily_spend=future_spends[channel] / horizon)
                else:
                    forecast = model.predict(periods=horizon)
                summary = model.get_forecast_summary(forecast, periods=horizon)

                result['channels'][channel] = {'summary': summary, 'forecast': forecast}
                total_revenue += summary['total_revenue']
                total_lower += summary.get('lower_bound', summary['total_revenue'] * 0.85)
                total_upper += summary.get('upper_bound', summary['total_revenue'] * 1.15)
                total_uncertainty += summary['uncertainty']

            result['aggregate'] = {
                'total_revenue': total_revenue,
                'lower_bound': total_lower,
                'upper_bound': total_upper,
                'uncertainty': total_uncertainty
            }

            # Aggregate ROAS using custom or historical spend
            total_spend = 0
            for channel in df_agg['channel'].unique():
                if channel in future_spends:
                    total_spend += future_spends[channel]
                else:
                    channel_hist = df_agg[df_agg['channel'] == channel].tail(30)
                    total_spend += float(channel_hist['spend'].sum())

            if total_spend > 0:
                result['aggregate']['blended_roas_expected'] = total_revenue / total_spend
                result['aggregate']['blended_roas_lower'] = total_lower / total_spend
                result['aggregate']['blended_roas_upper'] = total_upper / total_spend
                result['aggregate']['blended_roas_range'] = f"{result['aggregate']['blended_roas_lower']:.2f}x - {result['aggregate']['blended_roas_upper']:.2f}x"
                result['aggregate']['blended_roas'] = result['aggregate']['blended_roas_expected']
                result['aggregate']['total_spend'] = total_spend

            yield f"data: {json.dumps({'step': 'forecasting', 'progress': 100, 'message': 'Forecasts generated'})}\n\n"
            await asyncio.sleep(0.01)

            # Step 4: Generate ONE executive AI summary for all channels
            yield f"data: {json.dumps({'step': 'ai_insights', 'progress': 50, 'message': 'Generating executive AI summary...'})}\n\n"
            await asyncio.sleep(0.01)

            all_channels_summary = {}
            for channel, forecast_data in result['channels'].items():
                channel_hist = df_agg[df_agg['channel'] == channel].tail(30)
                hist_revenue = float(channel_hist['revenue'].sum())
                hist_spend = float(channel_hist['spend'].sum())
                hist_roas = hist_revenue / hist_spend if hist_spend > 0 else 0
                effective_spend = future_spends.get(channel, hist_spend)

                forecast_summary = forecast_data['summary']
                lower_bound = forecast_summary.get('lower_bound', forecast_summary['total_revenue'] * 0.85)
                upper_bound = forecast_summary.get('upper_bound', forecast_summary['total_revenue'] * 1.15)
                roas_lower = lower_bound / effective_spend if effective_spend > 0 else 0
                roas_expected = forecast_summary['total_revenue'] / effective_spend if effective_spend > 0 else 0
                roas_upper = upper_bound / effective_spend if effective_spend > 0 else 0

                all_channels_summary[channel] = {
                    'historical': {
                        'revenue': hist_revenue,
                        'spend': hist_spend,
                        'roas': hist_roas,
                        'trend': 'increasing' if len(channel_hist) >= 2 and channel_hist['revenue'].iloc[-1] > channel_hist['revenue'].iloc[0] else 'stable'
                    },
                    'forecast': {
                        'predicted_revenue': forecast_summary['total_revenue'],
                        'lower_bound': lower_bound,
                        'upper_bound': upper_bound,
                        'predicted_roas': roas_expected,
                        'roas_lower': roas_lower,
                        'roas_upper': roas_upper,
                        'roas_range': f"{roas_lower:.2f}x - {roas_upper:.2f}x",
                        'uncertainty_pct': (forecast_summary['uncertainty'] / forecast_summary['total_revenue'] * 100) if forecast_summary['total_revenue'] > 0 else 0,
                        'custom_spend_used': channel in future_spends
                    }
                }

            try:
                ai_data = {'aggregate': result['aggregate'], 'channels': all_channels_summary}
                executive_summary = ai_client.generate_channel_level_summary(ai_data, horizon)
            except Exception as e:
                logger.error(f"Error generating AI executive summary: {str(e)}")
                executive_summary = "AI insights temporarily unavailable"

            yield f"data: {json.dumps({'step': 'ai_insights', 'progress': 100, 'message': 'Executive AI summary complete'})}\n\n"
            await asyncio.sleep(0.01)

            # Final: Build response with ROAS using effective spend
            channels_data = {}
            for channel, data in result['channels'].items():
                channel_hist = df_agg[df_agg['channel'] == channel].tail(30)
                hist_spend = float(channel_hist['spend'].sum())
                effective_spend = future_spends.get(channel, hist_spend)

                summary = data['summary'].copy()
                lower_bound = summary.get('lower_bound', summary['total_revenue'] * 0.85)
                upper_bound = summary.get('upper_bound', summary['total_revenue'] * 1.15)
                summary['roas_expected'] = summary['total_revenue'] / effective_spend if effective_spend > 0 else 0
                summary['roas_lower'] = lower_bound / effective_spend if effective_spend > 0 else 0
                summary['roas_upper'] = upper_bound / effective_spend if effective_spend > 0 else 0
                summary['roas_range'] = f"{summary['roas_lower']:.2f}x - {summary['roas_upper']:.2f}x"
                summary['budget_used'] = effective_spend
                summary['custom_spend'] = channel in future_spends

                channels_data[channel] = {
                    "summary": summary,
                    "daily_forecast": dataframe_to_records(data.get('forecast').tail(horizon) if data.get('forecast') is not None and not data.get('forecast').empty else None)
                }

            final_data = {
                "success": True,
                "forecast": {
                    "horizon_days": horizon,
                    "generated_at": datetime.now().isoformat(),
                    "aggregate": result['aggregate'].copy(),
                    "ai_executive_summary": executive_summary,
                    "channels": channels_data,
                    "custom_budgets_used": bool(future_spends)
                }
            }

            # Save channel-level forecast to CSV
            csv_rows = []
            for ch, ch_data in channels_data.items():
                s = ch_data['summary']
                csv_rows.append({
                    'horizon_days': horizon,
                    'forecast_type': 'channel',
                    'channel': ch,
                    'campaign_type': '',
                    'campaign_name': '',
                    'predicted_revenue': s.get('total_revenue'),
                    'lower_bound': s.get('lower_bound'),
                    'upper_bound': s.get('upper_bound'),
                    'roas_expected': s.get('roas_expected'),
                    'roas_lower': s.get('roas_lower'),
                    'roas_upper': s.get('roas_upper'),
                    'custom_budget': s.get('budget_used'),
                })
            agg = result['aggregate']
            csv_rows.append({
                'horizon_days': horizon,
                'forecast_type': 'channel',
                'channel': 'aggregate',
                'campaign_type': '',
                'campaign_name': '',
                'predicted_revenue': agg.get('total_revenue'),
                'lower_bound': agg.get('lower_bound'),
                'upper_bound': agg.get('upper_bound'),
                'roas_expected': agg.get('blended_roas_expected'),
                'roas_lower': agg.get('blended_roas_lower'),
                'roas_upper': agg.get('blended_roas_upper'),
                'custom_budget': agg.get('total_spend'),
            })
            save_forecast_csv(csv_rows, 'channel', horizon)

            yield f"data: {json.dumps({'step': 'complete', 'progress': 100, 'data': sanitize_dict(final_data)})}\n\n"

        except Exception as e:
            import traceback
            logger.error(f"Error in SSE stream: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            yield f"data: {json.dumps({'step': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/forecast/campaign-type")
async def generate_campaign_type_forecast(request: ForecastRequest):
    """Generate campaign-type level forecast"""
    try:
        logger.info(f"Generating campaign-type forecast for horizon: {request.horizon} days")

        # Aggregate data by campaign type
        df_agg = preprocessor.aggregate_by_campaign_type(historical_data, freq='D')

        # Filter channels if specified
        if request.channels:
            df_agg = df_agg[df_agg['channel'].isin(request.channels)]

        # Train Prophet models for each campaign type
        campaign_type_models = {}
        for (channel, campaign_type), group in df_agg.groupby(['channel', 'campaign_type']):
            if len(group) < 20:
                continue
            key = f"{channel}_{campaign_type}"
            model = FinalProphetForecaster(channel=channel, forecast_horizon=request.horizon)
            model.fit(group)
            campaign_type_models[key] = {'model': model, 'channel': channel, 'campaign_type': campaign_type}

        # Generate predictions
        result = {}
        for key, data in campaign_type_models.items():
            ch = data['channel']
            ct = data['campaign_type']
            if request.future_spends and ch in request.future_spends:
                forecast = data['model'].predict_with_custom_spend(
                    periods=request.horizon,
                    daily_spend=request.future_spends[ch] / request.horizon
                )
            else:
                forecast = data['model'].predict(periods=request.horizon)
            summary = data['model'].get_forecast_summary(forecast, periods=request.horizon)

            if ch not in result:
                result[ch] = {}

            result[ch][ct] = {'summary': summary, 'forecast': forecast}

        # Prepare all campaign types data for executive summary
        all_campaign_types_summary = {}
        formatted_result = {}

        for channel, campaign_types in result.items():
            formatted_result[channel] = {}
            for ctype, forecast_data in campaign_types.items():
                summary = forecast_data['summary']

                # Get historical data for this campaign type
                hist_data = df_agg[(df_agg['channel'] == channel) & (df_agg['campaign_type'] == ctype)].tail(30)
                hist_spend = float(hist_data['spend'].sum())
                hist_revenue = float(hist_data['revenue'].sum())
                hist_roas = hist_revenue / hist_spend if hist_spend > 0 else 0

                # Calculate ROAS ranges
                roas_expected = summary['total_revenue'] / hist_spend if hist_spend > 0 else 0
                roas_lower = summary['lower_bound'] / hist_spend if hist_spend > 0 else 0
                roas_upper = summary['upper_bound'] / hist_spend if hist_spend > 0 else 0

                summary['roas_expected'] = roas_expected
                summary['roas_lower'] = roas_lower
                summary['roas_upper'] = roas_upper
                summary['roas_range'] = f"{roas_lower:.2f}x - {roas_upper:.2f}x"

                # Store for executive summary
                key = f"{channel}_{ctype}"
                all_campaign_types_summary[key] = {
                    'channel': channel,
                    'campaign_type': ctype,
                    'historical': {
                        'revenue': hist_revenue,
                        'spend': hist_spend,
                        'roas': hist_roas,
                        'trend': 'increasing' if len(hist_data) > 1 and hist_data['revenue'].iloc[-1] > hist_data['revenue'].iloc[0] else 'stable'
                    },
                    'forecast': {
                        'predicted_revenue': summary['total_revenue'],
                        'lower_bound': summary['lower_bound'],
                        'upper_bound': summary['upper_bound'],
                        'predicted_roas': roas_expected,
                        'roas_lower': roas_lower,
                        'roas_upper': roas_upper,
                        'roas_range': f"{roas_lower:.2f}x - {roas_upper:.2f}x",
                        'uncertainty_pct': (summary['uncertainty'] / summary['total_revenue'] * 100) if summary['total_revenue'] > 0 else 0
                    }
                }

                formatted_result[channel][ctype] = {
                    'summary': summary,
                    'campaign_type': ctype
                }

        # Generate ONE executive summary for all campaign types
        try:
            logger.info("Generating executive AI summary for all campaign types")
            executive_summary = ai_client.generate_campaign_type_summary(all_campaign_types_summary, request.horizon)
        except Exception as e:
            logger.error(f"Error generating AI executive summary: {str(e)}")
            executive_summary = ""

        return {
            "success": True,
            "forecast": {
                "horizon_days": request.horizon,
                "generated_at": datetime.now().isoformat(),
                "ai_executive_summary": executive_summary,  # ONE summary for all campaign types
                "campaign_types": formatted_result
            }
        }

    except Exception as e:
        import traceback
        logger.error(f"Error generating campaign-type forecast: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/forecast/campaign-type-stream")
async def generate_campaign_type_forecast_stream(
    horizon: int = 30,
    channels: Optional[str] = None,
    future_spends: Optional[str] = None
):
    """Generate campaign-type level forecast with real-time SSE progress updates"""

    async def event_stream():
        try:
            # Parse channels and optional future_spends from JSON strings
            channel_list = json.loads(channels) if channels else ['google', 'bing', 'meta']
            parsed_future_spends = json.loads(future_spends) if future_spends else {}

            # Step 1: Loading Data
            yield f"data: {json.dumps({'step': 'loading', 'progress': 0, 'message': 'Loading campaign type data...'})}\n\n"
            await asyncio.sleep(0.01)

            df_agg = preprocessor.aggregate_by_campaign_type(historical_data, freq='D')
            if channel_list:
                df_agg = df_agg[df_agg['channel'].isin(channel_list)]

            yield f"data: {json.dumps({'step': 'loading', 'progress': 100, 'message': 'Data loaded successfully'})}\n\n"
            await asyncio.sleep(0.01)

            # Step 2: Training Models
            yield f"data: {json.dumps({'step': 'training', 'progress': 0, 'message': 'Training forecast models...'})}\n\n"
            await asyncio.sleep(0.01)

            # Train Prophet models for each campaign type
            campaign_type_models = {}
            for (channel, campaign_type), group in df_agg.groupby(['channel', 'campaign_type']):
                if len(group) < 20:
                    continue
                key = f"{channel}_{campaign_type}"
                model = FinalProphetForecaster(channel=channel, forecast_horizon=horizon)
                model.fit(group)
                campaign_type_models[key] = {'model': model, 'channel': channel, 'campaign_type': campaign_type}

            yield f"data: {json.dumps({'step': 'training', 'progress': 100, 'message': 'Models trained successfully'})}\n\n"
            await asyncio.sleep(0.01)

            # Step 3: Generating Forecasts
            yield f"data: {json.dumps({'step': 'forecasting', 'progress': 0, 'message': 'Generating revenue forecasts...'})}\n\n"
            await asyncio.sleep(0.01)

            # Generate predictions
            result = {}
            for key, data in campaign_type_models.items():
                ch = data['channel']
                if parsed_future_spends and ch in parsed_future_spends:
                    forecast = data['model'].predict_with_custom_spend(
                        periods=horizon,
                        daily_spend=parsed_future_spends[ch] / horizon
                    )
                else:
                    forecast = data['model'].predict(periods=horizon)
                summary = data['model'].get_forecast_summary(forecast, periods=horizon)

                ch = data['channel']
                ct = data['campaign_type']

                if ch not in result:
                    result[ch] = {}

                result[ch][ct] = {'summary': summary, 'forecast': forecast}

            yield f"data: {json.dumps({'step': 'forecasting', 'progress': 100, 'message': 'Forecasts generated'})}\n\n"
            await asyncio.sleep(0.01)

            # Step 4: Prepare data and generate ONE executive AI summary
            yield f"data: {json.dumps({'step': 'ai_insights', 'progress': 50, 'message': 'Generating executive AI summary...'})}\n\n"
            await asyncio.sleep(0.01)

            formatted_result = {}
            all_campaign_types_summary = {}

            for channel, campaign_types in result.items():
                formatted_result[channel] = {}
                for ctype, forecast_data in campaign_types.items():
                    summary = forecast_data['summary']

                    # Get historical data for this campaign type
                    hist_data = df_agg[(df_agg['channel'] == channel) & (df_agg['campaign_type'] == ctype)].tail(30)
                    hist_spend = float(hist_data['spend'].sum())
                    hist_revenue = float(hist_data['revenue'].sum())
                    hist_roas = hist_revenue / hist_spend if hist_spend > 0 else 0

                    # Calculate ROAS ranges
                    summary['expected_roas'] = summary['total_revenue'] / hist_spend if hist_spend > 0 else 0
                    summary['lower_roas'] = summary['lower_bound'] / hist_spend if hist_spend > 0 else 0
                    summary['upper_roas'] = summary['upper_bound'] / hist_spend if hist_spend > 0 else 0

                    # Store for executive summary
                    key = f"{channel}_{ctype}"
                    all_campaign_types_summary[key] = {
                        'channel': channel,
                        'campaign_type': ctype,
                        'historical': {
                            'revenue': hist_revenue,
                            'spend': hist_spend,
                            'roas': hist_roas,
                            'trend': 'increasing' if len(hist_data) > 1 and hist_data['revenue'].iloc[-1] > hist_data['revenue'].iloc[0] else 'stable'
                        },
                        'forecast': {
                            'predicted_revenue': summary['total_revenue'],
                            'lower_bound': summary['lower_bound'],
                            'upper_bound': summary['upper_bound'],
                            'predicted_roas': summary['expected_roas'],
                            'uncertainty_pct': (summary['uncertainty'] / summary['total_revenue'] * 100) if summary['total_revenue'] > 0 else 0
                        }
                    }

                    forecast_df = forecast_data['forecast']
                    formatted_result[channel][ctype] = {
                        'summary': summary,
                        'campaign_type': ctype,
                        'daily_forecast': dataframe_to_records(forecast_df.tail(horizon) if forecast_df is not None and not forecast_df.empty else None)
                    }

            # Generate ONE executive summary for all campaign types
            try:
                executive_summary = ai_client.generate_campaign_type_summary(all_campaign_types_summary, horizon)
            except Exception as e:
                logger.error(f"Error generating AI executive summary: {str(e)}")
                executive_summary = "AI insights temporarily unavailable"

            yield f"data: {json.dumps({'step': 'ai_insights', 'progress': 100, 'message': 'Executive AI summary complete'})}\n\n"
            await asyncio.sleep(0.01)

            # Final: Send complete data
            final_data = {
                "success": True,
                "forecast": {
                    "horizon_days": horizon,
                    "generated_at": datetime.now().isoformat(),
                    "ai_executive_summary": executive_summary,  # ONE summary for all campaign types
                    "campaign_types": formatted_result
                }
            }

            # Save campaign-type forecast to CSV
            csv_rows = []
            for ch, ctypes in formatted_result.items():
                for ct, ct_data in ctypes.items():
                    s = ct_data['summary']
                    csv_rows.append({
                        'horizon_days': horizon,
                        'forecast_type': 'campaign_type',
                        'channel': ch,
                        'campaign_type': ct,
                        'campaign_name': '',
                        'predicted_revenue': s.get('total_revenue'),
                        'lower_bound': s.get('lower_bound'),
                        'upper_bound': s.get('upper_bound'),
                        'roas_expected': s.get('expected_roas'),
                        'roas_lower': s.get('lower_roas'),
                        'roas_upper': s.get('upper_roas'),
                        'custom_budget': '',
                    })
            save_forecast_csv(csv_rows, 'campaign_type', horizon)

            yield f"data: {json.dumps({'step': 'complete', 'progress': 100, 'data': sanitize_dict(final_data)})}\n\n"

        except Exception as e:
            import traceback
            logger.error(f"Error in SSE stream: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            yield f"data: {json.dumps({'step': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/forecast/campaign-level")
async def generate_campaign_level_forecast(request: ForecastRequest):
    """Generate individual campaign level forecast (top campaigns only)"""
    try:
        logger.info(f"Generating campaign-level forecast for horizon: {request.horizon} days")

        # Aggregate data by campaign
        df_campaign = historical_data.groupby(['campaign_id', 'channel', 'campaign_type', 'campaign_name', 'date']).agg({
            'revenue': 'sum',
            'spend': 'sum',
            'conversions': 'sum',
            'clicks': 'sum',
            'impressions': 'sum'
        }).reset_index()

        # Calculate ROAS
        df_campaign['roas'] = df_campaign['revenue'] / df_campaign['spend']
        df_campaign['roas'] = df_campaign['roas'].replace([np.inf, -np.inf], 0).fillna(0)

        # Filter channels if specified
        if request.channels:
            df_campaign = df_campaign[df_campaign['channel'].isin(request.channels)]

        # Filter by specific campaign IDs if provided
        if request.campaign_ids:
            df_campaign = df_campaign[df_campaign['campaign_id'].isin(request.campaign_ids)]

        # Train campaign-level forecaster with user-specified parameters
        min_data_points = request.min_data_points if request.min_data_points else 20

        # If specific campaigns selected, don't limit by top_n
        if request.campaign_ids:
            top_n = None  # Forecast all selected campaigns
        else:
            top_n = request.top_n if request.top_n and request.top_n > 0 else None

        # Train Prophet models for individual campaigns
        campaign_revenue = df_campaign.groupby('campaign_id')['revenue'].sum().sort_values(ascending=False)

        if top_n:
            selected_campaigns = campaign_revenue.head(top_n).index
        else:
            selected_campaigns = campaign_revenue.index

        campaign_models = {}
        campaign_metadata = {}

        for campaign_id in selected_campaigns:
            campaign_data = df_campaign[df_campaign['campaign_id'] == campaign_id].copy()

            if len(campaign_data) < min_data_points:
                continue

            try:
                campaign_name = campaign_data['campaign_name'].iloc[0]
                channel = campaign_data['channel'].iloc[0]
                campaign_type = campaign_data['campaign_type'].iloc[0]
                historical_revenue = campaign_data['revenue'].sum()

                model = FinalProphetForecaster(channel=channel, forecast_horizon=request.horizon)
                model.fit(campaign_data)

                campaign_models[campaign_id] = model
                campaign_metadata[campaign_id] = {
                    'campaign_name': campaign_name,
                    'channel': channel,
                    'campaign_type': campaign_type,
                    'historical_revenue': float(historical_revenue)
                }
            except Exception as e:
                logger.warning(f"Could not train campaign {campaign_id}: {str(e)}")
                continue

        # Generate predictions
        result = {}
        for campaign_id, model in campaign_models.items():
            ch = campaign_metadata[campaign_id]['channel']
            if request.future_spends and ch in request.future_spends:
                forecast = model.predict_with_custom_spend(
                    periods=request.horizon,
                    daily_spend=request.future_spends[ch] / request.horizon
                )
            else:
                forecast = model.predict(periods=request.horizon)
            summary = model.get_forecast_summary(forecast, periods=request.horizon)

            result[campaign_id] = {
                'summary': summary,
                'forecast': forecast,
                'metadata': campaign_metadata[campaign_id]
            }

        # Format response with ROAS ranges
        formatted_result = []
        for campaign_id, forecast_data in result.items():
            meta = forecast_data['metadata']
            summary = forecast_data['summary']

            # Get historical spend for this campaign
            hist_data = df_campaign[df_campaign['campaign_id'] == campaign_id].tail(30)
            hist_spend = float(hist_data['spend'].sum())

            # Calculate ROAS ranges
            roas_expected = summary['total_revenue'] / hist_spend if hist_spend > 0 else 0
            roas_lower = summary['lower_bound'] / hist_spend if hist_spend > 0 else 0
            roas_upper = summary['upper_bound'] / hist_spend if hist_spend > 0 else 0

            summary['roas_expected'] = roas_expected
            summary['roas_lower'] = roas_lower
            summary['roas_upper'] = roas_upper
            summary['roas_range'] = f"{roas_lower:.2f}x - {roas_upper:.2f}x"

            formatted_result.append({
                'campaign_id': str(campaign_id),
                'campaign_name': meta['campaign_name'],
                'channel': meta['channel'],
                'campaign_type': meta['campaign_type'],
                'historical_revenue': meta['historical_revenue'],
                'forecast': summary
            })

        # Sort by predicted revenue
        formatted_result.sort(key=lambda x: x['forecast']['total_revenue'], reverse=True)

        # Prepare aggregate data for ONE executive summary (no per-campaign AI insights)
        logger.info(f"Preparing executive summary for {len(formatted_result)} campaigns")

        all_campaigns_summary = {
            'total_campaigns': len(formatted_result),
            'total_forecasted_revenue': sum(c['forecast']['total_revenue'] for c in formatted_result),
            'top_10_campaigns': []
        }

        # Add top 10 campaigns details for executive summary context
        for campaign in formatted_result[:10]:
            try:
                campaign_id_int = int(campaign['campaign_id'])
                camp_hist = df_campaign[df_campaign['campaign_id'] == campaign_id_int].tail(30)

                if len(camp_hist) > 0:
                    hist_revenue = float(camp_hist['revenue'].sum())
                    hist_spend = float(camp_hist['spend'].sum())
                    hist_roas = hist_revenue / hist_spend if hist_spend > 0 else 0

                    all_campaigns_summary['top_10_campaigns'].append({
                        'campaign_name': campaign['campaign_name'],
                        'channel': campaign['channel'],
                        'campaign_type': campaign['campaign_type'],
                        'historical': {
                            'revenue': hist_revenue,
                            'spend': hist_spend,
                            'roas': hist_roas
                        },
                        'forecast': {
                            'predicted_revenue': campaign['forecast']['total_revenue'],
                            'predicted_roas': campaign['forecast']['expected_roas'],
                            'uncertainty_pct': (campaign['forecast']['uncertainty'] / campaign['forecast']['total_revenue'] * 100) if campaign['forecast']['total_revenue'] > 0 else 0
                        }
                    })
            except Exception as e:
                logger.error(f"Error processing campaign {campaign['campaign_id']} for summary: {str(e)}")
                continue

        # Generate ONE executive summary for all campaigns
        try:
            logger.info("Generating executive AI summary for campaign portfolio")
            executive_summary = ai_client.generate_campaign_level_summary(
                all_campaigns_summary,
                request.horizon,
                len(formatted_result)
            )
        except Exception as e:
            logger.error(f"Error generating AI executive summary: {str(e)}")
            executive_summary = ""

        return {
            "success": True,
            "forecast": {
                "horizon_days": request.horizon,
                "generated_at": datetime.now().isoformat(),
                "ai_executive_summary": executive_summary,  # ONE summary for all campaigns
                "campaigns": formatted_result,
                "total_campaigns": len(formatted_result)
            }
        }

    except Exception as e:
        import traceback
        logger.error(f"Error generating campaign-level forecast: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/forecast/campaign-level-stream")
async def generate_campaign_level_forecast_stream(request: ForecastRequest):
    """Generate campaign-level forecast with real-time SSE progress updates"""

    async def event_stream():
        try:
            # Step 1: Loading Data
            yield f"data: {json.dumps({'step': 'loading', 'progress': 0, 'message': 'Loading campaign data...'})}\n\n"
            await asyncio.sleep(0.01)

            df_campaign = historical_data.groupby(['campaign_id', 'channel', 'campaign_type', 'campaign_name', 'date']).agg({
                'revenue': 'sum',
                'spend': 'sum',
                'conversions': 'sum',
                'clicks': 'sum',
                'impressions': 'sum'
            }).reset_index()

            df_campaign['roas'] = df_campaign['revenue'] / df_campaign['spend']
            df_campaign['roas'] = df_campaign['roas'].replace([np.inf, -np.inf], 0).fillna(0)

            if request.channels:
                df_campaign = df_campaign[df_campaign['channel'].isin(request.channels)]

            if request.campaign_ids:
                df_campaign = df_campaign[df_campaign['campaign_id'].isin(request.campaign_ids)]

            yield f"data: {json.dumps({'step': 'loading', 'progress': 100, 'message': 'Data loaded successfully'})}\n\n"
            await asyncio.sleep(0.01)

            # Step 2: Training Models
            yield f"data: {json.dumps({'step': 'training', 'progress': 0, 'message': 'Training forecast models...'})}\n\n"
            await asyncio.sleep(0.01)

            min_data_points = request.min_data_points if request.min_data_points else 20
            top_n = None if request.campaign_ids else (request.top_n if request.top_n and request.top_n > 0 else None)

            # Train Prophet models for campaigns
            campaign_revenue = df_campaign.groupby('campaign_id')['revenue'].sum().sort_values(ascending=False)

            if top_n:
                selected_campaigns = campaign_revenue.head(top_n).index
            else:
                selected_campaigns = campaign_revenue.index

            campaign_models = {}
            campaign_metadata = {}

            for campaign_id in selected_campaigns:
                campaign_data_iter = df_campaign[df_campaign['campaign_id'] == campaign_id].copy()

                if len(campaign_data_iter) < min_data_points:
                    continue

                try:
                    campaign_name = campaign_data_iter['campaign_name'].iloc[0]
                    channel = campaign_data_iter['channel'].iloc[0]
                    campaign_type = campaign_data_iter['campaign_type'].iloc[0]
                    historical_revenue = campaign_data_iter['revenue'].sum()

                    model = FinalProphetForecaster(channel=channel, forecast_horizon=request.horizon)
                    model.fit(campaign_data_iter)

                    campaign_models[campaign_id] = model
                    campaign_metadata[campaign_id] = {
                        'campaign_name': campaign_name,
                        'channel': channel,
                        'campaign_type': campaign_type,
                        'historical_revenue': float(historical_revenue)
                    }
                except Exception as e:
                    logger.warning(f"Could not train campaign {campaign_id}: {str(e)}")
                    continue

            yield f"data: {json.dumps({'step': 'training', 'progress': 100, 'message': f'Trained models for {len(campaign_models)} campaigns'})}\n\n"
            await asyncio.sleep(0.01)

            # Step 3: Generating Forecasts
            yield f"data: {json.dumps({'step': 'forecasting', 'progress': 0, 'message': 'Generating revenue forecasts...'})}\n\n"
            await asyncio.sleep(0.01)

            # Generate predictions
            result = {}
            for campaign_id, model in campaign_models.items():
                ch = campaign_metadata[campaign_id]['channel']
                if request.future_spends and ch in request.future_spends:
                    forecast = model.predict_with_custom_spend(
                        periods=request.horizon,
                        daily_spend=request.future_spends[ch] / request.horizon
                    )
                else:
                    forecast = model.predict(periods=request.horizon)
                summary = model.get_forecast_summary(forecast, periods=request.horizon)

                result[campaign_id] = {
                    'summary': summary,
                    'forecast': forecast,
                    'metadata': campaign_metadata[campaign_id]
                }

            yield f"data: {json.dumps({'step': 'forecasting', 'progress': 100, 'message': 'Forecasts generated'})}\n\n"
            await asyncio.sleep(0.01)

            # Step 4: Format campaigns and prepare ONE executive summary
            yield f"data: {json.dumps({'step': 'formatting', 'progress': 50, 'message': 'Preparing campaign results...'})}\n\n"
            await asyncio.sleep(0.01)

            formatted_result = []
            for campaign_id, forecast_data in result.items():
                meta = forecast_data['metadata']
                summary = forecast_data['summary']
                hist_data = df_campaign[df_campaign['campaign_id'] == campaign_id].tail(30)
                hist_spend = float(hist_data['spend'].sum())

                summary['expected_roas'] = summary['total_revenue'] / hist_spend if hist_spend > 0 else 0
                summary['lower_roas'] = summary['lower_bound'] / hist_spend if hist_spend > 0 else 0
                summary['upper_roas'] = summary['upper_bound'] / hist_spend if hist_spend > 0 else 0

                forecast_df = forecast_data['forecast']
                campaign_result = {
                    'campaign_id': str(campaign_id),
                    'campaign_name': meta['campaign_name'],
                    'channel': meta['channel'],
                    'campaign_type': meta['campaign_type'],
                    'historical_revenue': meta['historical_revenue'],
                    'forecast': summary,
                    'daily_forecast': dataframe_to_records(forecast_df.tail(request.horizon) if forecast_df is not None and not forecast_df.empty else None)
                }
                formatted_result.append(campaign_result)

            # Sort by revenue
            formatted_result.sort(key=lambda x: x['forecast']['total_revenue'], reverse=True)

            yield f"data: {json.dumps({'step': 'ai_insights', 'progress': 50, 'message': 'Generating executive AI summary...'})}\n\n"
            await asyncio.sleep(0.01)

            # Prepare aggregate data for ONE executive summary
            all_campaigns_summary = {
                'total_campaigns': len(formatted_result),
                'total_forecasted_revenue': sum(c['forecast']['total_revenue'] for c in formatted_result),
                'top_10_campaigns': []
            }

            # Add top 10 campaigns details for executive summary context
            for campaign in formatted_result[:10]:
                try:
                    campaign_id_int = int(campaign['campaign_id'])
                    camp_hist = df_campaign[df_campaign['campaign_id'] == campaign_id_int].tail(30)

                    if len(camp_hist) > 0:
                        hist_revenue = float(camp_hist['revenue'].sum())
                        hist_spend_val = float(camp_hist['spend'].sum())
                        hist_roas = hist_revenue / hist_spend_val if hist_spend_val > 0 else 0

                        all_campaigns_summary['top_10_campaigns'].append({
                            'campaign_name': campaign['campaign_name'],
                            'channel': campaign['channel'],
                            'campaign_type': campaign['campaign_type'],
                            'historical': {
                                'revenue': hist_revenue,
                                'spend': hist_spend_val,
                                'roas': hist_roas
                            },
                            'forecast': {
                                'predicted_revenue': campaign['forecast']['total_revenue'],
                                'predicted_roas': campaign['forecast']['expected_roas'],
                                'uncertainty_pct': (campaign['forecast']['uncertainty'] / campaign['forecast']['total_revenue'] * 100) if campaign['forecast']['total_revenue'] > 0 else 0
                            }
                        })
                except Exception as e:
                    logger.error(f"Error processing campaign {campaign['campaign_id']} for summary: {str(e)}")
                    continue

            # Generate ONE executive summary for all campaigns
            try:
                executive_summary = ai_client.generate_campaign_level_summary(
                    all_campaigns_summary,
                    request.horizon,
                    len(formatted_result)
                )
            except Exception as e:
                logger.error(f"Error generating AI executive summary: {str(e)}")
                executive_summary = "AI insights temporarily unavailable"

            yield f"data: {json.dumps({'step': 'ai_insights', 'progress': 100, 'message': 'Executive AI summary complete'})}\n\n"
            await asyncio.sleep(0.01)

            # Final: Send complete data
            final_data = {
                "success": True,
                "forecast": {
                    "horizon_days": request.horizon,
                    "generated_at": datetime.now().isoformat(),
                    "ai_executive_summary": executive_summary,  # ONE summary for all campaigns
                    "campaigns": formatted_result,
                    "total_campaigns": len(formatted_result)
                }
            }

            # Save campaign-level forecast to CSV
            csv_rows = []
            for c in formatted_result:
                f = c['forecast']
                csv_rows.append({
                    'horizon_days': request.horizon,
                    'forecast_type': 'campaign',
                    'channel': c.get('channel'),
                    'campaign_type': c.get('campaign_type'),
                    'campaign_name': c.get('campaign_name'),
                    'predicted_revenue': f.get('total_revenue'),
                    'lower_bound': f.get('lower_bound'),
                    'upper_bound': f.get('upper_bound'),
                    'roas_expected': f.get('expected_roas'),
                    'roas_lower': f.get('lower_roas'),
                    'roas_upper': f.get('upper_roas'),
                    'custom_budget': '',
                })
            save_forecast_csv(csv_rows, 'campaign', request.horizon)

            yield f"data: {json.dumps({'step': 'complete', 'progress': 100, 'data': sanitize_dict(final_data)})}\n\n"

        except Exception as e:
            import traceback
            logger.error(f"Error in SSE stream: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            yield f"data: {json.dumps({'step': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/budget/optimize")
async def optimize_budget(request: BudgetOptimizationRequest):
    """Optimize budget allocation across channels"""
    try:
        logger.info(f"Optimizing budget: ${request.total_budget:,.2f}")

        available_channels = [ch for ch in request.channels if ch in budget_optimizer.spend_response_curves]
        if not available_channels:
            raise HTTPException(status_code=400, detail="No fitted channels available. Please upload data first.")

        result = budget_optimizer.optimize_allocation(
            request.total_budget,
            available_channels,
            min_roas=request.min_roas
        )

        try:
            ai_recommendation = ai_client.suggest_budget_allocation(
                result['allocation'],
                request.total_budget
            )
        except Exception as e:
            logger.error(f"Error generating AI recommendation: {str(e)}")
            ai_recommendation = "AI recommendation temporarily unavailable"

        return {
            "success": True,
            "optimization": result,
            "ai_recommendation": ai_recommendation
        }

    except Exception as e:
        logger.error(f"Error optimizing budget: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/budget/optimize-stream")
async def optimize_budget_stream(request: BudgetOptimizationRequest):
    """Optimize budget allocation with real-time SSE progress updates"""

    async def event_stream():
        try:
            # Step 1: Loading data
            yield f"data: {json.dumps({'step': 'loading', 'progress': 0, 'message': 'Loading channel performance data...'})}\n\n"
            await asyncio.sleep(0.01)

            available_channels = [ch for ch in request.channels if ch in budget_optimizer.spend_response_curves]
            if not available_channels:
                yield f"data: {json.dumps({'step': 'error', 'message': 'No fitted channels available. Please upload data first.'})}\n\n"
                return

            yield f"data: {json.dumps({'step': 'loading', 'progress': 100, 'message': f'Loaded data for {len(available_channels)} channel(s)'})}\n\n"
            await asyncio.sleep(0.01)

            # Step 2: Fitting spend-response curves
            yield f"data: {json.dumps({'step': 'fitting', 'progress': 0, 'message': 'Fitting spend-response curves...'})}\n\n"
            await asyncio.sleep(0.3)
            yield f"data: {json.dumps({'step': 'fitting', 'progress': 100, 'message': 'Spend-response curves fitted'})}\n\n"
            await asyncio.sleep(0.01)

            # Step 3: Running SLSQP optimisation
            yield f"data: {json.dumps({'step': 'optimizing', 'progress': 0, 'message': 'Running constrained optimisation (SLSQP)...'})}\n\n"
            await asyncio.sleep(0.01)

            result = budget_optimizer.optimize_allocation(
                request.total_budget,
                available_channels,
                min_roas=request.min_roas
            )

            yield f"data: {json.dumps({'step': 'optimizing', 'progress': 100, 'message': 'Optimal allocation found'})}\n\n"
            await asyncio.sleep(0.01)

            # Step 4: AI recommendation
            yield f"data: {json.dumps({'step': 'ai_insights', 'progress': 0, 'message': 'Generating AI budget recommendation...'})}\n\n"
            await asyncio.sleep(0.01)

            try:
                ai_recommendation = ai_client.suggest_budget_allocation(
                    result['allocation'],
                    request.total_budget
                )
            except Exception as e:
                logger.error(f"Error generating AI recommendation: {str(e)}")
                ai_recommendation = "AI recommendation temporarily unavailable"

            yield f"data: {json.dumps({'step': 'ai_insights', 'progress': 100, 'message': 'AI analysis complete'})}\n\n"
            await asyncio.sleep(0.01)

            final_data = {
                "success": True,
                "optimization": result,
                "ai_recommendation": ai_recommendation
            }

            yield f"data: {json.dumps({'step': 'complete', 'progress': 100, 'data': sanitize_dict(final_data)})}\n\n"

        except Exception as e:
            import traceback
            logger.error(f"Budget optimisation stream error: {str(e)}")
            logger.error(traceback.format_exc())
            yield f"data: {json.dumps({'step': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/budget/simulate")
async def simulate_scenario(request: ScenarioSimulationRequest):
    """Simulate revenue for custom budget scenario"""
    try:
        result = budget_optimizer.simulate_scenario(request.budget_allocation)

        return {
            "success": True,
            "scenario_name": request.scenario_name,
            "simulation": result
        }

    except Exception as e:
        logger.error(f"Error simulating scenario: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/insights/executive-summary")
async def get_executive_summary():
    """Get AI-generated executive summary"""
    try:
        # Get recent performance
        df_recent = historical_data.tail(30 * 10)
        summary_data = data_loader.get_data_summary(df_recent)

        ai_summary = ai_client.generate_executive_summary(summary_data)

        return {
            "success": True,
            "summary": ai_summary,
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error generating executive summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/channels")
async def get_channels():
    """Get available channels"""
    if historical_data is None:
        raise HTTPException(status_code=500, detail="Data not loaded")

    channels = historical_data['channel'].unique().tolist()

    return {
        "success": True,
        "channels": channels
    }


@app.get("/api/data/campaign-types")
async def get_campaign_types():
    """Get campaign types present in the loaded data, grouped by channel"""
    if historical_data is None:
        raise HTTPException(status_code=500, detail="Data not loaded")

    type_col = next(
        (c for c in ['campaign_type', 'campaign_advertising_channel_type', 'CampaignType'] if c in historical_data.columns),
        None
    )

    if type_col is None:
        return {"success": True, "campaign_types_by_channel": {}}

    result = {}
    for channel in historical_data['channel'].unique():
        channel_df = historical_data[historical_data['channel'] == channel]
        types = sorted(channel_df[type_col].dropna().unique().tolist())
        if types:
            result[channel.lower()] = types

    return {"success": True, "campaign_types_by_channel": result}


@app.post("/api/upload-data")
async def upload_data(files: List[UploadFile] = File(...)):
    """
    Upload CSV files for custom data
    Accepts multiple CSV files
    """
    try:
        logger.info(f"Received {len(files)} file(s) for upload")

        # Handle upload
        results = await upload_handler.handle_upload(files)

        if not results['success']:  # empty list = no files processed successfully
            failed_details = results.get('failed', [])
            error_msg = '; '.join(f"{f['filename']}: {f['error']}" for f in failed_details) if failed_details else 'No valid files uploaded'
            return {
                "success": False,
                "message": error_msg,
                "files_failed": failed_details
            }

        # Reload data with uploaded files
        global data_loader, preprocessor, historical_data, data_metadata, budget_optimizer

        dynamic_loader = DynamicDataLoader()
        df, metadata = dynamic_loader.load_data()

        # Store in global state
        historical_data = df
        data_metadata = metadata

        # Re-fit budget optimizer for available channels
        budget_optimizer = BudgetOptimizer()
        for channel in df['channel'].unique():
            budget_optimizer.fit_spend_response_curve(df, channel)

        logger.info(f"✅ Data reloaded: {len(df)} records, channels: {metadata['channels']}")

        return {
            "success": True,
            "message": f"Successfully uploaded {len(results['success'])} file(s)",
            "files_processed": results['success'],
            "files_failed": results['failed'],
            "total_records": results['total_records'],
            "channels": metadata['channels'],
            "date_range": metadata['date_range'],
            "metadata": metadata
        }

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/uploaded-files")
async def get_uploaded_files():
    """Get list of currently uploaded files"""
    try:
        files = upload_handler.get_uploaded_files()
        return {
            "success": True,
            "files": files,
            "count": len(files)
        }
    except Exception as e:
        logger.error(f"Error getting uploaded files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/upload-data")
async def clear_uploaded_data():
    """Clear all uploaded files and reload default data"""
    try:
        upload_handler.clear_uploads()

        # Reload default data
        global data_loader, preprocessor, historical_data, data_metadata, budget_optimizer

        dynamic_loader = DynamicDataLoader()
        df, metadata = dynamic_loader.load_data(force_static=True)

        historical_data = df
        data_metadata = metadata

        # Re-fit budget optimizer for available channels
        budget_optimizer = BudgetOptimizer()
        for channel in df['channel'].unique():
            budget_optimizer.fit_spend_response_curve(df, channel)

        logger.info("✅ Cleared uploaded data, loaded default data")

        return {
            "success": True,
            "message": "Uploaded data cleared, using default data",
            "channels": metadata['channels'],
            "total_records": len(df)
        }

    except Exception as e:
        logger.error(f"Error clearing data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data-status")
async def get_data_status():
    """Get current data source status"""
    try:
        uploaded_files = upload_handler.get_uploaded_files()

        return {
            "success": True,
            "using_uploaded_data": len(uploaded_files) > 0,
            "uploaded_files": uploaded_files,
            "metadata": data_metadata if data_metadata else None,
            "total_records": len(historical_data) if historical_data is not None else 0
        }
    except Exception as e:
        logger.error(f"Error getting data status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
