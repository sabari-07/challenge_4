# Tasks

## Implementation Tasks

- [x] 1. Set up project structure and environment configuration
  - Create `requirements.txt` with all Python dependencies
  - Create `frontend/package.json` with all frontend dependencies
  - Create `.env` with `COHERE_API_KEY`, `COHERE_MODEL`, `API_HOST`, `API_PORT`
  - Create `.gitignore` covering Python, Node, `.env`, model artifacts
  - Create `src/__init__.py`, `src/api/__init__.py`, `src/data/__init__.py`, `src/models/__init__.py`, `src/simulation/__init__.py`, `src/ai/__init__.py`

- [x] 2. Implement static and dynamic data loaders
  - Create `src/data/loader.py` with `DataLoader` — loads default CSVs for Google, Bing, Meta with channel-specific column mappings
  - Create `src/data/dynamic_loader.py` with `DynamicDataLoader` — auto-detects channel from filename, auto-maps columns via `COLUMN_ALIASES`, falls back to defaults when no uploads present
  - Implement `_normalise()` to standardise types, fill missing columns, convert Google micros to dollars
  - Implement `_compute_metadata()` to return channels, date range, total records

- [x] 3. Implement data preprocessor
  - Create `src/data/preprocessor.py` with `DataPreprocessor`
  - Implement `prepare_for_forecasting()` — compute ROAS with `spend > 0` guard using `np.where`, CTR, CPC, CPA, conversion rate, temporal features, rolling averages
  - Implement `aggregate_by_channel()` and `aggregate_by_campaign_type()` for daily rollups
  - Implement `get_channel_summary()` for `/api/data/summary`
  - Implement `get_historical_series()` for `/api/data/historical` — pivot to wide format per channel

- [x] 4. Implement Prophet forecasting model
  - Create `src/models/prophet_final.py` with `FinalProphetForecaster`
  - Define `CHANNEL_CONFIGS` dict with per-channel changepoint prior, seasonality mode, interval widths per horizon
  - Implement `fit()` — add weekly, yearly, quarterly seasonalities, Q4 conditional seasonality for Bing and Meta, spend regressor, fit Prophet model
  - Implement `predict()` and `predict_with_custom_spend()` — build future DataFrame with spend regressor values
  - Implement `get_forecast_summary()` — aggregate last N rows of yhat/yhat_lower/yhat_upper, clip at 0

- [x] 5. Implement budget optimizer
  - Create `src/simulation/budget_optimizer.py` with `BudgetOptimizer`
  - Implement `fit()` — group by channel and date, fit `log(spend+1) → revenue` LinearRegression per channel
  - Implement `optimize_allocation()` — SLSQP with budget equality constraint and optional per-channel min ROAS inequality constraints
  - Implement `simulate_allocation()` — evaluate manual spend dict without optimization
  - Implement `predict_revenue()` — `a * log(spend+1) + b`

- [x] 6. Implement Cohere AI client
  - Create `src/ai/cohere_client.py` with `CohereClient`
  - Instantiate `cohere.ClientV2` (SDK v2, NOT v1 `cohere.Client`)
  - Implement `_chat()` using `client.chat(model, messages, max_tokens)` and read `response.message.content[0].text`
  - Implement `generate_channel_level_summary()`, `generate_campaign_type_summary()`, `generate_campaign_level_summary()`, `suggest_budget_allocation()`
  - Handle missing API key and Cohere exceptions gracefully with fallback strings

- [x] 7. Implement file upload handler
  - Create `src/api/upload_handler.py`
  - Implement `save_uploaded_files()` — save CSVs to `data/uploads/` with timestamp suffix, skip non-CSV files
  - Implement `clear_uploaded_files()` — remove all CSVs from uploads dir, return count
  - Implement `list_uploaded_files()` — return basenames of all uploads

- [x] 8. Implement FastAPI backend application
  - Create `src/api/app.py` with lifespan handler initialising all module-level globals
  - Implement `_init_data()` helper to reload DynamicDataLoader, DataPreprocessor, BudgetOptimizer on startup and after uploads
  - Implement all data endpoints: `/api/data-status`, `/api/data/summary`, `/api/data/historical`, `/api/data/campaigns`
  - Implement upload endpoints: `POST /api/upload-data`, `DELETE /api/upload-data`
  - Implement SSE streaming forecast endpoints: `POST /api/forecast/generate-stream`, `GET /api/forecast/campaign-type-stream`, `POST /api/forecast/campaign-level-stream`
  - Implement budget endpoints: `POST /api/budget/optimize`, `POST /api/budget/simulate`
  - Add CORS middleware allowing all origins

- [x] 9. Implement frontend entry point and routing
  - Create `frontend/src/main.jsx` — mount React app with `QueryClientProvider`
  - Create `frontend/src/App.jsx` — BrowserRouter with lazy-loaded pages, fixed Scene3D background, Navbar
  - Create `frontend/src/index.css` — Tailwind directives, custom scrollbar, glass utility class
  - Update `frontend/tailwind.config.js` — add trading-cyan, trading-blue, trading-dark, trading-darker color tokens
  - Verify `frontend/vite.config.js` sets dev server port to 3000

- [x] 10. Implement frontend components
  - Create `components/Scene3D.jsx` — Three.js floating spheres + particles via React Three Fiber
  - Create `components/Navbar.jsx` — sticky top nav with NavLink active state
  - Create `components/MetricCard.jsx` — KPI tile with value, label, optional trend indicator
  - Create `components/RevenueChart.jsx` — Recharts AreaChart with per-channel gradient fills
  - Create `components/ChannelBreakdown.jsx` — Recharts PieChart donut with legend
  - Create `components/AggregateForecastChart.jsx` — Recharts ComposedChart Bar with ErrorBar, `dataKey="total_revenue"`
  - Create `components/ForecastProgress.jsx` — 5-step SSE progress indicator
  - Create `components/DataUpload.jsx` — drag-and-drop CSV upload panel
  - Create `components/MarkdownRenderer.jsx` — react-markdown + remark-gfm with Tailwind-styled components

- [x] 11. Implement Dashboard page
  - Create `pages/Dashboard.jsx` at route `/`
  - Show active dataset panel with channel status badges and metadata
  - Show KPI cards: total revenue, total spend, blended ROAS using `useQuery`
  - Show revenue trend AreaChart with period selector (30/90/180/365/all days)
  - Show channel breakdown PieChart
  - Show feature highlight cards for forecasting, budget optimizer, campaign insights, AI summaries
  - Include DataUpload component with refetch on success

- [x] 12. Implement Forecast page
  - Create `pages/Forecast.jsx` at route `/forecast`
  - Implement forecast level selector (channel, campaign-type)
  - Implement horizon selector (30, 60, 90 days)
  - Implement channel multi-select
  - Implement custom budget inputs with toggle
  - Implement POST SSE streaming using `fetch` + `ReadableStream` + `TextDecoder` with buffer handling
  - Render ForecastProgress during streaming
  - Render AggregateForecastChart and per-channel detail cards on complete
  - Render AI executive summary via MarkdownRenderer

- [x] 13. Implement Budget Optimizer page
  - Create `pages/BudgetOptimizer.jsx` at route `/budget-optimizer`
  - Implement total budget range slider ($10K–$200K)
  - Implement minimum ROAS range slider (0–5x, optional)
  - Call `POST /api/budget/optimize` using `useMutation`
  - Show loading animation during optimization
  - Render per-channel allocation cards with spend, revenue, ROAS, percentage bar
  - Render AI recommendation via MarkdownRenderer
  - Show visible red error message when API call fails (including 404)
