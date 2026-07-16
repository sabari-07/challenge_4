### Design

## Overview

AIgnition is a full-stack probabilistic revenue forecasting platform for digital marketing agencies. The system is split into a Python FastAPI backend that handles data loading, Prophet model training, budget optimisation, and Cohere AI summaries, and a React SPA frontend that provides real-time interactive dashboards and streaming forecast visualisations.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        React SPA (Vite)                      │
│  Dashboard  │  Forecast Page  │  Budget Optimizer Page       │
│  port 3000                                                    │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP + SSE (port 8000)
┌───────────────────────▼─────────────────────────────────────┐
│                    FastAPI Backend                            │
│  /api/data-status    /api/data/summary    /api/data/historical│
│  /api/forecast/generate-stream  (POST SSE)                   │
│  /api/forecast/campaign-type-stream (GET SSE)                │
│  /api/budget/optimize   /api/budget/simulate                 │
│  /api/upload-data (POST/DELETE)                              │
└──────┬──────────────┬───────────────┬────────────────────────┘
       │              │               │
┌──────▼──────┐ ┌─────▼──────┐ ┌─────▼──────────┐
│ DynamicData │ │  Prophet   │ │    Cohere       │
│ Loader      │ │ Forecaster │ │  ClientV2       │
│ + Preproc.  │ │ (per chan) │ │  chat()         │
└──────┬──────┘ └─────┬──────┘ └─────────────────┘
       │              │
