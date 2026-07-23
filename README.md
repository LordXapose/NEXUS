# NEXUS TERMINAL
 A financial terminal that runs from a single HTML file, backed by a Python risk engine that pulls real market data from free public sources.

30 modules. Zero build step. Zero paid API keys. Zero npm.

---

## Why this exists

A Bloomberg Terminal seat runs somewhere around **$30,000 a year**. BlackRock's Aladdin isn't even sold to individuals it's an institutional platform with a minimum contract that assumes you're managing billions. Between them, they define what "professional-grade market software" looks like: dense monochrome-on-black panels, keyboard-driven navigation, a hundred data views one tab away from each other, and a risk engine humming underneath all of it.

The result is that almost nobody outside a bank or a fund has ever actually *used* one. You can read about Value-at-Risk in a textbook. You can compute a covariance matrix in a Jupyter notebook. But you never get to sit in front of the thing where a VaR breach, a compliance flag, a stress scenario, and the position that caused all three are on the same screen at the same time which is the entire point of a terminal, and the part no textbook conveys.

**Nexus is my attempt to build that thing from scratch, and to learn quantitative finance by implementing it rather than reading about it.**

The bet behind the project is simple: every input those platforms use has a free public equivalent. Treasury yields and macro series are on FRED. Equity prices, 5-year OHLCV history, and full options chains come from Yahoo Finance. Sovereign macro data for 20 countries is a World Bank API call. Crypto is CoinGecko. News is RSS. None of it needs a key, and none of it needs a credit card. What you're actually paying $30k for is the **aggregation, the analytics layer, and the interface** and all three of those are just code.

So the project became three questions, and each one turned into a piece of the architecture:

**1. Can the analytics actually be real?**
Not mock numbers. Historical VaR and CVaR at 99% and 95% from a real 252-day return series. A real covariance matrix. Marginal contribution to risk per position, computed properly as `w ⊙ (Σw) / σ_p` rather than just reporting position weights and calling it risk. A 20,000-path Monte Carlo drawn from the portfolio's actual multivariate return distribution. Eight historical stress scenarios (2008, COVID, dot-com, the 2022 rate shock) mapped onto real position buckets. That's `py/py.py`, and it's the part I care most about.

**2. Can the whole front end be one file?**
No React, no Vite, no `node_modules`, no build step. `Nexus_v5_1.html` is 4,700 lines of vanilla JS, CSS, and HTML with two CDN dependencies (Chart.js and Leaflet). You can email it, drop it on a USB stick, or open it with a double-click on a machine that has never had a package manager installed. This is a constraint I keep choosing on purpose it forces every abstraction to earn its place, and the thing still boots instantly three years from now when the framework you would have picked is deprecated.

**3. Can it feel like the real thing?**
Amber-on-black. Share Tech Mono and Orbitron. A scrolling ticker tape pinned to the top bar. A nav rail grouped the way a terminal groups things — MARKETS, RISK & ANALYTICS, FIXED INCOME, COMMODITIES, INTELLIGENCE rather than the way a web app would. Dense information, tabular numerals, no whitespace-heavy dashboard aesthetics. If it doesn't feel oppressive and slightly overwhelming, it isn't a terminal.

The global aircraft and vessel tracking modules are the one piece that isn't strictly financial, and they're deliberate: physical trade flow *is* market data. Tankers leaving the Gulf and container traffic through Suez are a real input for commodity and shipping desks, and a terminal that shows you credit spreads but not the ships is telling you half the story.

---

## What you get

