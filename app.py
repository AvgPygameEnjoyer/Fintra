import os
import dotenv
import logging
from sys import stdout
from flask import Flask, request, jsonify, session, redirect, current_app
from flask_cors import CORS
from functools import wraps
from datetime import datetime, timedelta
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
from typing import List, Dict, Tuple

# Load environment variables (from .env or deployment environment)
dotenv.load_dotenv()

# ==================== DATA STORAGE (Global Scope) ====================
user_sessions = {}
latest_symbol_data = {}
conversation_context = {}
SESSION_TIMEOUT = timedelta(minutes=30)


# ==================== CONFIGURATION ====================
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
# NOTE: REDIRECT_URI must match the authorized redirect URI in Google Console
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
    # Required for API calls using user quota
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
        'exp': datetime.utcnow() + timedelta(seconds=expiry_seconds),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, secret, algorithm='HS256')


def verify_jwt_token(token: str, secret: str) -> dict:
    """Verify JWT token"""
    try:
        return jwt.decode(token, secret, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def set_token_cookies(response, access_token: str, refresh_token: str):
    """Set cookies safely so browser actually stores them."""
    # Check config dynamically
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
        print(f"❌ No refresh token for user {user_id}")
        return False

    try:
        print(f"🔄 Refreshing OAuth token for user {user_id}")

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
            user_session['token_expiry'] = datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600))
            print(f"✅ OAuth token refreshed for user {user_id}")
            return True
        else:
            print(f"❌ Token refresh failed ({response.status_code}): {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error refreshing OAuth token: {e}")
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
                    # User authenticated via valid JWT Access Token
                    user_session = user_sessions[user_id]
                    user_session['expires_at'] = datetime.now() + SESSION_TIMEOUT
                    # Check if Google token needs a refresh
                    if datetime.now() > user_session['token_expiry'] - timedelta(minutes=5):
                        refresh_oauth_token(user_id)
                    session['user_id'] = user_id
                    return f(*args, **kwargs)

        # Fallback to check JWT Refresh Token (if Access Token is missing or invalid)
        refresh_token_cookie = request.cookies.get('refresh_token')
        if refresh_token_cookie:
            payload = verify_jwt_token(refresh_token_cookie, REFRESH_TOKEN_JWT_SECRET)
            if payload:
                user_id = payload['user_id']
                if user_id in user_sessions:
                    # User is valid, generate a new Access Token and continue
                    user_data = user_sessions[user_id]
                    new_access_token = generate_jwt_token(user_data, ACCESS_TOKEN_JWT_SECRET, ACCESS_TOKEN_EXPIRETIME)
                    session['user_id'] = user_id

                    # Check if Google token needs a refresh
                    if datetime.now() > user_data['token_expiry'] - timedelta(minutes=5):
                        if not refresh_oauth_token(user_id):
                            return jsonify({"error": "Token refresh failed"}), 401

                    # Set new access token cookie and proceed
                    response = jsonify({"error": "Access token refreshed. Please try the request again."})
                    # Use the decorator's trick to manually set the new access token
                    set_token_cookies(response, new_access_token, refresh_token_cookie)
                    return f(*args, **kwargs)


        user_id = session.get('user_id')

        # Final check if user is logged in via session (should be unnecessary if JWTs are used properly)
        if not user_id or user_id not in user_sessions:
            return jsonify({"error": "Not authenticated. Please sign in."}), 401

        user_session = user_sessions[user_id]

        if datetime.now() > user_session['expires_at']:
            del user_sessions[user_id]
            session.clear()
            return jsonify({"error": "Session expired. Please sign in again."}), 401

        user_session['expires_at'] = datetime.now() + SESSION_TIMEOUT

        if datetime.now() > user_session['token_expiry']:
            if not refresh_oauth_token(user_id):
                del user_sessions[user_id]
                session.clear()
                return jsonify({"error": "Authentication expired. Please sign in again."}), 401

        return f(*args, **kwargs)

    return decorated_function


# ==================== SESSION CLEANUP ====================
def cleanup_expired_sessions():
    """Clean up expired user sessions"""
    current_time = datetime.now()
    expired_users = [
        user_id for user_id, session_data in user_sessions.items()
        if current_time > session_data['expires_at']
    ]
    for user_id in expired_users:
        del user_sessions[user_id]
        print(f"🧹 Cleaned up expired session for user: {user_id}")


# ==================== ANALYSIS HELPER FUNCTIONS ====================

def convert_to_serializable(value):
    """Convert numpy/pandas types to JSON-serializable"""
    if pd.isna(value) or value is None:
        return None
    if isinstance(value, (np.integer, np.int64)):
        return int(value)
    if isinstance(value, (np.floating, np.float64)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (np.bool_)):
        return bool(value)
    return value

def clean_df(df, columns):
    """Clean DataFrame"""
    df = df.copy().reset_index()

    if 'Date' in df.columns:
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')

    for col in columns:
        if col in df.columns:
            df[col] = df[col].apply(convert_to_serializable)

    cols_to_include = ['Date'] + [col for col in columns if col in df.columns]
    return df[cols_to_include].to_dict(orient='records')

