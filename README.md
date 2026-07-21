# Nexus

Nexus is a 29-module market terminal covering equities, options, fixed income, commodities, crypto, portfolio analytics, sentiment, and geopolitical risk. Everything markup, styles, and logic lives in one .html file.
This makes it trivially portable: download the file, double-click it, and the terminal boots. It also makes it a useful teaching artifact for demonstrating that a serious-looking financial dashboard doesn't require a server stack to be functional most of what people associate with a "terminal" is UI density and data modeling, not backend complexity.

## Status

Frontend: complete, runs standalone with Real data, no build step required.
Backend: in progress.

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
# Nexus Changelog

A complete version history of the Nexus Financial Terminal, from initial concept through each build iteration.

---

## v1.0 Initial Build
**The Bloomberg Terminal Clone**

The original upload. A single-file financial Analysis dashboard in vanilla JavaScript with no build step, no backend, no dependencies beyond Chart.js and Leaflet loaded from CDN.

**What was in v1:**
- Top bar with animated scrolling ticker (15 symbols — equities, crypto, FX, commodities)
- Live UTC clock
- Home / Overview screen with 4 landing cards
- Market Dashboard with watchlist (25 assets), interactive price chart (6 time ranges), quote detail panel, news feed, sector heatmap
- Order Book with Level 2 bid/ask ladder, depth chart, time & sales tape
- News & Macro module with 4 sub-tabs: News Feed (with article detail panel), Economic Calendar, Earnings tracker, Central Bank tracker (Fed, ECB, BoE, BoJ)
- Global Tracking (All Traffic) — Leaflet map overlaying 80 aircraft and 120 vessels simultaneously with sidebar list and click-through detail
- Aircraft Tracker — dedicated ADS-B module with map, flight table, and statistics tab
- Vessel Tracker — dedicated AIS module with map, vessel table, and statistics tab (120 vessels across 60+ real ocean shipping lanes)
- Aladdin Risk Engine with 7 sub-tabs: Risk Overview (VaR, sector exposure, correlation matrix, liquidity), Factor Decomposition, Stress Testing (8 historical scenarios), Monte Carlo (20,000 paths), Attribution, Compliance (48 rules), Portfolio Optimization
- Portfolio editor modal
- AI Analyst overlay panel
- Alerts panel with toast system
- Light / dark theme toggle
- Status bar

**Architecture established:**
- Single HTML file `<style>` + `<body>` + `<script>`, no build
- Module system: `div.module` elements toggled by `.active` class, routed through `switchModule(id, btn)`
- Lazy initialization: each module only boots on first click, tracked by boolean flags
- CSS design tokens: `--bg` through `--bg5`, `--amber`, `--green`, `--red`, `--blue`, `--purple`, `--text` through `--text4`, `--border` through `--border3`
- Fonts: Orbitron (display), Share Tech Mono (mono UI), via Google Fonts CDN
- API config block: `NEXUS_API` object with keys for Polygon.io, Alpha Vantage, CoinGecko, FRED — all pre-wired with `nexusFetch()` fallback to demo data

---

## v2.0 Four New Modules
**Options Chain, Dark Pool, Macro Heat Map, Correlation Lab**

Added four modules to fill gaps in the original market coverage.

**What changed:**
- `OPTIONS CHAIN` Full call/put ladder for any ticker. Enter a symbol, select expiry, see strike-by-strike bid/ask, IV, delta, volume, OI with depth bars. IV ticks every 3 seconds. Real API: Polygon options contracts endpoint, pre-wired.
- `DARK POOL` Off-exchange block trade flow tape. Shows sweeps and blocks with symbol, type (call/put/block), expiry, strike, premium, and bullish/bearish sentiment. Filterable by sweep, block, bullish, bearish. Live tick every 4 seconds. Sentiment heatmap for top 10 symbols. Top symbols by premium in right panel.
- `MACRO HEAT MAP` 20-country macroeconomic heat map across 5 metrics (GDP growth, CPI inflation, policy rate, unemployment, debt/GDP). Color-coded by health. Click any country for a detail panel with commentary. Region average bar chart.
- `CORRELATION LAB` User-defined asset basket (default: AAPL, MSFT, NVDA, BTC, JPM). N×N correlation matrix with color encoding from -1 to +1. Diversification score. Add/remove tickers dynamically.

**Bug fixes:**
Fixed tab navigation breaking due to `const _origSwitch = switchModule` wrapper pattern conflicting with JS hoisting removed wrapper, integrated all module init calls directly inside `switchModule()` body
Stripped all non-ASCII characters from the codebase (arrows, degree symbols, currency glyphs, etc.) to prevent encoding issues across environments

---