| | |
|---|---|
| **30 modules** | Markets, risk, fixed income, commodities, portfolio analytics, intelligence, global tracking |
| **Real market data** | Prices, 5y history, options chains, yield curve, macro, crypto, news — all from free sources |
| **Real risk engine** | VaR, CVaR, correlation, risk contribution, Monte Carlo, stress tests, compliance rules |
| **Single-file front end** | 4,700 lines of vanilla JS/HTML/CSS, two CDN libs, no build |
| **FastAPI backend** | 12 endpoints serving CSV → JSON, with CSV upload support |
| **Graceful degradation** | Backend offline? The terminal falls back to demo data and keeps working |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  py/py.py  — DATA & RISK ENGINE                              │
│                                                              │
│  yfinance ──────► prices · 5y OHLCV · options chains         │
│  FRED CSV ──────► yield curve (9 tenors) · 13 macro series   │
│  World Bank ────► 20-country macro heat map                  │
│  CoinGecko ─────► crypto prices & market caps                │
│  RSS × 5 ───────► news feed                                  │
│  numpy/pandas ──► VaR · CVaR · correlation · MC · stress     │
│                                                              │
└────────────────────────────┬─────────────────────────────────┘
                             │ writes 16 CSV + 2 JSON
                             ▼
                     ┌───────────────┐
                     │  py/data/     │
                     └───────┬───────┘
                             │ read on every request
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  py/main.py — FastAPI  ·  127.0.0.1:8000                     │
│  GET /api/prices · /portfolio · /news · /risk · /summary     │
│  POST /api/upload/{prices|portfolio|news}                    │
└────────────────────────────┬─────────────────────────────────┘
                             │ fetch() on load
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  Nexus_v5_1.html — SINGLE-FILE TERMINAL                      │
│  30 modules · Chart.js · Leaflet · vanilla JS                │
│  Falls back to demo data if the API is unreachable           │
└──────────────────────────────────────────────────────────────┘
```

The decoupling is intentional. The downloader can run on a cron at 6am and the API never blocks on a network call, because it only ever reads local CSVs. The front end can run entirely standalone open the HTML with no backend at all and every module still renders with demo data, which is what makes it shareable as a single file.

---

## Quick start

### 1. Install

```bash
cd py
pip install fastapi "uvicorn[standard]" python-multipart pandas
pip install yfinance feedparser requests numpy scipy   # needed by py.py
```

> **Note:** `requirements.txt` currently only covers the API server. The downloader's dependencies (`yfinance`, `feedparser`, `requests`, `numpy`, `scipy`) need the second line above. See [Known issues](#known-issues).

### 2. Pull the data

```bash
python py.py                      # full refresh — takes a few minutes
python py.py --quick              # prices + crypto + portfolio + news only
python py.py --section risk       # run one section
python py.py --broker export.csv  # load positions from a broker export
```

Sections run in dependency order: `prices → history → crypto → options → portfolio → risk → stress → macro → world → news → compliance`. Each is wrapped in its own try/except, so one dead feed doesn't kill the run.

### 3. Start the API

```bash
uvicorn main:app --reload --port 8000
```

Interactive docs at `http://127.0.0.1:8000/docs`.

### 4. Open the terminal

Double-click `Nexus_v5_1.html`. It probes `127.0.0.1:8000` on load. Console tells you which mode you're in:

```
[NEXUS] Dashboard updated from local API.        ← live
[NEXUS] Local API unavailable; showing demo data. ← standalone
```

---

## Module map

**HOME** Overview: NAV, market snapshot, tracking summary, news digest

**MARKETS**
- `Dashboard`  watchlist, technicals (RSI, MA20, 52w range), portfolio P&L, news rail
- `Order Book`  L2 depth ladder and time-and-sales prints
- `News & Macro` categorised feed (macro / earnings / tech / crypto / forex)

**RISK & ANALYTICS**
- `Aladdin Risk` VaR/CVaR, factor exposures, efficient frontier, risk budget, rebalance suggestions
- `Stress Test`  8 historical scenarios mapped to position buckets
- `Compliance`  8 configurable limit rules with live breach flags
- `Monte Carlo`  20,000 paths × 252 days, percentile fan chart

**NEW MODULES**  Options Chain · Dark Pool · Macro Heat Map · Correlation Lab

**INTELLIGENCE** Earnings Calendar · Short Interest · Insider Flow · Sentiment · Social Sentiment · Sector Rotation

**FIXED INCOME** Yield Curve · Bond Screener · Credit Spreads

**COMMODITIES** Commodities · On-Chain · Futures Curve

**PORTFOLIO** Backtester · Options P&L · Tax Lot

