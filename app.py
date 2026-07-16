# Nexus Backend - Flask Server
# This server proxies market data from multiple API providers
# and serves it to the Nexus frontend with proper CORS headers

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import requests
import os
import time
import threading
from dotenv import load_dotenv
from datetime import datetime, timedelta
from io import BytesIO
from fpdf import FPDF
import json

# File-based cache for prices and unified data
CACHE_TTL = 300  # seconds
CACHE_FILES = {
    'price': 'price_cache.json',
    'fx': 'fx_cache.json',
    'rates': 'rates_cache.json',
    'macro': 'macro_cache.json',
    'commodities': 'commodities_cache.json',
    'sectors': 'sectors_cache.json',
    'news': 'news_cache.json',
    'all': 'all_data_cache.json'
}

def load_json_file(path, default=None):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return default


def save_json_file(path, data):
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Failed to save cache file {path}: {str(e)}")


def file_mtime(path):
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0


def load_cache_from_file(name, default=None):
    path = CACHE_FILES.get(name)
    if not path:
        return default, 0
    data = load_json_file(path, default)
    timestamp = file_mtime(path) if os.path.exists(path) else 0
    return data, timestamp


def save_cache_to_file(name, data):
    path = CACHE_FILES.get(name)
    if not path:
        return
    save_json_file(path, data)


def normalize_fx_cache(fx_data):
    """Normalize FX cache data to a list of pair objects."""
    if isinstance(fx_data, dict):
        normalized = []
        for pair, values in fx_data.items():
            if pair == 'updated_at':
                continue
            if isinstance(values, dict):
                normalized.append({
                    'pair': pair,
                    'rate': float(values.get('rate', 0)),
                    'bid': float(values.get('bid', values.get('rate', 0))),
                    'ask': float(values.get('ask', values.get('rate', 0))),
                    'change': float(values.get('change', 0))
                })
            else:
                normalized.append({
                    'pair': pair,
                    'rate': float(values),
                    'bid': float(values),
                    'ask': float(values),
                    'change': 0.0
                })
        return normalized
    if isinstance(fx_data, list):
        return fx_data
    return []


def is_cache_stale(timestamp):
    return not timestamp or (time.time() - timestamp) > CACHE_TTL


def load_price_cache_from_file():
    """Load cached prices from JSON file"""
    global PRICE_CACHE
    try:
        price_cache, _ = load_cache_from_file('price', {})
        PRICE_CACHE.update(price_cache)
        print(f"Loaded price cache from {CACHE_FILES['price']}")
    except Exception as e:
        print(f"Failed to load cache file: {str(e)}")


def save_price_cache_to_file():
    """Save current prices to JSON file"""
    save_cache_to_file('price', PRICE_CACHE)


def refresh_price_cache(tickers=None):
    """Refresh stock quote cache from Alpha Vantage or fall back to existing cache."""
    global PRICE_CACHE
    tickers = tickers or ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN']
    alpha_key = API_KEYS.get('alpha_vantage', '')

    if not alpha_key:
        print('Alpha Vantage key not configured, skipping price refresh')
        return

    for ticker in tickers:
        try:
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': ticker,
                'apikey': alpha_key
            }
            success, data, error = safe_fetch('https://www.alphavantage.co/query', params)
            if success and data and 'Global Quote' in data:
                quote = data['Global Quote']
                price = float(quote.get('05. price', PRICE_CACHE.get(ticker, {}).get('p', 0)))
                change = float(quote.get('09. change', PRICE_CACHE.get(ticker, {}).get('c', 0)))
                volume = quote.get('06. volume', PRICE_CACHE.get(ticker, {}).get('s', '0'))
                PRICE_CACHE[ticker] = {'p': round(price, 2), 'c': round(change, 2), 's': str(volume)}
                print(f'✅ Refreshed {ticker}: {PRICE_CACHE[ticker]}')
        except Exception as e:
            print(f'Price refresh failed for {ticker}: {e}')

    save_price_cache_to_file()


