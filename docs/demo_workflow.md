# Demo Workflow — RevenueIQ

**AIgnition Hackathon 2026 · NetElixir**

This document walks through the four core scenarios a judge or evaluator should run to verify the prototype end-to-end.

---

## Prerequisites

- Application running locally (see [README](../README.md) for startup instructions)
- Frontend open at **http://localhost:3000**
- Backend running at **http://localhost:8000**

---

## Step 1 — Data Ingestion

### Using the default dataset

The application ships with three default CSVs in `data/`:
- `google_ads_campaign_stats.csv` — Google Ads campaign data (Jan 2024 – Jun 2026)
- `bing_campaign_stats.csv` — Microsoft Ads data
- `meta_ads_campaign_stats.csv` — Meta Ads data

On first load, these are automatically ingested. The Dashboard shows the **Active Dataset** panel with green channel chips for Google, Bing, and Meta.

### Uploading custom data

1. Navigate to the **Forecast** page (`/forecast`)
2. In the **Data Upload** section, click "Upload Data" or drag-and-drop one or more CSV files
3. Supported formats: any CSV with recognisable column headers (see column alias mapping in `docs/technical_documentation.md` Section 3)
4. After upload, the Active Dataset badge switches to **"Uploaded Data"** and only the uploaded channels appear in channel selectors
5. To revert to default data, click "Clear Uploaded Data" in the upload panel

**Verifiable outcome:** Dashboard → Active Dataset panel shows correct channel chips, date range, and record count matching the uploaded files.

---

## Step 2 — Forecast Generation

### Channel-Level Forecast (30 days)

1. Go to **Forecast** page
2. Select **Channel Level** forecast
3. Select horizon: **30 Days**
4. Ensure all channels (Google, Bing, Meta) are checked
5. Leave **Future Budget** disabled (uses historical 30-day average)
6. Click **Generate Forecast**
7. Watch the real-time progress bar: Loading → Training → Forecasting → AI Insights → Complete (~10–15 seconds)

**Results to verify:**
- `AggregateForecastChart` bar chart appears — one bar per channel with P10–P90 error bars
- Aggregate summary cards show Predicted Revenue, P10 Lower Bound, P90 Upper Bound
- Per-channel cards show Revenue Range and ROAS Range (P10 / Expected / P90)
- AI Executive Analysis section renders a markdown narrative with specific numbers

### Channel-Level Forecast with Custom Budget

1. Same as above, but enable **"Use custom budgets"** toggle
2. Enter different budget amounts per channel, e.g.:
   - Google: $30,000
   - Bing: $10,000
   - Meta: $15,000
3. Generate forecast
4. Compare: expected revenue values should differ from the historical-average run, reflecting the custom spend inputs fed into the Prophet spend regressor

### Campaign Type Forecast (60 days)

1. Select **Campaign Type** forecast level
2. Select horizon: **60 Days**
3. Choose channel: **All Channels** or a single channel
4. From the campaign type checklist, select a few types (e.g. SEARCH, PERFORMANCE_MAX for Google)
5. Click **Generate Forecast**

**Results to verify:**
- Bar chart shows one bar per `{channel}·{type}` combination
- Grid of campaign type cards with revenue ranges and ROAS ranges
- AI summary reflects campaign type breakdown

### Campaign-Level Forecast (90 days)

1. Select **Top Campaigns** forecast level
2. Horizon: **90 Days**
3. Selection mode: **Top N Campaigns**, set to 10
4. Minimum Historical Data: 20 days
5. Click **Generate Forecast**

**Results to verify:**
- Bar chart shows top 10 campaigns by predicted revenue
- Scrollable campaign list with rank, revenue, ROAS per campaign
- AI portfolio summary at the bottom

---

## Step 3 — Budget Simulation

1. Navigate to **Budget Optimizer** (`/budget-optimizer`)
2. Set **Total Budget** slider to **$75,000** (drag or use keyboard)
3. Leave **Minimum ROAS** at **0** (No constraint — Optional) to allow maximum revenue allocation
4. Click **Optimize Allocation**

**Results to verify:**
- Three channel allocation cards appear (or fewer if only some channels have data)
- Each card shows: Allocated Budget, % of Total, Expected Revenue, Channel ROAS
- Percentages sum to 100%
- Total Predicted Revenue and Blended ROAS summary cards are populated

### With ROAS Constraint

1. Set Minimum ROAS slider to **2.5x**
2. Click **Optimize Allocation** again
3. Observe: allocation may shift compared to the unconstrained run — channels that would produce sub-2.5x ROAS receive less budget; total predicted revenue may be slightly lower but efficiency floor is enforced

**Results to verify:**
- AI Recommendation section explains the trade-off in plain English
- Allocated budgets reflect the ROAS constraint impact

---

## Step 4 — AI-Generated Business Insights

AI summaries are generated automatically at the end of every forecast and optimization. They do not require any extra action.

### What to look for in each context:

**Channel-level forecast summary (bottom of results):**
- Named specific dollar amounts from the forecast output (not hallucinated)
- Identifies the highest-revenue channel and why
- Calls out P10–P90 range as an uncertainty indicator
- Gives one specific budget recommendation

**Campaign type summary:**
- Compares efficiency across campaign types (SEARCH vs PERFORMANCE_MAX vs Prospecting)
- Notes Q4 seasonality impact if applicable
- Recommends type-level budget shifts

**Campaign-level summary:**
- Portfolio view of top performers
- Identifies underperforming campaigns with high spend
- Flags campaigns with wide confidence intervals (high uncertainty)

**Budget optimization recommendation:**
- Explains logarithmic diminishing returns logic in plain language
- Justifies the specific percentage split recommended
- Notes what ROAS constraint impact means practically

---

## End-to-End Verification Checklist

| Step | Feature | Expected Result |
|---|---|---|
| 1 | Default data loads | Dashboard shows 3 green channel chips |
| 1 | Custom CSV upload | Channel chips update to uploaded channels only |
| 2a | Channel forecast (30d) | Bar chart + per-channel cards + AI summary |
| 2b | Custom budget inputs | Revenue values differ from historical-average run |
| 2c | Campaign type forecast | Per-type grid with ROAS ranges |
| 2d | Campaign-level forecast | Ranked campaign list + portfolio AI summary |
| 3a | Budget optimization (no ROAS) | 100% budget allocated, max revenue |
| 3b | Budget optimization (2.5x ROAS) | Allocation shifts, AI explains constraint |
| 4 | AI summary content | Contains exact forecast numbers, no hallucinated figures |

---

## Demo Script for Presentation (5 minutes)

| Time | Action |
|---|---|
| 0:00 | Open Dashboard — show active dataset panel and platform capabilities |
| 0:45 | Upload a custom CSV — watch channel chips update in real time |
| 1:15 | Forecast page → Channel Level → 30 days → Generate → walk through progress bar |
| 2:00 | Show bar chart, P10–P90 error bars, per-channel ROAS range |
| 2:30 | Show AI Executive Analysis — point to specific numbers in the narrative |
| 3:00 | Switch to Campaign Type level — show type-level breakdown |
| 3:30 | Budget Optimizer → $75K → 2.5x ROAS → Optimize — show allocation cards |
| 4:00 | Show AI recommendation — explain diminishing returns rationale |
| 4:30 | Enable custom budgets on Forecast page — re-run, show revenue changes |
