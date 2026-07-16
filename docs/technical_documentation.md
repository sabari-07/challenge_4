# Technical Documentation — RevenueIQ

**AIgnition Hackathon 2026 · NetElixir**

---

## 1. Forecasting Methodology

RevenueIQ generates **aggregate-period probabilistic forecasts** for ecommerce revenue and ROAS across paid media channels. The system does not produce single deterministic values; every forecast output is a **P10–P90 range** (lower bound, expected, upper bound) representing the statistical uncertainty inherent in future revenue prediction.

### Forecast Levels

The system supports three levels of granularity:

| Level | Description | Aggregation |
|---|---|---|
| **Channel** | One forecast per ad platform | Google / Bing / Meta aggregated by day across all campaigns |
| **Campaign Type** | One forecast per campaign type within each channel | e.g. Google SEARCH, Google PERFORMANCE_MAX, Meta Prospecting |
| **Campaign** | One forecast per individual campaign | Top N or user-selected campaigns with sufficient data |

### Planning Horizons

Forecasts are generated for aggregate planning periods of **30, 60, or 90 days**. The output is a total predicted revenue for the period — not a daily time-series — in line with the brief's requirement for aggregate-period forecasts.

### Probabilistic Ranges

Each forecast produces:
- **P10 (Lower Bound)** — pessimistic scenario; 10th percentile of the predictive distribution
- **P50 (Expected)** — the model's best estimate; sum of `yhat` over the forecast period
- **P90 (Upper Bound)** — optimistic scenario; 90th percentile

The interval width is calibrated per channel and horizon:
- 30-day horizon → 80% interval width
- 60-day horizon → 90% interval width
- 90-day horizon → 95% interval width (wider to account for longer-range uncertainty)

---

## 2. Model Selection

### Core Model: Facebook Prophet

The forecasting engine is built on **Facebook Prophet** (`prophet` Python library), a decomposable time-series model suited to business metrics with strong seasonality and irregular holiday effects.

**Why Prophet:**
- Handles multiple seasonality components (weekly, yearly, quarterly) natively
- Robust to missing data and outliers
- Supports external regressors (spend) which directly links budget inputs to revenue predictions
- Produces calibrated uncertainty intervals via MCMC-style simulation

### Channel-Specific Configurations

Each channel receives a purpose-tuned Prophet configuration (`FinalProphetForecaster`):

#### Google
- `changepoint_prior_scale`: 0.08 / 0.04 / 0.02 (30d / 60d / 90d)
- `seasonality_prior_scale`: 3.0
- `seasonality_mode`: multiplicative
- Custom seasonalities: weekly (3 Fourier orders), yearly (8 orders), monthly (30.5-day, 4 orders), quarterly (91.25-day, 4 orders)
- Regressor: `spend` (stable channel — spend is a reliable budget-simulation handle)

#### Bing (Microsoft Ads)
- `changepoint_prior_scale`: 0.05 / 0.08 / 0.10 (30d / 60d / 90d)
- `seasonality_prior_scale`: 2.0
- `seasonality_mode`: additive (only ~18 months of data; multiplicative amplifies noise)
- Custom seasonalities: weekly (3 orders), yearly (5 orders), conditional Q4 spike (Nov–Dec, 3 orders)
- Regressor: `conversions` (0.73 correlation with revenue; more stable than spend for Bing)
- No spend regressor: Bing spend swings 3,000%+ between months and misleads the model

#### Meta (Facebook/Instagram)
- `changepoint_prior_scale`: 0.10 / 0.15 / 0.20 (30d / 60d / 90d)
- `seasonality_prior_scale`: 2.0
- `seasonality_mode`: additive (prevents negative predictions on short/volatile data)
- Custom seasonalities: weekly (3 orders), yearly (6 orders), conditional holiday shopping season (Nov–Dec, 5 orders)
- No spend regressor: Meta spend collapsed ~70% in late May 2026; the model learned a high positive coefficient and would predict near-zero revenue when projecting from the low post-collapse median
- **Sub-model split**: Meta data is split into Remarketing and Prospecting sub-series before fitting. Two independent Prophet models are trained; their forecasts are summed for the final output. This separates the stable remarketing signal from the volatile prospecting signal, reducing 30d error from 56.2% to ~19.9%.