**GLOBAL** Geo Risk · Trade Flow · FX Intervention

**GLOBAL TRACKING** All Traffic · Aircraft (80) · Vessels (120), on Leaflet + OpenStreetMap with realistic shipping-lane routing

---

## The risk engine

This is the part worth reading the source for. `py/py.py::compute_risk()` does the following on the real return series:

**Returns & covariance** pivots `history.csv` to a date × symbol matrix, takes `pct_change()`, trims to the last 252 trading days, restricted to symbols actually held.

**Historical VaR & CVaR**
```python
port_returns = returns.dot(w)
var_99  = np.percentile(port_returns, 1)
cvar_99 = port_returns[port_returns <= var_99].mean()
```
Non-parametric no normality assumption. CVaR is the true conditional mean of the tail, not a scaled VaR.

**Risk contribution** the piece most dashboards get wrong. Position weight is not risk:
```python
cov      = returns.cov() * 252
port_vol = np.sqrt(w @ cov.values @ w)
marginal = cov.values @ w
contrib  = w * marginal / port_vol      # sums to port_vol
```
Marginal contribution to risk, correctly decomposed. A 3% crypto sleeve can carry 15% of portfolio volatility, and this is what shows you that.

**Monte Carlo** 20,000 paths over a 252-day horizon, sampled from the portfolio's actual multivariate normal `(μ, Σ)`, seeded at 42 for reproducibility. Exports percentiles plus 100 sample paths to `mc_paths.json` for the fan chart.

**Stress testing** eight published drawdown benchmarks (2008 GFC, COVID 2020, dot-com, 2022 rate shock, 9/11, Black Monday, Eurozone crisis, taper tantrum) applied as equity/bond/credit/FX/commodity shocks to bucketed positions.

**Compliance** 8 rules covering single-position concentration, sector caps, minimum fixed income, VaR limit, max drawdown, and a no-shorts block. Edit `data/compliance_rules.csv` to change the mandate.

Also computed: annualised volatility, a Sharpe proxy, and the full correlation matrix.

---

## API reference

| Method | Endpoint | Returns |
|---|---|---|
| `GET` | `/` | Health check + which data files exist |
| `GET` | `/api/prices` | All watchlist rows |
| `GET` | `/api/prices/{symbol}` | Single ticker |
| `GET` | `/api/portfolio` | Positions with computed P&L, NAV, weights |
| `GET` | `/api/news?limit=50&category=all` | News, newest first |
| `GET` | `/api/risk` | All six risk/compliance datasets |
| `GET` | `/api/summary` | Home-screen rollup |
| `GET` | `/api/schema` | Expected CSV columns + example rows |
| `POST` | `/api/upload/prices` | Replace prices CSV |
| `POST` | `/api/upload/portfolio` | Replace portfolio CSV |
| `POST` | `/api/upload/news` | Replace news CSV |

`/api/portfolio` enriches raw positions against `prices.csv` server-side, returning `current_price`, `cost_basis`, `market_value`, `unrealised_pnl`, `return_pct`, and `weight_pct`, plus a summary block with NAV and total return.

### Bring your own data

Every module reads CSV, so you don't have to use the downloader at all — export from your broker and upload:

```bash
curl -F "file=@my_positions.csv" http://127.0.0.1:8000/api/upload/portfolio
```

Minimum columns: `symbol, shares, avg_cost`. Hit `/api/schema` for the full spec.

---

## Data files

| File | Contents |
|---|---|
| `prices.csv` | 16 cols: OHLC, volume, market cap, P/E, 52w range, RSI, sector, signal |
| `history.csv` | 5 years of daily closes, long format |
| `portfolio.csv` | Positions with computed P&L and weights |
| `returns.csv` | 252 days of daily returns per holding |
| `correlation.csv` | Holdings correlation matrix |
| `var_results.csv` | VaR 99/95, CVaR 99, annualised vol, Sharpe |
| `risk_contribution.csv` | Per-position weight, return, vol, risk contribution |
| `monte_carlo.csv` | 9 percentiles + mean of terminal values |
| `mc_paths.json` | 100 sample paths × 252 days for charting |
| `scenarios.csv` | 8 stress scenarios with portfolio impact |
| `compliance_rules.csv` | 8 editable limit rules |
| `options.csv` | Full chains: strike, bid/ask, IV, OI, moneyness |
| `yields.csv` | 9 Treasury tenors with change in bps |
| `macro_us.csv` | 13 FRED series incl. IG/HY OAS spreads |
| `macro_global.csv` | 20 countries: GDP, CPI, unemployment, debt/GDP, policy rate |
| `crypto.csv` | Top crypto with ATH distance and 24h stats |
| `news.csv` | Headlines with source, category, tickers, links |

