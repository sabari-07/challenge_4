# Budget Optimizer Page — Feature Documentation

**Route:** `/budget-optimizer`  
**File:** `frontend/src/pages/BudgetOptimizer.jsx`

---

## Overview

The Budget Optimizer answers a specific strategic question: **given a fixed total advertising budget, how should it be split across channels to maximise total revenue and ROAS?**

The user provides a total budget figure and an optional minimum ROAS constraint. The system uses historical spend-revenue data from the loaded dataset to fit logarithmic spend-response curves per channel, then runs an SLSQP constrained optimisation to find the allocation that maximises predicted blended revenue. An AI-generated narrative explains the recommended strategy in plain English.

---

## How It Works (End-to-End)

1. On startup (or after a data upload), the backend fits a **logarithmic spend-response curve** for each available channel using `scikit-learn LinearRegression` on `log(spend + 1) → revenue`. This gives: `Revenue = a × log(Spend + 1) + b`.
2. The user sets a **total budget** and an optional **minimum ROAS** on the frontend.
3. On "Optimize Allocation", the frontend POSTs `{ total_budget, channels, min_roas }` to `/api/budget/optimize`.
4. The backend runs `scipy.optimize.minimize` with method `SLSQP`, minimizing negative total revenue subject to:
   - Spend per channel ≥ 0
   - Sum of all channel spends = total budget
   - (Optional) Revenue / Spend ≥ min_roas for each channel
5. The result is per-channel: optimal spend amount, predicted revenue, ROAS, and percentage of total.
6. Cohere `command-r-plus-08-2024` generates a budget strategy narrative from the allocation data.
7. The frontend renders the results and the AI recommendation.

---

## Sections

### 1. Page Header

Title: **"Budget Optimizer"** with a purple-to-cyan gradient.
Subtitle: "AI-powered budget allocation to maximize revenue and ROAS."

---

### 2. Optimization Parameters

#### 2a. Total Budget Slider

A range slider with:
- **Range:** $10,000 – $200,000
- **Step:** $5,000
- **Default:** $50,000
- **Live label:** "Total Budget: $X" (formatted with commas, updates as slider moves)

The slider uses the `accent-trading-cyan` Tailwind color for the filled track.

#### 2b. Minimum ROAS Constraint (Optional)

A range slider with:
- **Range:** 0 – 5.0x
- **Step:** 0.1
- **Default:** 2.0x
- **Label logic:**
  - When > 0: displays `"Minimum ROAS: X.Xx"`
  - When = 0: displays `"Minimum ROAS: No constraint (Optional)"` in muted grey, with "(Optional)" as smaller text

The left end of the scale shows **"No minimum (optional)"** to make it clear to users that they do not need to set this.

Setting this to 0 sends `min_roas: null` in the API request, disabling the ROAS constraint from the optimization. Setting it above 0 forces the optimizer to ensure every channel achieves at least that ROAS, which may result in lower total revenue (trade-off between revenue and efficiency floor).

#### 2c. Channel Detection

The page fetches `/api/data-status` on mount and updates `availableChannels` from `metadata.channels`. The optimizer only requests allocation for channels that have fitted spend-response curves in the backend. If only one dataset has been uploaded (e.g. Google only), the optimization runs for that single channel and the result shows one allocation.

**State variable:** `availableChannels` — defaults to `['google','bing','meta']`, updated from API on mount.

#### 2d. Optimize Allocation Button

Triggers `handleOptimize()` which calls the `useMutation` hook. While running:
- Button shows a spinner and "Optimizing…" text and is disabled

**API called:** `POST /api/budget/optimize`

**Request body:**
```json
{
  "total_budget": 50000,
  "channels": ["google", "bing", "meta"],
  "min_roas": 2.0
}
```

---

### 3. Loading State

While the mutation is in progress, a loading card is shown:
- A large purple spinner (4px border, animated)
- "Optimizing Budget Allocation" title
- "Calculating optimal spend distribution across channels…" subtitle
- A purple-to-cyan animated progress bar at 70% width (visual indicator, not tied to actual progress)

---

### 4. Optimization Results

Shown after the mutation completes successfully. Fades in with a Framer Motion animation.

#### 4a. Summary Cards

Three KPI cards in a 1→3-column grid:

