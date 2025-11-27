import os
import dotenv
import logging
from sys import stdout
import traceback
from flask import Flask, request, jsonify, session, redirect, current_app
from flask_cors import CORS
from functools import wraps
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import requests
import secrets
import jwt
import yfinance as yf
import pandas as pd
import numpy as np
import statistics
import math
import re
from typing import List, Dict, Tuple, Optional

# Load environment variables (from .env or deployment environment)
dotenv.load_dotenv()

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    handlers=[logging.StreamHandler(stdout)]
)
logger = logging.getLogger(__name__)

# ==================== DATA STORAGE (Global Scope) ====================
user_sessions = {}
latest_symbol_data = {}
conversation_context = {}
SESSION_TIMEOUT = timedelta(minutes=30)


# ==================== CONFIGURATION ====================
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'http://localhost:5000/oauth2callback')
CLIENT_REDIRECT_URL = os.getenv('CLIENT_REDIRECT_URL', 'http://localhost:5000')

ACCESS_TOKEN_JWT_SECRET = os.getenv('ACCESS_TOKEN_JWT_SECRET', secrets.token_hex(32))
REFRESH_TOKEN_JWT_SECRET = os.getenv('REFRESH_TOKEN_JWT_SECRET', secrets.token_hex(32))
ACCESS_TOKEN_EXPIRETIME = os.getenv('ACCESS_TOKEN_EXPIRETIME', '15m')
REFRESH_TOKEN_EXPIRETIME = os.getenv('REFRESH_TOKEN_EXPIRETIME', '7d')

SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/generative-language.peruserquota',
    "https://www.googleapis.com/auth/generative-language.retriever",
    "https://www.googleapis.com/auth/generative-language.tuning"
]


# ==================== AUTH HELPER FUNCTIONS ====================
def parse_time_to_seconds(time_str: str) -> int:
    """Convert time string like '15m' or '7d' to seconds"""
    if time_str.endswith('m'):
        return int(time_str[:-1]) * 60
    elif time_str.endswith('h'):
        return int(time_str[:-1]) * 3600
    elif time_str.endswith('d'):
        return int(time_str[:-1]) * 86400
    return 900


def generate_jwt_token(user_data: dict, secret: str, expires_in: str) -> str:
    """Generate JWT token"""
    expiry_seconds = parse_time_to_seconds(expires_in)
    payload = {
        'user_id': user_data['user_id'],
        'email': user_data['email'],
        'name': user_data.get('name', ''),
        'exp': datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds),
        'iat': datetime.now(timezone.utc)
    }
    return jwt.encode(payload, secret, algorithm='HS256')


def verify_jwt_token(token: str, secret: str) -> Optional[dict]:
    """Verify JWT token"""
    try:
        return jwt.decode(token, secret, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def set_token_cookies(response, access_token: str, refresh_token: str):
    """Set cookies safely so browser actually stores them."""
    is_production = current_app.config.get('SESSION_COOKIE_SECURE', False)
    cookie_domain = os.getenv('COOKIE_DOMAIN') if is_production else None

    response.set_cookie(
        'access_token',
        access_token,
        httponly=True,
        secure=is_production,
        samesite='Lax',
        max_age=parse_time_to_seconds(ACCESS_TOKEN_EXPIRETIME),
        domain=cookie_domain
    )

    response.set_cookie(
        'refresh_token',
        refresh_token,
        httponly=True,
        secure=is_production,
        samesite='Lax',
        max_age=parse_time_to_seconds(REFRESH_TOKEN_EXPIRETIME),
        domain=cookie_domain
    )

    return response


def refresh_oauth_token(user_id: str) -> bool:
    """Refresh OAuth token"""
    if user_id not in user_sessions:
        return False

    user_session = user_sessions[user_id]
    refresh_token = user_session.get('refresh_token')

    if not refresh_token:
        logger.warning(f"No refresh token for user {user_id}")
        return False

    try:
        logger.info(f"🔄 Refreshing OAuth token for user {user_id}")
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            },
            timeout=10
        )

        if response.status_code == 200:
            tokens = response.json()
            user_session['oauth_token'] = tokens['access_token']
            user_session['token_expiry'] = datetime.now(timezone.utc) + timedelta(seconds=tokens.get('expires_in', 3600))
            logger.info(f"✅ OAuth token refreshed for user {user_id}")
            return True
        else:
            logger.error(f"❌ Token refresh failed ({response.status_code}): {response.text}")
            return False

    except Exception as e:
        logger.error(f"❌ Exception during OAuth token refresh: {e}")
        return False


