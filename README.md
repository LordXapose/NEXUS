# # Nexus

Nexus is a 29-module market terminal covering equities, options, fixed income, commodities, crypto, portfolio analytics, sentiment, and geopolitical risk. Everything markup, styles, and logic lives in one .html file.
This makes it trivially portable: download the file, double-click it, and the terminal boots. It also makes it a useful teaching artifact for demonstrating that a serious-looking financial dashboard doesn't require a server stack to be functional most of what people associate with a "terminal" is UI density and data modeling, not backend complexity.

## Status

Frontend: complete, runs standalone with synthetic/demo data, no build step required.
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