### Budget-Adjusted Forecasting

When a user provides a custom future budget per channel, the model uses `predict_with_custom_spend()` which injects the user-supplied daily spend (`total_budget / horizon`) as the `spend` regressor for all future periods, replacing the default (30-day historical average). This directly influences the Prophet prediction because spend is a fitted regressor correlated with revenue.

---

## 3. Data Preprocessing Logic

### Ingestion (`DataLoader` + `ImprovedDataPreprocessor`)

The system uses `DataLoader` to load the three standard channel CSVs and `ImprovedDataPreprocessor` to clean them. For user-uploaded files, `DynamicDataLoader` auto-detects column names. All thresholds are derived from the data — no hardcoded dataset-specific constants.

| Internal Field | Accepted Aliases (examples) |
|---|---|
| `date` | `date`, `segments_date`, `TimePeriod`, `day`, `timestamp` |
| `revenue` | `revenue`, `metrics_conversions_value`, `conversions_value`, `sales`, `amount` |
| `spend` | `spend`, `metrics_cost_micros`, `cost`, `DailyBudget` |
| `clicks` | `clicks`, `metrics_clicks`, `click` |
| `impressions` | `impressions`, `metrics_impressions`, `impr`, `views` |
| `conversions` | `conversions`, `metrics_conversions`, `conversion_count` |
| `campaign_name` | `campaign_name`, `CampaignName`, `Campaign` |
| `campaign_type` | `campaign_type`, `CampaignType`, `campaign_advertising_channel_type` |

**Google Ads micros conversion:** If `metrics_cost_micros` is detected or spend values are >1,000,000× the revenue scale, the loader automatically divides by 1,000,000 to convert from micros to dollars.

**Channel detection:** Channel name is inferred from the filename using keyword matching (e.g. `google`, `adwords`, `gads` → `google`; `meta`, `facebook`, `fb` → `meta`). If no match, the filename stem is used as the channel name, enabling any new channel to be uploaded without code changes.

### Channel-Specific Preprocessing (`ImprovedDataPreprocessor`)

#### Bing (`prepare_bing`)
- All campaign types included — necessary because PerformanceMax and Shopping campaigns launched in Jan 2026 represented the majority of holdout data; filtering to Search-only caused 93% 60d error
- Training start date detected automatically: first date with non-zero revenue in a 14-day rolling window
- AOV derived from data: `median(revenue / conversions)` on active days (revenue > 0 and conversions > 0)
- Zero-revenue active days filled: `conversions × AOV`, floored at the median of non-zero revenue days
- ROAS column added

#### Meta (`prepare_meta`)
- Rows tagged `Remarketing` or `Prospecting` by keyword matching on `campaign_name` (keywords: `remarketing`, `retargeting`, `remarket`, `retarget`)
- Each sub-series aggregated and cleaned independently via `_clean_meta_daily()`
- `_clean_meta_daily()`: expands to full daily date range, records which dates were originally missing, interpolates numerics, then finds the longest contiguous missing-date gap (≥30 days) and discards all data before it (prevents imputed flat-line from poisoning the seasonal baseline)
- 99th-percentile outlier cap applied; 10th-percentile floor on non-zero revenue days
- `meta_type` column preserved through aggregation so `FinalProphetForecaster` can split sub-series

#### Google (`prepare_google`)
- Aggregates by date; ROAS computed
- No special cleaning needed — data is already clean

### Aggregation

The preprocessed daily DataFrames are passed directly to `FinalProphetForecaster.fit()`. For Meta, the multi-row-per-date DataFrame (one row per `meta_type` per day) is handled by the forecaster's `_split_meta_series()` function before fitting.