## v3.0 API Documentation
**Full developer documentation for all modules and integrations**

Produced a standalone `Nexus_Documentation.html` covering:
- Quick Start guide
- File architecture (three-part structure, module system, lazy init, live refresh pattern)
- Design system reference (all CSS variables, typography, utility classes)
- All 10 modules documented with usage notes
- All 6 API providers (Polygon.io, Alpha Vantage, CoinGecko, FRED, OpenSky, MarineTraffic) with signup URLs and code examples
- Key utility functions reference (`rnd`, `rndInt`, `pick`, `mkChart`, `nexusFetch`, `pushAlert`)
- Global state variables
- "Adding a new module" step-by-step guide
- Troubleshooting section

---

## v4.0 19-Module Intelligence Expansion
**The largest single update doubled the module count**

Added 19 modules across 5 new navigation groups. Total: 29 modules.

### INTELLIGENCE group
- `EARNINGS CALENDAR` Upcoming and recent earnings with EPS estimate vs actual, revenue estimate vs actual, and surprise %. Filterable by ALL / BEAT / MISS / UPCOMING and by sector.
- `SHORT INTEREST MONITOR` Short interest % of float, days-to-cover, borrow rate, and a computed squeeze score for the most-shorted names. Squeeze alert filter.
- `INSIDER TRANSACTIONS` SEC Form 4–style insider transaction feed (CEO/CFO/Director buys and sells). Net insider buying by ticker chart. Filterable by ALL / BUYS / SELLS / CEO/CFO.
- `SENTIMENT DASHBOARD` Fear & Greed index with gauge, VIX term structure, put/call ratio history (20D), AAII bull/bear survey donut, market breadth indicators, sentiment indicators table.
- `SOCIAL SENTIMENT` Trending tickers ranked by social mention volume with sentiment score, price change, and divergence signal (when price and sentiment disagree). 24-hour mention volume chart and live social feed.
- `SECTOR ROTATION` 11 sector ETF performance across 1D/1W/1M/3M/YTD. Bar chart re-sorts on period toggle. Economic cycle clock (canvas-drawn) showing phase. Rotation signal panel.

### FIXED INCOME group
- `YIELD CURVE` US Treasury yield curve (1M to 30Y) with historical overlays: 1Y ago, 2Y ago, Pre-2008. 2Y-10Y and 3M-10Y spread KPIs, inversion flag. 30-day spread history chart.
- `BOND SCREENER` 15 bonds covering government, IG corporate, high-yield, and municipal. Filterable by type, rating (AAA through CCC), and maturity (short/mid/long). YTM, duration, coupon, price displayed.
- `CREDIT SPREADS` IG and HY OAS spread history (60 weeks) with a side-by-side equity drawdown comparison chart and spread metrics table.

### COMMODITIES group
- `COMMODITIES DASHBOARD` Energy (WTI, Brent, Nat Gas, RBOB, Heating Oil), Metals (Gold, Silver, Copper, Platinum, Palladium), and Agriculture (Corn, Soy, Wheat, Coffee, Sugar) panels each with a 20-day price history chart.
- `ON-CHAIN ANALYTICS` BTC on-chain metrics switchable between MVRV ratio, NVT signal, exchange netflow, and active addresses as 60-day time series. Miner revenue bar chart. Signal interpretation panel.
- `FUTURES CURVE` Forward curve for WTI, Brent, Nat Gas, Gold, Copper, Wheat from Spot through M+24. Contango shown in red, backwardation in green. Roll yield displayed. Contract table.

### PORTFOLIO group
- `BACKTESTER` Portfolio backtester with configurable start/end year and benchmark (SPY/QQQ/60-40). Default: AAPL 30% / MSFT 25% / NVDA 20% / JPM 15% / GLD 10%. Outputs cumulative return chart, drawdown chart, annual returns, Sharpe, Sortino, Calmar, max drawdown, alpha, beta.
- `OPTIONS P&L CALCULATOR` 8 strategy templates (Covered Call, Protective Put, Straddle, Strangle, Bull Call Spread, Bear Put Spread, Iron Condor, Butterfly) priced with Black-Scholes. Interactive payoff diagram with break-evens, max gain/loss, all 5 Greeks, and a plain-language strategy explanation.
- `TAX LOT TRACKER` Cost basis tracking with FIFO, LIFO, HIFO, Specific ID methods. Short-term vs long-term gain/loss breakdown pie chart. Wash sale alert detection. Tax optimization suggestions with estimated liability.

