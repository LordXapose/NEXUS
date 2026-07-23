"""
Nexus CSV API
-------------
FastAPI server that reads CSV files and serves them to the Nexus terminal.

Endpoints:
  GET  /                        health check
  GET  /api/prices              all watchlist prices
  GET  /api/prices/{symbol}     single ticker
  GET  /api/portfolio           portfolio positions
  GET  /api/news                news feed items
  GET  /api/summary             combined summary (prices + portfolio NAV + news count)

  POST /api/upload/prices       upload a new prices CSV (replaces current)
  POST /api/upload/portfolio    upload a new portfolio CSV (replaces current)
  POST /api/upload/news         upload a new news CSV (replaces current)

  GET  /api/schema              returns expected CSV column schemas
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import io
import os
from datetime import datetime
from typing import Optional

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Nexus CSV API",
    description="Feeds CSV data into the Nexus Financial Terminal",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # Nexus is a local file:// page
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Data store (in-memory, reloaded from CSV on each request) ─────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

PRICES_CSV    = os.path.join(DATA_DIR, "prices.csv")
PORTFOLIO_CSV = os.path.join(DATA_DIR, "portfolio.csv")
NEWS_CSV      = os.path.join(DATA_DIR, "news.csv")
RISK_CSVS = {
    "var_results":       os.path.join(DATA_DIR, "var_results.csv"),
    "risk_contribution": os.path.join(DATA_DIR, "risk_contribution.csv"),
    "scenarios":         os.path.join(DATA_DIR, "scenarios.csv"),
    "monte_carlo":       os.path.join(DATA_DIR, "monte_carlo.csv"),
    "compliance_rules":  os.path.join(DATA_DIR, "compliance_rules.csv"),
    "correlation":       os.path.join(DATA_DIR, "correlation.csv"),
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _load(path: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip().str.lower()
        return df
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read {os.path.basename(path)}: {e}")


def _save(path: str, content: bytes):
    try:
        df = pd.read_csv(io.BytesIO(content))
        df.columns = df.columns.str.strip().str.lower()
        df.to_csv(path, index=False)
        return df
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {e}")


def _nan_safe(val):
    """Convert NaN / numpy types to JSON-safe Python types."""
    if pd.isna(val):
        return None
    if hasattr(val, "item"):
        return val.item()
    return val


def _row_to_dict(row: pd.Series) -> dict:
    return {k: _nan_safe(v) for k, v in row.items()}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def health():
    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat() + "Z",
        "files": {
            "prices":    os.path.exists(PRICES_CSV),
            "portfolio": os.path.exists(PORTFOLIO_CSV),
            "news":      os.path.exists(NEWS_CSV),
        },
    }


# ── Prices ────────────────────────────────────────────────────────────────────
@app.get("/api/prices")
def get_prices():
    """
    Returns all rows from prices.csv as a list of objects.

    Expected CSV columns (case-insensitive):
      symbol, name, price, change_pct, open, high, low,
      volume, market_cap, pe_ratio, week52_high, week52_low,
      rsi, sector, type, signal
    """
    df = _load(PRICES_CSV)
    if df is None:
        raise HTTPException(status_code=404, detail="prices.csv not uploaded yet. POST to /api/upload/prices")

    required = {"symbol", "price"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=422, detail=f"prices.csv is missing columns: {missing}")

    records = [_row_to_dict(row) for _, row in df.iterrows()]
    return {"count": len(records), "updated_at": datetime.utcnow().isoformat() + "Z", "data": records}


@app.get("/api/prices/{symbol}")
def get_price(symbol: str):
    """Single ticker lookup."""
    df = _load(PRICES_CSV)
    if df is None:
        raise HTTPException(status_code=404, detail="prices.csv not uploaded yet")

    match = df[df["symbol"].str.upper() == symbol.upper()]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    return _row_to_dict(match.iloc[0])


# ── Portfolio ─────────────────────────────────────────────────────────────────
@app.get("/api/portfolio")
def get_portfolio():
    """
    Returns portfolio positions with computed P&L.

    Expected CSV columns:
      symbol, name, shares, avg_cost, sector

    Enriched from prices.csv if available:
      current_price, market_value, unrealised_pnl, return_pct, weight_pct
    """
    pf = _load(PORTFOLIO_CSV)
    if pf is None:
        raise HTTPException(status_code=404, detail="portfolio.csv not uploaded yet. POST to /api/upload/portfolio")

    required = {"symbol", "shares", "avg_cost"}
    missing = required - set(pf.columns)
    if missing:
        raise HTTPException(status_code=422, detail=f"portfolio.csv is missing columns: {missing}")

    # Try to enrich with live prices
    px = _load(PRICES_CSV)
    price_map = {}
    if px is not None and "symbol" in px.columns and "price" in px.columns:
        price_map = dict(zip(px["symbol"].str.upper(), px["price"]))

    positions = []
    total_nav = 0.0

    for _, row in pf.iterrows():
        d = _row_to_dict(row)
        sym = str(d.get("symbol", "")).upper()
        shares = float(d.get("shares", 0) or 0)
        cost   = float(d.get("avg_cost", 0) or 0)
        price  = float(price_map.get(sym, d.get("current_price", cost) or cost))

        cost_basis   = shares * cost
        market_value = shares * price
        pnl          = market_value - cost_basis
        ret_pct      = (pnl / cost_basis * 100) if cost_basis else 0.0

        d.update({
            "symbol":         sym,
            "current_price":  round(price, 4),
            "cost_basis":     round(cost_basis, 2),
            "market_value":   round(market_value, 2),
            "unrealised_pnl": round(pnl, 2),
            "return_pct":     round(ret_pct, 2),
        })
        total_nav += market_value
        positions.append(d)

    # Add weight %
    for p in positions:
        p["weight_pct"] = round(p["market_value"] / total_nav * 100, 2) if total_nav else 0

    # Summary metrics
    total_cost  = sum(p["cost_basis"] for p in positions)
    total_pnl   = sum(p["unrealised_pnl"] for p in positions)
    total_ret   = round(total_pnl / total_cost * 100, 2) if total_cost else 0

    return {
        "summary": {
            "nav":         round(total_nav, 2),
            "total_cost":  round(total_cost, 2),
            "total_pnl":   round(total_pnl, 2),
            "return_pct":  total_ret,
            "positions":   len(positions),
        },
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "data": positions,
    }


# ── News ──────────────────────────────────────────────────────────────────────
@app.get("/api/news")
def get_news(limit: int = 50, category: str = "all"):
    """
    Returns news items newest-first.

    Expected CSV columns:
      time, source, category, headline, summary (optional), tickers (optional, comma-separated)

    category filter: all | macro | earn | tech | crypto | forex
    """
    df = _load(NEWS_CSV)
    if df is None:
        raise HTTPException(status_code=404, detail="news.csv not uploaded yet. POST to /api/upload/news")

    required = {"headline"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=422, detail=f"news.csv is missing columns: {missing}")

    if category != "all" and "category" in df.columns:
        df = df[df["category"].str.lower() == category.lower()]

    # Newest first if time column present
    if "time" in df.columns:
        try:
            df = df.sort_values("time", ascending=False)
        except Exception:
            pass

    df = df.head(limit)

    records = []
    for _, row in df.iterrows():
        d = _row_to_dict(row)
        # Parse tickers string into list
        if "tickers" in d and d["tickers"]:
            d["tickers"] = [t.strip().upper() for t in str(d["tickers"]).split(",") if t.strip()]
        else:
            d["tickers"] = []
        records.append(d)

    return {"count": len(records), "updated_at": datetime.utcnow().isoformat() + "Z", "data": records}


# ── Summary ───────────────────────────────────────────────────────────────────
@app.get("/api/summary")
def get_summary():
    """Single call that returns top-level data for the Nexus home screen."""
    result = {"updated_at": datetime.utcnow().isoformat() + "Z"}

    # Prices summary
    px = _load(PRICES_CSV)
    if px is not None and "price" in px.columns:
        gainers = px[px.get("change_pct", pd.Series(dtype=float)) > 0] if "change_pct" in px.columns else px
        losers  = px[px.get("change_pct", pd.Series(dtype=float)) < 0] if "change_pct" in px.columns else pd.DataFrame()
        result["prices"] = {
            "total_symbols": len(px),
            "gainers": len(gainers),
            "losers":  len(losers),
        }

    # Portfolio summary
    pf = _load(PORTFOLIO_CSV)
    if pf is not None:
        result["portfolio"] = {"positions": len(pf)}

    # News count
    nw = _load(NEWS_CSV)
    if nw is not None:
        result["news"] = {"total_items": len(nw)}

    return result


@app.get("/api/risk")
def get_risk():
    """Return all risk and compliance outputs created by the downloader."""
    datasets = {}
    available = False
    for name, path in RISK_CSVS.items():
        df = _load(path)
        if df is None:
            datasets[name] = []
            continue
        available = True
        datasets[name] = [_row_to_dict(row) for _, row in df.iterrows()]

    if not available:
        raise HTTPException(status_code=404, detail="Risk files not generated yet. Run py.py first.")

    return {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "data": datasets,
    }


# ── Upload endpoints ──────────────────────────────────────────────────────────

@app.post("/api/upload/prices")
async def upload_prices(file: UploadFile = File(...)):
    """Upload a prices CSV. Replaces the current prices data."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")
    content = await file.read()
    df = _save(PRICES_CSV, content)
    return {
        "message": f"Uploaded {len(df)} price rows",
        "columns": list(df.columns),
        "rows": len(df),
    }