def compute_rsi(series, period=14):
    """Calculate RSI indicator"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_macd(series):
    """Calculate MACD"""
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
    """Calculate linear slope using least squares"""
    if not y_values or len(y_values) < 2:
        return 0.0
    x = np.arange(len(y_values))
    y = np.array(y_values, dtype=float)
    xv = x - x.mean()
    yv = y - y.mean()
    denom = (xv * xv).sum()
    if denom == 0:
        return 0.0
    slope = (xv * yv).sum() / denom
    return float(slope)

def find_recent_macd_crossover(latest_data: List[Dict], lookback: int = 14) -> Tuple[str, int]:
    """Find the most recent MACD crossover"""
    n = len(latest_data)
    upper = max(1, n - lookback)
    for i in range(n - 1, upper - 1, -1):
        if i == 0:
            continue
        prev = latest_data[i - 1]
        curr = latest_data[i]
        prev_diff = safe_get(prev, 'MACD', 0) - safe_get(prev, 'Signal', 0)
        curr_diff = safe_get(curr, 'MACD', 0) - safe_get(curr, 'Signal', 0)
        if prev_diff <= 0 and curr_diff > 0:
            return ('bullish', n - i - 1)
        if prev_diff >= 0 and curr_diff < 0:
            return ('bearish', n - i - 1)
    return ('none', -1)

def fmt_price(x):
    try:
        return f"${round(x, 2)}"
    except Exception:
        return str(x)

# ==================== GEMINI API CALLS ====================
def call_gemini_with_user_token(prompt: str, user_id: str, retry_count: int = 0) -> str:
    """Call Gemini API using user's OAuth token"""
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
            headers={
                "Authorization": f"Bearer {oauth_token}",
                "Content-Type": "application/json"
            },
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 1024,
                }
            },
            timeout=30
        )

        if response.status_code == 401:
            if retry_count < 1:
                # Use the local refresh_oauth_token function
                if refresh_oauth_token(user_id):
                    return call_gemini_with_user_token(prompt, user_id, retry_count + 1)
            return "⚠️ **Session Expired** – Please sign in again"

        if response.status_code == 403:
            error_details = response.json() if response.text else {}
            return f"⚠️ **API Access Denied** – {error_details.get('error', {}).get('message', 'Permission denied')}"

        if response.status_code == 429:
            return "⚠️ **Rate Limit Exceeded** – Please wait and try again"

        if response.status_code != 200:
            return f"⚠️ **API Error {response.status_code}** – Please try again"

        result = response.json()

        if 'candidates' in result and len(result['candidates']) > 0:
            return result['candidates'][0]['content']['parts'][0]['text']

        return "⚠️ **Empty response from AI** – Please try again"

    except Exception as e:
        print(f"❌ Gemini API error: {e}")
        return f"⚠️ **Error** – {str(e)}"

def format_data_for_ai_skimmable(symbol: str, data: list) -> str:
    """Format data for AI analysis"""
    if not data:
        return "No data available."

    latest = data[-1]
    prev = data[-2] if len(data) >= 2 else latest

    close = latest.get('Close', 0)
    open_ = latest.get('Open', 0)
    ma5 = latest.get('MA5', 0)
    ma10 = latest.get('MA10', 0)
    rsi = latest.get('RSI', 0)
    macd = latest.get('MACD', 0)
    signal = latest.get('Signal', 0)
    hist = latest.get('Histogram', 0)
    volume = latest.get('Volume', 0)

    summary = []
    summary.append(f"**Date:** {latest.get('Date', 'N/A')} | **Close:** ${close:.2f} | "
                   f"{'Bullish 🟢' if close > open_ else 'Bearish 🔴'}")
    summary.append(f"**RSI:** {rsi:.2f} | {'Overbought 🔥' if rsi > 70 else 'Oversold ❄️' if rsi < 30 else 'Neutral ✅'}")
    summary.append(f"**MACD:** {macd:.2f} (Signal: {signal:.2f}) | Histogram: {hist:.2f}")

    trend = "Bullish 🟢" if close > prev.get('Close', close) else "Bearish 🔴"
    summary.append(f"**7-Day Trend:** {trend}")

    summary.append(f"**MA5:** ${ma5:.2f} | **MA10:** ${ma10:.2f} | "
                   f"{'Bullish Alignment 🟢' if ma5 > ma10 else 'Bearish Alignment 🔴'}")

    vols = [d.get('Volume', 0) for d in data if d.get('Volume')]
    avg_vol = sum(vols) / len(vols) if vols else 1
    vol_ratio = volume / avg_vol
    summary.append(f"**Volume:** {volume:,} ({vol_ratio:.2f}x avg) | "
                   f"{'Accumulation 📈' if vol_ratio > 1.1 else 'Distribution 📉' if vol_ratio < 0.9 else 'Stable ➡️'}")

    highs = [d.get('High', 0) for d in data]
    lows = [d.get('Low', 0) for d in data]
    summary.append(f"**Support:** ${min(lows):.2f} | **Resistance:** ${max(highs):.2f}")

    return "\n".join(summary)