| Card | Value Source |
|---|---|
| **Total Budget** | `optimization.total_budget` (the input budget, confirmed) |
| **Predicted Revenue** | `optimization.total_predicted_revenue / 1000` formatted as `$X.XK` |
| **Blended ROAS** | `optimization.blended_roas` formatted as `X.XXx` |

#### 4b. Per-Channel Allocation Cards

One card per channel in the optimization result, displayed in a 1→3-column grid. Each card shows:
- **Channel name** (uppercase, cyan)
- **Allocated Budget** — the optimal spend amount in `$X.XK` format
- **Percentage of Total** — `data.percentage.toFixed(1)%`
- **Expected Revenue** — predicted revenue in `$X.XK` format
- **ROAS** — channel-specific ROAS as `X.XXx`

Cards have a hover scale animation (`hover:scale-105`) and a lift on hover via Framer Motion `whileHover={{ y: -5 }}`.

The allocation percentages always sum to 100% (enforced by the SLSQP budget equality constraint).

#### 4c. AI Recommendation

Rendered via `MarkdownRenderer` (react-markdown + remark-gfm) inside a card with a left purple border. Contains:
- Plain-English explanation of why this allocation maximises revenue given the spend-response curves
- Calls out which channel has the highest marginal ROAS (steepest log curve)
- Notes any ROAS constraint impact if one was set
- One specific actionable recommendation (e.g. "Shift 10% from Meta to Google given Google's higher marginal return")

**Shown only when** `optimizationData.ai_recommendation` is truthy.

---

## State Variables

| Variable | Default | Purpose |
|---|---|---|
| `totalBudget` | `50000` | Total spend to distribute |
| `minRoas` | `2.0` | Minimum acceptable ROAS per channel (0 = no constraint) |
| `availableChannels` | `['google','bing','meta']` | Channels with fitted curves (from API) |

React Query `useMutation` manages:
- `isLoading` — mutation in progress
- `data` (as `optimizationData`) — the full API response once resolved

---

## API Integration

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/data-status` | Fetch available channels on mount |
| `POST` | `/api/budget/optimize` | Run the optimization |

**Response shape from `/api/budget/optimize`:**
```json
{
  "success": true,
  "optimization": {
    "total_budget": 50000,
    "total_predicted_revenue": 187432.50,
    "blended_roas": 3.75,
    "allocation": {
      "google": {
        "spend": 28000,
        "predicted_revenue": 112400,
        "roas": 4.01,
        "percentage": 56.0
      },
      "bing": {
        "spend": 12000,
        "predicted_revenue": 43200,
        "roas": 3.60,
        "percentage": 24.0
      },
      "meta": {
        "spend": 10000,
        "predicted_revenue": 31832.50,
        "roas": 3.18,
        "percentage": 20.0
      }
    }
  },
  "ai_recommendation": "## Budget Allocation Strategy\n..."
}
```

---

## Key Design Decisions

**Why logarithmic curves?**  
Advertising revenue exhibits diminishing returns — doubling spend rarely doubles revenue. `Revenue = a × log(Spend + 1) + b` captures this behaviour accurately for most digital ad channels and is computationally tractable for SLSQP optimization.

**Why SLSQP?**  
Sequential Least Squares Programming (from `scipy.optimize.minimize`) handles non-linear objective functions with equality and inequality constraints. The budget equality constraint (`sum(spends) = total_budget`) and ROAS floor constraints are both supported natively.

**Why is ROAS optional?**  
A strict ROAS floor can cause the optimizer to under-spend (leaving budget unallocated) or to allocate artificially to low-revenue channels that happen to be efficient. Allowing 0 (no constraint) gives the optimizer freedom to find the globally revenue-maximising solution, which is the more common use case for growth-stage advertisers. The optional label makes it clear this constraint is additive, not required.

**Single dataset support:**  
If only one channel's data has been uploaded, the budget optimizer still works — it fits one curve and allocates the full budget to that channel. The `POST /api/budget/optimize` endpoint filters `request.channels` to only those with fitted curves before running the optimization.

---

## Component Dependencies

| Component | Purpose |
|---|---|
| `Navbar` | Top navigation bar |
| `MarkdownRenderer` | Renders the AI recommendation markdown |