# ==================== AUTHENTICATION MIDDLEWARE ====================
def require_auth(f):
    """Authentication middleware"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        access_token = request.cookies.get('access_token')

        if access_token:
            payload = verify_jwt_token(access_token, ACCESS_TOKEN_JWT_SECRET)
            if payload:
                user_id = payload['user_id']
                if user_id in user_sessions:
                    user_session = user_sessions[user_id]
                    user_session['expires_at'] = datetime.now(timezone.utc) + SESSION_TIMEOUT
                    if datetime.now(timezone.utc) > user_session['token_expiry'] - timedelta(minutes=5):
                        refresh_oauth_token(user_id)
                    session['user_id'] = user_id
                    return f(*args, **kwargs)

        refresh_token_cookie = request.cookies.get('refresh_token')
        if refresh_token_cookie:
            payload = verify_jwt_token(refresh_token_cookie, REFRESH_TOKEN_JWT_SECRET)
            if payload:
                user_id = payload['user_id']
                if user_id in user_sessions:
                    user_data = user_sessions[user_id]
                    new_access_token = generate_jwt_token(user_data, ACCESS_TOKEN_JWT_SECRET, ACCESS_TOKEN_EXPIRETIME)
                    session['user_id'] = user_id
                    if datetime.now(timezone.utc) > user_data['token_expiry'] - timedelta(minutes=5):
                        if not refresh_oauth_token(user_id):
                            return jsonify({"error": "Token refresh failed"}), 401
                    response = jsonify({"error": "Access token refreshed. Please try the request again."})
                    set_token_cookies(response, new_access_token, refresh_token_cookie)
                    return f(*args, **kwargs)

        user_id = session.get('user_id')
        if not user_id or user_id not in user_sessions:
            return jsonify({"error": "Not authenticated. Please sign in."}), 401

        user_session = user_sessions[user_id]
        if datetime.now(timezone.utc) > user_session['expires_at']:
            del user_sessions[user_id]
            session.clear()
            return jsonify({"error": "Session expired. Please sign in again."}), 401

        user_session['expires_at'] = datetime.now(timezone.utc) + SESSION_TIMEOUT
        if datetime.now(timezone.utc) > user_session['token_expiry']:
            if not refresh_oauth_token(user_id):
                del user_sessions[user_id]
                session.clear()
                return jsonify({"error": "Authentication expired. Please sign in again."}), 401

        return f(*args, **kwargs)

    return decorated_function


# ==================== SESSION CLEANUP ====================
def cleanup_expired_sessions():
    """Clean up expired user sessions"""
    current_time = datetime.now(timezone.utc)
    expired_users = [
        user_id for user_id, session_data in user_sessions.items()
        if current_time > session_data['expires_at']
    ]
    for user_id in expired_users:
        del user_sessions[user_id]
        logger.info(f"🧹 Cleaned up expired session for user: {user_id}")


# ==================== ANALYSIS HELPER FUNCTIONS ====================
def convert_to_serializable(value):
    if pd.isna(value) or value is None: return None
    if isinstance(value, (np.integer, np.int64)): return int(value)
    if isinstance(value, (np.floating, np.float64)):
        if np.isnan(value) or np.isinf(value): return None
        return float(value)
    if isinstance(value, np.bool_): return bool(value)
    return value

def clean_df(df, columns):
    df = df.copy().reset_index()
    if 'Date' in df.columns:
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
    for col in columns:
        if col in df.columns:
            df[col] = df[col].apply(convert_to_serializable)
    cols_to_include = ['Date'] + [col for col in columns if col in df.columns]
    return df[cols_to_include].to_dict(orient='records')

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def compute_macd(series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal
    return macd, signal, histogram

def safe_get(d: Dict, key: str, default=None):
    v = d.get(key, default)
    return None if v is None else v

def mean_or(val_list, fallback=0.0):
    try:
        return statistics.mean(val_list) if val_list else fallback
    except Exception:
        return fallback

def linear_slope(y_values: List[float]) -> float:
    if not y_values or len(y_values) < 2: return 0.0
    x = np.arange(len(y_values))
    y = np.array(y_values, dtype=float)
    xv = x - x.mean()
    yv = y - y.mean()
    denom = (xv * xv).sum()
    if denom == 0: return 0.0
    return float((xv * yv).sum() / denom)

def find_recent_macd_crossover(latest_data: List[Dict], lookback: int = 14) -> Tuple[str, int]:
    n = len(latest_data)
    upper = max(1, n - lookback)
    for i in range(n - 1, upper - 1, -1):
        if i == 0: continue
        prev = latest_data[i - 1]
        curr = latest_data[i]
        prev_diff = safe_get(prev, 'MACD', 0) - safe_get(prev, 'Signal', 0)
        curr_diff = safe_get(curr, 'MACD', 0) - safe_get(curr, 'Signal', 0)
        if prev_diff <= 0 and curr_diff > 0: return 'bullish', n - i - 1
        if prev_diff >= 0 and curr_diff < 0: return 'bearish', n - i - 1
    return 'none', -1

def fmt_price(x):
    try:
        return f"${round(x, 2)}"
    except Exception:
        return str(x)

# ==================== GEMINI API CALLS ====================
def call_gemini_with_user_token(prompt: str, user_id: str, retry_count: int = 0) -> str:
    if user_id not in user_sessions:
        return "⚠️ **Authentication Required** – Please sign in to use AI analysis"

    user_session = user_sessions[user_id]
    oauth_token = user_session['oauth_token']
    granted_scopes = user_session.get('granted_scopes', [])
    required_scope = 'https://www.googleapis.com/auth/generative-language.peruserquota'

    if required_scope not in granted_scopes:
        return "⚠️ **Missing API Permissions** – Please sign out and sign in again to grant Gemini API access."

    try:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent",
            headers={"Authorization": f"Bearer {oauth_token}", "Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7, "topK": 40, "topP": 0.95, "maxOutputTokens": 1024}
            },
            timeout=30
        )

        if response.status_code == 401 and retry_count < 1:
            if refresh_oauth_token(user_id):
                return call_gemini_with_user_token(prompt, user_id, retry_count + 1)
            return "⚠️ **Session Expired** – Please sign in again"
        if response.status_code == 403:
            error_details = response.json() if response.text else {}
            return f"⚠️ **API Access Denied** – {error_details.get('error', {}).get('message', 'Permission denied')}"
        if response.status_code == 429: return "⚠️ **Rate Limit Exceeded** – Please wait and try again"
        if response.status_code != 200: return f"⚠️ **API Error {response.status_code}** – Please try again"

        result = response.json()
        if 'candidates' in result and len(result['candidates']) > 0:
            return result['candidates'][0]['content']['parts'][0]['text']
        return "⚠️ **Empty response from AI** – Please try again"

    except Exception as e:
        logger.error(f"❌ Gemini API error: {e}")
        return f"⚠️ **Error** – {str(e)}"

def format_data_for_ai_skimmable(symbol: str, data: list) -> str:
    if not data: return "No data available."
    latest = data[-1]
    prev = data[-2] if len(data) >= 2 else latest
    close, open_, ma5, ma10, rsi, macd, signal, hist, volume = (latest.get(k, 0) for k in ['Close', 'Open', 'MA5', 'MA10', 'RSI', 'MACD', 'Signal', 'Histogram', 'Volume'])
    summary = [
        f"**Date:** {latest.get('Date', 'N/A')} | **Close:** ${close:.2f} | {'Bullish 🟢' if close > open_ else 'Bearish 🔴'}",
        f"**RSI:** {rsi:.2f} | {'Overbought 🔥' if rsi > 70 else 'Oversold ❄️' if rsi < 30 else 'Neutral ✅'}",
        f"**MACD:** {macd:.2f} (Signal: {signal:.2f}) | Histogram: {hist:.2f}",
        f"**7-Day Trend:** {'Bullish 🟢' if close > prev.get('Close', close) else 'Bearish 🔴'}",
        f"**MA5:** ${ma5:.2f} | **MA10:** ${ma10:.2f} | {'Bullish Alignment 🟢' if ma5 > ma10 else 'Bearish Alignment 🔴'}"
    ]
    vols = [d.get('Volume', 0) for d in data if d.get('Volume')]
    avg_vol = sum(vols) / len(vols) if vols else 1
    vol_ratio = volume / avg_vol
    summary.append(f"**Volume:** {volume:,} ({vol_ratio:.2f}x avg) | {'Accumulation 📈' if vol_ratio > 1.1 else 'Distribution 📉' if vol_ratio < 0.9 else 'Stable ➡️'}")
    highs = [d.get('High', 0) for d in data]
    lows = [d.get('Low', 0) for d in data]
    summary.append(f"**Support:** ${min(lows):.2f} | **Resistance:** ${max(highs):.2f}")
    return "\n".join(summary)

def get_gemini_ai_analysis(symbol: str, data: list, user_id: str) -> str:
    data_summary = format_data_for_ai_skimmable(symbol, data)
    prompt = f"""You are a **top-tier quant analyst**. Analyze {symbol} in a **trader-friendly, skimmable way**. Provide:
