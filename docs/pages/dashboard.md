# Dashboard Page — Feature Documentation

**Route:** `/`  
**File:** `frontend/src/pages/Dashboard.jsx`

---

## Overview

The Dashboard is the landing page of RevenueIQ. It serves two purposes: a **marketing overview** that introduces the platform's capabilities, and a **live data status panel** that shows which datasets are currently active. A collapsible analytics section then provides historical performance visualisations for the loaded data.

---

## Sections

### 1. Hero Banner

The top section contains:
- **Product name** — "RevenueIQ" rendered in a gradient (cyan → blue → purple)
- **Tagline** — "AI-powered probabilistic revenue forecasting for e-commerce paid advertising"
- Two **quick-action buttons**:
  - **Generate Forecast** — navigates to `/forecast`
  - **Optimize Budget** — navigates to `/budget-optimizer`

Both buttons use Framer Motion entry animations (fade in, slide up).

---

### 2. Platform Capabilities

Four feature cards arranged in a 1→2→4-column responsive grid:

| Card | Description |
|---|---|
| **Probabilistic Forecasting** | Prophet-powered 30/60/90-day forecasts with P10–P90 confidence intervals per channel |
| **Budget Optimization** | SLSQP optimizer maximises blended ROAS across Google, Bing, Meta under a fixed budget |
| **Campaign-Level Insights** | Per-campaign and campaign-type revenue and ROAS forecasts |
| **AI Executive Summaries** | Cohere `command-r-plus` synthesises every forecast into a plain-English decision brief |

Each card has a colour-coded icon (cyan, purple, blue, green) and a gradient background.

---

### 3. Active Dataset Panel

**API used:** `GET /api/data-status` (auto-refreshes every 15 seconds via React Query's `refetchInterval`)

Shows:
- A badge indicating whether the system is running on **Uploaded Data** (green) or the **Default Dataset** (cyan)
- A manual **Refresh** button (RefreshCw icon) to force an immediate re-poll
- **Per-channel status chips** (Google, Bing, Meta) — green/active with a CheckCircle icon if the channel is present in the loaded data; grey/inactive with an AlertCircle icon if absent
- **Uploaded file list** — when using uploaded data, lists each uploaded filename with an Upload icon
- **Data metadata strip** (when available):
  - Date Range (start → end)
  - Total Records (row count)
  - Channels Loaded (n / 3)
- A note when using the default dataset indicating its date range (Jan 2024 – Jun 2026) and the instruction to upload CSVs on the Forecast page to override

**State variables:**
- `usingUploaded` — boolean from `/api/data-status` response `using_uploaded_data`
- `activeChannels` — array of channel names from `metadata.channels`
- `uploadedFiles` — array from `uploaded_files`

---

### 4. Detailed Analytics (Accordion)

Collapsed by default. Click **"View / Hide"** to toggle. Uses Framer Motion `AnimatePresence` for a height animation (0 → auto).

Data is fetched **lazily** — React Query only fires the API calls when `showAnalytics` is `true` (`enabled: showAnalytics`). This avoids unnecessary backend load on page open.

#### 4a. KPI Metric Cards

Three `MetricCard` components in a 1→3-column grid:

| Metric | Calculation |
|---|---|
| **Total Revenue** | Sum of `total_revenue` across all channels from `/api/data/summary` |
| **Total Spend** | Sum of `total_spend` across all channels |
| **Blended ROAS** | `Total Revenue / Total Spend` |

Each card shows a hardcoded percentage change indicator (placeholder for trend comparison feature).

**API used:** `GET /api/data/summary`

#### 4b. Revenue Trend Chart

An area chart (`RevenueChart` component, backed by Recharts `AreaChart`) showing daily revenue over time, one area per channel.

**Period selector** dropdown above the chart:
- Last 30 Days
- Last 90 Days
- Last 6 Months
- Last Year
- All Time (886 days)

Changing the period updates the `dateRange` state, which triggers a new React Query fetch with the updated `days` parameter.

**API used:** `GET /api/data/historical?days={dateRange}`

#### 4c. Channel Breakdown

A `ChannelBreakdown` component (Recharts `PieChart` donut) showing each channel's percentage of total revenue. Hovering a slice shows the channel name, revenue, and percentage.

**API used:** Data comes from the same `/api/data/summary` call as the metric cards (shared query cache).

#### 4d. Key Insights

Two insight cards rendered only when summary data is available:

- **Top Performing Channel** — displays the channel with the highest average ROAS from the summary data
- **Data Coverage** — total number of days of historical data and the date range

---

## Component Dependencies

| Component | File | Purpose |
|---|---|---|
| `Navbar` | `components/Navbar.jsx` | Top navigation bar with page links |
| `MetricCard` | `components/MetricCard.jsx` | KPI tile with value, label, and change indicator |
| `RevenueChart` | `components/RevenueChart.jsx` | Historical daily revenue area chart |
| `ChannelBreakdown` | `components/ChannelBreakdown.jsx` | Revenue share donut chart |

---

## Data Fetching

| Query Key | Endpoint | When Fired |
|---|---|---|
| `['dataStatus']` | `GET /api/data-status` | On mount, then every 15s |
| `['dataSummary']` | `GET /api/data/summary` | When analytics accordion opens |
| `['historicalData', dateRange]` | `GET /api/data/historical?days=N` | When analytics open + on period change |

All fetching is managed by **TanStack React Query**. No manual `useEffect` fetch loops.

---

## State Variables

| Variable | Type | Default | Purpose |
|---|---|---|---|
| `showAnalytics` | boolean | `false` | Controls analytics accordion visibility |
| `dateRange` | number | `90` | Number of days for historical chart |

---

## Animations

All sections use Framer Motion with staggered delays (0.3s → 0.35–0.63s per feature card). The analytics accordion animates height from 0 to auto with a 0.4s ease-in-out.

---

## Footer

Static footer: `© 2026 RevenueIQ. Powered by Cohere AI.`
