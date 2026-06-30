# # Nexus

Nexus is a 29-module market terminal covering equities, options, fixed income, commodities, crypto, portfolio analytics, sentiment, and geopolitical risk. Everything markup, styles, and logic lives in one .html file.
This makes it trivially portable: download the file, double-click it, and the terminal boots. It also makes it a useful teaching artifact for demonstrating that a serious-looking financial dashboard doesn't require a server stack to be functional most of what people associate with a "terminal" is UI density and data modeling, not backend complexity.

## Status

Frontend: complete, runs standalone with synthetic/demo data, no build step required.
Backend: in progress.

## Quick start (frontend only)

```bash
git clone https://github.com/LordXapose/nexus.git
cd nexus
open Nexus_v5.html   # or just double-click the file
```

No install step. The terminal boots immediately using built-in demo data generators, so it's fully interactive before any backend exists.

## Architecture

```

### Module system

Every screen is a `div.module`. A single router toggles visibility and lazily initializes a module the first time it's opened:

```js
function switchModule(id, btn) {
  document.querySelectorAll('.module').forEach(m => m.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  if (id === 'earnings' && !earningsInit) {
    setTimeout(() => { initEarnings(); earningsInit = true; }, 80);
  }
  // ...one line per module
}
```

### Shared utilities

| Function | Purpose |
|---|---|
| `mkChart(id, config)` | Wraps Chart.js, destroys/recreates the chart on a canvas to avoid leaks |
| `mkKpi(el, items)` | Renders a KPI tile row from `[label, value, class]` tuples |
| `drow(label, value, class)` | Renders a single label/value row |
| `fmtM(n)` | Formats large numbers as `$1.2M` / `$3.4B` |
| `nexusFetch(url, fallback)` | Fetches an API with a timeout, falls back to demo data on failure |
| `rnd(a,b)` / `rndInt(a,b)` / `pick(arr)` | Synthetic data generation helpers |

### Per-module pattern

Each module follows the same shape: `initX()` runs once and builds the dataset plus the initial render, `renderX()` / `filterX()` redraw the DOM and charts on filter or dropdown changes, and Chart.js canvases handle all visualizations.

## Modules (29, across 10 nav groups)

**Home** Overview dashboard

**Markets** Dashboard, Order Book, News & Macro

**Global Tracking** All Traffic (map), Aircraft, Vessels

**Risk & Analytics** Aladdin Risk, Stress Test, Compliance, Monte Carlo

**New Modules** Options Chain, Dark Pool, Macro Heat Map, Correlation Lab

**Intelligence** Earnings Calendar, Short Interest Monitor, Insider Transactions, Sentiment Dashboard, Social Sentiment, Sector Rotation

**Fixed Income** Yield Curve, Bond Screener, Credit Spreads

**Commodities** Commodities Dashboard, On-Chain Analytics, Futures Curve

**Portfolio** Backtester, Options P&L Calculator, Tax Lot Tracker

**Global** Geopolitical Risk Monitor, Trade Flow Map, FX Intervention Tracker

## Tech stack


## Backend (planned)

A Python backend will sit behind this frontend to:

- Proxy real market data providers (Polygon, Alpha Vantage, FRED, CoinGecko) so API keys aren't exposed client-side
- Cache responses and manage rate limits
- Normalize provider responses into the shapes each module already expects

Every data-driven module is structured so swapping its synthetic generator for a real API call is a small, contained change — the rendering and state logic doesn't need to know where the data came from.

