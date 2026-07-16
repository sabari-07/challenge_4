# Requirements

## Original Prompt

> Build a full-stack revenue forecasting platform for digital marketing agencies that predicts 30, 60, and 90-day revenue across Google Ads, Bing Ads, and Meta Ads using AI-powered probabilistic models with a budget optimization engine.

## Requirements

### Requirement 1 — Data Ingestion

**User Story:** As a marketing analyst, I want to load campaign performance data from Google Ads, Bing Ads, and Meta Ads, so that I can analyse historical revenue and spend across all my paid channels in one place.

#### Acceptance Criteria

- WHEN the application starts THEN the system SHALL automatically load the default CSV datasets for Google Ads, Bing Ads, and Meta Ads from the data directory
- WHEN a user uploads one or more CSV files THEN the system SHALL detect the channel from the filename, auto-map column names to the internal schema, and reload all downstream data and models
- WHEN uploaded CSV files are present THEN the system SHALL use uploaded data in preference to default datasets
- WHEN a user deletes uploaded data THEN the system SHALL revert to the default datasets
- WHEN Google Ads data is loaded THEN the system SHALL convert `metrics_cost_micros` to dollars by dividing by 1,000,000
- WHEN any CSV row has a missing or unparseable date THEN the system SHALL drop that row and continue loading

### Requirement 2 — Data Status and Summary

**User Story:** As a marketing analyst, I want to see what data is currently active and get a summary of historical performance, so that I know the quality and coverage of the data driving my forecasts.

#### Acceptance Criteria

- WHEN the dashboard loads THEN the system SHALL display which channels are active (Google, Bing, Meta) and whether uploaded or default data is in use
- WHEN the data summary endpoint is called THEN the system SHALL return total revenue, total spend, ROAS, total clicks, total conversions, and days of data per channel
- WHEN the historical data endpoint is called with a days parameter THEN the system SHALL return daily revenue per channel for the last N days
- WHEN spend is zero for a row THEN the system SHALL set ROAS to 0.0 rather than producing infinity or NaN

### Requirement 3 — Probabilistic Revenue Forecasting

**User Story:** As a marketing director, I want to generate probabilistic revenue forecasts at the channel, campaign type, and campaign level, so that I can plan budgets with a clear understanding of upside and downside risk.

#### Acceptance Criteria

- WHEN a user requests a channel-level forecast THEN the system SHALL train a Prophet model per selected channel and return P10, P50, and P90 revenue estimates for the chosen horizon (30, 60, or 90 days)
- WHEN a user requests a campaign-type forecast THEN the system SHALL train a Prophet model per campaign type within the selected channel and return P10/P50/P90 estimates
- WHEN a user provides custom future budgets THEN the system SHALL inject those values as the spend regressor into the Prophet model for the forecast period
- WHEN no custom budget is provided THEN the system SHALL use the 30-day trailing average spend as the default regressor
- WHEN a channel has fewer than 10 data points THEN the system SHALL skip that channel and log a warning rather than raising an error
- WHEN a forecast is generated THEN the system SHALL stream progress updates to the frontend using Server-Sent Events with steps: loading, training, forecasting, ai_insights, complete

### Requirement 4 — AI Executive Summaries

**User Story:** As a CMO, I want an AI-generated executive summary with every forecast, so that I can quickly understand the key findings and recommended actions without reading raw numbers.

#### Acceptance Criteria

- WHEN a channel-level forecast completes THEN the system SHALL generate an executive summary using Cohere command-r-plus-08-2024 via SDK v2 ClientV2 and the chat method
- WHEN a campaign-type forecast completes THEN the system SHALL generate a media planner summary using the same Cohere SDK v2 pattern
- WHEN the COHERE_API_KEY environment variable is not set THEN the system SHALL return a placeholder message and continue without crashing
- WHEN the Cohere API call fails THEN the system SHALL catch the exception, log the error, and return a fallback message rather than propagating the error

### Requirement 5 — Budget Optimization

**User Story:** As a marketing director, I want to find the optimal budget allocation across channels that maximises predicted revenue for a given total spend, so that I can make data-driven budget decisions.

#### Acceptance Criteria

- WHEN a user submits a total budget and channel list THEN the system SHALL use SLSQP constrained optimization to find the spend allocation that maximises total predicted revenue
- WHEN a minimum ROAS constraint is provided THEN the system SHALL enforce that each channel meets the minimum ROAS in the optimal solution
- WHEN optimization succeeds THEN the system SHALL return per-channel spend, predicted revenue, ROAS, and percentage of total budget
- WHEN a user submits a manual allocation THEN the system SHALL simulate the predicted revenue for that allocation without running optimization
- WHEN the optimization result is returned THEN the system SHALL generate an AI budget strategy recommendation using Cohere

### Requirement 6 — React Frontend Dashboard

**User Story:** As a marketing analyst, I want a real-time interactive dashboard, so that I can explore forecasts, upload data, and configure budget scenarios without needing any technical knowledge.

#### Acceptance Criteria

- WHEN the app loads THEN the system SHALL display a Dashboard page at route `/` with KPI cards, revenue trend chart, and channel breakdown
- WHEN the user navigates to `/forecast` THEN the system SHALL display forecast configuration options (level, horizon, channels, custom budgets) and render results as a bar chart with P10–P90 error bars
- WHEN the user navigates to `/budget-optimizer` THEN the system SHALL display budget and ROAS sliders and render the optimized allocation as per-channel cards with a progress bar
- WHEN a forecast is streaming THEN the system SHALL show a live progress indicator with the current step name
- WHEN the forecast chart renders THEN the system SHALL use `total_revenue` as the bar height data key and display P10–P90 as error bars
- WHEN the budget optimizer API call fails THEN the system SHALL display a visible red error message showing the HTTP status and endpoint that failed