def refresh_fx_cache():
    """Refresh FX cache and persist to file."""
    global FX_CACHE, FX_CACHE_TIME
    alpha_key = API_KEYS.get('alpha_vantage', '')
    fx_pairs = [
        {'from': 'EUR', 'to': 'USD'},
        {'from': 'GBP', 'to': 'USD'},
        {'from': 'USD', 'to': 'JPY'},
        {'from': 'AUD', 'to': 'USD'},
        {'from': 'USD', 'to': 'CHF'},
        {'from': 'USD', 'to': 'CAD'}
    ]

    if not alpha_key:
        print('Alpha Vantage key not configured, preserving existing FX cache')
        return

    rates = []
    for pair in fx_pairs:
        from_curr = pair['from']
        to_curr = pair['to']
        try:
            params = {
                'function': 'CURRENCY_EXCHANGE_RATE',
                'from_currency': from_curr,
                'to_currency': to_curr,
                'apikey': alpha_key
            }
            success, data, error = safe_fetch('https://www.alphavantage.co/query', params)
            if success and 'Realtime Currency Exchange Rate' in data:
                rate_data = data['Realtime Currency Exchange Rate']
                rate = float(rate_data.get('5. Exchange Rate', 0))
                if rate > 0:
                    rates.append({
                        'pair': f'{from_curr}/{to_curr}',
                        'rate': round(rate, 4),
                        'bid': round(rate - 0.0001, 4),
                        'ask': round(rate + 0.0001, 4),
                        'change': round(float(rate_data.get('8. Bid Price', rate)) * 0.001, 4)
                    })
        except Exception as e:
            print(f'FX refresh failed for {from_curr}/{to_curr}: {e}')

    if rates:
        FX_CACHE = rates
        FX_CACHE_TIME = time.time()
        save_cache_to_file('fx', FX_CACHE)
        return

    if FX_CACHE:
        print('⚠️ FX refresh failed, preserving existing FX cache')
        return

    print('FX refresh failed and no existing FX cache available')


def refresh_rates_cache():
    """Refresh rates cache and persist to file."""
    global RATES_CACHE, RATES_CACHE_TIME
    if RATES_CACHE:
        save_cache_to_file('rates', RATES_CACHE)
        return
    print('No rates API configured; preserving existing rates cache')
    RATES_CACHE = RATES_CACHE or []


def refresh_macro_cache():
    """Refresh macro cache and persist to file."""
    global MACRO_CACHE, MACRO_CACHE_TIME
    if MACRO_CACHE:
        save_cache_to_file('macro', MACRO_CACHE)
        return
    print('No macro API configured; preserving existing macro cache')
    MACRO_CACHE = MACRO_CACHE or []


def refresh_commodities_cache():
    """Refresh commodities cache and persist to file."""
    global COMMODITIES_CACHE, COMMODITIES_CACHE_TIME
    if COMMODITIES_CACHE:
        save_cache_to_file('commodities', COMMODITIES_CACHE)
        return
    print('No commodities API configured; preserving existing commodities cache')
    COMMODITIES_CACHE = COMMODITIES_CACHE or []


def refresh_sectors_cache():
    """Refresh sector cache and persist to file."""
    global SECTORS_CACHE, SECTORS_CACHE_TIME
    sector_changes = {
        'Technology': [],
        'Consumer': []
    }
    for ticker, price_data in PRICE_CACHE.items():
        if ticker == 'AMZN':
            sector_changes['Consumer'].append(price_data.get('c', 0))
        else:
            sector_changes['Technology'].append(price_data.get('c', 0))

    new_sectors = []
    for sector, changes in sector_changes.items():
        if changes:
            new_sectors.append({'name': sector, 'chg': round(sum(changes)/len(changes), 2)})

    if new_sectors:
        SECTORS_CACHE = new_sectors
        SECTORS_CACHE_TIME = time.time()
        save_cache_to_file('sectors', SECTORS_CACHE)
    else:
        print('Unable to compute sectors from price cache; preserving existing sectors cache')


def build_all_data_cache():
    """Build and persist the unified /api/all-data cache."""
    global ALL_DATA_CACHE, ALL_DATA_CACHE_TIME
    ALL_DATA_CACHE = {
        'screener': [
            {
                'symbol': ticker,
                'name': ticker,
                'type': 'equity',
                'price': PRICE_CACHE[ticker]['p'],
                'change': PRICE_CACHE[ticker]['c'],
                'volume': PRICE_CACHE[ticker]['s'],
                'mkt_cap': '',
                'rsi': 0,
                'ma20': 0,
                'signal': 'BUY' if PRICE_CACHE[ticker]['c'] > 2 else 'SELL' if PRICE_CACHE[ticker]['c'] < -2 else 'HOLD'
            }
            for ticker in ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN'] if ticker in PRICE_CACHE
        ],
        'markets': [
            {
                'symbol': ticker,
                'name': ticker,
                'type': 'equity',
                'sector': '',
                'exchange': '',
                'price': PRICE_CACHE[ticker]['p'],
                'change': PRICE_CACHE[ticker]['c'],
                'volume': PRICE_CACHE[ticker]['s'],
                'market_cap': '',
                'pe_ratio': 0,
                'dividend_yield': 0
            }
            for ticker in ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN'] if ticker in PRICE_CACHE
        ],
        'fx': FX_CACHE,
        'commodities': COMMODITIES_CACHE,
        'rates': RATES_CACHE,
        'macro': MACRO_CACHE,
        'news': NEWS_CACHE,
        'sectors': SECTORS_CACHE
    }
    ALL_DATA_CACHE_TIME = time.time()
    save_cache_to_file('all', ALL_DATA_CACHE)


