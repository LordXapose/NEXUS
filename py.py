"""
Nexus Data Downloader
=====================
Run this script once a day (or on demand) to refresh all CSV data
that powers the Nexus terminal. No paid APIs needed.

Sources used:
  - yfinance        -> prices, OHLCV history, options chain
  - pandas_datareader (FRED) -> yield curve, US macro, credit spreads
  - requests (World Bank API) -> 20-country macro heat map
  - requests (CoinGecko) -> crypto prices (no key needed)
  - feedparser      -> RSS news feeds (Yahoo, Reuters, CNBC, MarketWatch)
  - numpy / scipy   -> VaR, correlation, Monte Carlo, stress tests

Usage:
  pip install yfinance pandas pandas-datareader feedparser requests numpy scipy
  python downloader.py

  Optional flags:
    python downloader.py --quick     # skip heavy history/risk calcs
    python downloader.py --section prices   # run only one section
"""

import os
import sys
import argparse
import warnings
import csv
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")

# ── Config ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Tickers to track — edit this list to match your watchlist
WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA",
    "JPM", "BAC", "GS", "LLY", "AMD", "NFLX", "PLTR", "COIN",
    "SPY", "QQQ", "IWM", "GLD", "TLT",               # ETFs
    "BTC-USD", "ETH-USD",                              # Crypto via yfinance
    "EURUSD=X", "GBPUSD=X", "USDJPY=X",               # Forex via yfinance
    "GC=F", "CL=F",                                    # Gold & WTI futures
]

# Your portfolio — symbol must be in WATCHLIST above for live P&L enrichment
# If you export from your broker, that file will overwrite this
DEFAULT_PORTFOLIO = [
    {"symbol": "AAPL",    "name": "Apple Inc.",         "shares": 50,  "avg_cost": 155.20, "sector": "Technology"},
    {"symbol": "MSFT",    "name": "Microsoft Corp.",    "shares": 20,  "avg_cost": 310.00, "sector": "Technology"},
    {"symbol": "NVDA",    "name": "NVIDIA Corp.",       "shares": 15,  "avg_cost": 350.00, "sector": "Technology"},
    {"symbol": "BTC-USD", "name": "Bitcoin",            "shares": 0.5, "avg_cost": 42000,  "sector": "Crypto"},
    {"symbol": "ETH-USD", "name": "Ethereum",           "shares": 3,   "avg_cost": 2800,   "sector": "Crypto"},
    {"symbol": "JPM",     "name": "JPMorgan Chase",     "shares": 25,  "avg_cost": 178.00, "sector": "Finance"},
    {"symbol": "GLD",     "name": "SPDR Gold ETF",      "shares": 10,  "avg_cost": 185.00, "sector": "Commodities"},
    {"symbol": "LLY",     "name": "Eli Lilly",          "shares": 4,   "avg_cost": 620.00, "sector": "Healthcare"},
]

# FRED series IDs for yield curve (US Treasuries)
YIELD_SERIES = {
    "1M":  "DGS1MO",
    "3M":  "DGS3MO",
    "6M":  "DGS6MO",
    "1Y":  "DGS1",
    "2Y":  "DGS2",
    "5Y":  "DGS5",
    "10Y": "DGS10",
    "20Y": "DGS20",
    "30Y": "DGS30",
}

# FRED series for US macro indicators
MACRO_SERIES = {
    "CPI YoY":        "CPIAUCSL",
    "Core CPI":       "CPILFESL",
    "PCE":            "PCEPI",
    "Unemployment":   "UNRATE",
    "NFP":            "PAYEMS",
    "GDP Growth":     "A191RL1Q225SBEA",
    "ISM Mfg PMI":    "MANEMP",
    "Consumer Conf":  "UMCSENT",
    "Fed Funds Rate": "FEDFUNDS",
    "M2 Money Supply":"M2SL",
    "10Y-2Y Spread":  "T10Y2Y",
    "IG OAS Spread":  "BAMLC0A0CM",
    "HY OAS Spread":  "BAMLH0A0HYM2",
}

# 20 countries for macro heat map
WORLD_BANK_COUNTRIES = {
    "US": "United States", "EU": "Euro Zone",  "CN": "China",
    "JP": "Japan",         "GB": "UK",         "DE": "Germany",
    "IN": "India",         "BR": "Brazil",     "CA": "Canada",
    "AU": "Australia",     "KR": "South Korea","MX": "Mexico",
    "SA": "Saudi Arabia",  "CH": "Switzerland","SE": "Sweden",
    "NO": "Norway",        "SG": "Singapore",  "ID": "Indonesia",
    "TR": "Turkey",        "AR": "Argentina",
}

