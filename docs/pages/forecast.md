# Revenue Forecasting Page — Feature Documentation

**Route:** `/forecast`  
**File:** `frontend/src/pages/Forecast.jsx`

---

## Overview

The Revenue Forecasting page is the primary feature of RevenueIQ. It allows users to:
1. Upload their own advertising CSV datasets to replace the default data
2. Configure a forecast (level, horizon, channels, optional custom budgets)
3. Generate a probabilistic forecast in real time via a streaming SSE connection
4. View per-channel or per-campaign aggregate revenue and ROAS predictions with P10–P90 confidence intervals
5. Read an AI-generated executive summary of the forecast results

---

## Sections

### 1. Page Header

Title: **"Revenue Forecasting"** with a cyan-to-blue gradient.
Subtitle: "Generate probabilistic revenue forecasts with AI-powered insights."

---

### 2. Data Upload

Component: `DataUpload` (`frontend/src/components/DataUpload.jsx`)

This panel allows users to upload CSV files from Google Ads, Bing Ads, or Meta Ads exports. Features:
- Accepts any CSV format — the backend auto-detects columns via alias mapping
- Multiple files can be uploaded simultaneously (one per channel)
- After a successful upload, the page automatically re-polls `/api/data-status` and:
  - Updates `availableChannels` to reflect only the uploaded channels
  - Resets `selectedChannels` to the valid uploaded channels
  - Re-synchronises `futureSpends` inputs to match the new channel list
- Supports clearing all uploaded data to revert to the default dataset

**API used:**
- `POST /api/upload-data` — upload one or more files
- `DELETE /api/upload-data` — clear uploads, revert to default

---

### 3. Forecast Configuration Panel

#### 3a. Forecast Level Selection

Three mutually exclusive options rendered as styled radio-button cards:

| Level | API Endpoint | Description |
|---|---|---|
| **Channel Level** | `POST /api/forecast/generate-stream` | One aggregate forecast per ad platform (Google, Bing, Meta) |
| **Campaign Type** | `GET /api/forecast/campaign-type-stream` | One forecast per campaign type within each channel (e.g. Google SEARCH, Meta Prospecting) |
| **Top Campaigns** | `POST /api/forecast/campaign-level-stream` | One forecast per individual campaign |

Switching level clears previous results immediately (via `useEffect` on `forecastLevel`).

#### 3b. Forecast Horizon

Three buttons: **30 Days**, **60 Days**, **90 Days**.

The selected horizon controls:
- How many future days Prophet predicts
- The width of the confidence interval (80% / 85% / 95%)
- The chart title and data labels

#### 3c. Channel Selection

Visible for all forecast levels:
- **Channel Level** — checkboxes, one per available channel; multiple can be selected simultaneously
- **Campaign Type / Campaign** — single dropdown; choose "All Channels" or one specific channel

The list of channels is **dynamically loaded** from `/api/data-status` on mount and after each upload, so only channels with actual data are shown. If one dataset is uploaded (e.g. Google only), only Google is listed.

**State variable:** `availableChannels` — refreshed from `response.data.metadata.channels`

#### 3d. Future Budget Inputs (Optional)

Always visible (at all three forecast levels). A checkbox labeled **"Use custom budgets"** toggles this section.

- **Disabled (default):** A blue info box explains that the system will use the last 30 days' average spend per channel as the future spend regressor.
- **Enabled:** Text input fields appear for each channel in `availableChannels`, pre-labelled with the channel name. Each field accepts a dollar amount. Empty fields fall back to the historical average.

When the form is submitted, only channels with a positive numeric value have their budget sent as `future_spends` in the POST body. The backend uses these values to set the Prophet spend regressor for all future periods (`daily_spend = total_budget / horizon`), directly influencing the revenue prediction.

**State variables:**
- `useCustomBudgets` — boolean toggle
- `futureSpends` — `{ [channel]: string }` map, keyed by channel name

#### 3e. Campaign Type Filters (Campaign Type level only)

Shown when `forecastLevel === 'campaign-type'`. Lists all campaign types available for the selected channel(s) as checkboxes. Types are derived from a static lookup (`CAMPAIGN_TYPES_BY_CHANNEL`):

| Channel | Types |
|---|---|
| Google | SEARCH, PERFORMANCE_MAX, DISPLAY, VIDEO, DEMAND_GEN, SHOPPING |
| Bing | Search, PerformanceMax, Audience, Shopping |
| Meta | Shopping, Search, Prospecting, Remarketing, Display |

Up to 3 types are auto-selected when the level is first switched to.

#### 3f. Campaign Level Filters (Campaign level only)

Shown when `forecastLevel === 'campaign'`. Contains:

**Selection Mode toggle:**
- **Top N Campaigns** — dropdown to select Top 10, 20, 30, 50, or All campaigns
- **Select Specific** — checkbox list of individual campaigns fetched from `/api/data/campaigns`

**Specific Campaign selector features:**
- Search box (filters by campaign name or ID in real time)
- Scrollable list with campaign name, channel badge, type badge, data-points count, total revenue, and ROAS
- Clear selection button showing selected count

**Minimum Historical Data selector:** 20 (recommended), 30, 60, or 90 days. Campaigns with fewer historical data points than this threshold are excluded from the results.

**API used:** `GET /api/data/campaigns?channel={channel}&min_data_points={N}`

#### 3g. Generate Button

Disabled when:
- No channels are selected
- Campaign Type level and no types are selected
- Specific campaign mode and no campaigns are selected

While running:
- Button shows a spinner and "Generating Forecast…" text
- For campaign level, estimates processing time based on campaign count (~0.5s per campaign)

---