1. **🎯 Executive Summary:** 1-2 sentences max, key insight.
2. **📊 Momentum & Trend:** Micro/short-term trends, bullish/bearish signals.
3. **⚡ Key Levels:** Support/resistance, MA alignment.
4. **📈 Volume Analysis:** Accumulation/distribution.
5. **🚨 Risks:** Top 3 immediate/medium-term risks.
6. **💡 Actionable Advice:** Clear entry, stop, targets for aggressive/conservative traders.
Use **bold, professional and robotic words**. Make it concise and **easy to read for recreational traders**.
## MARKET DATA
{data_summary}"""
    return call_gemini_with_user_token(prompt, user_id)

def generate_rule_based_analysis(symbol: str, latest_data: List[Dict], lookback: int = 14) -> str:
    try:
        if not latest_data or len(latest_data) < 7:
            return "### ⚠️ Analysis Unavailable\nInsufficient data for reliable analysis. Need at least 7 trading days."
        n, lb = len(latest_data), min(lookback, len(latest_data))
        window = latest_data[-lb:]
        required = ['Close', 'Volume', 'MA5', 'MA10', 'RSI', 'MACD', 'Signal', 'Histogram', 'High', 'Low']
        if missing := {f for row in window for f in required if f not in row or row.get(f) is None}:
            return f"### ⚠️ Analysis Unavailable\nMissing required fields: {', '.join(sorted(missing))}"
        
        latest = window[-1]
        close_price, rsi, macd, signal, hist, volume, ma5, ma10 = (float(latest.get(k, 0.0)) for k in ['Close', 'RSI', 'MACD', 'Signal', 'Histogram', 'Volume', 'MA5', 'MA10'])
        recent_high = round(max(float(d.get('High', -math.inf)) for d in window), 2)
        recent_low = round(min(float(d.get('Low', math.inf)) for d in window), 2)
        rsi_series, macd_series, hist_series, vol_series = ([float(d[k]) for d in window] for k in ['RSI', 'MACD', 'Histogram', 'Volume'])
        rsi_velocity = (rsi_series[-1] - rsi_series[0]) / max(1, len(rsi_series) - 1)
        macd_slope, hist_slope = linear_slope(macd_series), linear_slope(hist_series)
        macd_diff = macd - signal
        crossover_type, crossover_days_ago = find_recent_macd_crossover(window, lookback=lb)
        avg_vol = mean_or(vol_series, fallback=volume if volume > 0 else 1.0)
        volume_ratio = (volume / avg_vol) if avg_vol > 0 else 1.0
        price_vs_ma5, price_vs_ma10 = ("above" if close_price > ma5 else "below"), ("above" if close_price > ma10 else "below")
        ma_trend = "bullish" if ma5 > ma10 else "bearish"
        ma_spread_pct = abs(ma5 - ma10) / ma10 * 100 if ma10 != 0 else 0.0

        def rsi_zone_score_and_note(rsi_val, rsi_vel):
            if rsi_val < 30: return 2.0, "Oversold - potential reversal zone", "🟢"
            if rsi_val < 40: return 1.0, "Lower neutral (bearish pressure)", "🟢"
            if rsi_val < 60: return 0.5, "Neutral/healthy", "⚪"
            if rsi_val < 70: return 0.5 + (0.5 if rsi_vel > 1.5 else 0.0), "Bullish zone - momentum building", "🟡"
            if rsi_val < 75: return (0.5, "Overbought with strong continuation momentum", "🟡") if rsi_vel > 2.5 else (-1.0, "Overbought - caution (likely pullback)", "🔴")
            return (-2.0, "Extremely overbought - exhaustion likely", "🔴") if rsi_vel > 4.0 else (-1.5, "Severely overbought - high reversal risk", "🔴")
        
        rsi_score, rsi_note, rsi_emoji = rsi_zone_score_and_note(rsi, rsi_velocity)
        
        def macd_score_and_note(diff, slope, hist_slope_val, cross_type):
            diff_score = 3.0 if diff > 1.0 else 2.0 if diff > 0.3 else 1.0 if diff > 0.05 else -3.0 if diff < -1.0 else -2.0 if diff < -0.3 else -1.0 if diff < -0.05 else 0.0
            slope_score = 1.0 if slope > 0.005 else 0.5 if slope > 0.0005 else -1.0 if slope < -0.005 else -0.5 if slope < -0.0005 else 0.0
            hist_score = 1.5 if hist_slope_val > 0.005 else 0.75 if hist_slope_val > 0.0005 else -1.5 if hist_slope_val < -0.005 else -0.75 if hist_slope_val < -0.0005 else 0.0
            cross_bonus = 0.75 if cross_type == 'bullish' else -0.75 if cross_type == 'bearish' else 0.0
            return diff_score + slope_score + hist_score + cross_bonus, f"MACD diff={diff:.3f}, slope={slope:.4f}, hist_slope={hist_slope_val:.4f}"

        macd_score_val, macd_note = macd_score_and_note(macd_diff, macd_slope, hist_slope, crossover_type)
        price_pos_score = 1.5 if price_vs_ma5 == "above" and price_vs_ma10 == "above" else -1.5 if price_vs_ma5 == "below" and price_vs_ma10 == "below" else 0.8 if price_vs_ma5 == "above" else -0.8
        price_context_note = "Strong bullish position above MA5 & MA10" if price_pos_score == 1.5 else "Strong bearish position below MA5 & MA10" if price_pos_score == -1.5 else "Mixed with bullish bias" if price_pos_score == 0.8 else "Mixed with bearish bias"
        ma_score = (0.5 if ma_trend == "bullish" else -0.5) if ma_spread_pct > 2 else (0.25 if ma_trend == "bullish" else -0.25) if ma_spread_pct > 0.5 else 0.0
        volume_score = 1.0 if volume_ratio > 1.5 else 0.5 if volume_ratio > 1.1 else -0.5 if volume_ratio < 0.8 else -1.0 if volume_ratio < 0.5 else 0.0
        sentiment_score = rsi_score + macd_score_val + price_pos_score + ma_score + volume_score
        
        if sentiment_score >= 4.0: overall_sentiment, sentiment_emoji = "**STRONGLY BULLISH**", "🟢"
        elif sentiment_score >= 0.5: overall_sentiment, sentiment_emoji = "**BULLISH**", "🟡"
        elif sentiment_score <= -4.0: overall_sentiment, sentiment_emoji = "**STRONGLY BEARISH**", "🔴"
        elif sentiment_score <= -0.5: overall_sentiment, sentiment_emoji = "**MILDLY BEARISH**", "🟡"
        else: overall_sentiment, sentiment_emoji = "**NEUTRAL**", "⚪"

        bullish_signals = sum(1 for s in [macd_score_val, rsi_score, price_pos_score, ma_score, volume_score] if s > 0)
        bearish_signals = sum(1 for s in [macd_score_val, rsi_score, price_pos_score, ma_score, volume_score] if s < 0)
        confidence = "high" if abs(bullish_signals - bearish_signals) >= 4 and volume_ratio > 1.1 else "medium" if abs(bullish_signals - bearish_signals) >= 2 else "low"
        
        risk_note_parts = []
        conservative_stop = max(ma10, recent_low)
        trailing_stop_pct = 0.03 if sentiment_score > 2.0 else 0.06

        if "BULLISH" in overall_sentiment:
            if rsi >= 75 and hist_slope < -0.01:
                recommendation = f"**Wait / Avoid aggressive entries** — Overbought (RSI {rsi:.1f}) and momentum weakening."
                risk_note_parts.append("High RSI + weakening MACD histogram suggests pullback risk.")
            elif confidence == "high" and volume_ratio > 1.1:
                recommendation = f"**BUY** (scale-in allowed) — Trend confirmed. Entry near {fmt_price(close_price)}. Use trailing stop ~{int(trailing_stop_pct * 100)}% or stop at {fmt_price(conservative_stop)}."
            elif confidence == "medium":
                recommendation = f"**Cautiously BUY / scale in** — Entry near {fmt_price(close_price)}. Place stop at {fmt_price(conservative_stop)}; scale on pullback."
            else:
                recommendation = f"**Watch / Wait for cleaner setup** — Current score is low confidence. Wait for bullish confirmation or below {fmt_price(ma10)} for bearish."
        elif "BEARISH" in overall_sentiment:
            if rsi <= 25 and hist_slope > 0.01:
                recommendation = f"**Wait / Avoid aggressive shorts** — Oversold (RSI {rsi:.1f}) and momentum strengthening."
                risk_note_parts.append("Low RSI + strengthening MACD histogram suggests bounce risk.")
            elif confidence == "high" and volume_ratio > 1.1:
                recommendation = f"**SELL/SHORT** (scale-in allowed) — Trend confirmed. Entry near {fmt_price(close_price)}. Use trailing stop ~{int(trailing_stop_pct * 100)}% or stop at {fmt_price(recent_high)}."
            elif confidence == "medium":
                recommendation = f"**Cautiously SELL/SHORT / scale in** — Entry near {fmt_price(close_price)}. Place stop at {fmt_price(recent_high)}; scale on bounce."
            else:
                recommendation = f"**Watch / Wait for cleaner setup** — Current score is low confidence. Wait for bearish confirmation or above {fmt_price(ma10)} for bullish."
        else:
            recommendation = f"**HOLD / RANGE TRADE** — Neutral signals. Price is consolidating between {fmt_price(recent_low)} (Support) and {fmt_price(recent_high)} (Resistance). Wait for a decisive break."
            if volume_ratio > 1.1: risk_note_parts.append("High volume on neutral trend - potential for large move soon.")

        if volume_ratio < 0.8: risk_note_parts.append("Volume below average — low conviction.")
        if confidence == "low" and not any("conflicting" in s.lower() for s in risk_note_parts): risk_note_parts.append("Conflicting signals — trade with caution.")
        risk_note = " • ".join(risk_note_parts) if risk_note_parts else "None."

        return "\n".join([
            f"### {sentiment_emoji} Technical Analysis for {symbol}", "",
            f"**Overall Sentiment:** {overall_sentiment} ({confidence} confidence)", "",
            f"**Current Price:** {fmt_price(close_price)} ({price_context_note})", "",
            "#### 📊 Price Position Analysis",
            f"- Trading **{price_vs_ma5} MA5 ({fmt_price(ma5)})** and **{price_vs_ma10} MA10 ({fmt_price(ma10)})**",
            f"- **MA Alignment:** {ma_trend} (spread {ma_spread_pct:.2f}%)", "",
            "#### 🎯 MACD Analysis (Trend Following)",
            f"- MACD diff: {macd_diff:.3f}, slope: {macd_slope:.4f}, hist slope: {hist_slope:.4f}",
            f"- Recent crossover: {crossover_type} {crossover_days_ago} days ago" if crossover_type != 'none' else "",
            f"- {macd_note}", "",
            "#### 📈 RSI Analysis (Momentum)",
            f"- RSI at **{rsi:.2f}** {rsi_emoji} — {rsi_note} (velocity {rsi_velocity:.3f} pts/day)", "",
            "#### 📊 Volume Context",
            f"- Volume: {volume_ratio:.2f}x avg → {'strong' if volume_ratio > 1.1 else 'weak' if volume_ratio < 0.9 else 'average'}", "",
            "#### 💡 Recommendation", f"{recommendation}",
            f"\n**Risk Note:** {risk_note}" if risk_note else "", "",
            "#### 🧠 Key Levels to Watch",
            f"- **Support:** {fmt_price(recent_low)}",
            f"- **Resistance:** {fmt_price(recent_high)}"
        ])
    except Exception as e:
        logger.error(f"❌ Error in rule-based analysis: {e}")
        return f"### ❌ Analysis Error\nFailed to compute rule-based analysis: {str(e)}"

# ==================== ENVIRONMENT CONFIGURATION ====================
is_production = os.getenv('FLASK_ENV', 'development') == 'production'

# ==================== APPLICATION SETUP ====================
app = Flask(__name__, static_folder="static")
app.secret_key = os.getenv('FLASK_SECRET_KEY')
if not app.secret_key:
    if is_production:
        logger.critical("FATAL: FLASK_SECRET_KEY is required in production environment.")
        raise EnvironmentError("FLASK_SECRET_KEY is required in production environment.")
    else:
        app.secret_key = 'dev_fixed_key_for_local_testing_only'
        logger.warning("Using development fallback FLASK_SECRET_KEY.")

if is_production:
    # FIX: Set SameSite to 'None' for cross-domain OAuth to work with browsers' modern security policies.
    # This is necessary because the frontend (Vercel) and backend (Render) are on different domains.
    # 'None' requires the 'Secure' flag to be True, which is correctly set here for HTTPS.
    app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_SAMESITE='None')
    logger.info("Running in PRODUCTION mode. Session cookies are Secure and SameSite=None.")
else:
    # For local development (HTTP), 'Lax' is sufficient and correct.
    app.config.update(SESSION_COOKIE_SECURE=False, SESSION_COOKIE_SAMESITE='Lax')
    logger.info("Running in DEVELOPMENT mode. Session cookies are Insecure and SameSite=Lax.")

CORS(app, supports_credentials=True, origins=["http://localhost:3000", "http://localhost:5000", "https://budgetwarrenbuffet.vercel.app", CLIENT_REDIRECT_URL], methods=["GET", "POST", "OPTIONS"])
app.permanent_session_lifetime = timedelta(days=7)

# ==================== APPLICATION HOOKS & ERROR HANDLING ====================
@app.before_request
def cleanup_and_session_setup():
    """Run before every request to clean up expired sessions."""
    cleanup_expired_sessions()

@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler."""
    tb_str = traceback.format_exc()
    logger.error(f"Unhandled Exception: {e}\n{tb_str}")
    # In production, you might want to return a generic error page/JSON
    # For debugging, we can return the error details
    response = jsonify(error="An internal server error occurred.", details=str(e), traceback=tb_str)
    response.status_code = 500
    return response