# Historical stress scenarios (published drawdown benchmarks)
STRESS_SCENARIOS = [
    {"scenario": "2008 GFC",          "equity": -50.0, "bond": 5.2,  "credit": -28.0, "fx": -8.0,  "commodity": -54.0},
    {"scenario": "COVID Crash 2020",  "equity": -34.0, "bond": 8.0,  "credit": -21.0, "fx": -3.0,  "commodity": -65.0},
    {"scenario": "Dot-com 2000-02",   "equity": -49.0, "bond": 12.0, "credit": -15.0, "fx": -14.0, "commodity": -25.0},
    {"scenario": "2022 Rate Shock",   "equity": -25.0, "bond": -18.0,"credit": -16.0, "fx": 14.0,  "commodity": 26.0},
    {"scenario": "9/11 2001",         "equity": -12.0, "bond": 4.0,  "credit": -8.0,  "fx": -2.0,  "commodity": -8.0},
    {"scenario": "Black Monday 1987", "equity": -22.0, "bond": 2.0,  "credit": -5.0,  "fx": -5.0,  "commodity": -10.0},
    {"scenario": "Eurozone Crisis 2011","equity":-22.0, "bond": 6.0, "credit": -14.0, "fx": -9.0,  "commodity": -14.0},
    {"scenario": "Taper Tantrum 2013","equity": -6.0,  "bond": -5.0, "credit": -4.0,  "fx": -4.0,  "commodity": -8.0},
]

# RSS news feeds
NEWS_FEEDS = [
    {"url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=AAPL,MSFT,NVDA&region=US&lang=en-US", "source": "Yahoo Finance"},
    {"url": "https://www.investing.com/rss/news.rss",                                                   "source": "Investing.com"},
    {"url": "https://feeds.marketwatch.com/marketwatch/topstories/",                                    "source": "MarketWatch"},
    {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",     "source": "CNBC"},
    {"url": "https://feeds.reuters.com/reuters/businessNews",                                           "source": "Reuters"},
]

HISTORY_PERIOD = "5y"       # how much price history to fetch
MONTE_CARLO_SIMS = 20000    # number of MC simulation paths
HISTORY_DAYS = 252          # trading days for VaR / correlation


# ── Helpers ───────────────────────────────────────────────────────────────────
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def save(df: pd.DataFrame, name: str):
    path = DATA_DIR / name
    df.to_csv(path, index=False, encoding="utf-8")
    log(f"  saved {name} — {len(df)} rows")

def safe_float(value, default=0.0) -> float:
    """Return a finite float, treating missing provider values as the default."""
    try:
        value = float(value)
        return value if np.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0) -> int:
    """Return an integer without failing on NaN values from market-data feeds."""
    return int(safe_float(value, default))