### 4. Real-Time Progress Indicator

Component: `ForecastProgress` (`frontend/src/components/ForecastProgress.jsx`)

Visible while the forecast is running. Shows a step-by-step progress indicator that updates in real time as each SSE event arrives:

1. **Loading** — data loaded, preprocessing starts
2. **Training** — Prophet models fitted
3. **Forecasting** — predictions generated
4. **AI Insights** — Cohere executive summary generated
5. **Complete**

**SSE Transport:**
- **Channel level:** `fetch` + `ReadableStream` POST (required because `EventSource` is GET-only and `future_spends` must be in the request body)
- **Campaign type:** native `EventSource` GET
- **Campaign level:** `fetch` + `ReadableStream` POST

The `ReadableStream` reader splits the byte stream on `\n\n` boundaries, parses each `data: {...}` line as JSON, and calls `setProgressState(progress)` which the `ForecastProgress` component uses to update its UI.

---

### 5. Forecast Results

Results are shown with a Framer Motion fade-in and slide-up after loading completes. `AnimatePresence` handles the transition when switching between result sets.

#### 5a. Aggregate Bar Chart (all levels)

Component: `AggregateForecastChart` (`frontend/src/components/AggregateForecastChart.jsx`)

A Recharts `ComposedChart` with `Bar` + `ErrorBar`. Each bar represents the total predicted revenue for the **full forecast period** (not daily values).

- **Bar height** = `total_revenue` (P50 expected value)
- **Error bars** = `[expected - lower, upper - expected]` (representing P10–P90 spread)
- **Colours**: Google=blue (#3b82f6), Bing=cyan (#06b6d4), Meta=purple (#8b5cf6); additional channels use a rotating palette
- **Custom tooltip**: shows Expected, P10 (Low), P90 (High), and Range on hover
- **Label rotation**: automatic when >5 items
- **Legend chips** below the chart for quick identification

**Data fed to the chart:**
- Channel level: one item per channel from `forecastData.forecast.channels`
- Campaign type level: one item per `{channel}·{type}` combination from `campaignTypeData.forecast.campaign_types`
- Campaign level: top 10 campaigns by expected revenue from `campaignData.forecast.campaigns`

#### 5b. Aggregate Summary Cards (channel level)

Below the chart, three metric cards showing the **cross-channel aggregate**:
- Predicted Revenue (P50)
- Lower Bound (P10)
- Upper Bound (P90)

And optionally a **Predicted Blended ROAS** card if `aggregate.blended_roas` is present in the response.

#### 5c. Per-Channel Detail Cards (channel level)

One card per forecasted channel, each containing two sections:

**Revenue Forecast (Probabilistic Range):**
- Lower Bound (P10)
- Expected Revenue (P50)
- Upper Bound (P90)

**ROAS Forecast (Probabilistic Range):**
- Lower ROAS (P10)
- Expected ROAS (P50)
- Upper ROAS (P90)

#### 5d. Campaign Type Cards (campaign type level)

Below the chart, a grid of compact cards, grouped by channel. Each card shows:
- Revenue Range (`lower – upper`)
- Expected Revenue
- ROAS Range

#### 5e. Campaign List (campaign level)

Below the chart, a scrollable list (max height 600px with a custom cyan scrollbar) of all forecasted campaigns, ranked by expected revenue. Each row shows:
- Campaign name
- Channel and campaign type badges
- Rank number (`#1`, `#2`, …)
- Expected Revenue
- Revenue Range (P10–P90)
- Expected ROAS
- ROAS Range (P10–P90)

An info box above the list describes the selection mode and minimum data threshold used.

#### 5f. Executive AI Analysis

Displayed at the bottom of each result set, rendered via `MarkdownRenderer` (react-markdown + remark-gfm). Contains:
- Strategic narrative from Cohere `command-r-plus-08-2024`
- Exact forecast numbers woven into prose
- Key risk callouts (seasonality, uncertainty range)
- One specific actionable recommendation

Color-coded by forecast level:
- Channel level: cyan border
- Campaign type level: purple border
- Campaign level: green border

---

## State Variables

| Variable | Default | Purpose |
|---|---|---|
| `horizon` | `30` | Forecast period in days |
| `forecastLevel` | `'channel'` | Active forecast granularity |
| `selectedChannels` | `['google','bing','meta']` | Channels to include (updated from data status) |
| `availableChannels` | `['google','bing','meta']` | Channels with data (dynamic, from API) |
| `useCustomBudgets` | `false` | Toggle for custom spend inputs |
| `futureSpends` | `{}` | Map of `{ channel: string }` budget amounts |
| `forecastData` | `null` | Channel-level forecast response |
| `campaignTypeData` | `null` | Campaign-type forecast response |
| `campaignData` | `null` | Campaign-level forecast response |
| `progressState` | `null` | Current SSE step event |
| `isLoading` | `false` | Whether a forecast request is in progress |
| `selectionMode` | `'topN'` | Campaign mode: Top N or Specific |
| `topNCampaigns` | `20` | Number of top campaigns to forecast |
| `minDataPoints` | `20` | Minimum historical days per campaign |
| `selectedCampaignIds` | `[]` | IDs of specifically selected campaigns |
| `selectedCampaignTypes` | `[]` | Campaign types for campaign-type level |

---

## Component Dependencies

| Component | Purpose |
|---|---|
| `DataUpload` | CSV upload modal with drag-and-drop |
| `ForecastProgress` | SSE step progress indicator |
| `AggregateForecastChart` | Aggregate bar chart with P10–P90 error bars |
| `MarkdownRenderer` | Renders AI summary as formatted markdown |
| `Navbar` | Top navigation bar |
