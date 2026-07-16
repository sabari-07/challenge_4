# Architecture Overview — RevenueIQ

**AIgnition Hackathon 2026 · NetElixir**

---

## System Overview

RevenueIQ is a full-stack probabilistic revenue forecasting application for digital marketing agencies. It consists of a React single-page application served through Vite, a FastAPI Python backend, and a Prophet-based forecasting pipeline with Cohere LLM integration.

```
┌──────────────────────────────────────────────────────┐
│                    Browser (React SPA)                │
│  Dashboard  ──  Revenue Forecasting  ──  Budget Opt  │
└─────────────────────────┬────────────────────────────┘
                          │ HTTP / SSE
┌─────────────────────────▼────────────────────────────┐
│                  FastAPI Backend                      │
│   /api/forecast/*    /api/budget/*    /api/data/*    │
└──────┬──────────────────┬──────────────────┬─────────┘
       │                  │                  │
┌──────▼──────┐  ┌────────▼───────┐  ┌──────▼──────┐
│   Prophet   │  │ BudgetOptimizer│  │  Cohere LLM │
│ Forecaster  │  │  (SLSQP +      │  │  command-r+ │
│ (per channel│  │   log curves)  │  │  -08-2024   │
│  /type/camp)│  └────────────────┘  └─────────────┘
└─────────────┘
       │
┌──────▼──────┐
│  CSV Data   │
│  (static /  │
│  uploaded)  │
└─────────────┘
```

---

## Frontend Stack

| Technology | Version | Purpose |
|---|---|---|
| React | 18.2.0 | UI framework |
| Vite | 4.5.0 | Build tool and dev server |
| React Router DOM | 6.16.0 | Client-side routing (3 routes) |
| TanStack React Query | 5.0.0 | Server-state caching and mutations |
| Axios | 1.5.0 | HTTP client for REST calls |
| Recharts | 2.8.0 | Data visualizations (bar chart with error bars) |
| Framer Motion | 10.16.4 | Page and component animations |
| Tailwind CSS | 3.3.5 | Utility-first styling |
| Lucide React | 0.292.0 | Icon library |
| Three.js + R3F | 0.158.0 / 8.15.0 | 3D animated background scene |
| date-fns | 2.30.0 | Date formatting |
| react-markdown + remark-gfm | 10.1.0 | Rendering AI-generated markdown summaries |

### Application Routes

```
/                   → Dashboard (historical analytics)
/forecast           → Revenue Forecasting
/budget-optimizer   → Budget Allocation Optimizer
```

### Pages

#### Dashboard (`/`)
Displays historical performance across uploaded channels. Components:
- **MetricCard** — KPI tiles (total revenue, spend, ROAS, conversions)
- **RevenueChart** — `AreaChart` showing historical daily revenue trend per channel, date-filterable (7d / 30d / 90d / 180d / 1yr)
- **ChannelBreakdown** — `PieChart` donut showing revenue share by channel (3D SVG gradient effect)
- Data fetched via React Query from `/api/data/summary` and `/api/data/historical`

#### Revenue Forecasting (`/forecast`)
The core feature. Allows users to:
1. Upload CSV datasets (any channel, auto-detected)
2. Configure forecast level (Channel / Campaign Type / Campaign)
3. Set forecast horizon (30 / 60 / 90 days)
4. Enter optional custom budgets per channel
5. Generate forecast with real-time SSE progress
6. View aggregate bar chart with P10–P90 error bars
7. Read AI executive summary

Components: `DataUpload`, `ForecastProgress`, `AggregateForecastChart`, `MarkdownRenderer`

#### Budget Optimizer (`/budget-optimizer`)
Budget allocation recommendation tool. User provides:
- Total budget (slider $10K–$200K)
- Minimum ROAS constraint (optional, slider 0–5x)

Returns optimal per-channel spend allocation, predicted revenue per channel, and an AI-generated strategy rationale.

### State Management

No global client state store. State is managed via:
- **React Query** — server state (data status, historical data, campaigns list)
- **Local `useState`** — page-level UI state (forecast results, selections, inputs)
- **No Redux / Zustand used** (zustand is in `package.json` but not instantiated)

### Real-Time Progress (SSE)

All three forecast endpoints stream progress events using **Server-Sent Events** format. The frontend reads these as a `fetch` + `ReadableStream` (POST-compatible, unlike native `EventSource` which is GET-only).

```
data: {"step": "loading",    "progress": 0,   "message": "Loading data..."}
data: {"step": "training",   "progress": 100, "message": "Models trained"}
data: {"step": "forecasting","progress": 100, "message": "Forecasts generated"}
data: {"step": "ai_insights","progress": 100, "message": "AI summary complete"}
data: {"step": "complete",   "progress": 100, "data": { ...full result... }}
```

The `ForecastProgress` component renders a step indicator that updates in real time as each SSE event arrives.

---

