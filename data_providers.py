import logging
import requests
import time
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf
from config import Config

logger = logging.getLogger(__name__)

class DataProviderError(Exception):
    pass

def fetch_daily_ohlcv(symbol: str, period: str = "90d", providers: list = None) -> pd.DataFrame:
    """Fetch daily OHLCV data with fallback chain: yfinance -> Polygon -> AlphaVantage -> Finnhub"""
    if providers is None:
        providers = ['yfinance', 'polygon', 'alphavantage', 'finnhub']

    # Fix symbol format (NSE stocks often need .NS for yfinance, but sometimes no suffix for others)
    yf_symbol = symbol if symbol.endswith('.NS') else f"{symbol}.NS"
    base_symbol = symbol.replace('.NS', '')
    
    # Try 1: yFinance
    if 'yfinance' in providers:
        try:
            logger.info(f"[yFinance] Fetching daily data for {yf_symbol}")
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period=period, interval='1d', auto_adjust=False)
            if not df.empty:
                logger.info(f"[yFinance] Success: {len(df)} rows")
                return _standardize_df(df)
            logger.warning("[yFinance] Returned empty dataframe")
        except Exception as e:
            logger.warning(f"[yFinance] Failed: {e}")

    # Calculate dates for API requests
    days = 90
    if period.endswith('d'):
        days = int(period[:-1])
    elif period.endswith('y'):
        days = int(period[:-1]) * 365
        
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Try 2: Polygon.io
    if 'polygon' in providers and Config.POLYGON_API_KEY:
        try:
            logger.info(f"[Polygon] Fetching daily data for {base_symbol}")
            url = f"https://api.polygon.io/v2/aggs/ticker/{base_symbol}/range/1/day/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
            res = requests.get(url, params={"apiKey": Config.POLYGON_API_KEY, "adjusted": "true"})
            if res.status_code == 200:
                data = res.json()
                if data.get('results'):
                    df = pd.DataFrame(data['results'])
                    df['Date'] = pd.to_datetime(df['t'], unit='ms')
                    df = df.rename(columns={'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume'})
                    df = df.set_index('Date')[['Open', 'High', 'Low', 'Close', 'Volume']]
                    logger.info(f"[Polygon] Success: {len(df)} rows")
                    return df
            logger.warning(f"[Polygon] Failed: {res.text}")
        except Exception as e:
            logger.warning(f"[Polygon] Exception: {e}")

    # Try 3: Alpha Vantage
    if 'alphavantage' in providers and Config.ALPHA_VANTAGE_API_KEY:
        try:
            logger.info(f"[AlphaVantage] Fetching daily data for {base_symbol}")
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "TIME_SERIES_DAILY",
                "symbol": base_symbol,
                "outputsize": "compact" if days <= 100 else "full",
                "apikey": Config.ALPHA_VANTAGE_API_KEY
            }
            res = requests.get(url, params=params)
            if res.status_code == 200:
                data = res.json()
                ts_key = "Time Series (Daily)"
                if ts_key in data:
                    df = pd.DataFrame.from_dict(data[ts_key], orient='index')
                    df.index = pd.to_datetime(df.index)
                    df = df.rename(columns={
                        '1. open': 'Open', '2. high': 'High', 
                        '3. low': 'Low', '4. close': 'Close', '5. volume': 'Volume'
                    }).astype(float)
                    df = df[df.index >= start_date]
                    df = df.sort_index()
                    logger.info(f"[AlphaVantage] Success: {len(df)} rows")
                    return df
            logger.warning(f"[AlphaVantage] Failed: {res.text}")
        except Exception as e:
            logger.warning(f"[AlphaVantage] Exception: {e}")

    # Try 4: Finnhub
    if 'finnhub' in providers and Config.FINNHUB_API_KEY:
        try:
            logger.info(f"[Finnhub] Fetching daily data for {base_symbol}")
            url = "https://finnhub.io/api/v1/stock/candle"
            params = {
                "symbol": base_symbol,
                "resolution": "D",
                "from": int(start_date.timestamp()),
                "to": int(end_date.timestamp()),
                "token": Config.FINNHUB_API_KEY
            }
            res = requests.get(url, params=params)
            if res.status_code == 200:
                data = res.json()
                if data.get('s') == 'ok':
                    df = pd.DataFrame(data)
                    df['Date'] = pd.to_datetime(df['t'], unit='s')
                    df = df.rename(columns={'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume'})
                    df = df.set_index('Date')[['Open', 'High', 'Low', 'Close', 'Volume']]
                    logger.info(f"[Finnhub] Success: {len(df)} rows")
                    return df
            logger.warning(f"[Finnhub] Failed: {res.text}")
        except Exception as e:
            logger.warning(f"[Finnhub] Exception: {e}")

    logger.error(f"All specified data providers failed for daily data: {symbol}")
    return None

