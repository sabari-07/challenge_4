# AIgnition — Project Steering

## What This Project Is

AIgnition is a full-stack probabilistic revenue forecasting platform for digital marketing agencies. It forecasts revenue across Google Ads, Bing Ads, and Meta Ads using Facebook Prophet time-series models with Cohere AI-generated executive summaries.

## Stack

- **Frontend**: React 18 + Vite, React Router DOM v6, TanStack React Query v5, Recharts, Framer Motion, Tailwind CSS, Three.js + React Three Fiber, react-markdown + remark-gfm
- **Backend**: Python 3.11+, FastAPI, Uvicorn, Prophet, pandas, NumPy, scikit-learn, SciPy (SLSQP), Cohere Python SDK v2
- **AI**: Cohere `command-r-plus-08-2024` via `cohere.ClientV2`

## Project Layout

```
AIgnition/
├── frontend/          React SPA (Vite, port 3000)
│   └── src/
│       ├── main.jsx           Entry point — React Query provider, app mount
│       ├── App.jsx            Router, 3D background, lazy pages
│       ├── pages/             Dashboard.jsx, Forecast.jsx, BudgetOptimizer.jsx
│       └── components/        All reusable UI components
├── src/               Python backend
│   ├── api/           app.py (FastAPI), upload_handler.py
│   ├── data/          loader.py, dynamic_loader.py, preprocessor.py
│   ├── models/        prophet_final.py
│   ├── simulation/    budget_optimizer.py
│   └── ai/            cohere_client.py
├── data/              CSV data files (Google, Bing, Meta)
└── .env               COHERE_API_KEY (never commit)
```

## Routes

| URL | Page |
|-----|------|
| `/` | Dashboard |
| `/forecast` | Revenue Forecasting |
| `/budget-optimizer` | Budget Optimizer |

## API Base URL

Frontend talks to `http://localhost:8000` via Axios. All backend routes are prefixed `/api/`.

## Key Conventions

- The Cohere client should use **SDK v2** (`cohere.ClientV2`), not v1 — **currently broken (Bug D): uses `cohere.Client` v1 with `.generate()` instead of `.chat()`**
- Google Ads `metrics_cost_micros` must be divided by 1,000,000 to get dollars.
- No global state store — React Query for server state, `useState` for page-level UI state. Zustand is in package.json but intentionally unused.
- SSE streaming for forecasts: channel-level uses `fetch` + `ReadableStream` POST; campaign-type uses native `EventSource` GET.
- Prophet models are trained **on demand per request** — no pre-trained pickle files required.
- All forecast outputs are **P10/P50/P90 ranges**, never single point estimates.
- ROAS must be computed with a zero-spend guard — **currently broken (Bug C): direct division without `spend > 0` guard causes `inf`/`NaN`**
- Budget Optimizer API endpoint is `/api/budget/optimize` — **currently broken (Bug A): frontend calls `/api/budget/optimise` (typo)**
- Forecast chart uses `dataKey="total_revenue"` — **currently broken (Bug B): chart uses `predicted_revenue` (wrong field), bars render at zero**