# ==================== AUTHENTICATION ROUTES ====================
@app.route('/auth/login', methods=['GET'])
def auth_login():
    """Initiate Google OAuth flow."""
    try:
        state = secrets.token_urlsafe(32)
        session.permanent = True
        session['oauth_state'] = state
        session.modified = True

        auth_params = {
            'client_id': GOOGLE_CLIENT_ID,
            'redirect_uri': REDIRECT_URI,
            'response_type': 'code',
            'scope': ' '.join(SCOPES),
            'access_type': 'offline',
            'prompt': 'select_account',
            'state': state
        }
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(auth_params)}"
        
        resp = jsonify(success=True, auth_url=auth_url)
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return resp, 200
    except Exception as e:
        logger.error(f"❌ OAuth initiation error: {e}")
        return jsonify(error=f"Failed to initiate OAuth: {str(e)}"), 500

@app.route('/oauth2callback', methods=['GET'])
def oauth_callback():
    """Handle OAuth callback safely with detailed logging."""
    try:
        logger.info("--- OAuth Callback Start ---")
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        print("push")
        if error:
            logger.error(f"Google returned error: {error}")
            return redirect(f'{CLIENT_REDIRECT_URL}?error=auth_failed&reason={error}')

        if not code:
            logger.error("No 'code' parameter found in callback.")
            return redirect(f'{CLIENT_REDIRECT_URL}?error=no_code')

        stored_state = session.pop('oauth_state', None)
        if not stored_state:
            logger.error("No 'oauth_state' in session. Cookie might have been dropped or expired.")
            return redirect(f'{CLIENT_REDIRECT_URL}?error=invalid_state&reason=missing_session')

        if state != stored_state:
            logger.error(f"State mismatch. Received: '{state}', Stored: '{stored_state}'")
            return redirect(f'{CLIENT_REDIRECT_URL}?error=invalid_state&reason=state_mismatch')

        logger.info("State verified. Exchanging code for tokens...")
        token_data = {
            'code': code,
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code'
        }
        token_response = requests.post("https://oauth2.googleapis.com/token", data=token_data, timeout=10)

        if token_response.status_code != 200:
            logger.error(f"Token exchange failed ({token_response.status_code}): {token_response.text}")
            return redirect(f'{CLIENT_REDIRECT_URL}?error=token_exchange_failed')

        tokens = token_response.json()
        logger.info("Tokens received. Decoding ID token...")
        id_token = tokens.get('id_token')
        
        try:
            user_info = jwt.decode(id_token, options={"verify_signature": False})
        except Exception as e:
            logger.error(f"Failed to decode ID token: {e}")
            return redirect(f'{CLIENT_REDIRECT_URL}?error=invalid_id_token')

        user_id = user_info.get('sub')
        if not user_id:
            logger.error("No 'sub' (user_id) in ID token.")
            return redirect(f'{CLIENT_REDIRECT_URL}?error=missing_user_id')

        logger.info(f"User '{user_info.get('email')}' authenticated. Storing session.")
        user_sessions[user_id] = {
            'user_id': user_id,
            'email': user_info.get('email'),
            'name': user_info.get('name'),
            'picture': user_info.get('picture'),
            'oauth_token': tokens.get('access_token'),
            'refresh_token': tokens.get('refresh_token'),
            'token_expiry': datetime.now(timezone.utc) + timedelta(seconds=tokens.get('expires_in', 3600)),
            'expires_at': datetime.now(timezone.utc) + SESSION_TIMEOUT,
            'granted_scopes': tokens.get('scope', '').split(' ')
        }

        jwt_access = generate_jwt_token(user_sessions[user_id], ACCESS_TOKEN_JWT_SECRET, ACCESS_TOKEN_EXPIRETIME)
        jwt_refresh = generate_jwt_token(user_sessions[user_id], REFRESH_TOKEN_JWT_SECRET, REFRESH_TOKEN_EXPIRETIME)

        session['user_id'] = user_id
        response = redirect(f'{CLIENT_REDIRECT_URL}?auth=success')
        set_token_cookies(response, jwt_access, jwt_refresh)
        
        logger.info("--- OAuth Callback End: Success ---")
        return response

    except Exception as e:
        tb_str = traceback.format_exc()
        logger.error(f"CRITICAL ERROR in /oauth2callback: {e}\n{tb_str}")
        session.clear()
        return redirect(f'{CLIENT_REDIRECT_URL}?error=callback_crash&reason={str(e)}')