def refresh_news_cache():
    """Refresh news cache and persist to file."""
    global NEWS_CACHE, NEWS_CACHE_TIME
    existing_news = NEWS_CACHE or []
    news_items = []
    if API_KEYS.get('newsapi'):
        try:
            params = {
                'q': 'stock market finance business',
                'sortBy': 'publishedAt',
                'language': 'en',
                'apiKey': API_KEYS['newsapi'],
                'pageSize': 6
            }
            success, data, error = safe_fetch(f"{ENDPOINTS['newsapi']}/everything", params)
            if success and data and 'articles' in data:
                for article in data['articles']:
                    news_items.append({
                        'time': datetime.fromisoformat(article['publishedAt'].replace('Z', '+00:00')).strftime('%H:%M'),
                        'src': article.get('source', {}).get('name', 'NEWS'),
                        'tag': 'news',
                        'hl': article.get('title', '')[:100]
                    })
        except Exception as e:
            print(f'News refresh failed: {e}')
    else:
        print('NewsAPI key not configured, preserving existing news cache')

    if news_items:
        NEWS_CACHE = news_items
        NEWS_CACHE_TIME = time.time()
        save_cache_to_file('news', NEWS_CACHE)
    elif existing_news:
        NEWS_CACHE = existing_news
        print('News refresh failed, preserving existing news cache')
    else:
        NEWS_CACHE = []
        print('No news cache available')


def load_all_caches_from_files():
    """Load cached data from files on startup."""
    global FX_CACHE, FX_CACHE_TIME, RATES_CACHE, RATES_CACHE_TIME, MACRO_CACHE, MACRO_CACHE_TIME, COMMODITIES_CACHE, COMMODITIES_CACHE_TIME, SECTORS_CACHE, SECTORS_CACHE_TIME, ALL_DATA_CACHE, ALL_DATA_CACHE_TIME, NEWS_CACHE, NEWS_CACHE_TIME

    load_price_cache_from_file()
    FX_CACHE, FX_CACHE_TIME = load_cache_from_file('fx', [])
    FX_CACHE = normalize_fx_cache(FX_CACHE)
    RATES_CACHE, RATES_CACHE_TIME = load_cache_from_file('rates', [])
    MACRO_CACHE, MACRO_CACHE_TIME = load_cache_from_file('macro', [])
    COMMODITIES_CACHE, COMMODITIES_CACHE_TIME = load_cache_from_file('commodities', [])
    SECTORS_CACHE, SECTORS_CACHE_TIME = load_cache_from_file('sectors', [])
    NEWS_CACHE, NEWS_CACHE_TIME = load_cache_from_file('news', [])
    ALL_DATA_CACHE, ALL_DATA_CACHE_TIME = load_cache_from_file('all', {})


def periodic_refresh():
    """Background refresh loop for cached data."""
    while True:
        try:
            refresh_all_data_cache(force=True)
        except Exception as e:
            print(f'⚠️ Periodic refresh error: {e}')
        time.sleep(CACHE_TTL)


def start_periodic_refresh():
    t = threading.Thread(target=periodic_refresh, daemon=True)
    t.start()


def refresh_all_data_cache(force=False):
    """Refresh all caches and unified data if stale or forced."""
    global ALL_DATA_CACHE_TIME
    if force or is_cache_stale(ALL_DATA_CACHE_TIME):
        print('🔄 Refreshing all-data cache')
        refresh_price_cache()
        refresh_fx_cache()
        refresh_rates_cache()
        refresh_macro_cache()
        refresh_commodities_cache()
        refresh_sectors_cache()
        refresh_news_cache()
        build_all_data_cache()
    else:
        print('✅ Using up-to-date all-data cache')

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# ============================================
# CONFIGURATION & API KEYS
# ============================================

API_KEYS = {
    'polygon': os.getenv('POLYGON_API_KEY', ''),
    'alpha_vantage': os.getenv('ALPHA_VANTAGE_API_KEY', ''),
    'fred': os.getenv('FRED_API_KEY', 'DEMO'),
    'coingecko': os.getenv('COINGECKO_API_KEY', ''),
    'newsapi': os.getenv('NEWSAPI_KEY', ''),
}

# API Endpoints (do not modify)
ENDPOINTS = {
    'polygon': 'https://api.polygon.io',
    'alpha_vantage': 'https://www.alphavantage.co',
    'fred': 'https://api.stlouisfed.org/fred',
    'coingecko': 'https://api.coingecko.com/api/v3',
    'newsapi': 'https://newsapi.org/v2',
}

# Price Cache - Store last successful API responses
PRICE_CACHE = {}

REQUEST_TIMEOUT = 10  # seconds
CACHE = {}  # Simple in-memory cache