## Backend Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.10+ | Runtime |
| FastAPI | latest | REST + streaming API framework |
| Uvicorn | latest | ASGI server |
| Prophet | latest | Time-series forecasting |
| pandas | latest | Data manipulation |
| NumPy | latest | Numerical computation |
| scikit-learn | latest | Logarithmic regression (budget optimizer) |
| SciPy | latest | SLSQP optimization (budget optimizer) |
| Cohere Python SDK | v2 | LLM API client |
| python-dotenv | latest | Environment variable management |

### API Endpoints

#### Data Endpoints
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/data-status` | Returns current data source, available channels, metadata |
| `GET` | `/api/data/summary` | Aggregate stats: total revenue, spend, ROAS, channel breakdown |
| `GET` | `/api/data/historical` | Daily revenue/spend time-series (filterable by `days`) |
| `GET` | `/api/data/campaigns` | List of campaigns with data point counts and ROAS |
| `POST` | `/api/upload-data` | Upload one or more CSV files; triggers data reload |
| `DELETE` | `/api/upload-data` | Clear uploaded files; reverts to default static data |

#### Forecast Endpoints
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/forecast/generate-stream` | SSE stream: channel-level forecast with optional `future_spends` |
| `GET` | `/api/forecast/campaign-type-stream` | SSE stream: campaign-type-level forecast |
| `POST` | `/api/forecast/campaign-level-stream` | SSE stream: campaign-level forecast (top N or specific IDs) |

#### Budget Endpoints
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/budget/optimize` | Optimize total budget allocation across available channels |
| `POST` | `/api/budget/simulate` | Simulate revenue outcome for a manually specified allocation |

### Application Startup

On `startup`, the backend:
1. Instantiates `DynamicDataLoader` — loads uploaded files if present, otherwise loads default static CSVs
2. Runs `DataPreprocessor.validate_campaign_consistency()` — logs data quality report
3. Runs `DataPreprocessor.prepare_for_forecasting()` — computes ROAS, rolling features, temporal flags
4. Instantiates `CohereClient` — validates `COHERE_API_KEY`
5. Instantiates `BudgetOptimizer` — fits logarithmic spend-response curves for each available channel
6. All objects stored as **module-level globals** and shared across requests

On data upload or clear, steps 1 and 5 are re-run so the `BudgetOptimizer` curves always reflect the active dataset.

---

## Forecasting Pipeline

```
Upload CSV  (or use default static files)
    │
    ▼
DataLoader.load_all_channels()          ← standardise columns, add channel tag
    │
    ▼
ImprovedDataPreprocessor.prepare_for_prophet(channel_data, channel)
    ├─ prepare_bing()     ← all campaign types, data-derived AOV, rolling start date
    ├─ prepare_meta()     ← keyword-based Remarketing/Prospecting tagging,
    │                        per-sub-series gap detection + cleaning
    └─ prepare_google()   ← aggregate + ROAS

    │
    ▼
[On forecast request]
MultiHorizonForecaster.predict(df_agg)
    └─ For each (channel, horizon):
       FinalProphetForecaster.fit(channel_data)
           ├─ Prophet config lookup (channel + horizon specific)
           ├─ Meta: _split_meta_series() → fit remarketing + prospecting sub-models
           ├─ Google: add spend regressor
           ├─ Bing: add conversions regressor
           ├─ Add channel-specific seasonalities (weekly/yearly/conditional Q4)
           └─ prophet.fit(df)

    │
    ▼
FinalProphetForecaster.predict(periods, future_spend?)
    ├─ Meta: _predict_one() × 2, align on date index union, sum yhat/lower/upper
    ├─ Other channels: _predict_one()
    ├─ Inject spend regressor (custom budget or 60d median)
    ├─ Inject conversions regressor (Bing: spend × historical conversion rate)
    └─ All yhat values clipped to ≥ 0

    │
    ▼
get_forecast_summary()
    ├─ total_revenue = sum(yhat)
    ├─ lower_bound   = sum(yhat_lower)   ← P10
    └─ upper_bound   = sum(yhat_upper)   ← P90

    │
    ▼
ROAS calculation
    └─ effective_spend = custom_budget OR 30d historical average

    │
    ▼
CohereClient.generate_*_summary()
    └─ Single executive AI summary for all channels/types/campaigns

    │
    ▼
SSE stream → complete event → frontend renders AggregateForecastChart
```

---

## LLM Integration Workflow

```
Statistical model output (revenue, ROAS, bounds, trends)
    │
    ▼
CohereClient.generate_insights(prompt)
    │
    ├─ API call: cohere.ClientV2.chat()
    │   model:       command-r-plus-08-2024
    │   temperature: 0.7
    │   max_tokens:  2000 (3000 for campaign-level)
    │
    ▼
Structured prompt containing:
    ├─ Exact aggregate metrics (total revenue, ROAS, bounds)
    ├─ Per-channel historical performance (last 30 days)
    ├─ Trend direction (increasing / stable)
    └─ Explicit instructions: "use these exact numbers"

    │
    ▼
