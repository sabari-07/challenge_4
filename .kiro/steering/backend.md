# Backend Steering — AIgnition

## FastAPI App (`src/api/app.py`)

The app is started with:
```
python -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

On `startup`, the app initialises these module-level globals (shared across requests):
1. `data_loader` — `DynamicDataLoader` — loads `data/uploads/*.csv` if present, else `data/*.csv`
2. `preprocessor` — `DataPreprocessor` — validates and prepares data, computes ROAS + rolling features
3. `cohere_client` — `CohereClient` — validates `COHERE_API_KEY`
4. `budget_optimizer` — `BudgetOptimizer` — fits logarithmic spend-response curves per channel

## Endpoints

### Data
- `GET /api/data-status` → channel availability, metadata, `using_uploaded_data` flag
- `GET /api/data/summary` → aggregate revenue, spend, ROAS, per-channel breakdown
- `GET /api/data/historical?days=N` → daily revenue/spend time series
- `GET /api/data/campaigns?channel=X&min_data_points=N` → campaign list
- `POST /api/upload-data` → upload CSVs, re-init data_loader + budget_optimizer
- `DELETE /api/upload-data` → clear uploads, revert to defaults

### Forecast (SSE Streaming)
- `POST /api/forecast/generate-stream` → channel-level forecast
- `GET /api/forecast/campaign-type-stream` → campaign-type forecast
- `POST /api/forecast/campaign-level-stream` → campaign-level forecast

### Budget
- `POST /api/budget/optimize` → SLSQP allocation optimisation
- `POST /api/budget/simulate` → simulate a manual allocation

## SSE Event Format

```
data: {"step": "loading",     "progress": 0,   "message": "Loading data..."}
data: {"step": "training",    "progress": 100, "message": "Models trained"}
data: {"step": "forecasting", "progress": 100, "message": "Forecasts generated"}
data: {"step": "ai_insights", "progress": 100, "message": "AI summary complete"}
data: {"step": "complete",    "progress": 100, "data": { ...full result... }}
```

## Cohere SDK v2 Usage (Correct Pattern — currently broken as Bug D)

The correct implementation uses SDK v2:

```python
import cohere

client = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))
response = client.chat(
    model=os.getenv("COHERE_MODEL", "command-r-plus-08-2024"),
    messages=[{"role": "user", "content": prompt}],
    max_tokens=2000
)
text = response.message.content[0].text
```

**Current broken state (Bug D):** `cohere_client.py` uses `cohere.Client` (v1) with
`client.generate(prompt=...)` — this raises `AttributeError` because `.message.content[0].text`
does not exist on the v1 `Generations` response object.

## Prophet Model

`FinalProphetForecaster` in `src/models/prophet_final.py`:
- Channel-specific configs (google/bing/meta)
- `fit(df)` expects columns: `ds` (date), `y` (revenue), `spend`
- `predict(periods, future_spend=None)` returns Prophet forecast DataFrame
- `predict_with_custom_spend(periods, daily_spend)` uses custom budget
- `get_forecast_summary(forecast, periods)` returns `{p10, p50, p90, total_revenue, lower_bound, upper_bound}`

## Budget Optimizer

`BudgetOptimizer` in `src/simulation/budget_optimizer.py`:
- `fit(df)` — fits `log(spend+1) → revenue` curves per channel via `sklearn.LinearRegression`
- `optimize_allocation(total_budget, channels, min_roas)` — SLSQP minimization, returns per-channel allocation dict
- `predict_revenue(channel, spend)` — `a * log(spend + 1) + b`

## Environment Variables

```
COHERE_API_KEY=<required>
COHERE_MODEL=command-r-plus-08-2024   # optional
API_HOST=0.0.0.0
API_PORT=8000
```