@app.route('/auth/token/refresh', methods=['POST'])
def refresh_token():
    try:
        refresh_token_cookie = request.cookies.get('refresh_token')
        if not refresh_token_cookie:
            return jsonify(error="No refresh token provided"), 401
        payload = verify_jwt_token(refresh_token_cookie, REFRESH_TOKEN_JWT_SECRET)
        if not payload:
            return jsonify(error="Invalid or expired refresh token"), 401
        user_id = payload['user_id']
        if user_id not in user_sessions:
            return jsonify(error="User session not found"), 401
        user_data = user_sessions[user_id]
        if user_data.get('refresh_token') and datetime.now(timezone.utc) > user_data['token_expiry'] - timedelta(minutes=5):
            refresh_oauth_token(user_id)
        new_access_token = generate_jwt_token(user_data, ACCESS_TOKEN_JWT_SECRET, ACCESS_TOKEN_EXPIRETIME)
        response = jsonify(success=True, message="Access token refreshed")
        set_token_cookies(response, new_access_token, refresh_token_cookie)
        return response, 200
    except Exception as e:
        logger.error(f"❌ Token refresh error: {e}")
        return jsonify(error="Internal token refresh error"), 500

@app.route('/auth/logout', methods=['POST'])
def logout():
    try:
        user_id = session.pop('user_id', None)
        if user_id and user_id in user_sessions:
            del user_sessions[user_id]
            logger.info(f"Logged out user: {user_id}")
        session.clear()
        response = jsonify(success=True, message="Logged out")
        response.set_cookie('access_token', '', max_age=0)
        response.set_cookie('refresh_token', '', max_age=0)
        return response, 200
    except Exception as e:
        logger.error(f"❌ Logout error: {e}")
        return jsonify(error="Logout failed"), 500