Response extraction:
    └─ response.message.content[].text → concatenated string

    │
    ▼
Returned as ai_executive_summary in forecast response
    │
    ▼
Frontend: MarkdownRenderer renders with react-markdown + remark-gfm
```

### AI Functions by Context

| Function | Where called | Audience |
|---|---|---|
| `generate_channel_level_summary()` | After channel forecast | CMO — cross-channel strategy |
| `generate_campaign_type_summary()` | After campaign-type forecast | Media planner — type efficiency |
| `generate_campaign_level_summary()` | After campaign forecast | Account manager — portfolio view |
| `suggest_budget_allocation()` | After budget optimization | Marketing director — spend rationale |

---

## Data Flow Diagram

```
User Browser
    │
    │── POST /api/upload-data ──────────────────────────────┐
    │                                                        ▼
    │                                             ./data/uploads/*.csv
    │                                             DynamicDataLoader reloads
    │                                             BudgetOptimizer refits
    │
    │── POST /api/forecast/generate-stream ────────────────┐
    │   body: { horizon, channels, future_spends }          │
    │                                                        ▼
    │                                         aggregate_by_channel()
    │                                         FinalProphetForecaster.fit()
    │                                         .predict(future_spend)
    │                                         CohereClient.generate_summary()
    │                                         ← SSE: step events
    │                                         ← SSE: complete + full result
    │
    │── POST /api/budget/optimize ─────────────────────────┐
    │   body: { total_budget, channels, min_roas }          │
    │                                                        ▼
    │                                         BudgetOptimizer.optimize_allocation()
    │                                         SLSQP minimization
    │                                         CohereClient.suggest_budget_allocation()
    │                                         ← JSON response
    │
    └── GET /api/data/historical ──────────── historical_data → records → JSON
```

---

## Environment Configuration

Required environment variables (`.env` file):

```
COHERE_API_KEY=<your_cohere_api_key>
COHERE_MODEL=command-r-plus-08-2024     # optional, this is the default
```

---

## Project Directory Structure

```
AIgnition/
├── docs/
│   ├── technical_documentation.md      ← forecasting methodology, model, preprocessing
│   ├── architecture_overview.md        ← this file
│   └── pages/
│       ├── dashboard.md                ← Dashboard page feature documentation
│       ├── forecast.md                 ← Revenue Forecasting page feature documentation
│       └── budget_optimizer.md         ← Budget Optimizer page feature documentation
├── frontend/
│   ├── src/
│   │   ├── App.jsx                      ← router, 3D background, lazy-loaded pages
│   │   ├── main.jsx                     ← React Query provider, app mount
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx            ← historical analytics
│   │   │   ├── Forecast.jsx             ← forecast configuration + results
│   │   │   └── BudgetOptimizer.jsx      ← budget allocation tool
│   │   └── components/
│   │       ├── AggregateForecastChart.jsx ← bar chart with P10–P90 error bars
│   │       ├── RevenueChart.jsx           ← historical area chart
│   │       ├── ChannelBreakdown.jsx       ← donut chart
│   │       ├── DataUpload.jsx             ← CSV upload modal
│   │       ├── ForecastProgress.jsx       ← SSE step progress indicator
│   │       ├── MarkdownRenderer.jsx       ← AI summary renderer
│   │       ├── MetricCard.jsx             ← KPI tile
│   │       ├── Navbar.jsx                 ← navigation
│   │       └── Scene3D.jsx                ← Three.js animated background
│   └── package.json
├── src/
│   ├── api/
│   │   ├── app.py                       ← FastAPI application, all endpoints
│   │   └── upload_handler.py            ← file upload management
│   ├── data/
│   │   ├── loader.py                    ← static CSV loader (Google/Bing/Meta column standardisation)
│   │   ├── preprocessor_improved.py     ← channel-specific cleaning (gap detection, AOV, sub-series split)
│   │   ├── dynamic_loader.py            ← dynamic loader with column auto-mapping for uploaded files
│   │   └── preprocessor.py             ← legacy preprocessor (not used in production path)
│   ├── models/
│   │   ├── prophet_final.py             ← FinalProphetForecaster + _split_meta_series, channel configs
│   │   └── multi_horizon_forecaster.py  ← MultiHorizonForecaster (9 models: 3 channels × 3 horizons)
│   ├── simulation/
│   │   └── budget_optimizer.py          ← BudgetOptimizer, SLSQP, log curves
│   └── ai/
│       └── cohere_client.py             ← CohereClient, all prompt functions
├── data/
│   ├── google_ads_campaign_stats.csv    ← default Google dataset
│   ├── meta_ads_campaign_stats.csv      ← default Meta dataset
│   ├── bing_campaign_stats.csv          ← default Bing dataset
│   └── uploads/                         ← user-uploaded files (runtime)
└── .env                                 ← COHERE_API_KEY
```
