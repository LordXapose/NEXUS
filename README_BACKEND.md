# Nexus Backend Server

Flask-based API server that proxies market data from multiple providers (Polygon, Alpha Vantage, FRED, CoinGecko) to the Nexus terminal frontend.

## Release

- Version: `5.1.5`
- GitHub repository: `https://github.com/LordXapose/NEXUS`
- Tag: `v5.1.5`

---

## 📋 Requirements

- Python 3.8+
- pip (Python package manager)
- Virtual Environment (venv)

---

## 🚀 Quick Start (Windows)

### Step 1: Create Virtual Environment

```bash
python -m venv venv
```

### Step 2: Activate Virtual Environment

**Windows:**
```bash
venv\Scripts\activate
```

**Mac/Linux:**
```bash
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure API Keys

Copy the template and fill in your keys:

```bash
# Copy template
copy .env.example .env

# Windows - Edit .env in Notepad (or VSCode)
notepad .env
```

**What to fill in:**

| Provider | Where to get key | Free tier |
|----------|------------------|-----------|
| **Polygon** | https://polygon.io | ✅ Yes (limited) |
| **Alpha Vantage** | https://www.alphavantage.co/ | ✅ Yes (5 calls/min) |
| **FRED** | https://fred.stlouisfed.org/docs/api/ | ✅ Yes (default: DEMO) |
| **CoinGecko** | https://www.coingecko.com/api | ✅ Yes (no key needed) |

### Step 5: Run Server

```bash
python app.py
```

You should see:
```
==================================================
🚀 Nexus Backend Server
==================================================
Running on: http://localhost:5000
Debug mode: True

API Keys Configured:
  ✓ polygon
  ✓ alpha_vantage
  ✓ fred
  ✓ coingecko

==================================================
```

---

## 🔌 API Endpoints

### Health Check

```bash
curl http://localhost:5000/
curl http://localhost:5000/health
```

### Stock Data (Polygon)

```bash
# Get latest quote for a stock
curl http://localhost:5000/api/stocks/quote/AAPL

# Get daily OHLCV data for date range
curl "http://localhost:5000/api/stocks/aggs/AAPL?from=2024-01-01&to=2024-06-01"

# Get options chain
curl http://localhost:5000/api/stocks/options/AAPL
```

### Crypto Data (CoinGecko)

```bash
# Get price data for cryptocurrency
curl http://localhost:5000/api/crypto/price/bitcoin

# Get top crypto by market cap
curl "http://localhost:5000/api/crypto/markets?limit=50"
```

### Macro Data (FRED)

```bash
# Get economic series (e.g., unemployment rate)
curl http://localhost:5000/api/macro/series/UNRATE

# Search for series
curl "http://localhost:5000/api/macro/series?q=unemployment"
```

---

## 🎯 Common FRED Series IDs

| Series ID | Description |
|-----------|-------------|
| UNRATE | Unemployment Rate |
| PAYEMS | Total Nonfarm Payroll |
| CPIAUCSL | Consumer Price Index |
| DEXUSEU | USD/EUR Exchange Rate |
| DGS10 | 10-Year Treasury Yield |
| FEDFUNDS | Federal Funds Rate |

---

## 📁 Project Structure

```
nexus-backend/
├── app.py                 # Main Flask server
├── requirements.txt       # Python dependencies
├── .env.example          # API key template
├── .env                  # Your actual API keys (ignored by git)
└── README_BACKEND.md     # This file
```

---

## 🔄 How It Works

1. **Frontend** (Nexus.html) sends requests to `http://localhost:5000/api/*`
2. **Backend** receives request and adds your API keys
3. **Backend** calls external API (Polygon, CoinGecko, FRED)
4. **Backend** returns JSON response to frontend
5. **Frontend** displays data in the Nexus terminal

This way, **your API keys stay private** and only the backend uses them.

---

## 🛠️ Troubleshooting

### "ModuleNotFoundError: No module named 'flask'"

Make sure virtual environment is active:
```bash
# Windows
venv\Scripts\activate

# Should show (venv) at start of prompt
```

Then install dependencies:
```bash
pip install -r requirements.txt
```

### "The server is not responding"

1. Check if server is running (you should see `Running on: http://localhost:5000`)
2. Check if firewall is blocking port 5000
3. Make sure `http://localhost:5000/` returns JSON response (test in browser)

### "API key not configured" error

1. Create `.env` file from `.env.example`
2. Fill in your actual API keys
3. Restart server with `python app.py`

### "Connection timeout" error

This means the external API (Polygon, CoinGecko, etc.) is slow or down.
- Wait a moment and try again
- Check API provider status
- Try different ticker/coin ID

---

## 📝 Environment Variables

Create `.env` file in the same folder as `app.py`:

```
# API Keys
POLYGON_API_KEY=pk_live_xxxxx
ALPHA_VANTAGE_API_KEY=xxxxx
FRED_API_KEY=xxxxx
COINGECKO_API_KEY=

# Server
DEBUG=True
PORT=5000
```

---

## 🌐 Connect Frontend to Backend

In your `Nexus.html` file, update the `nexusFetch` function to use your backend:

```javascript
async function nexusFetch(url, fallbackData) {
    // Example: /api/stocks/quote/AAPL 
    // becomes http://localhost:5000/api/stocks/quote/AAPL
    const backendUrl = `http://localhost:5000${url}`;
    
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    try {
        const r = await fetch(backendUrl, { signal: ctrl.signal });
        clearTimeout(timer);
        return await r.json();
    } catch (e) {
        clearTimeout(timer);
        console.warn(`Fetch failed for ${url}, using fallback`);
        return fallbackData || { status: 'error', message: e.message };
    }
}
```

---

## 🚀 Production Deployment

For production, change in `.env`:

```
DEBUG=False
PORT=8000
```

Then use a production WSGI server:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

---

## 📞 Support

If you encounter issues:

1. Check that **Virtual Environment is active** (see `(venv)` in prompt)
2. Verify **all dependencies installed** (`pip list` should show flask, requests, etc.)
3. Verify **API keys in .env** are correct
4. Check **API provider status** (sites might be down)
5. Try **http://localhost:5000/** in browser - should return JSON

---

**Version:** 1.0.0  
**Created:** July 2026