def fetch_intraday_ohlcv(symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """Fetch 1-min OHLCV data with fallback chain: yfinance -> Polygon -> AlphaVantage"""
    yf_symbol = symbol if symbol.endswith('.NS') else f"{symbol}.NS"
    base_symbol = symbol.replace('.NS', '')
    
    # Try 1: yFinance (with retry)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"[yFinance] Fetching 1-min data for {yf_symbol}")
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(interval='1m', start=start_dt, end=end_dt, auto_adjust=False)
            if not df.empty:
                logger.info(f"[yFinance] Success: {len(df)} rows")
                return _standardize_df(df)
            break # empty df, break to fallback
        except Exception as e:
            err_str = str(e).lower()
            if 'rate' in err_str or 'too many' in err_str or '429' in err_str:
                wait = 2 ** (attempt + 1)
                logger.warning(f"[yFinance] Rate limited, waiting {wait}s...")
                time.sleep(wait)
                if attempt == max_retries - 1:
                    logger.warning("[yFinance] Rate limits exhausted")
            else:
                logger.warning(f"[yFinance] Failed: {e}")
                break

    # Try 2: Polygon.io
    if Config.POLYGON_API_KEY:
        try:
            logger.info(f"[Polygon] Fetching 1-min data for {base_symbol}")
            url = f"https://api.polygon.io/v2/aggs/ticker/{base_symbol}/range/1/minute/{int(start_dt.timestamp()*1000)}/{int(end_dt.timestamp()*1000)}"
            res = requests.get(url, params={"apiKey": Config.POLYGON_API_KEY, "adjusted": "true"})
            if res.status_code == 200:
                data = res.json()
                if data.get('results'):
                    df = pd.DataFrame(data['results'])
                    df['Date'] = pd.to_datetime(df['t'], unit='ms')
                    df = df.rename(columns={'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume'})
                    df = df.set_index('Date')[['Open', 'High', 'Low', 'Close', 'Volume']]
                    logger.info(f"[Polygon] Success: {len(df)} rows")
                    return df
            logger.warning(f"[Polygon] Failed: {res.text}")
        except Exception as e:
            logger.warning(f"[Polygon] Exception: {e}")

    # Try 3: Alpha Vantage
    if Config.ALPHA_VANTAGE_API_KEY:
        try:
            logger.info(f"[AlphaVantage] Fetching 1-min data for {base_symbol}")
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "TIME_SERIES_INTRADAY",
                "symbol": base_symbol,
                "interval": "1min",
                "outputsize": "full",
                "apikey": Config.ALPHA_VANTAGE_API_KEY
            }
            res = requests.get(url, params=params)
            if res.status_code == 200:
                data = res.json()
                ts_key = "Time Series (1min)"
                if ts_key in data:
                    df = pd.DataFrame.from_dict(data[ts_key], orient='index')
                    df.index = pd.to_datetime(df.index)
                    df = df.rename(columns={
                        '1. open': 'Open', '2. high': 'High', 
                        '3. low': 'Low', '4. close': 'Close', '5. volume': 'Volume'
                    }).astype(float)
                    df = df[(df.index >= start_dt) & (df.index <= end_dt)]
                    df = df.sort_index()
                    logger.info(f"[AlphaVantage] Success: {len(df)} rows")
                    return df
            logger.warning(f"[AlphaVantage] Failed: {res.text}")
        except Exception as e:
            logger.warning(f"[AlphaVantage] Exception: {e}")

    logger.error(f"All data providers failed for intraday data: {symbol}")
    return None

def _standardize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure standard Index and Columns for yFinance DataFrame"""
    if getattr(df.index, 'tz', None) is not None:
        df.index = df.index.tz_localize(None)
    df.columns = [col.lower().replace(' ', '_') for col in df.columns]
    df.columns = [col.title().replace('_', '') for col in df.columns]
    df.index.name = 'Date'
    return df
