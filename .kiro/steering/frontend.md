# Frontend Steering — AIgnition

## Entry Point

`frontend/index.html` loads `/src/main.jsx` which mounts the React app inside `<div id="root">`.

`main.jsx` wraps the app in `QueryClientProvider` (TanStack React Query v5).

`App.jsx` contains the router, 3D background (`Scene3D`), `Navbar`, and three lazy-loaded page routes.

## Pages

| File | Route | Description |
|------|-------|-------------|
| `pages/Dashboard.jsx` | `/` | Historical analytics + active dataset panel |
| `pages/Forecast.jsx` | `/forecast` | Forecast configuration + SSE results |
| `pages/BudgetOptimizer.jsx` | `/budget-optimizer` | Budget allocation tool |

## Components

| File | Purpose |
|------|---------|
| `components/Navbar.jsx` | Top navigation with links to all three routes |
| `components/MetricCard.jsx` | KPI tile — value, label, optional change % |
| `components/RevenueChart.jsx` | Historical area chart (Recharts AreaChart) per channel |
| `components/ChannelBreakdown.jsx` | Revenue share donut (Recharts PieChart) |
| `components/AggregateForecastChart.jsx` | Bar + ErrorBar chart (P10–P90), one bar per channel/type/campaign |
| `components/DataUpload.jsx` | CSV drag-and-drop upload panel |
| `components/ForecastProgress.jsx` | SSE step progress indicator (5 steps) |
| `components/MarkdownRenderer.jsx` | react-markdown + remark-gfm renderer for AI summaries |
| `components/Scene3D.jsx` | Three.js animated background (floating spheres + particles) |

## Tailwind Theme Colors

| Token | Usage |
|-------|-------|
| `trading-cyan` | `#06b6d4` — primary accent, headings, borders |
| `trading-blue` | `#3b82f6` — links, Google channel color |
| `trading-dark` | `#0a0e27` — background |
| `trading-darker` | `#060817` — deeper background |

Define these in `tailwind.config.js` under `theme.extend.colors`.

## API Client

All HTTP calls go through Axios to `http://localhost:8000`. No base URL config needed in development (Vite proxy not used — direct calls).

## Data Fetching Patterns

- Use **TanStack React Query** `useQuery` for GET endpoints with cache keys like `['dataStatus']`, `['dataSummary']`, `['historicalData', days]`
- Use `useMutation` for POST endpoints (forecast, budget optimize)
- SSE streaming: use `fetch` + `response.body.getReader()` + `TextDecoder` for POST SSE; native `EventSource` for GET SSE
- **No Redux, no Zustand** — Zustand is in package.json but intentionally not used

## SSE Streaming (POST, channel forecast)

```js
const response = await fetch('http://localhost:8000/api/forecast/generate-stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload)
})
const reader = response.body.getReader()
const decoder = new TextDecoder()
while (true) {
  const { done, value } = await reader.read()
  if (done) break
  const text = decoder.decode(value)
  const lines = text.split('\n')
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const event = JSON.parse(line.slice(6))
      if (event.step === 'complete') setForecastData(event.data)
      else setProgressState(event)
    }
  }
}
```

## Known Broken Behaviors (Active Bugs for Demo)

| Bug | File | What's Wrong | Correct Value |
|-----|------|-------------|---------------|
| A | `pages/BudgetOptimizer.jsx` | `mutationFn` calls `/api/budget/optimise` → 404 | `/api/budget/optimize` |
| B | `components/AggregateForecastChart.jsx` | `dataKey="predicted_revenue"` → bars at zero | `dataKey="total_revenue"` |

## Chart Colors by Channel

```js
const CHANNEL_COLORS = {
  google: '#3b82f6',   // blue
  bing:   '#06b6d4',   // cyan
  meta:   '#8b5cf6',   // purple
}
```

## Vite Config

Dev server runs on port 3000. No proxy needed — frontend calls backend on port 8000 directly.