# Global cache for real-time data
FX_CACHE = []
FX_CACHE_TIME = 0
NEWS_CACHE = []
NEWS_CACHE_TIME = 0
SECTORS_CACHE = []
SECTORS_CACHE_TIME = 0
ALL_DATA_CACHE = {}
ALL_DATA_CACHE_TIME = 0
PORTFOLIO_CACHE = None
PORTFOLIO_CACHE_TIME = 0
MARKETS_CACHE = None
MARKETS_CACHE_TIME = 0
SCREENER_CACHE = None
SCREENER_CACHE_TIME = 0
COMMODITIES_CACHE = None
COMMODITIES_CACHE_TIME = 0
RATES_CACHE = None
RATES_CACHE_TIME = 0
MACRO_CACHE = None
MACRO_CACHE_TIME = 0


# ============================================
# UTILITY FUNCTIONS
# ============================================

def cache_key(provider, endpoint, params):
    """Generate a cache key from provider, endpoint, and params"""
    return f"{provider}:{endpoint}:{json.dumps(params, sort_keys=True)}"


def get_from_cache(key):
    """Retrieve from cache if exists and not expired"""
    if key in CACHE:
        data, timestamp = CACHE[key]
        if datetime.now() - timestamp < timedelta(minutes=5):  # 5-minute cache
            return data
        else:
            del CACHE[key]
    return None


def set_cache(key, data):
    """Store data in cache with timestamp"""
    CACHE[key] = (data, datetime.now())


def safe_fetch(url, params=None, timeout=REQUEST_TIMEOUT):
    """
    Safely fetch from external API with timeout and error handling
    Returns: (success: bool, data: dict or None, error: str or None)
    """
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return True, response.json(), None
    except requests.exceptions.Timeout:
        return False, None, "Request timeout - API server is slow"
    except requests.exceptions.ConnectionError:
        return False, None, "Connection error - check internet or API endpoint"
    except requests.exceptions.HTTPError as e:
        return False, None, f"HTTP Error {e.response.status_code}"
    except ValueError:
        return False, None, "Invalid JSON response from API"
    except Exception as e:
        return False, None, f"Unexpected error: {str(e)}"


def fetch_stock_quote(ticker):
    """Fetch a real stock quote from Alpha Vantage or return None on failure."""
    ticker = ticker.upper()
    alpha_key = API_KEYS.get('alpha_vantage', '')
    if not alpha_key:
        return None

    url = 'https://www.alphavantage.co/query'
    params = {
        'function': 'GLOBAL_QUOTE',
        'symbol': ticker,
        'apikey': alpha_key
    }
    success, data, error = safe_fetch(url, params)
    if not success or not data:
        print(f'Stock quote fetch failed for {ticker}: {error}')
        return None

    if 'Note' in data or 'Information' in data:
        print(f'Alpha Vantage rate limit or info message for {ticker}: {data.get("Note") or data.get("Information")}')
        return None

    quote = data.get('Global Quote') or {}
    if not quote or not quote.get('05. price'):
        return None

    try:
        price = float(quote.get('05. price', 0))
        change = float(quote.get('09. change', 0))
        volume = int(quote.get('06. volume', '0').replace(',', '') or 0)
        previous_close = float(quote.get('08. previous close', price))
        return {
            'symbol': ticker,
            'price': round(price, 2),
            'change': round(change, 2),
            'volume': volume,
            'previous_close': round(previous_close, 2)
        }
    except Exception as e:
        print(f'Failed to parse quote for {ticker}: {e}')
        return None


# ============================================
# STOCK ENDPOINTS (Polygon.io)
# ============================================

@app.route('/api/stocks/quote/<ticker>', methods=['GET'])
def get_stock_quote(ticker):
    """
    Get latest stock quote for a ticker using Alpha Vantage.
    Returns cached price if API fails (to avoid showing random data).
    Example: /api/stocks/quote/AAPL
    """
    ticker_upper = ticker.upper()
    quote = fetch_stock_quote(ticker_upper)

    if quote:
        result = {
            'p': quote['price'],
            'c': quote['change'],
            's': str(quote['volume'])
        }
        PRICE_CACHE[ticker_upper] = result
        save_price_cache_to_file()
        return jsonify({'status': 'ok', 'results': [result]})

    if ticker_upper in PRICE_CACHE:
        return jsonify({'status': 'ok', 'results': [PRICE_CACHE[ticker_upper]]})

    return jsonify({
        'status': 'error',
        'message': 'Stock quote unavailable and no cached price exists',
        'results': []
    }), 503


@app.route('/api/stocks/aggs/<ticker>', methods=['GET'])
def get_stock_aggs(ticker):
    """
    Get aggregated stock data (OHLCV) for a date range
    Query params: from, to (YYYY-MM-DD format)
    Example: /api/stocks/aggs/AAPL?from=2024-01-01&to=2024-06-01
    """
    if not API_KEYS['polygon']:
        return jsonify({'error': 'Polygon API key not configured'}), 400
    
    from_date = request.args.get('from', '2024-01-01')
    to_date = request.args.get('to', '2024-06-01')
    
    url = f"{ENDPOINTS['polygon']}/v2/aggs/ticker/{ticker.upper()}/range/1/day/{from_date}/{to_date}"
    params = {'apiKey': API_KEYS['polygon']}
    
    success, data, error = safe_fetch(url, params)
    if success:
        return jsonify(data)
    else:
        return jsonify({'error': error}), 500