---

## What's real and what isn't

I'd rather be explicit about this than have you find out by trusting a number.

**Real, pulled from live sources**
Equity/ETF/FX/futures prices · 5y OHLCV history · options chains · Treasury yield curve · US macro & credit spreads · 20-country World Bank macro · crypto prices · news headlines · **every risk metric in the engine VaR, CVaR, correlation, risk contribution, Monte Carlo, stress tests**

**Simulated in-browser (structurally realistic, not real)**
Order book depth and trade prints · dark pool flow · insider transactions · short interest · sentiment and social sentiment · aircraft and vessel positions · options chain when the API is offline · several intelligence modules

The simulated modules exist because the real feeds behind them are genuinely expensive L2 depth, dark pool prints, and ADS-B/AIS are all paid products. They're built to the shape of the real data so they can be swapped for a live source without touching the UI. **Nothing simulated feeds the risk engine.**

---

## Known issues

Being upfront about the rough edges, because this is an active project rather than a finished product:

- **`requirements.txt` is incomplete**  covers the API server only. See the install step for the downloader's deps.
- **`/api/risk` isn't wired to the UI yet**  the endpoint serves all six risk datasets correctly, but the front end currently only consumes `/prices`, `/portfolio`, and `/news`. The risk modules still render from demo data. Top of the roadmap.
- **The AI Analyst panel calls `api.anthropic.com` with no key** and will fail from `file://`. It's a stub for a proper backend proxy. **Never put an API key in client-side code** the fix is a `/api/ai` endpoint that holds the key server-side.
- **CORS is `allow_origins=["*"]` with `allow_credentials=True`** correct for a localhost tool loaded from `file://`, unacceptable if this is ever deployed.
- **Upload endpoints have no auth and validate only the file extension**, then overwrite live data files. Localhost-only by design; lock down before exposing.
- **Docstrings reference `downloader.py` and `Nexus_v5.html`** the actual filenames are `py.py` and `Nexus_v5_1.html`.
- **RSS feeds break** Reuters in particular has changed its feed structure. Failures are caught and logged rather than fatal.

---

## Roadmap

- [ ] Wire `/api/risk` into the risk, stress, compliance, and Monte Carlo modules
- [ ] Move the AI analyst behind a server-side proxy endpoint
- [ ] Parametric and Cornish-Fisher VaR alongside historical
- [ ] Real Black-Scholes Greeks on the options chain (currently approximated client-side)
- [ ] Backtester wired to `history.csv` instead of synthetic series
- [ ] Live yield curve rendering from `yields.csv`
- [ ] Factor model (Fama-French) for the exposures panel
- [ ] Optional ADS-B / AIS feeds for real tracking

---

## Repo structure

```
nexus/
├── Nexus_v5_1.html          # the entire terminal — 4,733 lines
├── image.png                # screenshot
└── py/
    ├── py.py                # data downloader + risk engine (~1,000 lines)
    ├── main.py              # FastAPI server
    ├── requirements.txt
    └── data/                # 16 CSV + 2 JSON, regenerated by py.py
```

---

## Stack

**Front end**  vanilla JS/HTML/CSS · Chart.js 4.4.1 · Leaflet 1.9.4 · Share Tech Mono + Orbitron
**Back end**  Python · FastAPI · Uvicorn · pandas · numpy · scipy · yfinance · feedparser
**Data** Yahoo Finance · FRED · World Bank · CoinGecko · RSS

---