def get_gemini_ai_analysis(symbol: str, data: list, user_id: str) -> str:
    """AI-powered tech analysis using USER'S OAuth token"""
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
{data_summary}
"""

    return call_gemini_with_user_token(prompt, user_id)

def generate_rule_based_analysis(symbol: str, latest_data: List[Dict], lookback: int = 14) -> str:
    """Generate confidence-weighted technical analysis using rule-based algorithms."""
    try:
        if not latest_data or len(latest_data) < 7:
            return "### ⚠️ Analysis Unavailable\nInsufficient data for reliable analysis. Need at least 7 trading days."

        n = len(latest_data)
        lb = min(lookback, n)
        window = latest_data[-lb:]

        required_fields = ['Close', 'Volume', 'MA5', 'MA10', 'RSI', 'MACD', 'Signal', 'Histogram', 'High', 'Low']
        missing = set()
        for row in window:
            for f in required_fields:
                if f not in row or row.get(f) is None:
                    missing.add(f)
        if missing:
            return f"### ⚠️ Analysis Unavailable\nMissing required fields: {', '.join(sorted(missing))}"

        latest = window[-1]
        close_price = float(latest['Close'])
        rsi = float(latest['RSI'])
        macd = float(latest['MACD'])
        signal = float(latest['Signal'])
        hist = float(latest['Histogram'])
        volume = float(latest['Volume']) if latest['Volume'] is not None else 0.0
        ma5 = float(latest['MA5'])
        ma10 = float(latest['MA10'])
        recent_high = round(max([float(d.get('High', -math.inf)) for d in window]), 2)
        recent_low = round(min([float(d.get('Low', math.inf)) for d in window]), 2)

        rsi_series = [float(d['RSI']) for d in window]
        macd_series = [float(d['MACD']) for d in window]
        hist_series = [float(d['Histogram']) for d in window]
        vol_series = [float(d['Volume']) for d in window if d.get('Volume') is not None]

        rsi_velocity = (rsi_series[-1] - rsi_series[0]) / max(1, (len(rsi_series) - 1))
        macd_slope = linear_slope(macd_series)
        hist_slope = linear_slope(hist_series)
        macd_diff = macd - signal
        crossover_type, crossover_days_ago = find_recent_macd_crossover(window, lookback=lb)

        avg_vol = mean_or(vol_series, fallback=volume if volume > 0 else 1.0)
        volume_ratio = (volume / avg_vol) if avg_vol > 0 else 1.0

        price_vs_ma5 = "above" if close_price > ma5 else "below"
        price_vs_ma10 = "above" if close_price > ma10 else "below"
        ma_trend = "bullish" if ma5 > ma10 else "bearish"
        ma_spread_pct = abs(ma5 - ma10) / ma10 * 100 if ma10 != 0 else 0.0

        def rsi_zone_score_and_note(rsi_val, rsi_vel):
            if rsi_val < 30:
                return (2.0, "Oversold - potential reversal zone", "🟢")
            if rsi_val < 40:
                return (1.0, "Lower neutral (bearish pressure)", "🟢")
            if rsi_val < 60:
                return (0.5, "Neutral/healthy", "⚪")
            if rsi_val < 70:
                vel_bonus = 0.5 if rsi_vel > 1.5 else 0.0
                return (0.5 + vel_bonus, "Bullish zone - momentum building", "🟡")
            if rsi_val < 75:
                if rsi_vel > 2.5:
                    return (0.5, "Overbought with strong continuation momentum", "🟡")
                return (-1.0, "Overbought - caution (likely pullback)", "🔴")
            if rsi_vel > 4.0:
                return (-2.0, "Extremely overbought - exhaustion likely", "🔴")
            return (-1.5, "Severely overbought - high reversal risk", "🔴")

        rsi_score, rsi_note, rsi_emoji = rsi_zone_score_and_note(rsi, rsi_velocity)

        def macd_score_and_note(diff, slope, hist_slope_val, cross_type):
            diff_score = 0.0
            if diff > 1.0:
                diff_score = 3.0
            elif diff > 0.3:
                diff_score = 2.0
            elif diff > 0.05:
                diff_score = 1.0
            elif diff < -1.0:
                diff_score = -3.0
            elif diff < -0.3:
                diff_score = -2.0
            elif diff < -0.05:
                diff_score = -1.0

            slope_score = 0.0
            if slope > 0.005:
                slope_score = 1.0
            elif slope > 0.0005:
                slope_score = 0.5
            elif slope < -0.005:
                slope_score = -1.0
            elif slope < -0.0005:
                slope_score = -0.5

            hist_score = 0.0
            if hist_slope_val > 0.005:
                hist_score = 1.5  # Strong momentum
            elif hist_slope_val > 0.0005:
                hist_score = 0.75
            elif hist_slope_val < -0.005:
                hist_score = -1.5  # Strong momentum loss
            elif hist_slope_val < -0.0005:
                hist_score = -0.75

            cross_bonus = 0.0
            if cross_type == 'bullish':
                cross_bonus = 0.75
            elif cross_type == 'bearish':
                cross_bonus = -0.75

            total_macd = diff_score + slope_score + hist_score + cross_bonus
            note = f"MACD diff={round(diff, 3)}, slope={round(slope, 4)}, hist_slope={round(hist_slope_val, 4)}"
            return (total_macd, note)

        macd_score_val, macd_note = macd_score_and_note(macd_diff, macd_slope, hist_slope, crossover_type)

        if price_vs_ma5 == "above" and price_vs_ma10 == "above":
            price_pos_score = 1.5
            price_context_note = "Strong bullish position above MA5 & MA10"
        elif price_vs_ma5 == "below" and price_vs_ma10 == "below":
            price_pos_score = -1.5
            price_context_note = "Strong bearish position below MA5 & MA10"
        elif price_vs_ma5 == "above" and price_vs_ma10 == "below":
            price_pos_score = 0.8
            price_context_note = "Mixed with bullish bias"
        else:
            price_pos_score = -0.8
            price_context_note = "Mixed with bearish bias"

        ma_score = 0.0
        if ma_spread_pct > 2:
            ma_score = 0.5 if ma_trend == "bullish" else -0.5
        elif ma_spread_pct > 0.5:
            ma_score = 0.25 if ma_trend == "bullish" else -0.25

        volume_score = 0.0
        if volume_ratio > 1.5:
            volume_score = 1.0
        elif volume_ratio > 1.1:
            volume_score = 0.5
        elif volume_ratio < 0.8:
            volume_score = -0.5
        elif volume_ratio < 0.5:
            volume_score = -1.0

        sentiment_score = rsi_score + macd_score_val + price_pos_score + ma_score + volume_score

        overall_sentiment = ""
        sentiment_emoji = ""
        if sentiment_score >= 4.0:
            overall_sentiment = "**STRONGLY BULLISH**"
            sentiment_emoji = "🟢"
        elif sentiment_score >= 0.5:
            overall_sentiment = "**BULLISH**"
            sentiment_emoji = "🟡"
        elif sentiment_score <= -4.0:
            overall_sentiment = "**STRONGLY BEARISH**"
            sentiment_emoji = "🔴"
        elif sentiment_score <= -0.5:
            overall_sentiment = "**MILDLY BEARISH**"
            sentiment_emoji = "🟡"
        else:
            overall_sentiment = "**NEUTRAL**"
            sentiment_emoji = "⚪"

        bullish_signals = sum([
            1 if macd_score_val > 0 else 0,
            1 if rsi_score > 0 else 0,
            1 if price_pos_score > 0 else 0,
            1 if ma_score > 0 else 0,
            1 if volume_score > 0 else 0
        ])
        bearish_signals = sum([
            1 if macd_score_val < 0 else 0,
            1 if rsi_score < 0 else 0,
            1 if price_pos_score < 0 else 0,
            1 if ma_score < 0 else 0,
            1 if volume_score < 0 else 0
        ])

        alignment = bullish_signals - bearish_signals
        if abs(alignment) >= 4 and volume_ratio > 1.1:
            confidence = "high"
        elif abs(alignment) >= 2:
            confidence = "medium"
        else:
            confidence = "low"

        recommendation = ""
        risk_note_parts = []
        conservative_stop = max(ma10, recent_low)
        trailing_stop_pct = 0.03 if sentiment_score > 2.0 else 0.06

        if "BULLISH" in overall_sentiment:
            if rsi >= 75 and hist_slope < -0.01:
                recommendation = f"**Wait / Avoid aggressive entries** — Overbought (RSI {rsi:.1f}) and momentum weakening."
                risk_note_parts.append("High RSI + weakening MACD histogram suggests pullback risk.")
            else:
                if confidence == "high" and volume_ratio > 1.1:
                    recommendation = (
                        f"**BUY** (scale-in allowed) — Trend confirmed. Entry near {fmt_price(close_price)}. "
                        f"Use trailing stop ~{int(trailing_stop_pct * 100)}% or stop at {fmt_price(conservative_stop)}.")
                elif confidence == "medium":
                    recommendation = (
                        f"**Cautiously BUY / scale in** — Entry near {fmt_price(close_price)}. "
                        f"Place stop at {fmt_price(conservative_stop)}; scale on pullback.")
                else:
                    recommendation = (
                        f"**Watch / Wait for cleaner setup** — Current score is low confidence. "
                        f"Wait for bullish confirmation or below {fmt_price(ma10)} for bearish.")

        elif "BEARISH" in overall_sentiment:
            if rsi <= 25 and hist_slope > 0.01:
                recommendation = f"**Wait / Avoid aggressive shorts** — Oversold (RSI {rsi:.1f}) and momentum strengthening."
                risk_note_parts.append("Low RSI + strengthening MACD histogram suggests bounce risk.")
            else:
                if confidence == "high" and volume_ratio > 1.1:
                    recommendation = (
                        f"**SELL/SHORT** (scale-in allowed) — Trend confirmed. Entry near {fmt_price(close_price)}. "
                        f"Use trailing stop ~{int(trailing_stop_pct * 100)}% or stop at {fmt_price(recent_high)}.")
                elif confidence == "medium":
                    recommendation = (
                        f"**Cautiously SELL/SHORT / scale in** — Entry near {fmt_price(close_price)}. "
                        f"Place stop at {fmt_price(recent_high)}; scale on bounce.")
                else:
                    recommendation = (
                        f"**Watch / Wait for cleaner setup** — Current score is low confidence. "
                        f"Wait for bearish confirmation or above {fmt_price(ma10)} for bullish.")
        else: # Neutral
            recommendation = (
                f"**HOLD / RANGE TRADE** — Neutral signals. Price is consolidating between {fmt_price(recent_low)} (Support) and "
                f"{fmt_price(recent_high)} (Resistance). Wait for a decisive break.")
            if volume_ratio > 1.1:
                risk_note_parts.append("High volume on neutral trend - potential for large move soon.")

        if volume_ratio < 0.8:
            risk_note_parts.append("Volume below average — low conviction.")

        if confidence == "low" and not any("conflicting" in s.lower() for s in risk_note_parts):
            risk_note_parts.append("Conflicting signals — trade with caution.")

        risk_note = " • ".join(risk_note_parts) if risk_note_parts else "None."

        output_lines = []
        output_lines.append(f"### {sentiment_emoji} Technical Analysis for {symbol}")
        output_lines.append("")
        output_lines.append(f"**Overall Sentiment:** {overall_sentiment} ({confidence} confidence)")
        output_lines.append("")
        output_lines.append(f"**Current Price:** {fmt_price(close_price)} ({price_context_note})")
        output_lines.append("")
        output_lines.append("#### 📊 Price Position Analysis")
        output_lines.append(
            f"- Trading **{price_vs_ma5} MA5 ({fmt_price(ma5)})** and **{price_vs_ma10} MA10 ({fmt_price(ma10)})**")
        output_lines.append(f"- **MA Alignment:** {ma_trend} (spread {round(ma_spread_pct, 2)}%)")
        output_lines.append("")
        output_lines.append("#### 🎯 MACD Analysis (Trend Following)")
        output_lines.append(
            f"- MACD diff: {round(macd_diff, 3)}, slope: {round(macd_slope, 4)}, hist slope: {round(hist_slope, 4)}")
        if crossover_type != 'none':
            output_lines.append(f"- Recent crossover: {crossover_type} {crossover_days_ago} days ago")
        output_lines.append(f"- {macd_note}")
        output_lines.append("")
        output_lines.append("#### 📈 RSI Analysis (Momentum)")
        output_lines.append(
            f"- RSI at **{round(rsi, 2)}** {rsi_emoji} — {rsi_note} (velocity {round(rsi_velocity, 3)} pts/day)")
        output_lines.append("")
        output_lines.append("#### 📊 Volume Context")
        output_lines.append(
            f"- Volume: {volume_ratio:.2f}x avg → {'strong' if volume_ratio > 1.1 else 'weak' if volume_ratio < 0.9 else 'average'}")
        output_lines.append("")
        output_lines.append("#### 💡 Recommendation")
        output_lines.append(f"{recommendation}")
        if risk_note:
            output_lines.append(f"\n**Risk Note:** {risk_note}")
        output_lines.append("")
        output_lines.append(f"#### 🧠 Key Levels to Watch")
        output_lines.append(f"- **Support:** {fmt_price(recent_low)}")
        output_lines.append(f"- **Resistance:** {fmt_price(recent_high)}")


        return "\n".join(output_lines)

    except Exception as e:
        print(f"❌ Error generating rule-based analysis: {e}")
        return f"### ❌ Analysis Error\nFailed to compute rule-based analysis due to an internal error: {str(e)}"


# ==================== LOGGING SETUP ====================
# Configure global logging for production visibility
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    handlers=[logging.StreamHandler(stdout)]
)
logger = logging.getLogger(__name__)

# ==================== ENVIRONMENT CONFIGURATION ====================
is_production = os.getenv('FLASK_ENV', 'development') == 'production'

# ==================== APPLICATION SETUP ====================
app = Flask(__name__, static_folder="static")

# 1. Secret Key (MANDATORY for sessions)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

if not app.secret_key:
    if is_production:
        logger.critical("FATAL: FLASK_SECRET_KEY is required in production environment.")
        raise EnvironmentError("FLASK_SECRET_KEY is required in production environment.")
    else:
        # Fallback for local development, but use a fixed, known key
        app.secret_key = 'dev_fixed_key_for_local_testing_only'
        logger.warning("Using development fallback FLASK_SECRET_KEY.")


# 2. Session Cookie Settings
# Production settings require HTTPS (Secure=True)
if is_production:
    app.config['SESSION_COOKIE_SECURE'] = True
    # Setting this on Render is CRITICAL for the OAuth state cookie to work.
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    logger.info("Running in PRODUCTION mode. Session cookies are Secure and Lax.")
else:
    # Relaxed settings for localhost (HTTP)
    app.config['SESSION_COOKIE_SECURE'] = False
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    logger.info("Running in DEVELOPMENT mode. Session cookies are Insecure (HTTP) and Lax.")


# 3. CORS Configuration
# Adjust origins to match your frontend URL in production
CORS(app, supports_credentials=True, origins=["http://localhost:3000", "http://localhost:5000" ,"https://budgetwarrenbuffet.vercel.app", CLIENT_REDIRECT_URL])


# 4. Session Lifetime (Important for authentication state)
app.permanent_session_lifetime = timedelta(days=7)


# ==================== APPLICATION HOOKS ====================
@app.before_request
def cleanup_and_session_setup():
    """Run before every request to clean up expired sessions."""
    cleanup_expired_sessions()


# ==================== AUTHENTICATION ROUTES (Merged from auth.py Blueprint) ====================
@app.route('/auth/login', methods=['GET'])
def auth_login():
    """Initiate Google OAuth flow (no double-login & no unnecessary prompt=consent)."""
    try:
        # Always generate a fresh state
        state = secrets.token_urlsafe(32)

        # 🛠️ FIX: Force session to be permanent and modified to ensure the cookie is sent
        session.permanent = True
        session['oauth_state'] = state
        session['oauth_initiated'] = True
        session.modified = True

        auth_params = {
            'client_id': GOOGLE_CLIENT_ID,
            'redirect_uri': REDIRECT_URI,
            'response_type': 'code',
            'scope': ' '.join(SCOPES),
            'access_type': 'offline', # CRITICAL for getting a refresh_token
            'prompt': 'select_account', # Forces account selection on first login/scope change
            'state': state
        }

        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(auth_params)}"

        resp = jsonify({
            "success": True,
            "auth_url": auth_url,
            "message": "Redirect to this URL to authenticate"
        })

        # Prevent caching of the auth initiation
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'

        return resp, 200

    except Exception as e:
        print(f"❌ OAuth initiation error: {e}")
        return jsonify({"error": f"Failed to initiate OAuth: {str(e)}"}), 500

@app.route('/oauth2callback', methods=['GET'])
def oauth_callback():
    """Handle OAuth callback safely."""
    try:
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')

        if error:
            print(f"❌ Google returned error: {error}")
            return redirect(f'{CLIENT_REDIRECT_URL}?error=auth_failed&reason={error}')

        if not code:
            return redirect(f'{CLIENT_REDIRECT_URL}?error=no_code')

        # 🛠️ FIX: Improved State Verification Debugging
        stored_state = session.pop('oauth_state', None)

        if not stored_state:
            print("❌ Error: No state found in session. Cookie might have been dropped.")
            # Debug hint: print(f" Session keys present: {list(session.keys())}")
            return redirect(f'{CLIENT_REDIRECT_URL}?error=invalid_state&reason=missing_session')

        if state != stored_state:
            print(f"❌ State mismatch! Received: {state[:10]}... | Stored: {stored_state[:10]}...")
            return redirect(f'{CLIENT_REDIRECT_URL}?error=invalid_state&reason=state_mismatch')

        # 1. Exchange authorization code for tokens
        token_data = {
            'code': code,
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code'
        }
        token_response = requests.post("https://oauth2.googleapis.com/token", data=token_data)

        if token_response.status_code != 200:
            print(f"❌ Token exchange failed: {token_response.text}")
            return redirect(f'{CLIENT_REDIRECT_URL}?error=token_exchange_failed')

        tokens = token_response.json()
        id_token = tokens.get('id_token')
        oauth_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token') # This is the CRITICAL, long-lived token
        expires_in = tokens.get('expires_in')

        if not id_token or not oauth_token:
            return redirect(f'{CLIENT_REDIRECT_URL}?error=missing_tokens')

        # 2. Decode the ID token to get user info (Email/ID)
        try:
            user_info = jwt.decode(id_token, options={"verify_signature": False})
        except Exception as e:
            print(f"❌ Failed to decode ID token: {e}")
            return redirect(f'{CLIENT_REDIRECT_URL}?error=invalid_id_token')

        user_id = user_info.get('sub')
        user_email = user_info.get('email')
        user_name = user_info.get('name')
        granted_scopes = tokens.get('scope', '').split(' ')

        if not user_id:
            return redirect(f'{CLIENT_REDIRECT_URL}?error=missing_user_id')

        # 3. Store the user's Google tokens in the session storage
        user_sessions[user_id] = {
            'user_id': user_id,
            'email': user_email,
            'name': user_name,
            'oauth_token': oauth_token,
            'refresh_token': refresh_token,
            'token_expiry': datetime.now() + timedelta(seconds=expires_in),
            'expires_at': datetime.now() + SESSION_TIMEOUT,
            'granted_scopes': granted_scopes
        }

        # 4. Create and set JWT tokens (for stateless authentication)
        user_data = user_sessions[user_id]
        jwt_access = generate_jwt_token(user_data, ACCESS_TOKEN_JWT_SECRET, ACCESS_TOKEN_EXPIRETIME)
        jwt_refresh = generate_jwt_token(user_data, REFRESH_TOKEN_JWT_SECRET, REFRESH_TOKEN_EXPIRETIME)

        # 5. Set session and cookies, then redirect
        session['user_id'] = user_id
        response = redirect(f'{CLIENT_REDIRECT_URL}?auth=success')
        response = set_token_cookies(response, jwt_access, jwt_refresh)

        return response

    except Exception as e:
        print(f"❌ OAuth callback error: {e}")
        session.clear()
        return redirect(f'{CLIENT_REDIRECT_URL}?error=callback_error')

@app.route('/auth/token/refresh', methods=['POST'])
def refresh_token():
    """Refresh access token using refresh token"""
    try:
        refresh_token_cookie = request.cookies.get('refresh_token')
        if not refresh_token_cookie:
            return jsonify({"error": "No refresh token provided"}), 401

        payload = verify_jwt_token(refresh_token_cookie, REFRESH_TOKEN_JWT_SECRET)
        if not payload:
            return jsonify({"error": "Invalid or expired refresh token"}), 401

        user_id = payload['user_id']
        if user_id not in user_sessions:
            return jsonify({"error": "User session not found"}), 401

        user_data = user_sessions[user_id]

        # Check if we need to refresh Google Access Token too
        if user_data.get('refresh_token'):
            # Check expiry before force refreshing
            if datetime.now() > user_data['token_expiry'] - timedelta(minutes=5):
                refresh_oauth_token(user_id) # OAuth token refreshed in user_sessions

        new_access_token = generate_jwt_token(user_data, ACCESS_TOKEN_JWT_SECRET, ACCESS_TOKEN_EXPIRETIME)

        response = jsonify({
            "success": True,
            "message": "Access token refreshed"
        })
        response = set_token_cookies(response, new_access_token, refresh_token_cookie)
        return response, 200

    except Exception as e:
        print(f"❌ Token refresh error: {e}")
        return jsonify({"error": "Internal token refresh error"}), 500

@app.route('/auth/logout', methods=['POST'])
def logout():
    """Clear session and JWT cookies"""
    try:
        user_id = session.pop('user_id', None)
        if user_id and user_id in user_sessions:
            del user_sessions[user_id]
            print(f"Logged out user: {user_id}")

        session.clear()

        response = jsonify({"success": True, "message": "Logged out"})

        # Clear cookies by setting expiry to past
        response.set_cookie('access_token', '', max_age=0)
        response.set_cookie('refresh_token', '', max_age=0)

        return response, 200

    except Exception as e:
        print(f"❌ Logout error: {e}")
        return jsonify({"error": "Logout failed"}), 500

@app.route('/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status"""
    try:
        access_token = request.cookies.get('access_token')

        if not access_token:
            return jsonify({"authenticated": False}), 200

        payload = verify_jwt_token(access_token, ACCESS_TOKEN_JWT_SECRET)

        if payload:
            user_id = payload['user_id']
            if user_id in user_sessions:
                user_session = user_sessions[user_id]
                return jsonify({
                    "authenticated": True,
                    "user": {
                        "email": user_session['email'],
                        "name": user_session['name'],
                        "expires_in": int((user_session['expires_at'] - datetime.now()).total_seconds())
                    }
                }), 200

        return jsonify({"authenticated": False}), 200

    except Exception as e:
        print(f"❌ Auth status error: {e}")
        return jsonify({"authenticated": False}), 200