@app.route('/auth/status', methods=['GET'])
def auth_status():
    try:
        access_token = request.cookies.get('access_token')
        if not access_token:
            return jsonify(authenticated=False), 200
        payload = verify_jwt_token(access_token, ACCESS_TOKEN_JWT_SECRET)
        if payload:
            user_id = payload['user_id']
            if user_id in user_sessions:
                user_session = user_sessions[user_id]
                return jsonify(
                    authenticated=True,
                    user={
                        "email": user_session.get('email'),
                        "name": user_session.get('name'),
                        "picture": user_session.get('picture'),
                        "expires_in": int((user_session['expires_at'] - datetime.now(timezone.utc)).total_seconds())
                    }
                ), 200
        return jsonify(authenticated=False), 200
    except Exception as e:
        logger.error(f"❌ Auth status error: {e}")
        return jsonify(authenticated=False), 200

# ==================== API DATA ROUTES ====================
@app.route('/api/get_data', methods=['POST'])
@require_auth
def get_data():
    data = request.get_json()
    symbol = data.get('symbol', '').upper().strip()
    user_id = session.get('user_id')
    if not symbol:
        return jsonify(error="No symbol provided"), 400
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="90d", interval="1d")
        if hist.empty:
            return jsonify(error=f"Could not retrieve data for {symbol}"), 404
        hist['MA5'] = hist['Close'].rolling(window=5).mean()
        hist['MA10'] = hist['Close'].rolling(window=10).mean()
        hist['RSI'] = compute_rsi(hist['Close'])
        hist['MACD'], hist['Signal'], hist['Histogram'] = compute_macd(hist['Close'])
        hist_display = hist.dropna(subset=['MA5', 'MA10', 'RSI', 'MACD', 'Signal', 'Histogram'])
        latest_data_list = clean_df(hist_display, ['Open', 'High', 'Low', 'Close', 'Volume', 'MA5', 'MA10', 'RSI', 'MACD', 'Signal', 'Histogram'])
        latest_symbol_data[symbol] = latest_data_list
        rule_based_text = generate_rule_based_analysis(symbol, latest_data_list)
        gemini_analysis = get_gemini_ai_analysis(symbol, latest_data_list, user_id)
        if user_id not in conversation_context:
            conversation_context[user_id] = {"current_symbol": symbol, "conversation_history": [], "last_active": datetime.now(timezone.utc).isoformat(), "user_positions": {}}
        else:
            conversation_context[user_id]["current_symbol"] = symbol
            conversation_context[user_id]["last_active"] = datetime.now(timezone.utc).isoformat()
        return jsonify(
            ticker=symbol,
            OHLCV=clean_df(hist_display, ['Open', 'High', 'Low', 'Close', 'Volume']),
            MA=clean_df(hist_display, ['MA5', 'MA10']),
            RSI=[convert_to_serializable(x) for x in hist_display['RSI'].tolist()],
            MACD=clean_df(hist_display, ['MACD', 'Signal', 'Histogram']),
            AI_Review=gemini_analysis,
            Rule_Based_Analysis=rule_based_text
        ), 200
    except Exception as e:
        logger.error(f"❌ Error in /api/get_data: {e}")
        return jsonify(error=f"Server error: {str(e)}"), 500

