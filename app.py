from flask import Flask, request, jsonify
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import numpy as np
import os
from google import genai
from google.genai.errors import APIError
from google.api_core.exceptions import ResourceExhausted
import dotenv
import json
from datetime import datetime, timedelta

app = Flask(__name__)
dotenv.load_dotenv()

# CORS Configuration
CORS(app)

# --- Gemini API Initialization ---
try:
    client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
    print("Gemini client initialized successfully.")
except Exception as e:
    print(f"Warning: Failed to initialize Gemini client. Check GEMINI_API_KEY environment variable. Error: {e}")
    client = None


# --- Helper Functions (RSI, MACD, Serialization) ---

def compute_rsi(series, period=14):
    """Calculate RSI indicator (using EWM for standard formula)"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_macd(series):
    """Calculate MACD, Signal line, and Histogram"""
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal
    return macd, signal, histogram


def convert_to_serializable(value):
    """Convert numpy/pandas types to JSON-serializable Python types"""
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
    """Clean DataFrame and convert to JSON-safe format"""
    df = df.copy().reset_index()

    if 'Date' in df.columns:
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')

    for col in columns:
        if col in df.columns:
            df[col] = df[col].apply(convert_to_serializable)

    cols_to_include = ['Date'] + [col for col in columns if col in df.columns]
    return df[cols_to_include].to_dict(orient='records')


# --- IMPROVED RULE-BASED TECHNICAL ANALYSIS ALGORITHM ---

"""
Enhanced Rule-Based Technical Analysis v2
Author: ChatGPT-for-Dhairya (GPT-5 Thinking mini)
Purpose: Replace the previous generator with a more robust, confidence-weighted,
         risk-aware technical analysis engine.
Inputs:
 - symbol (str)
 - latest_data (list of dicts), each dict must contain at least:
     'Open','High','Low','Close','Volume','MA5','MA10','RSI','MACD','Signal','Histogram'
   Prefer >= 14 rows (lookback default = 14)
Output:
 - Markdown string summarizing analysis, sentiment, recommendation, levels, and confidence.
Notes:
 - Avoids hard "tie" decisions by using dynamic weights and "momentum age".
 - Uses volume as a multiplier to confidence and recommendation aggressiveness.