---

## 4. Assumptions

1. **Attribution as source of truth** — Existing channel-level attribution (Google Ads, Bing Ads, Meta Ads conversion data) is used as-is. No custom attribution model is built.
2. **Spend is a causal driver** — Revenue is treated as a function of spend. The logarithmic spend-response model and Prophet spend regressor both assume diminishing returns on additional spend.
3. **Historical patterns continue** — The model assumes that seasonality, trend, and spend-response relationships observed in historical data persist into the forecast period.
4. **Daily granularity is sufficient** — Data is aggregated to day-level before model training. Intra-day patterns are not modelled.
5. **Minimum 20 data points** — Campaign-level forecasts require at least 20 days of historical data per campaign. Below this threshold, a reliable Prophet model cannot be trained.
6. **Logarithmic spend-response** — The budget optimizer assumes `Revenue = a × log(Spend + 1) + b`. This captures diminishing returns but may not hold at extreme spend levels.
7. **Q4 seasonality** — Conditional seasonal components for Bing and Meta are applied in November–December. If uploaded data does not span at least one Q4, these components may have limited impact.

---

## 5. Limitations

1. **No cross-channel interaction effects** — The model treats channels independently. Cannibalization or synergy between Google and Meta is not captured.
2. **External events not modelled** — Competitor activity, macroeconomic shifts, or platform algorithm changes are not inputs to the model.
3. **Campaign-level uncertainty is higher** — Individual campaign forecasts have wider confidence intervals than channel-level aggregates due to less data and higher idiosyncratic variance.
4. **90-day forecasts are less reliable** — Forecast accuracy degrades with horizon. The 95% interval width at 90 days is deliberately wide to communicate this.
5. **Budget optimizer uses historical curves only** — The `BudgetOptimizer` fits a logarithmic curve to historical spend-revenue data. It does not use the Prophet model for scenario simulation; it is a separate analytical tool.
6. **Single-channel CSV uploads** — The system is designed for multi-channel analysis. Uploading a single channel's data will limit forecasts to that one channel and the budget optimizer will only have one curve to work with.
7. **No real-time data** — The system requires CSV upload; there is no live API connection to Google Ads, Bing Ads, or Meta Ads.

---

## 6. AI Integration Strategy

### LLM Provider

**Cohere** (`cohere-python` SDK v2) using model **`command-r-plus-08-2024`**. The model is configurable via the `COHERE_MODEL` environment variable.

### Integration Points

The AI layer (`CohereClient`) is invoked **once per forecast generation** to produce a single executive summary. It is not called per-channel or per-campaign to avoid excessive API usage and latency.

| Trigger | Method | Output |
|---|---|---|
| Channel-level forecast complete | `generate_channel_level_summary()` | Strategic cross-channel executive analysis |
| Campaign-type forecast complete | `generate_campaign_type_summary()` | Campaign type efficiency comparison and recommendation |
| Campaign-level forecast complete | `generate_campaign_level_summary()` | Portfolio-level insights and top-performer highlights |
| Budget optimization complete | `suggest_budget_allocation()` | Natural-language budget strategy rationale |

### Prompt Design

Each prompt provides the model with:
- Exact numeric outputs from the statistical model (revenue, ROAS, bounds)
- Historical performance context (last 30 days)
- Trend direction (increasing / stable)
- Explicit instructions to use the provided numbers verbatim — preventing hallucinated figures

The system prompt role is a **"digital marketing analytics expert"** targeting CMO-level language: strategic, actionable, and number-specific.

### Causal Inference Role

The LLM acts as a **causal inference layer** — it does not generate the forecast numbers, but interprets why the statistical model's output makes sense given observed patterns, identifies key risks (e.g. Q4 seasonality dependency, high uncertainty), and surfaces one specific optimization recommendation per forecast. This separates the statistical computation from the business reasoning layer.

---