@app.route('/api/chat', methods=['POST'])
@require_auth
def chat():
    data = request.get_json()
    query = data.get('query', '').strip()
    user_id = session.get('user_id')
    current_symbol_hint = data.get('current_symbol')
    if not query:
        return jsonify(error="No query provided"), 400
    try:
        if user_id not in conversation_context:
            conversation_context[user_id] = {"current_symbol": None, "conversation_history": [], "last_active": datetime.now(timezone.utc).isoformat(), "user_positions": {}}
        session_ctx = conversation_context[user_id]
        if "user_positions" not in session_ctx: session_ctx["user_positions"] = {}
        session_ctx["last_active"] = datetime.now(timezone.utc).isoformat()
        matched_symbol = next((s for s in latest_symbol_data.keys() if s.lower() in query.lower()), current_symbol_hint or session_ctx["current_symbol"])
        if matched_symbol and matched_symbol in latest_symbol_data:
            session_ctx["current_symbol"] = matched_symbol
        else:
            matched_symbol = None
        
        position_info, has_position = "", False
        if matched_symbol:
            position_match = re.search(r'(?:bought|sold|entry|long|short|got)\s+at\s+\$?(\d+\.?\d*)', query, re.IGNORECASE)
            if position_match:
                entry_price = float(position_match.group(1))
                session_ctx["user_positions"][matched_symbol] = {"entry_price": entry_price, "date": datetime.now(timezone.utc).isoformat()}
                position_info = f"The user just updated their position: they are **long** {matched_symbol} with an **entry price of ${entry_price}**."
            elif matched_symbol in session_ctx["user_positions"]:
                has_position = True
                entry = session_ctx["user_positions"][matched_symbol]['entry_price']
                current_price = latest_symbol_data[matched_symbol][-1]['Close']
                pnl_dollars, pnl_percent = current_price - entry, (current_price - entry) / entry * 100
                position_info = f"User has a position in {matched_symbol} with an **entry price of ${entry}**. Current price: ${current_price}. P&L: **${pnl_dollars:.2f} ({pnl_percent:.2f}%)**."
        
        technical_summary = generate_rule_based_analysis(matched_symbol, latest_symbol_data[matched_symbol]) if matched_symbol in latest_symbol_data else ""
        history_text = "\n".join(f"User: {h['user']}\nAssistant: {h['assistant']}" for h in session_ctx["conversation_history"][-3:])
        
        prompt = f"""You are an **experienced trading analyst chatbot** named **QuantAI**. Your goal is to provide concise, direct, and actionable advice to a recreational trader based on their question and the provided context.
RESPONSE GUIDELINES:
1. **Tone**: Sound like a savvy trader/mentor. Use simple, confident language.
2. **Context**: Use the CURRENT STOCK and TECHNICAL CONTEXT for analysis.
3. **Position**: If P&L is available, calculate it precisely and state it first.
4. **Length**: Be brief (2-3 sentences) unless they need detailed analysis.
5. If user mentions 'detailed', give a longer more in depth answer preferably in markdown.
CURRENT STOCK: {matched_symbol or 'None'}
{position_info}
TECHNICAL CONTEXT:
{technical_summary[:500] if technical_summary else 'No technical data available'}
CONVERSATION HISTORY (Last 3 turns):
{history_text}
USER QUESTION: {query}
RESPONSE RULES:
- If they ask about profit/loss and you have their entry price, CALCULATE IT EXACTLY.
- Reference their specific entry price if they gave you one.
- Be brief (2-3 sentences) unless they need detailed analysis.
- Sound like a trader chatting, not a robot.
Respond now:"""
        
        assistant_response = call_gemini_with_user_token(prompt, user_id)
        session_ctx["conversation_history"].append({"user": query, "assistant": assistant_response, "timestamp": datetime.now(timezone.utc).isoformat()})
        if len(session_ctx["conversation_history"]) > 15:
            session_ctx["conversation_history"] = session_ctx["conversation_history"][-15:]
        
        return jsonify(response=assistant_response, context={"current_symbol": matched_symbol, "has_position": has_position, "history_length": len(session_ctx["conversation_history"])}), 200
    except Exception as e:
        logger.error(f"❌ Chat handler error: {e}")
        return jsonify(error=f"Server error: {str(e)}"), 500