@app.post("/api/upload/portfolio")
async def upload_portfolio(file: UploadFile = File(...)):
    """Upload a portfolio CSV. Replaces the current portfolio data."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")
    content = await file.read()
    df = _save(PORTFOLIO_CSV, content)
    return {
        "message": f"Uploaded {len(df)} portfolio positions",
        "columns": list(df.columns),
        "rows": len(df),
    }


@app.post("/api/upload/news")
async def upload_news(file: UploadFile = File(...)):
    """Upload a news CSV. Replaces the current news data."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")
    content = await file.read()
    df = _save(NEWS_CSV, content)
    return {
        "message": f"Uploaded {len(df)} news items",
        "columns": list(df.columns),
        "rows": len(df),
    }


# ── Schema docs ───────────────────────────────────────────────────────────────

@app.get("/api/schema")
def get_schema():
    """Returns the expected CSV column schema for each upload type."""
    return {
        "prices": {
            "required": ["symbol", "price"],
            "optional": [
                "name", "change_pct", "open", "high", "low",
                "volume", "market_cap", "pe_ratio",
                "week52_high", "week52_low", "rsi",
                "sector", "type", "signal"
            ],
            "example_row": {
                "symbol": "AAPL", "name": "Apple Inc.", "price": 182.63,
                "change_pct": 1.24, "open": 180.10, "high": 183.90,
                "low": 179.50, "volume": "58.2M", "market_cap": "2.81T",
                "pe_ratio": 28.4, "week52_high": 199.62,
                "week52_low": 143.90, "rsi": 58, "sector": "Technology",
                "type": "equity", "signal": "buy"
            }
        },
        "portfolio": {
            "required": ["symbol", "shares", "avg_cost"],
            "optional": ["name", "sector", "current_price"],
            "example_row": {
                "symbol": "AAPL", "name": "Apple Inc.",
                "shares": 50, "avg_cost": 155.20, "sector": "Technology"
            }
        },
        "news": {
            "required": ["headline"],
            "optional": ["time", "source", "category", "summary", "tickers"],
            "example_row": {
                "time": "09:41", "source": "BBG", "category": "macro",
                "headline": "Fed signals rate cut in Q2 as inflation cools",
                "summary": "Minutes show growing consensus toward easing.",
                "tickers": "SPY, TLT, GLD"
            }
        }
    }
