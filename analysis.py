from flask import request, jsonify, session
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import statistics
import math
import re
from datetime import datetime
from typing import List, Dict, Tuple

from auth import user_sessions

# Data Storage
latest_symbol_data = {}
conversation_context = {}

# ==================== HELPER FUNCTIONS ====================
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
            "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent",            headers={
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
                from auth import refresh_oauth_token
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
            if slope > 0.05:
                slope_score = 1.0
            elif slope > 0.01:
                slope_score = 0.5
            elif slope < -0.05:
                slope_score = -1.5
            elif slope < -0.01:
                slope_score = -0.5

            hist_score = 0.0
            if hist_slope_val > 0.05:
                hist_score = 1.0
            elif hist_slope_val > 0.01:
                hist_score = 0.5
            elif hist_slope_val < -0.05:
                hist_score = -1.0
            elif hist_slope_val < -0.01:
                hist_score = -0.5

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
        elif volume_ratio < 0.7:
            volume_score = -1.0
        elif volume_ratio < 0.9:
            volume_score = -0.5

        w_macd = 1.2
        w_rsi = 1.0
        w_price = 0.9
        w_ma = 0.4

        freshness_boost = 0.0
        if crossover_type != 'none' and crossover_days_ago >= 0:
            freshness_boost = max(0.0, (lb - crossover_days_ago) / lb) * 0.5

        cooldown_penalty = 0.0
        if rsi >= 75 and hist_slope < -0.01:
            cooldown_penalty = -2.0

        momentum_age_score = 0.0
        if crossover_type != 'none' and crossover_days_ago >= 0:
            recency_factor = max(0.0, (lb - crossover_days_ago) / lb)
            momentum_age_score = recency_factor * (1 if crossover_type == 'bullish' else -1)

        raw_sentiment = (
                (macd_score_val * w_macd) +
                (rsi_score * w_rsi) +
                (price_pos_score * w_price) +
                (ma_score * w_ma) +
                (volume_score * 0.3) +
                freshness_boost +
                momentum_age_score * 0.8 +
                cooldown_penalty
        )

        volume_multiplier = 1.0
        if volume_ratio < 0.8:
            volume_multiplier = 0.7
        elif volume_ratio > 1.4:
            volume_multiplier = 1.15
        elif volume_ratio > 2.0:
            volume_multiplier = 1.3

        sentiment_score = raw_sentiment * volume_multiplier

        if sentiment_score >= 4.0:
            overall_sentiment = "**STRONGLY BULLISH**"
            sentiment_emoji = "🟢"
        elif sentiment_score >= 2.0:
            overall_sentiment = "**BULLISH**"
            sentiment_emoji = "🟢"
        elif sentiment_score >= 0.5:
            overall_sentiment = "**MILDLY BULLISH**"
            sentiment_emoji = "🟡"
        elif sentiment_score <= -4.0:
            overall_sentiment = "**STRONGLY BEARISH**"
            sentiment_emoji = "🔴"
        elif sentiment_score <= -2.0:
            overall_sentiment = "**BEARISH**"
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
        trailing_stop_pct = 0.03 if sentiment_score > 2.0 else 0.06 if sentiment_score > 0.5 else 0.08

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
                        f"**Watch / Wait for cleaner setup** — Mixed signals. Consider buying on pullback to {fmt_price(ma5)}-{fmt_price(ma10)}.")
        elif "BEARISH" in overall_sentiment:
            if rsi <= 30:
                recommendation = f"**Watch for reversal** — Oversold but bearish. Wait for MACD confirmation above signal."
                risk_note_parts.append("RSI oversold could limit downside.")
            else:
                recommendation = f"**Reduce exposure / consider shorting** — Downtrend signals dominate."
                risk_note_parts.append("Risk: trend may continue; keep stops tight.")
        else:
            if sentiment_score > 0.5:
                recommendation = (
                    f"**Range-bound with bullish bias** — Trade ranges; buy dips near {fmt_price(conservative_stop)}, target {fmt_price(recent_high)}.")
            elif sentiment_score < -0.5:
                recommendation = (
                    f"**Range-bound with bearish bias** — Look to reduce longs; prefer short on failed rallies.")
            else:
                recommendation = (
                    f"**Monitor** — Mixed signals. Key triggers: break above {fmt_price(ma5)} for bullish confirmation or below {fmt_price(ma10)} for bearish.")

        if volume_ratio < 0.8:
            risk_note_parts.append("Volume below average — low conviction.")
        if confidence == "low" and not any("conflicting" in s.lower() for s in risk_note_parts):
            risk_note_parts.append("Conflicting signals — trade with caution.")

        risk_note = " • ".join(risk_note_parts) if risk_note_parts else ""

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
        output_lines.append("#### 🧠 Key Levels to Watch")
        output_lines.append(f"- **Support:** {fmt_price(conservative_stop)} (MA10 or recent low)")
        support_lines = []
        if ma10 < close_price:
            support_lines.append(f"{fmt_price(ma10)} (MA10)")
        if ma5 < close_price:
            support_lines.append(f"{fmt_price(ma5)} (MA5)")
        if recent_low < close_price:
            support_lines.append(f"{fmt_price(recent_low)} (Recent Low)")
        if support_lines:
            output_lines.append(f"- **Other supports:** {', '.join(support_lines)}")
        output_lines.append(f"- **Resistance:** {fmt_price(recent_high)} (Recent High)")
        output_lines.append(f"- **RSI Context:** {rsi_note}")
        output_lines.append(f"- **Trend Confidence:** {confidence}")

        return "\n".join(output_lines)

    except Exception as e:
        return f"### ❌ Analysis Generation Failed\nError: {str(e)}"