# ==================== STATIC FILE ROUTES ====================
@app.route('/')
def home():
    return app.send_static_file("index.html")

@app.route('/<path:path>')
def serve_static(path):
    return app.send_static_file(path)

@app.route('/health', methods=['GET'])
def health():
    return jsonify(status="healthy", services={"yfinance": "operational", "rule_based_analysis": "operational", "oauth_authentication": "enabled"}, version="4.0-Monolithic", active_sessions=len(user_sessions), env="production" if is_production else "development"), 200

# ==================== APPLICATION STARTUP ====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = '0.0.0.0'
    print("=" * 70)
    print(" 📊 STOCK ANALYSIS BACKEND v4.0 (MONOLITHIC)")
    print("=" * 70)
    print(f" 🚀 Server running on: http://{host}:{port}")
    print(f" 🔐 OAuth Status: {'✅ Configured' if GOOGLE_CLIENT_ID else '⚠️ Missing credentials'}")
    print(f" 🌍 Environment: {'Production (HTTPS required)' if is_production else 'Development (HTTP OK)'}")
    print(f" 📦 Secret Key Set: {'✅' if app.secret_key and app.secret_key != 'dev_fixed_key_for_local_testing_only' else '⚠️ Development Key'}")
    print("-" * 70)
    print(" 🔎 DIAGNOSING REGISTERED ROUTES:")
    with app.app_context():
        if any('auth' in str(rule) or 'oauth2callback' in str(rule) or 'api' in str(rule) for rule in app.url_map.iter_rules()):
            for rule in app.url_map.iter_rules():
                print(f"    ✅ ROUTE FOUND: {str(rule)} | Endpoint: {rule.endpoint}")
        else:
            print("    ❌ WARNING: No application routes registered. Flask app may be misconfigured.")
    print("-" * 70)
    app.run(host=host, port=port, debug=not is_production)