### GLOBAL group
- `GEOPOLITICAL RISK MONITOR` 12 countries scored across overall risk, conflict level, sanctions exposure, and supply chain impact. Grid re-sorts and recolours by mode. Click any country for risk drivers and active alerts.
- `TRADE FLOW MAP` Top 10 global trade corridors by value with commodity-type breakdown (oil, tech, food, metals). Status of 5 maritime chokepoints (Suez, Hormuz, Malacca, Panama, Gibraltar).
- `FX INTERVENTION TRACKER` 8 currencies with FX reserves, reserve changes (30D), REER vs nominal, and intervention status. Three views: FX Reserves, REER vs Nominal, Watchlist. Bar chart + signal panel + US Treasury manipulation watchlist.

**Navigation structure added:**
```
HOME         — Overview, Help, API Health
MARKETS      — Dashboard, Order Book, News & Macro
GLOBAL TRACKING — All Traffic, Aircraft, Vessels
RISK & ANALYTICS — Aladdin Risk, Stress Test, Compliance, Monte Carlo
NEW MODULES  — Options Chain, Dark Pool, Macro Heat Map, Correlation Lab
INTELLIGENCE — Earnings Cal, Short Interest, Insider Flow, Sentiment, Social Sent., Sector Rotat.
FIXED INCOME — Yield Curve, Bond Screener, Credit Spreads
COMMODITIES  — Commodities, On-Chain, Futures Curve
PORTFOLIO    — Backtester, Options P&L, Tax Lot
GLOBAL       — Geo Risk, Trade Flow, FX Intervention
```

---

## v5.0 User Stories, Help System & Export
**Production-readiness features based on formal user stories**

Five user stories implemented.

### Help Panel (Story: Customer support self-service docs)
- `HELP` module added to HOME nav group
- Documents all 35 modules in plain language, each with a "WHAT IT DOES" and "HOW TO USE" section
- Live search box filters by module name or keyword
- OPEN button on each card jumps directly to that module
- No external documentation required

### API Health Check (Story: Provider self-diagnosis)
- `API HEALTH` module added to HOME nav group
- On-demand check of all 6 configured data providers
- Returns one of four states per provider: `OK`, `NOT CONFIGURED`, `RATE LIMITED`, `UNREACHABLE`
- Each result includes HTTP status or error message, timestamp, and which modules depend on that provider
- KPI row summarises overall health (total / configured / reachable / issues)

### Portfolio Export (Story: Export portfolio data)
Added to the Aladdin Risk module toolbar (EXPORT CSV / EXPORT JSON / EXPORT PDF):
- **CSV** All positions with symbol, name, sector, quantity, cost basis, current price, market value, P&L, return %, and weight. Risk summary appended below (NAV, VaR, Sharpe, volatility, beta, compliance breaches, export timestamp).
- **JSON** Structured payload with `meta` (risk summary) and `positions` array.
- **PDF** Print-ready HTML report opened via blob URL in a new tab. Auto-triggers browser print dialog (`window.onload = print()`). Landscape A4 layout with NEXUS logo header, 6-column KPI grid, positions table, sector allocation bar chart, key metrics table, footer. User saves as PDF through browser Print → Save as PDF.

### News & Macro (Story: Consolidated news feed)
Already complete in v1. Confirmed: items appear newest-first with timestamp and source, macro indicators and scheduled events included alongside headlines in the Economic Calendar sub-tab.

### Portfolio Risk Overview (Story: Risk in one place)
Already complete in v1. Confirmed: NAV, 1D P&L, VaR 99% 1D, Sharpe, volatility, and beta as KPI tiles; exposure breakdown by asset class and sector; updates when positions change.

**Bug fixes in v5:**
- Fixed `Unexpected token '}'` syntax error  extra closing brace left in `exportPortfolio()` PDF branch from a previous str_replace operation
- Fixed all buttons not responding  `helpInit`, `apiHealthInit`, and `opnlInit` were declared with `let` after `switchModule()` was defined, causing temporal dead zone errors. Moved all three flags to line 1487, with the existing `mapInitialized`, `dashInitialized`, `obInitialized`, `riskInitialized` flags
- Fixed PDF export  replaced `window.open('', '_blank')` + `document.write()` approach (blocked by popup blockers) with a `Blob` URL opened directly via `window.open(blobUrl, '_blank')` blob URLs are same-origin and not blocked. `window.onload = print()` embedded in the report HTML auto-triggers the print dialog when the tab loads

---

## Changelog

Full version history is in [CHANGELOG.md](./CHANGELOG.md). Summary:

