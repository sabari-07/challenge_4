# Known Bugs — Kiro Birthday Challenge Day 3

These bugs were identified by Kiro Autopilot during investigation of the broken AIgnition project.
Each one was diagnosed from root cause and fixed without breaking existing behavior.

---

## Bug A — Wrong API Endpoint (Frontend)

**File:** `frontend/src/pages/BudgetOptimizer.jsx`

**Symptom:** Clicking "Optimize Allocation" on the Budget Optimizer page shows a red error:
`404 Not Found — endpoint "/api/budget/optimise" does not exist`

**Root Cause:** The `useMutation` call uses `/api/budget/optimise` (British spelling) instead of
the correct `/api/budget/optimize`. The backend route is registered as `/api/budget/optimize`,
so every request returns HTTP 404.

**Fix:** Change `optimise` → `optimize` in the `mutationFn` URL.

---

## Bug B — Wrong Response Field in Chart (Frontend)

**File:** `frontend/src/components/AggregateForecastChart.jsx`

**Symptom:** After a forecast completes, the revenue bar chart renders with all bars at zero height.
No data appears even though the forecast succeeded and per-channel cards show correct numbers.

**Root Cause:** The `Bar` component uses `dataKey="predicted_revenue"` and the `errorBar`
computation reads `d.predicted_revenue`, but the API response field is named `total_revenue`.
Since `predicted_revenue` is `undefined` on every data point, Recharts renders bars at height 0.

**Fix:** Change both `dataKey` and the `errorBar` calculation to use `total_revenue`.

---

## Bug C — Division by Zero in ROAS Calculation (Backend)

**File:** `src/data/preprocessor.py`

**Symptom:** The backend crashes on startup with a `ZeroDivisionError` (or produces `inf`/`NaN`
values that propagate into API responses, breaking JSON serialization downstream).

**Root Cause:** The ROAS calculation `df['roas'] = df['revenue'] / df['spend']` performs a
direct pandas division without guarding against rows where `spend == 0`. Any campaign day with
zero spend produces `inf` or `NaN`, which then poisons rolling averages and causes the
`/api/data/summary` endpoint to return invalid numeric values.

**Fix:** Restore the `np.where(df['spend'] > 0, df['revenue'] / df['spend'], 0.0)` guard so
zero-spend rows safely produce `0.0` ROAS instead of `inf`.

---

## Bug D — Wrong Cohere SDK Version (Backend)

**File:** `src/ai/cohere_client.py`

**Symptom:** Every forecast that reaches the AI insights step raises:
`AttributeError: 'Client' object has no attribute 'message'`
The backend logs show a traceback from inside `_chat()` and the SSE stream never emits
the `complete` event — the frontend progress bar hangs at the "AI Insights" step.

**Root Cause:** The client is instantiated as `cohere.Client` (SDK v1) instead of
`cohere.ClientV2` (SDK v2). The v1 `Client` uses `client.generate()` which returns a
`Generations` object — calling `.message.content[0].text` on it raises `AttributeError`
because that attribute path only exists on the v2 `ChatResponse` object.

**Fix:** Change `cohere.Client` → `cohere.ClientV2` and `client.generate(prompt=...)` →
`client.chat(model=..., messages=[...], max_tokens=...)`, then read the response as
`response.message.content[0].text`.

---

## Fix Summary

| Bug | File | Type | Visible Effect |
|-----|------|------|----------------|
| A | `BudgetOptimizer.jsx` | Wrong URL typo | Red 404 error in UI |
| B | `AggregateForecastChart.jsx` | Wrong field name | Empty bar chart |
| C | `preprocessor.py` | Missing zero-guard | Backend crash / NaN data |
| D | `cohere_client.py` | Wrong SDK version | AI step crash, progress hangs |