# ==================== REQUEST HANDLERS ====================
def get_data_handler():
    """Main API endpoint handler"""
    try:
        data = request.json
        symbol = data.get('symbol', '').strip().upper()
        user_id = session.get('user_id')

        if not symbol:
            return jsonify({"error": "Stock symbol is required"}), 400

        stock = yf.Ticker(symbol)
        hist = stock.history(period="3mo")

        if hist.empty:
            return jsonify({"error": f"No data found for symbol '{symbol}'"}), 404

        # Calculate indicators
        hist['MA5'] = hist['Close'].rolling(window=5, min_periods=1).mean()
        hist['MA10'] = hist['Close'].rolling(window=10, min_periods=1).mean()
        hist['RSI'] = compute_rsi(hist['Close'])
        hist['MACD'], hist['Signal'], hist['Histogram'] = compute_macd(hist['Close'])

        hist_display = hist.tail(7)

        ai_data = clean_df(
            hist_display,
            ['Open', 'High', 'Low', 'Close', 'Volume', 'MA5', 'MA10', 'RSI', 'MACD', 'Signal', 'Histogram']
        )

        gemini_analysis = get_gemini_ai_analysis(symbol, ai_data, user_id)
        rule_based_text = generate_rule_based_analysis(symbol, ai_data)

        latest_symbol_data[symbol] = {
            "symbol": symbol,
            "rule_based_analysis": rule_based_text,
            "ai_review": gemini_analysis,
            "technical_data": ai_data,
            "last_updated": datetime.now().isoformat()
        }

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
        print(f"❌ Error in /get_data: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


def chat_handler():
    """Context-aware chatbot handler"""
    data = request.get_json()
    query = data.get('query', '').strip()
    user_id = session.get('user_id')
    current_symbol_hint = data.get('current_symbol')

    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
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

        if not matched_symbol and latest_symbol_data:
            matched_symbol = list(latest_symbol_data.keys())[-1]

        if not matched_symbol:
            return jsonify({"response": "Please search for a stock symbol first!"})

        session_ctx["current_symbol"] = matched_symbol
        stock_data = latest_symbol_data.get(matched_symbol, {})

        buy_patterns = [
            r'(?:bought|buy|entry|entered|got in)\s+(?:at\s+)?[\$]?(\d+(?:\.\d+)?)',
            r'my\s+entry\s+(?:is\s+|was\s+)?[\$]?(\d+(?:\.\d+)?)',
            r'entry\s+(?:price\s+)?[\$]?(\d+(?:\.\d+)?)',
            r'[\$]?(\d+(?:\.\d+)?)\s+entry'
        ]

        for pattern in buy_patterns:
            buy_match = re.search(pattern, query.lower())
            if buy_match:
                entry_price = float(buy_match.group(1))
                session_ctx["user_positions"][matched_symbol] = {
                    "entry_price": entry_price,
                    "type": "long",
                    "timestamp": datetime.now().isoformat()
                }
                break

        current_price = None
        if stock_data.get('technical_data'):
            latest_data = stock_data['technical_data'][-1]
            current_price = latest_data.get('Close')

        is_pnl_query = any(keyword in query.lower() for keyword in [
            'profit', 'loss', 'gain', 'p&l', 'pnl', 'how much', 'made', 'percentage'
        ])

        position_info = ""
        has_position = matched_symbol in session_ctx.get("user_positions", {})

        if has_position:
            position = session_ctx["user_positions"][matched_symbol]
            entry_price = position['entry_price']

            if current_price:
                pnl_dollars = current_price - entry_price
                pnl_percent = (pnl_dollars / entry_price) * 100

                position_info = f"""
🎯 USER'S ACTIVE POSITION ON {matched_symbol}:
   Entry Price: ${entry_price}
   Current Price: ${current_price}
   Profit/Loss: ${pnl_dollars:.2f} ({pnl_percent:+.2f}%)
   Status: {'🟢 In Profit' if pnl_dollars > 0 else '🔴 In Loss' if pnl_dollars < 0 else '⚪ Break Even'}
"""

        technical_summary = ""
        if stock_data:
            if stock_data.get('rule_based_analysis'):
                technical_summary = stock_data['rule_based_analysis'][:400]

        history_text = ""
        recent_history = session_ctx["conversation_history"][-3:]
        if recent_history:
            history_text = "RECENT CONVERSATION:\n"
            for h in recent_history:
                history_text += f"User: {h['user']}\nYou: {h['assistant']}\n\n"

        if is_pnl_query and has_position and current_price:
            position = session_ctx["user_positions"][matched_symbol]
            entry = position['entry_price']
            pnl_dollars = current_price - entry
            pnl_percent = (pnl_dollars / entry) * 100

            direct_response = f"You bought {matched_symbol} at ${entry}, and it's currently at ${current_price}. "

            if pnl_percent > 0:
                direct_response += f"You're up ${pnl_dollars:.2f}, which is a {pnl_percent:.2f}% gain. "
            elif pnl_percent < 0:
                direct_response += f"You're down ${abs(pnl_dollars):.2f}, which is a {pnl_percent:.2f}% loss. "
            else:
                direct_response += f"You're at break even (0%). "

            if 'RSI' in technical_summary:
                if 'overbought' in technical_summary.lower():
                    direct_response += "RSI suggests it's overbought, so consider taking some profit."
                elif 'oversold' in technical_summary.lower():
                    direct_response += "RSI suggests it's oversold, might have more upside."

            session_ctx["conversation_history"].append({
                "user": query,
                "assistant": direct_response,
                "timestamp": datetime.now().isoformat()
            })

            return jsonify({
                "response": direct_response,
                "context": {
                    "current_symbol": matched_symbol,
                    "has_position": True,
                    "entry_price": entry,
                    "current_price": current_price,
                    "pnl_percent": pnl_percent
                }
            })

        prompt = f"""You are Astra, a sharp market analyst who talks like a real trader.

CRITICAL RULES:
1. The user has given you specific information - USE IT EXACTLY AS PROVIDED
2. When they mention an entry price, REMEMBER IT and reference it
3. Calculate P&L using THEIR entry price, not some hypothetical price
4. Be conversational but ACCURATE with numbers
5. If user mentions detailed, give a longer more in depth answer preferably in markdown

CURRENT STOCK: {matched_symbol}
{position_info}

TECHNICAL CONTEXT:
{technical_summary[:500] if technical_summary else 'No technical data available'}

{history_text}

USER QUESTION: {query}

RESPONSE RULES:
- If they ask about profit/loss and you have their entry price, CALCULATE IT EXACTLY
- Reference their specific entry price if they gave you one
- Be brief (2-3 sentences) unless they need detailed analysis
- Sound like a trader chatting, not a robot

Respond now:"""

        assistant_response = call_gemini_with_user_token(prompt, user_id)

        session_ctx["conversation_history"].append({
            "user": query,
            "assistant": assistant_response,
            "timestamp": datetime.now().isoformat()
        })

        if len(session_ctx["conversation_history"]) > 15:
            session_ctx["conversation_history"] = session_ctx["conversation_history"][-15:]

        return jsonify({
            "response": assistant_response,
            "context": {
                "current_symbol": matched_symbol,
                "has_position": has_position,
                "history_length": len(session_ctx["conversation_history"])
            }
        })

    except Exception as e:
        print(f"❌ Chat error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Chat error: {str(e)}"}), 500