"""

import math
from typing import List, Dict, Tuple
import numpy as np
import statistics
from datetime import datetime

# -----------------------------
# Helper functions
# -----------------------------
def safe_get(d: Dict, key: str, default=None):
    v = d.get(key, default)
    return None if v is None else v

def mean_or(val_list, fallback=0.0):
    try:
        return statistics.mean(val_list) if val_list else fallback
    except Exception:
        return fallback

def linear_slope(y_values: List[float]) -> float:
    """
    Simple linear slope of y_values vs index (ordinary least squares).
    Returns slope per index.
    """
    if not y_values or len(y_values) < 2:
        return 0.0
    x = np.arange(len(y_values))
    y = np.array(y_values, dtype=float)
    # slope = cov(x,y) / var(x)
    xv = x - x.mean()
    yv = y - y.mean()
    denom = (xv * xv).sum()
    if denom == 0:
        return 0.0
    slope = (xv * yv).sum() / denom
    return float(slope)

def find_recent_macd_crossover(latest_data: List[Dict], lookback:int=14) -> Tuple[str, int]:
    """
    Look for the most recent MACD <-> Signal crossover in the last `lookback` rows.
    Returns ('bullish'|'bearish'|'none', days_ago)
    days_ago = 0 means today, 1 means yesterday, etc. If none found, days_ago = -1
    """
    n = len(latest_data)
    upper = max(1, n - lookback)
    for i in range(n-1, upper-1, -1):
        if i == 0:
            continue
        prev = latest_data[i-1]
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

# -----------------------------
# Core function
# -----------------------------
def generate_rule_based_analysis(symbol: str, latest_data: List[Dict], lookback: int = 14) -> str:
    """
    Generate a confidence-weighted technical analysis.
    """
    try:
        # Basic validation
        if not latest_data or len(latest_data) < 7:
            return "### ⚠️ Analysis Unavailable\nInsufficient data for reliable trend analysis. Need at least 7 rows."

        # Ensure we have numeric lists for lookback period (cap lookback to available rows)
        n = len(latest_data)
        lb = min(lookback, n)
        window = latest_data[-lb:]

        required_fields = ['Close','Volume','MA5','MA10','RSI','MACD','Signal','Histogram','High','Low']
        missing = set()
        for row in window:
            for f in required_fields:
                if f not in row or row.get(f) is None:
                    missing.add(f)
        if missing:
            return f"### ⚠️ Analysis Unavailable\nMissing required fields in input data: {', '.join(sorted(missing))}"

        # Extract latest row
        latest = window[-1]
        close_price = float(latest['Close'])
        rsi = float(latest['RSI'])
        macd = float(latest['MACD'])
        signal = float(latest['Signal'])
        hist = float(latest['Histogram'])
        volume = float(latest['Volume']) if latest['Volume'] is not None else 0.0
        ma5 = float(latest['MA5'])
        ma10 = float(latest['MA10'])
        recent_high = round(max([float(d.get('High', -math.inf)) for d in window]),2)
        recent_low = round(min([float(d.get('Low', math.inf)) for d in window]),2)

        # Build indicator series
        rsi_series = [float(d['RSI']) for d in window]
        macd_series = [float(d['MACD']) for d in window]
        hist_series = [float(d['Histogram']) for d in window]
        vol_series = [float(d['Volume']) for d in window if d.get('Volume') is not None]

        # --- Derived metrics ---
        # RSI velocity: points per day over the window
        rsi_velocity = (rsi_series[-1] - rsi_series[0]) / max(1, (len(rsi_series)-1))

        # MACD slope & histogram slope
        macd_slope = linear_slope(macd_series)
        hist_slope = linear_slope(hist_series)

        # MACD diff & recent crossover
        macd_diff = macd - signal
        crossover_type, crossover_days_ago = find_recent_macd_crossover(window, lookback=lb)

        # Volume context
        avg_vol = mean_or(vol_series, fallback=volume if volume>0 else 1.0)
        volume_ratio = (volume / avg_vol) if avg_vol > 0 else 1.0

        # MA context
        price_vs_ma5 = "above" if close_price > ma5 else "below"
        price_vs_ma10 = "above" if close_price > ma10 else "below"
        ma_trend = "bullish" if ma5 > ma10 else "bearish"
        ma_spread_pct = abs(ma5 - ma10) / ma10 * 100 if ma10 != 0 else 0.0

        # Momentum age: how fresh is the current MACD crossover? Fresh = higher confidence
        momentum_age_score = 0.0
        if crossover_type != 'none' and crossover_days_ago >= 0:
            # Recent crossovers have higher score; older crossovers give less boost
            recency_factor = max(0.0, (lb - crossover_days_ago) / lb)  # 1.0 = today, 0 = old
            momentum_age_score = recency_factor * (1 if crossover_type == 'bullish' else -1)

        # -------------------------
        # Base scoring from each indicator (bounded)
        # -------------------------
        # RSI zone scoring with velocity context (more granular and forgiving)
        def rsi_zone_score_and_note(rsi_val, rsi_vel):
            # returns (score, note, emoji)
            if rsi_val < 30:
                return (2.0, "Oversold - potential reversal zone", "🟢")
            if rsi_val < 40:
                return (1.0, "Lower neutral (bearish pressure)", "🟢")
            if rsi_val < 60:
                return (0.5, "Neutral/healthy", "⚪")
            if rsi_val < 70:
                # approaching overbought
                vel_bonus = 0.5 if rsi_vel > 1.5 else 0.0
                return (0.5 + vel_bonus, "Bullish zone - momentum building", "🟡")
            if rsi_val < 75:
                # overbought but if velocity strong with supportive MACD, less negative
                if rsi_vel > 2.5:
                    return (0.5, "Overbought with strong continuation momentum", "🟡")
                return (-1.0, "Overbought - caution (likely pullback)", "🔴")
            # rsi >= 75
            # If RSI exploded quickly, it's exhaustion risk; else severely overbought
            if rsi_vel > 4.0:
                return (-2.0, "Extremely overbought and fast — exhaustion likely", "🔴")
            return (-1.5, "Severely overbought — high reversal risk", "🔴")

        rsi_score, rsi_note, rsi_emoji = rsi_zone_score_and_note(rsi, rsi_velocity)

        # MACD scoring (consider both diff and slope & histogram slope)
        def macd_score_and_note(diff, slope, hist_slope_val, cross_type):
            # diff sensitivity
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
            else:
                diff_score = 0.0

            slope_score = 0.0
            # slope is per-day-index; scale gently
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

            # crossover_respect
            cross_bonus = 0.0
            if cross_type == 'bullish':
                cross_bonus = 0.75
            elif cross_type == 'bearish':
                cross_bonus = -0.75

            total_macd = diff_score + slope_score + hist_score + cross_bonus
            # note
            note = f"MACD diff={round(diff,3)}, slope={round(slope,4)}, hist_slope={round(hist_slope_val,4)}"
            return (total_macd, note)

        macd_score_val, macd_note = macd_score_and_note(macd_diff, macd_slope, hist_slope, crossover_type)

        # MA / price position scoring
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

        # MA trend strength
        ma_score = 0.0
        if ma_spread_pct > 2:
            ma_score = 0.5 if ma_trend == "bullish" else -0.5
        elif ma_spread_pct > 0.5:
            ma_score = 0.25 if ma_trend == "bullish" else -0.25

        # Volume score: amplify or dampen confidence
        volume_score = 0.0
        if volume_ratio > 1.5:
            volume_score = 1.0
        elif volume_ratio > 1.1:
            volume_score = 0.5
        elif volume_ratio < 0.7:
            volume_score = -1.0
        elif volume_ratio < 0.9:
            volume_score = -0.5

        # -------------------------
        # Fusion: dynamic weighting
        # -------------------------
        # Base weights (modifiable)
        w_macd = 1.2
        w_rsi = 1.0
        w_price = 0.9
        w_ma = 0.4
        w_volume = 0.8  # volume used both as score and multiplier for confidence

        # Boost fresh momentum
        freshness_boost = 0.0
        if crossover_type != 'none' and crossover_days_ago >= 0:
            # give small boost that decays with age
            freshness_boost = max(0.0, (lb - crossover_days_ago) / lb) * 0.5  # up to +0.5

        # Special cooldown for overbought + weakening MACD histogram
        cooldown_penalty = 0.0
        if rsi >= 75 and hist_slope < -0.01:
            # high chance of pullback; penalize bullishness
            cooldown_penalty = -2.0

        # Weighted sentiment
        raw_sentiment = (
            (macd_score_val * w_macd) +
            (rsi_score * w_rsi) +
            (price_pos_score * w_price) +
            (ma_score * w_ma) +
            (volume_score * 0.3)  # volume as minor additive
            + freshness_boost
            + momentum_age_score * 0.8
            + cooldown_penalty
        )

        # Now apply a volume multiplier to the raw sentiment to reflect conviction
        volume_multiplier = 1.0
        # dampen extreme signals if volume is weak
        if volume_ratio < 0.8:
            volume_multiplier = 0.7
        elif volume_ratio > 1.4:
            volume_multiplier = 1.15
        elif volume_ratio > 2.0:
            volume_multiplier = 1.3

        sentiment_score = raw_sentiment * volume_multiplier

        # Normalize sentiment into categories using thresholds
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

        # Confidence metric (based on alignment & volume)
        bullish_signals = 0
        bearish_signals = 0
        # count sub-decisions
        if macd_score_val > 0: bullish_signals += 1
        if rsi_score > 0: bullish_signals += 1
        if price_pos_score > 0: bullish_signals += 1
        if ma_score > 0: bullish_signals += 1
        if volume_score > 0: bullish_signals += 1

        if macd_score_val < 0: bearish_signals += 1
        if rsi_score < 0: bearish_signals += 1
        if price_pos_score < 0: bearish_signals += 1
        if ma_score < 0: bearish_signals += 1
        if volume_score < 0: bearish_signals += 1

        alignment = bullish_signals - bearish_signals
        if abs(alignment) >= 4 and volume_ratio > 1.1:
            confidence = "high"
        elif abs(alignment) >= 2:
            confidence = "medium"
        else:
            confidence = "low"

        # -------------------------
        # Recommendation engine (clearer actionable rules)
        # -------------------------
        recommendation = ""
        risk_note_parts = []

        # compute dynamic stops & scale levels (practical approach)
        # use conservative stop at max(MA10, recent_low) for bullish entries
        conservative_stop = max(ma10, recent_low)
        # trailing stop suggestion (percent)
        trailing_stop_pct = 0.03 if sentiment_score > 2.0 else 0.06 if sentiment_score > 0.5 else 0.08

        # Entry suggestion logic
        if "BULLISH" in overall_sentiment:
            # If overbought & histogram weakening, avoid new aggressive entries
            if rsi >= 75 and hist_slope < -0.01:
                recommendation = f"**Wait / Avoid aggressive new entries** — Overbought (RSI {rsi}) and momentum weakening."
                risk_note_parts.append("High RSI + weakening MACD histogram suggests pullback risk.")
            else:
                # If confidence high & volume supportive, recommend buy with stop or trail
                if confidence == "high" and volume_ratio > 1.1:
                    recommendation = (f"**Buy** (scale-in allowed) — Trend confirmed. Entry near {fmt_price(close_price)}. "
                                      f"Use trailing stop ~{int(trailing_stop_pct*100)}% or stop at {fmt_price(conservative_stop)}.")
                elif confidence == "medium":
                    recommendation = (f"**Cautiously buy / scale in** — Entry near {fmt_price(close_price)}. "
                                      f"Place stop at {fmt_price(conservative_stop)}; scale on pullback.")
                else:  # low confidence
                    recommendation = (f"**Watch / Wait for cleaner setup** — Mixed signals. Consider buying only on pullback to {fmt_price(ma5)}-{fmt_price(ma10)}.")
        elif "BEARISH" in overall_sentiment:
            # bearish recs
            if rsi <= 30:
                recommendation = f"**Watch for reversal** — Oversold but bearish. Wait for MACD confirmation above signal."
                risk_note_parts.append("RSI oversold could limit downside.")
            else:
                recommendation = f"**Reduce exposure / consider shorting** (if your strategy allows) — Downtrend signals dominate."
                risk_note_parts.append("Risk: trend may continue; keep stops tight.")
        else:
            # Neutral
            # Use bias if slight positive or negative numeric
            if sentiment_score > 0.5:
                recommendation = (f"**Range-bound with bullish bias** — Trade ranges; buy dips near {fmt_price(conservative_stop)}, target {fmt_price(recent_high)}.")
            elif sentiment_score < -0.5:
                recommendation = (f"**Range-bound with bearish bias** — Look to reduce longs; prefer short on failed rallies.")
            else:
                recommendation = (f"**Monitor** — Mixed signals. Key triggers: break above {fmt_price(ma5)} for bullish confirmation or below {fmt_price(ma10)} for bearish.")

        # Add volume caution if necessary
        if volume_ratio < 0.8:
            risk_note_parts.append("Volume below average — low conviction.")
        if confidence == "low" and not any("conflicting" in s.lower() for s in risk_note_parts):
            risk_note_parts.append("Conflicting signals — trade with caution.")

        risk_note = " • ".join(risk_note_parts) if risk_note_parts else ""

        # -------------------------
        # Format output
        # -------------------------
        output_lines = []
        output_lines.append(f"### {sentiment_emoji} Technical Analysis for {symbol}")
        output_lines.append("")
        output_lines.append(f"**Overall Sentiment:** {overall_sentiment} ({confidence} confidence)")
        output_lines.append("")
        output_lines.append(f"**Current Price:** {fmt_price(close_price)} ({price_context_note})")
        output_lines.append("")
        output_lines.append("#### 📊 Price Position Analysis")
        output_lines.append(f"- Trading **{price_vs_ma5} MA5 ({fmt_price(ma5)})** and **{price_vs_ma10} MA10 ({fmt_price(ma10)})**")
        output_lines.append(f"- **MA Alignment:** {ma_trend} (spread {round(ma_spread_pct,2)}%)")
        output_lines.append("")
        output_lines.append("#### 🎯 MACD Analysis (Trend Following)")
        output_lines.append(f"- MACD diff: {round(macd_diff,3)}, slope: {round(macd_slope,4)}, hist slope: {round(hist_slope,4)}")
        if crossover_type != 'none':
            output_lines.append(f"- Recent crossover: {crossover_type} {crossover_days_ago} days ago")
        output_lines.append(f"- Note: {macd_note}")
        output_lines.append("")
        output_lines.append("#### 📈 RSI Analysis (Momentum)")
        output_lines.append(f"- RSI at **{round(rsi,2)}** {rsi_emoji} — {rsi_note} (velocity {round(rsi_velocity,3)} pts/day)")
        output_lines.append("")
        output_lines.append("#### 📊 Volume Context")
        output_lines.append(f"- Volume: {volume_ratio:.2f}x avg → {'strong' if volume_ratio>1.1 else 'weak' if volume_ratio<0.9 else 'average'}")
        output_lines.append("")
        output_lines.append("#### 💡 Recommendation")
        output_lines.append(f"{recommendation}{f' **Note:** {risk_note}' if risk_note else ''}")
        output_lines.append("")
        output_lines.append("#### 🧠 Key Levels to Watch")
        output_lines.append(f"- **Support:** {fmt_price(conservative_stop)} (MA10 or recent low)")
        # include multiple support lines if present
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
        output_lines.append("")
        output_lines.append(f"**Model internals (for debugging):** sentiment_score={round(sentiment_score,3)}, raw={round(raw_sentiment,3)}, volume_ratio={round(volume_ratio,3)}, macd_score={round(macd_score_val,3)}, rsi_score={round(rsi_score,3)}, price_pos_score={round(price_pos_score,3)}")

        return "\n".join(output_lines)

    except Exception as e:
        return f"### ❌ Analysis Generation Failed\nError: {str(e)}"

# -----------------------------
# End of file
# -----------------------------

# --- GEMINI AI Function ---

def generate_gemini_review(symbol, latest_data_list):
    """
    Connects to the Gemini API to generate a technical analysis review.
    Returns None if unavailable.
    """
    if client is None:
        return None

    latest_data_json = json.dumps(latest_data_list, indent=2)

    system_instruction = (
        "You are an expert financial analyst focused solely on technical indicators "
        "for the last 7 days of trading data. Your goal is to provide a concise, "
        "professional summary in markdown format."
    )

    prompt = f"""**Stock Symbol:** {symbol}