┌──────▼──────┐ ┌─────▼──────┐
│  data/*.csv │ │  Budget    │
│  uploads/   │ │ Optimizer  │
└─────────────┘ │ (SLSQP)   │
                └────────────┘
```

## Backend Components

### `src/data/dynamic_loader.py` — DynamicDataLoader
- Scans `data/uploads/*.csv` first; falls back to `data/*.csv`
- Auto-detects channel from filename keywords (google, bing, meta)
- Auto-maps column aliases to internal schema via `COLUMN_ALIASES` dict
- Computes metadata: channels, date range, total records

### `src/data/preprocessor.py` — DataPreprocessor
- Computes derived metrics: ROAS (with spend > 0 guard), CTR, CPC, CPA, conversion rate
- Adds temporal features: day_of_week, month, quarter, is_weekend, is_q4
- Computes 7-day and 30-day rolling averages per channel/campaign
- Provides aggregation helpers: by channel, by campaign type
- Provides summary and historical series for API endpoints

### `src/models/prophet_final.py` — FinalProphetForecaster
- Channel-specific Prophet configs (changepoint prior, seasonality mode, interval widths)
- Adds weekly, yearly, quarterly seasonalities
- Adds conditional Q4 holiday seasonality for Bing and Meta
- Adds `spend` as an external regressor
- `get_forecast_summary()` returns: total_revenue, lower_bound, upper_bound, p10, p50, p90, daily_avg

### `src/simulation/budget_optimizer.py` — BudgetOptimizer
- Fits `Revenue = a * log(Spend + 1) + b` per channel via LinearRegression
- `optimize_allocation()` uses SciPy SLSQP with budget equality constraint and optional min ROAS inequality constraints
- `simulate_allocation()` evaluates a manually provided channel → spend dict

### `src/ai/cohere_client.py` — CohereClient
- Uses `cohere.ClientV2` (SDK v2) — NOT v1 `cohere.Client`
- Calls `client.chat(model, messages, max_tokens)` — NOT `client.generate()`
- Reads response as `response.message.content[0].text`
- Four summary generators: channel-level, campaign-type, campaign-level, budget allocation

### `src/api/app.py` — FastAPI Application
- Lifespan handler initialises all globals on startup: DynamicDataLoader, DataPreprocessor, CohereClient, BudgetOptimizer
- All forecast endpoints return `StreamingResponse` with `text/event-stream` media type
- SSE event format: `data: {"step": "...", "progress": N, "message": "...", "data": {...}}\n\n`
- CORS middleware allows all origins for local development

### `src/api/upload_handler.py` — Upload Handler
- Saves uploaded CSVs to `data/uploads/` with timestamp suffix
- `clear_uploaded_files()` removes all files from uploads dir
- After upload or delete, `app.py` calls `_init_data()` to reload everything

## Frontend Components

### Entry Point
- `src/main.jsx` — mounts React app, wraps in `QueryClientProvider`
- `src/App.jsx` — BrowserRouter, lazy-loaded pages, fixed `Scene3D` background, `Navbar`

### Pages
| Page | Route | Key Behaviour |
|------|-------|---------------|
| `Dashboard.jsx` | `/` | KPI cards, revenue trend (Recharts AreaChart), channel breakdown (PieChart), data upload panel, active dataset status |
| `Forecast.jsx` | `/forecast` | Forecast level/horizon/channel config, custom budget inputs, POST SSE streaming, AggregateForecastChart, per-channel cards, AI summary |
| `BudgetOptimizer.jsx` | `/budget-optimizer` | Budget + ROAS sliders, useMutation to `/api/budget/optimize`, allocation cards, AI recommendation |

### Key Components
| Component | Purpose |
|-----------|---------|
| `Scene3D.jsx` | Three.js animated background — floating spheres + particles via React Three Fiber |
| `AggregateForecastChart.jsx` | Recharts ComposedChart — Bar with ErrorBar for P10–P90 range. Uses `dataKey="total_revenue"` |
| `RevenueChart.jsx` | Recharts AreaChart — per-channel daily revenue trend with gradient fills |
| `ChannelBreakdown.jsx` | Recharts PieChart — revenue share donut per channel |
| `ForecastProgress.jsx` | 5-step SSE progress indicator with animated spinner on current step |
| `MetricCard.jsx` | KPI tile with value, label, trend indicator |
| `DataUpload.jsx` | Drag-and-drop CSV upload, calls POST/DELETE `/api/upload-data` |
| `MarkdownRenderer.jsx` | react-markdown + remark-gfm renderer for Cohere AI summaries |
| `Navbar.jsx` | Top nav with NavLink active state styling |

## Data Flow — Channel Forecast

```
User clicks Generate
  → Forecast.jsx sends POST /api/forecast/generate-stream
  → Backend: DynamicDataLoader → DataPreprocessor.aggregate_by_channel()
  → Per channel: FinalProphetForecaster.fit() → .predict() → .get_forecast_summary()
  → SSE events streamed: loading → training (per channel) → forecasting → ai_insights → complete
  → CohereClient.generate_channel_level_summary()
  → Frontend: ForecastProgress shows steps, AggregateForecastChart renders on complete
```

## Data Flow — Budget Optimization

```
User sets budget + ROAS slider → clicks Optimize
  → BudgetOptimizer.jsx sends POST /api/budget/optimize
  → Backend: BudgetOptimizer.optimize_allocation() via SLSQP
  → CohereClient.suggest_budget_allocation()
  → Frontend: per-channel allocation cards + AI recommendation rendered
```

## API Contract

### SSE Event Schema
```json
{
  "step": "loading | training | forecasting | ai_insights | complete | error",
  "progress": 0,
  "message": "Human-readable status",
  "data": { }
}
```

### Forecast Response (on complete event `data` field)
```json
{
  "forecast": {
    "horizon": 30,
    "channels": [
      {
        "channel": "google",
        "total_revenue": 125000.00,
        "lower_bound": 98000.00,
        "upper_bound": 152000.00,
        "roas": 3.42
      }
    ],
    "aggregate": {
      "total_revenue": 310000.00,
      "lower_bound": 245000.00,
      "upper_bound": 378000.00,
      "blended_roas": 2.87
    }
  },
  "ai_executive_summary": "## Forecast Analysis\n..."
}
```

### Budget Optimization Response
```json
{
  "success": true,
  "optimization": {
    "total_budget": 50000,
    "total_predicted_revenue": 143500.00,
    "blended_roas": 2.87,
    "allocation": {
      "google": { "spend": 28000, "predicted_revenue": 82000, "roas": 2.93, "percentage": 56.0 },
      "bing":   { "spend": 12000, "predicted_revenue": 35500, "roas": 2.96, "percentage": 24.0 },
      "meta":   { "spend": 10000, "predicted_revenue": 26000, "roas": 2.60, "percentage": 20.0 }
    }
  },
  "ai_recommendation": "## Budget Strategy\n..."
}
```

## Environment Variables

```
COHERE_API_KEY=<required>
COHERE_MODEL=command-r-plus-08-2024
API_HOST=0.0.0.0
API_PORT=8000
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend framework | React 18 + Vite |
| Routing | React Router DOM v6 |
| Server state | TanStack React Query v5 |
| Charts | Recharts 2 |
| Animation | Framer Motion |
| 3D background | Three.js + React Three Fiber + Drei |
| Styling | Tailwind CSS v3 |
| AI markdown | react-markdown + remark-gfm |
| Backend framework | FastAPI + Uvicorn |
| Forecasting | Facebook Prophet |
| Optimization | SciPy SLSQP |
| ML | scikit-learn LinearRegression |
| AI | Cohere SDK v2 (command-r-plus-08-2024) |
| Data | pandas + NumPy |