# ==================== API DATA ROUTES (Merged from analysis.py handlers) ====================
@app.route('/api/get_data', methods=['POST'])
@require_auth
def get_data():
    """
    Fetches stock data from yfinance, computes technical indicators,
    and generates AI/Rule-based analysis.
    """
    data = request.get_json()
    symbol = data.get('symbol', '').upper().strip()
    user_id = session.get('user_id')

    if not symbol:
        return jsonify({"error": "No symbol provided"}), 400

    try:
        # 1. Fetch data
        ticker = yf.Ticker(symbol)
        # Fetch 90 days of history for indicators
        hist = ticker.history(period="90d", interval="1d")

        if hist.empty:
            return jsonify({"error": f"Could not retrieve data for {symbol}"}), 404

        # 2. Compute Technical Indicators (MA, RSI, MACD)
        hist['MA5'] = hist['Close'].rolling(window=5).mean()
        hist['MA10'] = hist['Close'].rolling(window=10).mean()
        hist['RSI'] = compute_rsi(hist['Close'])
        hist['MACD'], hist['Signal'], hist['Histogram'] = compute_macd(hist['Close'])

        # Drop rows with NaN values (initial periods for indicators)
        hist_display = hist.dropna(subset=['MA5', 'MA10', 'RSI', 'MACD', 'Signal', 'Histogram'])

        # Store latest data for chat context
        latest_data_list = clean_df(hist_display, ['Open', 'High', 'Low', 'Close', 'Volume', 'MA5', 'MA10', 'RSI', 'MACD', 'Signal', 'Histogram'])
        latest_symbol_data[symbol] = latest_data_list

        # 3. Generate Analysis
        # Rule-based analysis (immediate feedback, no API call delay)
        rule_based_text = generate_rule_based_analysis(symbol, latest_data_list)

        # Gemini AI analysis (requires user's OAuth token, called with retry logic)
        gemini_analysis = get_gemini_ai_analysis(symbol, latest_data_list, user_id)

        # 4. Initialize or update conversation context
        if user_id not in conversation_context:
            conversation_context[user_id] = {
                "current_symbol": symbol,
                "conversation_history": [],
                "last_active": datetime.now().isoformat(),
                "user_positions": {}
            }
        else:
            conversation_context[user_id]["current_symbol"] = symbol
            conversation_context[user_id]["last_active"] = datetime.now().isoformat()

        # 5. Format and return response
        response = {
            "ticker": symbol,
            "OHLCV": clean_df(hist_display, ['Open', 'High', 'Low', 'Close', 'Volume']),
            "MA": clean_df(hist_display, ['MA5', 'MA10']),
            "RSI": [convert_to_serializable(x) for x in hist_display['RSI'].tolist()],
            "MACD": clean_df(hist_display, ['MACD', 'Signal', 'Histogram']),
            "AI_Review": gemini_analysis,
            "Rule_Based_Analysis": rule_based_text
        }
        return jsonify(response), 200

    except Exception as e:
        print(f"❌ Error in /api/get_data: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route('/api/chat', methods=['POST'])
@require_auth
def chat():
    """Context-aware chatbot handler (Merged from analysis.py chat_handler)"""
    data = request.get_json()
    query = data.get('query', '').strip()
    user_id = session.get('user_id')
    current_symbol_hint = data.get('current_symbol')

    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        # 1. Initialize context
        if user_id not in conversation_context:
            conversation_context[user_id] = {
                "current_symbol": None,
                "conversation_history": [],
                "last_active": datetime.now().isoformat(),
                "user_positions": {}
            }
        
        session_ctx = conversation_context[user_id]

        if "user_positions" not in session_ctx:
            session_ctx["user_positions"] = {}
        
        session_ctx["last_active"] = datetime.now().isoformat()

        # 2. Determine current symbol context
        matched_symbol = None
        current_symbol = session_ctx["current_symbol"]

        for symbol in latest_symbol_data.keys():
            if symbol.lower() in query.lower():
                matched_symbol = symbol
                break
        
        if not matched_symbol and current_symbol_hint:
            matched_symbol = current_symbol_hint

        if not matched_symbol and current_symbol:
            matched_symbol = current_symbol

        if matched_symbol and matched_symbol in latest_symbol_data:
            session_ctx["current_symbol"] = matched_symbol
        else:
            matched_symbol = None

        # 3. Handle position updates (buy/sell/entry)
        has_position = False
        position_info = ""
        technical_summary = ""

        # Pattern: (buy|sell|entry|long|short|got) [a|at] (price)
        position_match = re.search(r'(?:bought|sold|entry|long|short|got)\s+at\s+\$?(\d+\.?\d*)', query, re.IGNORECASE)

        if matched_symbol:
            latest_price = latest_symbol_data[matched_symbol][-1]['Close']
            
            # Check for position update
            if position_match:
                entry_price = float(position_match.group(1))
                session_ctx["user_positions"][matched_symbol] = {
                    "entry_price": entry_price,
                    "date": datetime.now().isoformat()
                }
                position_info = f"The user just updated their position: they are **long** {matched_symbol} with an **entry price of ${entry_price}**."
            
            # Check for existing position
            elif matched_symbol in session_ctx["user_positions"]:
                has_position = True
                position = session_ctx["user_positions"][matched_symbol]
                entry = position['entry_price']
                current_price = latest_symbol_data[matched_symbol][-1]['Close']
                
                pnl_dollars = current_price - entry
                pnl_percent = (pnl_dollars / entry) * 100
                
                position_info = (
                    f"User has a position in {matched_symbol} with an **entry price of ${entry}**. "
                    f"Current price: ${current_price}. "
                    f"P&L: **${pnl_dollars:.2f} ({pnl_percent:.2f}%)**."
                )
            
            # Extract technical context
            if matched_symbol in latest_symbol_data:
                # Use the rule-based analysis as the technical summary if available
                rule_analysis = generate_rule_based_analysis(matched_symbol, latest_symbol_data[matched_symbol])
                technical_summary = rule_analysis
        
        # 4. Generate history text
        history_text = "\n".join([
            f"User: {h['user']}\nAssistant: {h['assistant']}"
            for h in session_ctx["conversation_history"][-3:]
        ])

        # 5. Construct prompt for Gemini
        prompt = f"""You are an **experienced trading analyst chatbot** named **QuantAI**. Your goal is to provide concise, direct, and actionable advice to a recreational trader based on their question and the provided context.

RESPONSE GUIDELINES:
1. **Tone**: Sound like a savvy trader/mentor. Use simple, confident language.
2. **Context**: Use the CURRENT STOCK and TECHNICAL CONTEXT for analysis.
3. **Position**: If P&L is available, calculate it precisely and state it first.
4. **Length**: Be brief (2-3 sentences) unless they need detailed analysis.
5. If user mentions 'detailed', give a longer more in depth answer preferably in markdown.

CURRENT STOCK: {matched_symbol if matched_symbol else 'None'}
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

        # 6. Update history
        session_ctx["conversation_history"].append({
            "user": query,
            "assistant": assistant_response,
            "timestamp": datetime.now().isoformat()
        })

        if len(session_ctx["conversation_history"]) > 15:
            session_ctx["conversation_history"] = session_ctx["conversation_history"][-15:]

        # 7. Return response
        return jsonify({
            "response": assistant_response,
            "context": {
                "current_symbol": matched_symbol,
                "has_position": has_position,
                "history_length": len(session_ctx["conversation_history"])
            }
        }), 200

    except Exception as e:
        print(f"❌ Chat handler error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# ==================== STATIC FILE ROUTES ====================
@app.route('/')
def home():
    """Serves the main application file."""
    return app.send_static_file("index.html")

@app.route('/<path:path>')
def serve_static(path):
    """Serves other static files."""
    return app.send_static_file(path)

@app.route('/health', methods=['GET'])
def health():
    """Health check for load balancers/monitors."""
    return jsonify({
        "status": "healthy",
        "services": {
            "yfinance": "operational",
            "rule_based_analysis": "operational",
            "oauth_authentication": "enabled"
        },
        "version": "4.0-Monolithic",
        "active_sessions": len(user_sessions),
        "env": "production" if is_production else "development"
    }), 200


# ==================== APPLICATION STARTUP ====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = '0.0.0.0' # Listen on all interfaces

    print("=" * 70)
    print(" 📊 STOCK ANALYSIS BACKEND v4.0 (MONOLITHIC)")
    print("=" * 70)
    print(f" 🚀 Server running on: http://{host}:{port}")
    print(f" 🔐 OAuth Status: {'✅ Configured' if os.getenv('GOOGLE_CLIENT_ID') else '⚠️ Missing credentials'}")
    print(f" 🌍 Environment: {'Production (HTTPS required)' if is_production else 'Development (HTTP OK)'}")
    print(f" 📦 Secret Key Set: {'✅' if app.secret_key and app.secret_key != 'dev_fixed_key_for_local_testing_only' else '⚠️ Development Key'}")

    # ==================== ROUTE DIAGNOSTICS ====================
    print("-" * 70)
    print(" 🔎 DIAGNOSING REGISTERED ROUTES (Should all be visible):")
    
    with app.app_context():
        auth_routes_found = False
        for rule in app.url_map.iter_rules():
            rule_str = str(rule)
            # Check all key routes including the new API ones
            if 'auth' in rule_str or 'oauth2callback' in rule_str or 'api' in rule_str:
                print(f"    ✅ ROUTE FOUND: {rule_str} | Endpoint: {rule.endpoint}")
                auth_routes_found = True
        
        if not auth_routes_found:
            print("    ❌ WARNING: No application routes registered. Flask app may be misconfigured.")
            
    print("-" * 70)
    # ==================== END DIAGNOSTICS ====================
    
    app.run(host=host, port=port, debug=not is_production)