def fred_csv(series_id: str) -> pd.DataFrame:
    """Fetch a FRED series as a DataFrame via the public CSV endpoint (no key needed)."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        # FRED currently returns "observation_date"; older responses used "DATE".
        # Read first, then normalize the two columns instead of requiring one name.
        df = pd.read_csv(url)
        if df.shape[1] < 2:
            raise ValueError("FRED response did not include date and value columns")
        df = df.iloc[:, :2].copy()
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df[df["value"] != "."].copy()
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna()
    except Exception as e:
        log(f"    FRED {series_id} failed: {e}")
        return pd.DataFrame(columns=["date", "value"])


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — PRICES (current snapshot)
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_prices():
    log("PRICES — downloading current quotes...")
    import yfinance as yf

    tickers = yf.Tickers(" ".join(WATCHLIST))
    rows = []

    for sym in WATCHLIST:
        try:
            info = tickers.tickers[sym].fast_info
            hist = tickers.tickers[sym].history(period="2d")

            if hist.empty:
                continue

            price = float(hist["Close"].iloc[-1])
            prev  = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price
            chg   = round((price - prev) / prev * 100, 2) if prev else 0

            # Clean up symbol display (remove =X, =F, -USD suffixes)
            display_sym = sym.replace("-USD","").replace("=X","").replace("=F","")

            # Sector mapping
            sector_map = {
                "AAPL":"Technology","MSFT":"Technology","NVDA":"Technology",
                "GOOGL":"Technology","META":"Technology","AMD":"Technology",
                "NFLX":"Technology","PLTR":"Technology",
                "AMZN":"Consumer","TSLA":"Auto",
                "JPM":"Finance","BAC":"Finance","GS":"Finance","COIN":"Crypto",
                "LLY":"Healthcare",
                "SPY":"Index","QQQ":"Index","IWM":"Index",
                "GLD":"Commodities","TLT":"Fixed Income",
                "BTC-USD":"Crypto","ETH-USD":"Crypto",
                "EURUSD=X":"Forex","GBPUSD=X":"Forex","USDJPY=X":"Forex",
                "GC=F":"Commodities","CL=F":"Energy",
            }
            type_map = {
                "SPY":"etf","QQQ":"etf","IWM":"etf","GLD":"etf","TLT":"etf",
                "BTC-USD":"crypto","ETH-USD":"crypto",
                "EURUSD=X":"forex","GBPUSD=X":"forex","USDJPY=X":"forex",
                "GC=F":"commodity","CL=F":"commodity",
            }

            row = {
                "symbol":      display_sym,
                "name":        getattr(info, "display_name", display_sym),
                "price":       round(price, 4),
                "change_pct":  chg,
                "open":        round(float(hist["Open"].iloc[-1]), 4),
                "high":        round(float(hist["High"].iloc[-1]), 4),
                "low":         round(float(hist["Low"].iloc[-1]), 4),
                "volume":      int(hist["Volume"].iloc[-1]),
                "market_cap":  getattr(info, "market_cap", ""),
                "pe_ratio":    "",
                "week52_high": round(float(getattr(info, "fifty_two_week_high", 0)), 2),
                "week52_low":  round(float(getattr(info, "fifty_two_week_low", 0)), 2),
                "rsi":         "",                        # computed in history section
                "sector":      sector_map.get(sym, "Equity"),
                "type":        type_map.get(sym, "equity"),
                "signal":      "",                        # computed from RSI/MA
            }
            rows.append(row)
            time.sleep(0.1)  # be polite to Yahoo

        except Exception as e:
            log(f"    {sym} failed: {e}")

    df = pd.DataFrame(rows)
    save(df, "prices.csv")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — PRICE HISTORY (OHLCV for charts + risk calculations)
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_history():
    log("HISTORY — downloading 5-year OHLCV data...")
    import yfinance as yf

    # Download all tickers in one batch call (much faster)
    raw = yf.download(
        WATCHLIST,
        period=HISTORY_PERIOD,
        interval="1d",
        auto_adjust=True,
        progress=False,
    )

    if raw.empty:
        log("  ERROR: no history data returned")
        return pd.DataFrame()

    # Flatten multi-level columns → long format
    rows = []
    closes = raw["Close"] if "Close" in raw else raw

    for sym in closes.columns:
        series = closes[sym].dropna()
        for date, price in series.items():
            rows.append({
                "symbol": sym.replace("-USD","").replace("=X","").replace("=F",""),
                "date":   date.strftime("%Y-%m-%d"),
                "close":  round(float(price), 4),
            })

    df = pd.DataFrame(rows)
    save(df, "history.csv")

    # Also compute and append RSI + MA20 + signal back to prices.csv
    _compute_technicals(closes)

    return df


def _compute_technicals(closes: pd.DataFrame):
    """Compute RSI(14), MA20, signal per ticker and patch prices.csv."""
    prices_path = DATA_DIR / "prices.csv"
    if not prices_path.exists():
        return

    pf = pd.read_csv(prices_path)
    pf.columns = pf.columns.str.lower()
    # Empty cells are inferred as float64 by pandas. Signals are text values.
    pf["signal"] = pf["signal"].astype("object")

    for sym in closes.columns:
        display = sym.replace("-USD","").replace("=X","").replace("=F","")
        series = closes[sym].dropna()
        if len(series) < 20:
            continue

        # RSI(14)
        delta = series.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi   = 100 - (100 / (1 + rs))
        rsi_val = round(float(rsi.iloc[-1]), 1) if not rsi.empty else ""

        # MA20
        ma20 = series.rolling(20).mean()
        ma20_val = round(float(ma20.iloc[-1]), 4) if not ma20.empty else ""

        # Signal
        price = float(series.iloc[-1])
        signal = "hold"
        if isinstance(rsi_val, float) and isinstance(ma20_val, float):
            if rsi_val < 40 and price > ma20_val:
                signal = "buy"
            elif rsi_val > 70 or price < ma20_val * 0.97:
                signal = "sell"

        mask = pf["symbol"].str.upper() == display.upper()
        pf.loc[mask, "rsi"]    = rsi_val
        pf.loc[mask, "signal"] = signal

    pf.to_csv(prices_path, index=False)
    log(f"  RSI/signal patched into prices.csv")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — OPTIONS CHAIN
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_options(symbols=None):
    log("OPTIONS — downloading options chain data...")
    import yfinance as yf

    if symbols is None:
        symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "SPY", "QQQ"]

    rows = []
    for sym in symbols:
        try:
            tk = yf.Ticker(sym)
            expiries = tk.options[:6]  # next 6 expiry dates

            for exp in expiries:
                chain = tk.option_chain(exp)

                for _, row in chain.calls.iterrows():
                    rows.append({
                        "symbol":            sym,
                        "expiry":            exp,
                        "type":              "call",
                        "strike":            round(safe_float(row.get("strike")), 2),
                        "bid":               round(safe_float(row.get("bid")), 2),
                        "ask":               round(safe_float(row.get("ask")), 2),
                        "last":              round(safe_float(row.get("lastPrice")), 2),
                        "volume":            safe_int(row.get("volume")),
                        "open_interest":     safe_int(row.get("openInterest")),
                        "implied_volatility":round(safe_float(row.get("impliedVolatility")) * 100, 1),
                        "in_the_money":      bool(row.get("inTheMoney", False)),
                    })

                for _, row in chain.puts.iterrows():
                    rows.append({
                        "symbol":            sym,
                        "expiry":            exp,
                        "type":              "put",
                        "strike":            round(safe_float(row.get("strike")), 2),
                        "bid":               round(safe_float(row.get("bid")), 2),
                        "ask":               round(safe_float(row.get("ask")), 2),
                        "last":              round(safe_float(row.get("lastPrice")), 2),
                        "volume":            safe_int(row.get("volume")),
                        "open_interest":     safe_int(row.get("openInterest")),
                        "implied_volatility":round(safe_float(row.get("impliedVolatility")) * 100, 1),
                        "in_the_money":      bool(row.get("inTheMoney", False)),
                    })

            log(f"    {sym}: {len([r for r in rows if r['symbol']==sym])} contracts across {len(expiries)} expiries")
            time.sleep(0.3)

        except Exception as e:
            log(f"    {sym} options failed: {e}")

    df = pd.DataFrame(rows)
    save(df, "options.csv")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — PORTFOLIO (positions + live P&L)
# ═══════════════════════════════════════════════════════════════════════════════
def build_portfolio(broker_csv_path=None):
    log("PORTFOLIO — building positions with live P&L...")

    # Load from broker export if provided, else use default
    if broker_csv_path and Path(broker_csv_path).exists():
        pf = pd.read_csv(broker_csv_path)
        pf.columns = pf.columns.str.strip().str.lower()
        log(f"  loaded broker CSV: {broker_csv_path}")
    else:
        pf = pd.DataFrame(DEFAULT_PORTFOLIO)
        log("  using default portfolio (edit DEFAULT_PORTFOLIO in config or pass --broker path.csv)")

    # Load current prices for enrichment
    prices_path = DATA_DIR / "prices.csv"
    price_map = {}
    if prices_path.exists():
        px = pd.read_csv(prices_path)
        px.columns = px.columns.str.lower()
        # Map both original and display symbol formats
        for _, row in px.iterrows():
            price_map[str(row["symbol"]).upper()] = float(row["price"])

    rows = []
    total_nav = 0

    for _, pos in pf.iterrows():
        sym     = str(pos.get("symbol", "")).upper().replace("-USD","")
        shares  = float(pos.get("shares", pos.get("quantity", 0)) or 0)
        cost    = float(pos.get("avg_cost", pos.get("average_cost", pos.get("avg_price", 0))) or 0)
        name    = pos.get("name", sym)
        sector  = pos.get("sector", "")

        # Try both sym and sym+"-USD" for crypto
        price = price_map.get(sym) or price_map.get(sym + "USD") or cost

        mv  = shares * price
        pnl = mv - shares * cost
        ret = (pnl / (shares * cost) * 100) if cost else 0

        total_nav += mv
        rows.append({
            "symbol":         sym,
            "name":           name,
            "shares":         shares,
            "avg_cost":       round(cost, 4),
            "sector":         sector,
            "current_price":  round(price, 4),
            "cost_basis":     round(shares * cost, 2),
            "market_value":   round(mv, 2),
            "unrealised_pnl": round(pnl, 2),
            "return_pct":     round(ret, 2),
            "weight_pct":     0,  # filled below
        })

    for r in rows:
        r["weight_pct"] = round(r["market_value"] / total_nav * 100, 2) if total_nav else 0

    df = pd.DataFrame(rows)
    save(df, "portfolio.csv")

    # Save summary separately for quick API access
    summary = {
        "nav":         round(total_nav, 2),
        "total_cost":  round(sum(r["cost_basis"] for r in rows), 2),
        "total_pnl":   round(sum(r["unrealised_pnl"] for r in rows), 2),
        "return_pct":  round(sum(r["unrealised_pnl"] for r in rows) /
                            max(sum(r["cost_basis"] for r in rows), 1) * 100, 2),
        "positions":   len(rows),
        "updated_at":  datetime.utcnow().isoformat() + "Z",
    }
    with open(DATA_DIR / "portfolio_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    log(f"  NAV: ${total_nav:,.2f}  |  P&L: ${summary['total_pnl']:+,.2f}  ({summary['return_pct']:+.2f}%)")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — RISK: VaR, Correlation, Monte Carlo
# ═══════════════════════════════════════════════════════════════════════════════
def compute_risk():
    log("RISK — computing VaR, correlation matrix, Monte Carlo...")

    history_path = DATA_DIR / "history.csv"
    portfolio_path = DATA_DIR / "portfolio.csv"

    if not history_path.exists() or not portfolio_path.exists():
        log("  ERROR: run fetch_history() and build_portfolio() first")
        return

    hist = pd.read_csv(history_path)
    pf   = pd.read_csv(portfolio_path)

    # Pivot history to wide format: date × symbol
    hist["date"] = pd.to_datetime(hist["date"])
    price_pivot  = hist.pivot(index="date", columns="symbol", values="close").sort_index()

    # Daily returns
    returns = price_pivot.pct_change().dropna()

    # Keep only portfolio symbols + last HISTORY_DAYS days
    port_syms = [s.replace("-USD","").replace("=X","").replace("=F","")
                 for s in pf["symbol"].tolist()]
    available = [s for s in port_syms if s in returns.columns]
    returns   = returns[available].tail(HISTORY_DAYS)

    if returns.empty:
        log("  ERROR: no overlapping return data found for portfolio symbols")
        return

    # ── 1. Daily returns CSV ──────────────────────────────────────────────────
    returns_out = returns.reset_index()
    returns_out.columns = ["date"] + list(returns_out.columns[1:])
    save(returns_out, "returns.csv")

    # ── 2. Correlation matrix ─────────────────────────────────────────────────
    corr = returns.corr().round(4)
    corr.index.name = "symbol"
    corr_out = corr.reset_index()
    save(corr_out, "correlation.csv")

    # ── 3. Portfolio weights ──────────────────────────────────────────────────
    pf_idx = pf.set_index("symbol")
    weights = {}
    total_nav = pf["market_value"].sum()
    for sym in available:
        mv = float(pf_idx.loc[sym, "market_value"]) if sym in pf_idx.index else 0
        weights[sym] = mv / total_nav if total_nav else 1 / len(available)

    w = np.array([weights.get(s, 0) for s in available])
    w = w / w.sum()  # normalise

    # ── 4. Historical VaR & CVaR (99%, 1-day) ────────────────────────────────
    port_returns = returns.dot(w)
    var_99       = float(np.percentile(port_returns, 1))
    cvar_99      = float(port_returns[port_returns <= var_99].mean())
    var_95       = float(np.percentile(port_returns, 5))

    var_rows = [
        {"metric": "VaR 99% 1D",  "value_pct": round(var_99 * 100, 3),  "value_dollar": round(var_99 * total_nav, 0)},
        {"metric": "CVaR 99% 1D", "value_pct": round(cvar_99 * 100, 3), "value_dollar": round(cvar_99 * total_nav, 0)},
        {"metric": "VaR 95% 1D",  "value_pct": round(var_95 * 100, 3),  "value_dollar": round(var_95 * total_nav, 0)},
        {"metric": "Volatility Ann", "value_pct": round(port_returns.std() * np.sqrt(252) * 100, 2), "value_dollar": ""},
        {"metric": "Sharpe (proxy)", "value_pct": round((port_returns.mean() * 252) / (port_returns.std() * np.sqrt(252)), 3), "value_dollar": ""},
    ]
    save(pd.DataFrame(var_rows), "var_results.csv")
    log(f"  VaR 99% 1D: {var_99*100:.2f}%  |  CVaR: {cvar_99*100:.2f}%")

    # ── 5. Per-asset risk contribution ───────────────────────────────────────
    cov  = returns.cov() * 252  # annualised
    port_vol = float(np.sqrt(w @ cov.values @ w))
    marginal = cov.values @ w
    contrib  = w * marginal / port_vol if port_vol else w

    risk_rows = []
    for i, sym in enumerate(available):
        ret_mean = float(returns[sym].mean() * 252)
        vol_ann  = float(returns[sym].std() * np.sqrt(252))
        risk_rows.append({
            "symbol":          sym,
            "weight_pct":      round(w[i] * 100, 2),
            "ann_return_pct":  round(ret_mean * 100, 2),
            "ann_vol_pct":     round(vol_ann * 100, 2),
            "risk_contrib_pct":round(float(contrib[i]) * 100, 2),
        })
    save(pd.DataFrame(risk_rows), "risk_contribution.csv")

    # ── 6. Monte Carlo (HISTORY_DAYS-day horizon, MONTE_CARLO_SIMS paths) ────
    log(f"  running {MONTE_CARLO_SIMS:,} Monte Carlo simulations...")
    mean_returns = returns.mean().values
    cov_matrix   = returns.cov().values

    np.random.seed(42)
    sim_returns  = np.random.multivariate_normal(mean_returns, cov_matrix, (MONTE_CARLO_SIMS, HISTORY_DAYS))
    port_paths   = (1 + sim_returns.dot(w)).cumprod(axis=1) * total_nav

    final_values = port_paths[:, -1]
    percentiles  = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    mc_rows = [
        {
            "percentile":   p,
            "final_value":  round(float(np.percentile(final_values, p)), 0),
            "gain_loss":    round(float(np.percentile(final_values, p)) - total_nav, 0),
            "return_pct":   round((float(np.percentile(final_values, p)) / total_nav - 1) * 100, 2),
        }
        for p in percentiles
    ]
    mc_rows.append({
        "percentile": "mean",
        "final_value": round(float(final_values.mean()), 0),
        "gain_loss":   round(float(final_values.mean()) - total_nav, 0),
        "return_pct":  round((float(final_values.mean()) / total_nav - 1) * 100, 2),
    })
    save(pd.DataFrame(mc_rows), "monte_carlo.csv")

    # Save a sample of paths for chart rendering (100 paths, 252 days)
    sample_paths = port_paths[:100].tolist()
    with open(DATA_DIR / "mc_paths.json", "w") as f:
        json.dump({"nav": total_nav, "paths": [[round(v,0) for v in p] for p in sample_paths]}, f)
    log(f"  MC median: ${np.percentile(final_values,50):,.0f}  |  5th pct: ${np.percentile(final_values,5):,.0f}")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — STRESS TESTING
# ═══════════════════════════════════════════════════════════════════════════════
def build_stress_scenarios():
    log("STRESS TEST — computing scenario impacts on portfolio...")

    portfolio_path = DATA_DIR / "portfolio.csv"
    if not portfolio_path.exists():
        log("  ERROR: run build_portfolio() first")
        return

    pf = pd.read_csv(portfolio_path)
    total_nav = float(pf["market_value"].sum())

    # Classify portfolio positions into shock buckets
    type_to_bucket = {
        "equity": "equity", "etf": "equity",
        "crypto": "equity",   # crypto treated as high-beta equity in stress
        "forex":  "fx",
        "commodity": "commodity",
        "bond":   "bond",
    }

    # Load prices for type info
    prices_path = DATA_DIR / "prices.csv"
    type_map = {}
    if prices_path.exists():
        px = pd.read_csv(prices_path)
        for _, row in px.iterrows():
            type_map[str(row["symbol"]).upper()] = str(row.get("type", "equity")).lower()

    rows = []
    for scenario in STRESS_SCENARIOS:
        shock_per_bucket = {
            "equity":    scenario["equity"] / 100,
            "bond":      scenario["bond"] / 100,
            "credit":    scenario["credit"] / 100,
            "fx":        scenario["fx"] / 100,
            "commodity": scenario["commodity"] / 100,
        }

        total_impact = 0
        pos_impacts  = []

        for _, pos in pf.iterrows():
            sym    = str(pos["symbol"]).upper()
            mv     = float(pos["market_value"])
            ptype  = type_map.get(sym, "equity")
            bucket = type_to_bucket.get(ptype, "equity")
            shock  = shock_per_bucket.get(bucket, shock_per_bucket["equity"])
            impact = mv * shock
            total_impact += impact
            pos_impacts.append(f"{sym}:{round(impact,0)}")

        rows.append({
            "scenario":          scenario["scenario"],
            "equity_shock_pct":  scenario["equity"],
            "bond_shock_pct":    scenario["bond"],
            "credit_shock_pct":  scenario["credit"],
            "fx_shock_pct":      scenario["fx"],
            "commodity_shock_pct":scenario["commodity"],
            "portfolio_impact":  round(total_impact, 0),
            "impact_pct":        round(total_impact / total_nav * 100, 2) if total_nav else 0,
            "post_scenario_nav": round(total_nav + total_impact, 0),
        })

    df = pd.DataFrame(rows)
    save(df, "scenarios.csv")
    log(f"  worst scenario: {df.loc[df['portfolio_impact'].idxmin(),'scenario']} "
        f"({df['impact_pct'].min():.1f}%)")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — MACRO DATA (FRED + World Bank)
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_macro():
    log("MACRO — downloading yield curve and US economic indicators...")

    # ── Yield curve ───────────────────────────────────────────────────────────
    yield_rows = []
    for maturity, series_id in YIELD_SERIES.items():
        df = fred_csv(series_id)
        if not df.empty:
            latest = df.iloc[-1]
            prev   = df.iloc[-2] if len(df) > 1 else latest
            yield_rows.append({
                "maturity":   maturity,
                "series_id":  series_id,
                "yield_pct":  round(float(latest["value"]), 3),
                "prev_yield": round(float(prev["value"]), 3),
                "change_bps": round((float(latest["value"]) - float(prev["value"])) * 100, 1),
                "date":       str(latest["date"])[:10],
            })
            time.sleep(0.2)

    save(pd.DataFrame(yield_rows), "yields.csv")

    # ── US Macro indicators ────────────────────────────────────────────────────
    macro_rows = []
    for name, series_id in MACRO_SERIES.items():
        df = fred_csv(series_id)
        if not df.empty:
            latest = df.iloc[-1]
            prev   = df.iloc[-2] if len(df) > 1 else latest
            macro_rows.append({
                "indicator":  name,
                "series_id":  series_id,
                "value":      round(float(latest["value"]), 3),
                "prev_value": round(float(prev["value"]), 3),
                "change":     round(float(latest["value"]) - float(prev["value"]), 3),
                "date":       str(latest["date"])[:10],
            })
            time.sleep(0.2)

    save(pd.DataFrame(macro_rows), "macro_us.csv")
    log(f"  {len(yield_rows)} yield curve points, {len(macro_rows)} macro indicators")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — GLOBAL MACRO HEAT MAP (World Bank)
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_world_bank():
    log("WORLD BANK — downloading 20-country macro heat map data...")

    # World Bank indicator codes
    indicators = {
        "gdp_growth":   "NY.GDP.MKTP.KD.ZG",
        "cpi":          "FP.CPI.TOTL.ZG",
        "unemployment": "SL.UEM.TOTL.ZS",
        "debt_gdp":     "GC.DOD.TOTL.GD.ZS",
    }

    all_data = {}

    for field, indicator in indicators.items():
        # World Bank API: all countries, last 5 years, JSON format
        url = (f"https://api.worldbank.org/v2/country/"
               f"{';'.join(WORLD_BANK_COUNTRIES.keys())}"
               f"/indicator/{indicator}"
               f"?format=json&mrv=5&per_page=500")
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()

            if not data or len(data) < 2:
                continue

            for entry in data[1] or []:
                code  = entry.get("countryiso3code", "")[:2]  # use 2-char code
                # World Bank returns 3-char, find our 2-char match
                for our_code in WORLD_BANK_COUNTRIES:
                    if entry.get("country", {}).get("id", "") == our_code:
                        code = our_code
                        break

                if code not in WORLD_BANK_COUNTRIES:
                    continue

                val = entry.get("value")
                if val is None:
                    continue

                year = entry.get("date", "")
                if code not in all_data:
                    all_data[code] = {}
                # Keep latest non-null value
                if field not in all_data[code]:
                    all_data[code][field] = {"value": val, "year": year}

            time.sleep(0.5)

        except Exception as e:
            log(f"    World Bank {field} failed: {e}")

    # Central bank rates — hardcoded as World Bank doesn't publish them cleanly
    # These are approximate and should be updated when central banks change rates
    central_bank_rates = {
        "US": 5.50, "EU": 4.00, "CN": 3.45, "JP": -0.10,
        "GB": 5.25, "DE": 4.00, "IN": 6.50, "BR": 10.50,
        "CA": 5.00, "AU": 4.35, "KR": 3.50, "MX": 11.00,
        "SA": 6.00, "CH": 1.75, "SE": 4.00, "NO": 4.50,
        "SG": 3.68, "ID": 6.00, "TR": 50.0, "AR": 60.0,
    }

    rows = []
    for code, name in WORLD_BANK_COUNTRIES.items():
        country_data = all_data.get(code, {})
        rows.append({
            "code":        code,
            "name":        name,
            "gdp_growth":  round(float(country_data.get("gdp_growth", {}).get("value", 0) or 0), 2),
            "cpi":         round(float(country_data.get("cpi", {}).get("value", 0) or 0), 2),
            "unemployment":round(float(country_data.get("unemployment", {}).get("value", 0) or 0), 2),
            "debt_gdp":    round(float(country_data.get("debt_gdp", {}).get("value", 0) or 0), 1),
            "policy_rate": central_bank_rates.get(code, 0),
            "region":      _region(code),
        })

    save(pd.DataFrame(rows), "macro_global.csv")


def _region(code):
    americas = {"US","CA","BR","MX","AR"}
    europe   = {"EU","GB","DE","CH","SE","NO","TR"}
    asia     = {"CN","JP","IN","KR","SG","ID"}
    pacific  = {"AU"}
    mideast  = {"SA"}
    if code in americas: return "Americas"
    if code in europe:   return "Europe"
    if code in asia:     return "Asia"
    if code in pacific:  return "Pacific"
    if code in mideast:  return "Middle East"
    return "Other"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — CRYPTO PRICES (CoinGecko, no key needed)
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_crypto():
    log("CRYPTO — downloading prices from CoinGecko...")

    coins = {
        "bitcoin":       "BTC",
        "ethereum":      "ETH",
        "solana":        "SOL",
        "binancecoin":   "BNB",
        "ripple":        "XRP",
        "cardano":       "ADA",
        "avalanche-2":   "AVAX",
        "chainlink":     "LINK",
        "polkadot":      "DOT",
        "uniswap":       "UNI",
    }

    ids = ",".join(coins.keys())
    url = (f"https://api.coingecko.com/api/v3/coins/markets"
           f"?vs_currency=usd&ids={ids}"
           f"&order=market_cap_desc&sparkline=false&price_change_percentage=24h")

    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()

        rows = []
        for coin in data:
            cid = coin.get("id","")
            sym = coins.get(cid, cid.upper())
            rows.append({
                "symbol":        sym,
                "name":          coin.get("name",""),
                "price":         round(float(coin.get("current_price",0)), 4),
                "change_pct_24h":round(float(coin.get("price_change_percentage_24h",0) or 0), 2),
                "market_cap":    coin.get("market_cap",""),
                "volume_24h":    coin.get("total_volume",""),
                "high_24h":      coin.get("high_24h",""),
                "low_24h":       coin.get("low_24h",""),
                "ath":           coin.get("ath",""),
                "ath_change_pct":round(float(coin.get("ath_change_percentage",0) or 0), 1),
                "rank":          coin.get("market_cap_rank",""),
            })

        save(pd.DataFrame(rows), "crypto.csv")

        # Patch crypto prices into main prices.csv
        prices_path = DATA_DIR / "prices.csv"
        if prices_path.exists():
            pf = pd.read_csv(prices_path)
            for row in rows:
                mask = pf["symbol"].str.upper() == row["symbol"].upper()
                pf.loc[mask, "price"]      = row["price"]
                pf.loc[mask, "change_pct"] = row["change_pct_24h"]
            pf.to_csv(prices_path, index=False)
            log("  crypto prices patched into prices.csv")

    except Exception as e:
        log(f"  CoinGecko failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — NEWS (RSS feeds)
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_news():
    log("NEWS — downloading RSS feeds...")
    try:
        import feedparser
    except ImportError:
        log("  feedparser not installed. Run: pip install feedparser")
        return

    # Ticker keywords for category tagging
    CATEGORY_KEYWORDS = {
        "macro":  ["fed","federal reserve","cpi","inflation","gdp","unemployment",
                   "interest rate","ecb","boj","central bank","nfp","payroll"],
        "earn":   ["earnings","eps","revenue","quarterly","profit","beat","miss","guidance"],
        "tech":   ["ai","artificial intelligence","chip","semiconductor","cloud","software"],
        "crypto": ["bitcoin","btc","ethereum","crypto","blockchain","defi","web3"],
        "forex":  ["dollar","euro","yen","gbp","fx","currency","forex"],
    }

    rows = []
    seen = set()

    for feed in NEWS_FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
            for entry in parsed.entries[:20]:
                title = entry.get("title","").strip()
                if not title or title in seen:
                    continue
                seen.add(title)

                # Detect category from title
                title_lower = title.lower()
                category = "general"
                for cat, keywords in CATEGORY_KEYWORDS.items():
                    if any(kw in title_lower for kw in keywords):
                        category = cat
                        break

                # Extract tickers mentioned in title (crude match)
                words   = title.upper().split()
                tickers = [w.strip(".,!?:;()") for w in words
                           if w.strip(".,!?:;()") in [s.replace("-USD","").replace("=X","")
                                                       for s in WATCHLIST]]

                # Parse published time
                pub = entry.get("published", "")
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(pub)
                    time_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    time_str = pub[:16] if pub else ""

                rows.append({
                    "time":     time_str,
                    "source":   feed["source"],
                    "category": category,
                    "headline": title,
                    "summary":  entry.get("summary","")[:300].replace("\n"," "),
                    "tickers":  " ".join(tickers),
                    "link":     entry.get("link",""),
                })

        except Exception as e:
            log(f"    {feed['source']} failed: {e}")

    # Sort newest first
    rows.sort(key=lambda r: r["time"], reverse=True)
    save(pd.DataFrame(rows[:100]), "news.csv")    # keep latest 100 items


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11 — COMPLIANCE RULES
# ═══════════════════════════════════════════════════════════════════════════════
def build_compliance():
    log("COMPLIANCE — writing default rules template...")

    rules = [
        {"rule_id":"R01","type":"concentration","description":"Max single position weight","limit_pct":10.0,"action":"ALERT"},
        {"rule_id":"R02","type":"sector","description":"Max Technology sector weight","sector":"Technology","limit_pct":35.0,"action":"ALERT"},
        {"rule_id":"R03","type":"sector","description":"Max Crypto sector weight","sector":"Crypto","limit_pct":20.0,"action":"ALERT"},
        {"rule_id":"R04","type":"sector","description":"Max Finance sector weight","sector":"Finance","limit_pct":30.0,"action":"ALERT"},
        {"rule_id":"R05","type":"asset_class","description":"Min cash / bond allocation","asset_class":"Fixed Income","min_pct":5.0,"action":"WARN"},
        {"rule_id":"R06","type":"var","description":"Max 1D VaR 99%","limit_pct":-3.0,"action":"ALERT"},
        {"rule_id":"R07","type":"drawdown","description":"Max drawdown from peak","limit_pct":-20.0,"action":"ALERT"},
        {"rule_id":"R08","type":"leverage","description":"No short positions","limit_pct":0.0,"action":"BLOCK"},
    ]

    save(pd.DataFrame(rules), "compliance_rules.csv")
    log("  edit compliance_rules.csv to customise your risk limits")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN — run all sections
# ═══════════════════════════════════════════════════════════════════════════════
def run_all(quick=False, broker_csv=None, section=None):
    start = time.time()
    log("=" * 55)
    log("NEXUS DOWNLOADER — starting full refresh")
    log(f"Output directory: {DATA_DIR.resolve()}")
    log("=" * 55)

    sections = {
        "prices":      fetch_prices,
        "history":     fetch_history,
        "options":     fetch_options,
        "portfolio":   lambda: build_portfolio(broker_csv),
        "risk":        compute_risk,
        "stress":      build_stress_scenarios,
        "macro":       fetch_macro,
        "world":       fetch_world_bank,
        "crypto":      fetch_crypto,
        "news":        fetch_news,
        "compliance":  build_compliance,
    }

    if section:
        # Run a single named section
        if section in sections:
            sections[section]()
        else:
            log(f"ERROR: unknown section '{section}'. Options: {', '.join(sections)}")
        return

    if quick:
        # Quick mode: prices + portfolio + news only (skip heavy history/risk)
        for name in ["prices", "crypto", "portfolio", "news", "compliance"]:
            try:
                sections[name]()
            except Exception as e:
                log(f"ERROR in {name}: {e}")
    else:
        # Full refresh — run in dependency order
        order = [
            "prices",     # 1. current quotes
            "history",    # 2. OHLCV history (patches RSI into prices.csv)
            "crypto",     # 3. crypto patches into prices.csv
            "options",    # 4. options chain
            "portfolio",  # 5. portfolio P&L (needs prices.csv)
            "risk",       # 6. VaR / correlation / MC (needs history + portfolio)
            "stress",     # 7. stress tests (needs portfolio + prices)
            "macro",      # 8. FRED data
            "world",      # 9. World Bank
            "news",       # 10. RSS feeds
            "compliance", # 11. compliance rules template
        ]
        for name in order:
            try:
                sections[name]()
            except Exception as e:
                log(f"ERROR in {name}: {e}")
                import traceback
                traceback.print_exc()

    elapsed = time.time() - start
    log("=" * 55)
    log(f"DONE — {elapsed:.0f}s elapsed")
    log(f"Files in {DATA_DIR}:")
    for f in sorted(DATA_DIR.glob("*.csv")):
        with open(f, encoding="utf-8", errors="replace") as csv_file:
            rows = max(sum(1 for _ in csv_file) - 1, 0)  # -1 for header
        log(f"  {f.name:30} {rows:>5} rows")
    log("=" * 55)
    log("Now run:  python main.py   to start the API server")
    log("Then open Nexus_v5.html in your browser")
    log("=" * 55)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nexus Data Downloader")
    parser.add_argument("--quick",   action="store_true",
                        help="Fast mode: prices + portfolio + news only")
    parser.add_argument("--broker",  type=str, default=None,
                        help="Path to broker-exported portfolio CSV")
    parser.add_argument("--section", type=str, default=None,
                        help="Run one section only: prices|history|options|portfolio|risk|stress|macro|world|crypto|news|compliance")
    args = parser.parse_args()

    run_all(quick=args.quick, broker_csv=args.broker, section=args.section)