| Version | What changed |
|---|---|
| **v1.0** | Initial build terminal, 10 modules across 4 nav groups, aircraft/vessel tracking, Aladdin risk engine, AI analyst overlay |
| **v2.0** | Options Chain, Dark Pool flow tape, Macro Heat Map (20 countries), Correlation Lab. Fixed tab navigation bug. Removed all non-ASCII characters. |
| **v3.0** | Full API and developer documentation (`Nexus_Documentation.html`) |
| **v4.0** | 19 new modules across 5 new nav groups (Intelligence, Fixed Income, Commodities, Portfolio, Global). Total: 29 modules. |
| **v5.0** | Help panel, API Health Check, portfolio export (CSV / JSON / PDF), Options P&L calculator. Fixed `let` TDZ bug breaking all buttons. Fixed PDF popup-blocker issue. |


## Architecture (current)

```
Nexus_v5.html
├── <style>   600 lines   — CSS custom properties, layout, all component classes
├── <body>    1400 lines  — 29 module panels + Help + API Health + Options P&L = 32 panels total
└── <script>  2700 lines  — flags, utilities, all module init/render functions, export, boot
```

**Dependencies (CDN only):**
- Chart.js 4.4.1
- Leaflet 1.9.4
- Google Fonts (Orbitron, Share Tech Mono)

**Backend:** Planned Python service to proxy Polygon.io, Alpha Vantage, FRED, and CoinGecko — normalising responses into the shapes each module already expects and managing rate limits server-side.


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

Here's every topic explained in **one simple line**:

| **Topic**                     | **Simple Definition**                                                         |
| ----------------------------- | ----------------------------------------------------------------------------- |
| **Overview Dashboard**        | A home screen showing the most important market and portfolio information.    |
| **Markets Dashboard**         | Displays live prices of stocks, bonds, forex, crypto, and commodities.        |
| **Order Book**                | Shows all current buy and sell orders for an asset.                           |
| **News & Macro**              | Provides financial news and major economic updates affecting markets.         |
| **All Traffic (Map)**         | Displays global movement of ships, planes, and other transportation on a map. |
| **Aircraft**                  | Tracks airplanes and flights in real time.                                    |
| **Vessels**                   | Tracks ships and cargo vessels around the world.                              |
| **Aladdin Risk**              | Analyzes and measures the overall risk of an investment portfolio.            |
| **Stress Test**               | Simulates how a portfolio performs during extreme market events.              |
| **Compliance**                | Checks whether investments follow legal and internal rules.                   |
| **Monte Carlo Simulation**    | Uses thousands of random scenarios to predict possible future outcomes.       |
| **Options Chain**             | Lists all available call and put option contracts for a stock.                |
| **Dark Pool**                 | Shows large private trades executed outside public stock exchanges.           |
| **Macro Heat Map**            | Uses colors to show economic performance across countries or sectors.         |
| **Correlation Lab**           | Measures how closely two assets move together.                                |
| **Earnings Calendar**         | Shows upcoming dates when companies report financial results.                 |
| **Short Interest Monitor**    | Tracks how many investors are betting a stock's price will fall.              |
| **Insider Transactions**      | Displays stock buying and selling by company executives and insiders.         |
| **Sentiment Dashboard**       | Measures whether news about an asset is mostly positive or negative.          |
| **Social Sentiment**          | Analyzes public opinion from social media and online forums.                  |
| **Sector Rotation**           | Shows how investment money is moving between different industries.            |
| **Yield Curve**               | Displays interest rates for bonds with different maturities.                  |
| **Bond Screener**             | Helps search and filter bonds based on selected criteria.                     |
| **Credit Spreads**            | Measures the extra return investors demand for taking credit risk.            |
| **Commodities Dashboard**     | Shows live prices of commodities like oil, gold, and wheat.                   |
| **On-Chain Analytics**        | Analyzes blockchain data to understand cryptocurrency activity.               |
| **Futures Curve**             | Shows futures prices for different delivery dates.                            |
| **Backtester**                | Tests how an investment strategy would have performed in the past.            |
| **Options P&L Calculator**    | Calculates the profit or loss of an options trade.                            |
| **Tax Lot Tracker**           | Tracks individual investment purchases for tax reporting.                     |
| **Geopolitical Risk Monitor** | Monitors global political events that could impact financial markets.         |
| **Trade Flow Map**            | Visualizes the movement of goods and trade between countries.                 |
| **FX Intervention Tracker**   | Tracks when central banks buy or sell currencies to influence exchange rates. |

## Tech stack


## Backend (planned)

A Python backend will sit behind this frontend to:

- Proxy real market data providers (Polygon, Alpha Vantage, FRED, CoinGecko) so API keys aren't exposed client-side
- Cache responses and manage rate limits
- Normalize provider responses into the shapes each module already expects

Every data-driven module is structured so swapping its synthetic generator for a real API call is a small, contained change — the rendering and state logic doesn't need to know where the data came from.