**Technical Indicator Data (Last 7 Trading Days):**
```json
{latest_data_json}
```

Instructions:
- Start with a main heading '### AI Technical Summary for {symbol}'.
- Provide an 'Overall Sentiment' (BULLISH, BEARISH, or NEUTRAL) based on the MACD crossover and RSI levels.
- Create separate sub-sections for 'RSI Analysis (Momentum)' and 'MACD Analysis (Trend Following)'.
- Conclude with a 'Recommendation' (e.g., 'Monitor,' 'Cautiously buy,' 'Hold').
- Use bold formatting for key figures and sentiment words, but do NOT include the markdown code block in the final output.
"""

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_instruction,
            )
        )
        return response.text
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return None


# --- API Route ---

@app.route('/get_data', methods=['POST'])
def get_data():
    try:
        data = request.json
        symbol = data.get('symbol', '').strip().upper()

        if not symbol:
            return jsonify({"error": "Stock symbol is required"}), 400

        stock = yf.Ticker(symbol)
        hist = stock.history(period="3mo")

        if hist.empty:
            return jsonify(
                {"error": f"No data found for symbol '{symbol}'. Please check the symbol and try again."}), 404

        # Calculate indicators
        hist['MA5'] = hist['Close'].rolling(window=5, min_periods=1).mean()
        hist['MA10'] = hist['Close'].rolling(window=10, min_periods=1).mean()
        hist['RSI'] = compute_rsi(hist['Close'])
        hist['MACD'], hist['Signal'], hist['Histogram'] = compute_macd(hist['Close'])

        # Get the last 7 days for display
        hist_display = hist.tail(7)

        # Prepare the data for analysis
        ai_data_for_prompt = clean_df(
            hist_display,
            ['Open', 'High', 'Low', 'Close', 'Volume', 'MA5', 'MA10', 'RSI', 'MACD', 'Signal', 'Histogram']
        )

        # Generate BOTH analyses
        ai_review_text = None
        if client is not None:
            try:
                ai_review_text = generate_gemini_review(symbol, ai_data_for_prompt)
            except Exception as e:
                print(f"Could not generate AI review: {e}")
                ai_review_text = None

        # Always generate rule-based analysis
        rule_based_text = generate_rule_based_analysis(symbol, ai_data_for_prompt)

        # Prepare JSON response
        response = {
            "ticker": symbol,
            "OHLCV": clean_df(hist_display, ['Open', 'High', 'Low', 'Close', 'Volume']),
            "MA": clean_df(hist_display, ['MA5', 'MA10']),
            "RSI": [convert_to_serializable(x) for x in hist_display['RSI'].tolist()],
            "MACD": clean_df(hist_display, ['MACD', 'Signal', 'Histogram']),
            "AI_Review": "Coming Soon",
            "Rule_Based_Analysis": rule_based_text
        }

        return jsonify(response), 200

    except Exception as e:
        print(f"Error: {str(e)}")
        if "No data found" in str(e):
            return jsonify({"error": f"No data found for symbol '{symbol}'. Please verify the ticker."}), 404
        return jsonify({"error": f"An unexpected server error occurred. Please try again later. ({str(e)})"}), 500


# --- Health Check Route ---

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    gemini_status = "available" if client is not None else "unavailable"
    return jsonify({
        "status": "healthy",
        "gemini_api": gemini_status,
        "rule_based_analysis": "always available"
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 60)
    print("Stock Analysis Backend Server")
    print("=" * 60)
    if client is None:
        print("⚠️ Gemini API not configured - AI analysis will be unavailable")
    else:
        print("✅ Gemini AI configured and available")
    print("✅ Rule-Based Analysis always available")
    print("✅ All data fields properly integrated")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=True)