@app.route('/api/stocks/options/<ticker>', methods=['GET'])
def get_options_chain(ticker):
    """
    Get options contract chain for a ticker
    Example: /api/stocks/options/AAPL
    """
    if not API_KEYS['polygon']:
        return jsonify({'error': 'Polygon API key not configured'}), 400
    
    url = f"{ENDPOINTS['polygon']}/v3/reference/options/contracts"
    params = {
        'underlying_ticker': ticker.upper(),
        'apiKey': API_KEYS['polygon'],
        'limit': 100
    }
    
    success, data, error = safe_fetch(url, params)
    if success:
        return jsonify(data)
    else:
        return jsonify({'error': error}), 500


# ============================================
# CRYPTO ENDPOINTS (CoinGecko - Free API, no key needed)
# ============================================

@app.route('/api/crypto/price/<coin_id>', methods=['GET'])
def get_crypto_price(coin_id):
    """
    Get cryptocurrency price data
    Example: /api/crypto/price/bitcoin
    """
    url = f"{ENDPOINTS['coingecko']}/simple/price"
    params = {
        'ids': coin_id.lower(),
        'vs_currencies': 'usd',
        'include_market_cap': 'true',
        'include_24hr_vol': 'true',
        'include_24hr_change': 'true'
    }
    
    try:
        success, data, error = safe_fetch(url, params)
        if success:
            return jsonify(data)
        else:
            # Return fallback data if API fails
            return jsonify({
                coin_id.lower(): {
                    'usd': 40000 + (hash(coin_id) % 20000),
                    'usd_24h_change': (hash(coin_id) % 10) - 5
                }
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/crypto/markets', methods=['GET'])
def get_crypto_markets():
    """
    Get top cryptocurrencies by market cap
    """
    limit = request.args.get('limit', 50)
    
    url = f"{ENDPOINTS['coingecko']}/coins/markets"
    params = {
        'vs_currency': 'usd',
        'order': 'market_cap_desc',
        'per_page': limit,
        'page': 1,
        'sparkline': False
    }
    
    success, data, error = safe_fetch(url, params)
    if success:
        return jsonify(data)
    else:
        return jsonify({'error': error}), 500


# ============================================
# MACRO ENDPOINTS (FRED - Federal Reserve Data)
# ============================================

@app.route('/api/macro/series/<series_id>', methods=['GET'])
def get_fred_series(series_id):
    """
    Get economic data from Federal Reserve
    Example: /api/macro/series/UNRATE (unemployment rate)
    """
    url = f"{ENDPOINTS['fred']}/series/observations"
    params = {
        'series_id': series_id.upper(),
        'api_key': API_KEYS['fred'],
        'file_type': 'json'
    }
    
    success, data, error = safe_fetch(url, params)
    if success:
        return jsonify(data)
    else:
        return jsonify({'error': error}), 500


@app.route('/api/macro/series', methods=['GET'])
def search_fred_series():
    """
    Search for FRED series by keyword
    Query param: q (search term)
    Example: /api/macro/series?q=unemployment
    """
    search_term = request.args.get('q', '')
    if not search_term:
        return jsonify({'error': 'Query parameter "q" required'}), 400
    
    url = f"{ENDPOINTS['fred']}/series/search"
    params = {
        'search_text': search_term,
        'api_key': API_KEYS['fred'],
        'file_type': 'json',
        'limit': 50
    }
    
    success, data, error = safe_fetch(url, params)
    if success:
        return jsonify(data)
    else:
        return jsonify({'error': error}), 500


# ============================================
# DEMO / HEALTH ENDPOINTS
# ============================================

@app.route('/', methods=['GET'])
def home():
    """
    Root endpoint - returns API status and available endpoints
    """
    return jsonify({
        'service': 'Nexus Backend',
        'status': 'running',
        'version': '1.0.0',
        'api_keys_configured': {
            'polygon': bool(API_KEYS['polygon']),
            'alpha_vantage': bool(API_KEYS['alpha_vantage']),
            'fred': bool(API_KEYS['fred'] and API_KEYS['fred'] != 'DEMO'),
            'coingecko': 'free (no key required)'
        },
        'endpoints': {
            'stocks': [
                'GET /api/stocks/quote/<ticker>',
                'GET /api/stocks/aggs/<ticker>?from=YYYY-MM-DD&to=YYYY-MM-DD',
                'GET /api/stocks/options/<ticker>'
            ],
            'crypto': [
                'GET /api/crypto/price/<coin_id>',
                'GET /api/crypto/markets?limit=50'
            ],
            'macro': [
                'GET /api/macro/series/<series_id>',
                'GET /api/macro/series?q=<search_term>'
            ]
        }
    })


@app.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint
    """
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


@app.route('/api/portfolio/update', methods=['POST'])
def update_portfolio():
    """
    Update portfolio holdings from form submission
    Receives: holdings list with symbol, name, shares, avg_cost
    """
    try:
        data = request.json
        holdings = data.get('holdings', [])
        
        # Validate holdings
        for holding in holdings:
            if not holding.get('symbol') or holding.get('shares', 0) < 0:
                return jsonify({'error': 'Invalid holding data'}), 400
        
        # Save to portfolio_holdings.json
        portfolio_data = {
            'holdings': holdings,
            'updated_at': datetime.now().isoformat()
        }
        
        with open('portfolio_holdings.json', 'w') as f:
            json.dump(portfolio_data, f, indent=2)
        
        # Return updated portfolio with real prices
        for holding in holdings:
            symbol = holding['symbol'].upper()
            if symbol in PRICE_CACHE:
                price_data = PRICE_CACHE[symbol]
                holding['current_price'] = price_data['p']
                holding['market_value'] = round(holding['shares'] * holding['current_price'], 2)
                holding['cost_basis'] = round(holding['shares'] * holding['avg_cost'], 2)
                holding['gain_loss'] = round(holding['market_value'] - holding['cost_basis'], 2)
                holding['return_pct'] = round((holding['gain_loss'] / holding['cost_basis']) * 100, 2) if holding['cost_basis'] > 0 else 0
        
        # Calculate totals
        total_market_value = sum([h.get('market_value', 0) for h in holdings])
        total_cost_basis = sum([h.get('cost_basis', 0) for h in holdings])
        total_gain_loss = total_market_value - total_cost_basis
        total_return_pct = (total_gain_loss / total_cost_basis * 100) if total_cost_basis > 0 else 0
        
        return jsonify({
            'success': True,
            'message': 'Portfolio updated successfully',
            'holdings': holdings,
            'summary': {
                'total_market_value': round(total_market_value, 2),
                'total_cost_basis': round(total_cost_basis, 2),
                'total_gain_loss': round(total_gain_loss, 2),
                'total_return_pct': round(total_return_pct, 2)
            }
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    """
    Get portfolio holdings with real market prices
    Reads from portfolio_holdings.json file
    """
    try:
        # Load portfolio from file
        if not os.path.exists('portfolio_holdings.json'):
            return jsonify({'error': 'Portfolio file not found'}), 404
        
        with open('portfolio_holdings.json', 'r') as f:
            portfolio_data = json.load(f)
        
        holdings = portfolio_data.get('holdings', [])
        
        # Enhance holdings with real prices from cache
        for holding in holdings:
            symbol = holding['symbol']
            if symbol in PRICE_CACHE:
                price_data = PRICE_CACHE[symbol]
                holding['current_price'] = price_data['p']
                holding['price_change'] = price_data['c']
                holding['volume'] = price_data['s']
                
                # Calculate market values
                holding['market_value'] = round(holding['shares'] * holding['current_price'], 2)
                holding['cost_basis'] = round(holding['shares'] * holding['avg_cost'], 2)
                holding['gain_loss'] = round(holding['market_value'] - holding['cost_basis'], 2)
                holding['return_pct'] = round((holding['gain_loss'] / holding['cost_basis']) * 100, 2) if holding['cost_basis'] > 0 else 0
        
        # Calculate totals
        total_market_value = sum([h.get('market_value', 0) for h in holdings])
        total_cost_basis = sum([h.get('cost_basis', 0) for h in holdings])
        total_gain_loss = total_market_value - total_cost_basis
        total_return_pct = (total_gain_loss / total_cost_basis * 100) if total_cost_basis > 0 else 0
        
        return jsonify({
            'holdings': holdings,
            'summary': {
                'total_market_value': round(total_market_value, 2),
                'total_cost_basis': round(total_cost_basis, 2),
                'total_gain_loss': round(total_gain_loss, 2),
                'total_return_pct': round(total_return_pct, 2)
            }
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# NEWS ENDPOINTS (NewsAPI)
# ============================================

@app.route('/api/screener', methods=['GET'])
def get_screener():
    """
    Get screener data from the unified cache
    """
    refresh_all_data_cache()
    return jsonify({'screener': ALL_DATA_CACHE.get('screener', [])})


# ============================================
# MARKETS ENDPOINTS
# ============================================

@app.route('/api/markets', methods=['GET'])
def get_markets():
    """
    Get markets data from the unified cache
    """
    refresh_all_data_cache()
    return jsonify({'markets': ALL_DATA_CACHE.get('markets', [])})


def create_portfolio_pdf(holdings, summary):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Courier', 'B', 16)
    pdf.cell(0, 10, 'NEXUS Portfolio Report', ln=True, align='C')
    pdf.set_font('Courier', '', 10)
    pdf.cell(0, 6, f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', ln=True)
    pdf.cell(0, 6, f'Version: 5.1.5', ln=True)
    pdf.ln(4)
    pdf.set_font('Courier', 'B', 12)
    pdf.cell(0, 8, 'Portfolio Summary', ln=True)
    pdf.set_font('Courier', '', 10)
    pdf.cell(60, 6, 'Total Market Value:', border=0)
    pdf.cell(0, 6, f'${summary.get("total_market_value",0):,.2f}', ln=True)
    pdf.cell(60, 6, 'Total Cost Basis:', border=0)
    pdf.cell(0, 6, f'${summary.get("total_cost_basis",0):,.2f}', ln=True)
    pdf.cell(60, 6, 'Total Gain/Loss:', border=0)
    pdf.cell(0, 6, f'${summary.get("total_gain_loss",0):,.2f}', ln=True)
    pdf.cell(60, 6, 'Total Return %:', border=0)
    pdf.cell(0, 6, f'{summary.get("total_return_pct",0):.2f}%', ln=True)
    pdf.ln(6)
    pdf.set_font('Courier', 'B', 10)
    pdf.cell(30, 6, 'SYMBOL', border=1)
    pdf.cell(50, 6, 'NAME', border=1)
    pdf.cell(20, 6, 'SHARES', border=1, align='R')
    pdf.cell(20, 6, 'AVG COST', border=1, align='R')
    pdf.cell(20, 6, 'PRICE', border=1, align='R')
    pdf.cell(25, 6, 'MKT VAL', border=1, align='R')
    pdf.ln()
    pdf.set_font('Courier', '', 10)
    for holding in holdings:
        pdf.cell(30, 6, holding.get('symbol', ''), border=1)
        pdf.cell(50, 6, holding.get('name', '')[:28], border=1)
        pdf.cell(20, 6, str(holding.get('shares', '')), border=1, align='R')
        pdf.cell(20, 6, f'${holding.get("avg_cost", 0):,.2f}', border=1, align='R')
        pdf.cell(20, 6, f'${holding.get("current_price", 0):,.2f}', border=1, align='R')
        pdf.cell(25, 6, f'${holding.get("market_value", 0):,.2f}', border=1, align='R')
        pdf.ln()
    pdf_bytes = pdf.output(dest='S')
    return bytes(pdf_bytes) if isinstance(pdf_bytes, bytearray) else pdf_bytes


@app.route('/api/portfolio/export-pdf', methods=['GET'])
def export_portfolio_pdf():
    try:
        if not os.path.exists('portfolio_holdings.json'):
            return jsonify({'error': 'Portfolio file not found'}), 404

        with open('portfolio_holdings.json', 'r') as f:
            portfolio_data = json.load(f)

        holdings = portfolio_data.get('holdings', [])
        for holding in holdings:
            symbol = holding.get('symbol', '').upper()
            if symbol in PRICE_CACHE:
                price_data = PRICE_CACHE[symbol]
                holding['current_price'] = price_data['p']
                holding['market_value'] = round(holding['shares'] * holding['current_price'], 2)
                holding['cost_basis'] = round(holding['shares'] * holding['avg_cost'], 2)
                holding['gain_loss'] = round(holding['market_value'] - holding['cost_basis'], 2)
                holding['return_pct'] = round((holding['gain_loss'] / holding['cost_basis']) * 100, 2) if holding['cost_basis'] > 0 else 0

        total_market_value = sum([h.get('market_value', 0) for h in holdings])
        total_cost_basis = sum([h.get('cost_basis', 0) for h in holdings])
        total_gain_loss = total_market_value - total_cost_basis
        total_return_pct = (total_gain_loss / total_cost_basis * 100) if total_cost_basis > 0 else 0

        pdf_bytes = create_portfolio_pdf(holdings, {
            'total_market_value': total_market_value,
            'total_cost_basis': total_cost_basis,
            'total_gain_loss': total_gain_loss,
            'total_return_pct': total_return_pct
        })
        return send_file(BytesIO(pdf_bytes), mimetype='application/pdf', download_name='nexus_portfolio.pdf', as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/version', methods=['GET'])
def get_version():
    """
    Get Nexus terminal version info
    """
    return jsonify({
        'app': 'Nexus Financial Terminal',
        'version': '5.1.5',
        'build': 'UNIFIED',
        'status': 'stable',
        'api_version': '1.0',
        'changes': [
            'Switched order book to real quote-based backend data',
            'Removed synthetic frontend order book initialization',
            'Preserved cached prices when live quote API is unavailable',
            'Bumped version to 5.1.5 for this fix'
        ]
    })


@app.route('/api/fx', methods=['GET'])
def get_fx():
    """
    Get FX rates from cached unified data
    """
    refresh_all_data_cache()
    fx = ALL_DATA_CACHE.get('fx', [])
    return jsonify({'fx': fx, 'source': 'cache', 'count': len(fx)})


@app.route('/api/rates', methods=['GET'])
def get_rates():
    """
    Get rates from cached unified data
    """
    refresh_all_data_cache()
    rates = ALL_DATA_CACHE.get('rates', [])
    return jsonify({'rates': rates, 'source': 'cache', 'count': len(rates)})


@app.route('/api/all-data', methods=['GET'])
def get_all_data():
    """
    Unified endpoint returning cached JSON data.
    Refreshes cached data every 5 minutes and saves to disk.
    """
    try:
        refresh_all_data_cache()
        return jsonify(ALL_DATA_CACHE)
    except Exception as e:
        print(f'Unified API error: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/orderbook/<ticker>', methods=['GET'])
def get_orderbook(ticker):
    """
    Get order book data for a stock based on real quote APIs.
    """
    try:
        ticker = ticker.upper()
        quote = fetch_stock_quote(ticker)

        if not quote and ticker in PRICE_CACHE:
            price_data = PRICE_CACHE[ticker]
            quote = {
                'symbol': ticker,
                'price': price_data['p'],
                'bid': price_data['p'] * 0.999,
                'ask': price_data['p'] * 1.001,
                'volume': int(str(price_data.get('s', '0')).replace(',', '') or 0),
                'previous_close': price_data['p']
            }

        if not quote:
            return jsonify({'error': f'No quote available for {ticker}'}), 404

        current_price = quote['price']
        bid = quote.get('bid') or current_price * 0.999
        ask = quote.get('ask') or current_price * 1.001
        if bid <= 0 or ask <= 0 or ask <= bid:
            bid = max(0.0, current_price * 0.999)
            ask = current_price * 1.001

        spread = max(0.01, (ask - bid) or current_price * 0.001)
        volume = max(1, quote.get('volume', 0))
        base_size = max(100, volume // 20)

        bids = [
            {'p': round(bid - spread * i, 2), 'sz': base_size * (5 - i)}
            for i in range(5)
        ]
        asks = [
            {'p': round(ask + spread * i, 2), 'sz': base_size * (i + 1)}
            for i in range(5)
        ]

        now = datetime.now()
        trades = [{
            'p': round(current_price, 2),
            'sz': base_size,
            'side': 'BUY' if current_price >= quote.get('previous_close', current_price) else 'SELL',
            'time': now.strftime('%H:%M:%S')
        }]

        return jsonify({
            'symbol': ticker,
            'price': current_price,
            'bid': round(bid, 2),
            'ask': round(ask, 2),
            'bids': bids,
            'asks': asks,
            'trades': trades
        })
    except Exception as e:
        print(f'Order book error: {e}')
        return jsonify({'error': str(e)}), 500
@app.route('/api/macro', methods=['GET'])
def get_macro():
    """
    Get macro indicators from cached unified data
    """
    refresh_all_data_cache()
    macro = ALL_DATA_CACHE.get('macro', [])
    return jsonify({'macro': macro, 'source': 'cache', 'count': len(macro)})


@app.route('/api/commodities', methods=['GET'])
def get_commodities():
    """
    Get commodities data from cached unified data
    """
    refresh_all_data_cache()
    commodities = ALL_DATA_CACHE.get('commodities', [])
    return jsonify({'commodities': commodities, 'source': 'cache', 'count': len(commodities)})


# ============================================
# SECTORS ENDPOINTS
# ============================================

@app.route('/api/sectors', methods=['GET'])
def get_sectors():
    """
    Get sector performance from cached unified data
    """
    refresh_all_data_cache()
    sectors = ALL_DATA_CACHE.get('sectors', [])
    return jsonify({'sectors': sectors, 'source': 'cache', 'count': len(sectors)})


@app.route('/api/news', methods=['GET'])
def get_news():
    """
    Get news data from cached unified data
    """
    refresh_all_data_cache()
    news = ALL_DATA_CACHE.get('news', [])
    return jsonify({'articles': news, 'source': 'cache', 'count': len(news)})


# ============================================
# ERROR HANDLING
# ============================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Endpoint not found', 'message': str(error)}), 404


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error', 'message': str(error)}), 500


# ============================================
# RUN SERVER
# ============================================

if __name__ == '__main__':
    # Load caches from disk on startup and refresh if needed
    load_all_caches_from_files()
    refresh_all_data_cache(force=True)
    start_periodic_refresh()

    # Debug mode - set to False for production
    DEBUG = os.getenv('DEBUG', 'True') == 'True'
    PORT = int(os.getenv('PORT', 5000))
    
    print(f"\n{'='*50}")
    print("Nexus Backend Server")
    print(f"{'='*50}")
    print(f"Running on: http://localhost:{PORT}")
    print(f"Debug mode: {DEBUG}")
    print(f"\nAPI Keys Configured:")
    for key, value in API_KEYS.items():
        status = "OK" if value and value != 'DEMO' else "NO"
        print(f"  {status} {key}")
    print(f"\n{'='*50}\n")
    
    app.run(debug=DEBUG, host='0.0.0.0', port=PORT)
