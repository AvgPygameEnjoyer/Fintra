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

def generate_rule_based_analysis(symbol, latest_data):
    """
    Enhanced rule-based technical analysis with proper data validation,
    improved logic, and actionable recommendations.
    """
    try:
        if not latest_data or len(latest_data) < 4:
            return "### ⚠️ Analysis Unavailable\nInsufficient data for multi-day trend analysis."

        # Validate all required fields exist
        required_fields = ['Close', 'Volume', 'MA5', 'MA10', 'RSI', 'MACD', 'Signal', 'Histogram']
        latest = latest_data[-1]

        missing_fields = [field for field in required_fields if field not in latest or latest[field] is None]
        if missing_fields:
            return f"### ⚠️ Analysis Unavailable\nMissing data fields: {', '.join(missing_fields)}"

        # --- Extract and Round Key Indicators ---
        close_price = round(latest.get("Close"), 2)
        rsi = round(latest.get("RSI"), 2)
        macd = round(latest.get("MACD"), 3)
        macd_signal = round(latest.get("Signal"), 3)
        macd_hist = round(latest.get("Histogram"), 3)
        volume = latest.get("Volume")
        ma5 = round(latest.get("MA5"), 2)
        ma10 = round(latest.get("MA10"), 2)

        # --- Volume Analysis ---
        volume_data = [d.get("Volume", 0) for d in latest_data if d.get("Volume") is not None]
        avg_vol = np.mean(volume_data) if volume_data else volume
        volume_trend = "strong" if volume >= avg_vol else "weak"

        # --- RSI Trend Analysis ---
        rsi_values = [round(d.get("RSI", 0), 2) for d in latest_data]
        rsi_change = rsi_values[-1] - rsi_values[0]

        if rsi_change > 8:
            rsi_trend = "strongly increasing"
        elif rsi_change > 3:
            rsi_trend = "increasing"
        elif rsi_change < -8:
            rsi_trend = "strongly decreasing"
        elif rsi_change < -3:
            rsi_trend = "decreasing"
        else:
            rsi_trend = "stable"

        # RSI Zone with proper thresholds
        def get_rsi_zone(rsi_val):
            if rsi_val < 30:
                return "oversold", "🟢"
            elif rsi_val > 70:
                return "overbought", "🔴"
            elif rsi_val > 60:
                return "approaching overbought", "🟡"
            elif rsi_val < 40:
                return "approaching oversold", "🟡"
            else:
                return "neutral", "⚪"

        rsi_zone, rsi_zone_emoji = get_rsi_zone(rsi)

        # --- MACD Trend Analysis ---
        macd_diff = macd - macd_signal
        macd_hist_values = [d.get("Histogram", 0) for d in latest_data]
        macd_hist_change = macd_hist_values[-1] - macd_hist_values[0]

        # Detect crossovers
        crossover_info = None
        for i in range(len(latest_data) - 1):
            prev_macd = latest_data[i].get("MACD", 0)
            prev_signal = latest_data[i].get("Signal", 0)
            curr_macd = latest_data[i + 1].get("MACD", 0)
            curr_signal = latest_data[i + 1].get("Signal", 0)

            prev_diff = prev_macd - prev_signal
            curr_diff = curr_macd - curr_signal

            if prev_diff <= 0 and curr_diff > 0:
                days_ago = len(latest_data) - i - 2
                crossover_info = f"Bullish crossover occurred {days_ago} days ago"
                break
            elif prev_diff >= 0 and curr_diff < 0:
                days_ago = len(latest_data) - i - 2
                crossover_info = f"Bearish crossover occurred {days_ago} days ago"
                break

        # MACD momentum
        if macd_hist_change > 0.1:
            macd_momentum = "strengthening bullish momentum"
        elif macd_hist_change < -0.1:
            macd_momentum = "strengthening bearish momentum"
        else:
            macd_momentum = "relatively stable momentum"

        # --- Moving Average Analysis ---
        ma_trend = "bullish" if ma5 > ma10 else "bearish"
        ma_spread = round(abs(ma5 - ma10) / ma10 * 100, 2)

        # --- Sentiment Scoring ---
        sentiment_score = 0

        # MACD Scoring
        if crossover_info and "Bullish" in crossover_info:
            sentiment_score += 2
        elif crossover_info and "Bearish" in crossover_info:
            sentiment_score -= 2
        elif macd_diff > 0:
            sentiment_score += 1
        else:
            sentiment_score -= 1

        # RSI Scoring with context
        if rsi_zone == "oversold":
            sentiment_score += 1.5
        elif rsi_zone == "overbought":
            sentiment_score -= 1.5
        elif "increasing" in rsi_trend and rsi_zone != "overbought":
            sentiment_score += 1
        elif "decreasing" in rsi_trend and rsi_zone != "oversold":
            sentiment_score -= 1

        # MA Scoring
        if ma_trend == "bullish":
            sentiment_score += 0.5
        else:
            sentiment_score -= 0.5

        # Volume Scoring
        if volume_trend == "strong":
            sentiment_score += 0.5
        else:
            sentiment_score -= 0.3

        # --- Determine Overall Sentiment ---
        if sentiment_score >= 2.5:
            overall_sentiment = "**BULLISH**"
            sentiment_color = "🟢"
        elif sentiment_score <= -2.5:
            overall_sentiment = "**BEARISH**"
            sentiment_color = "🔴"
        else:
            overall_sentiment = "**NEUTRAL**"
            sentiment_color = "🟡"

        # --- Construct Narrative ---
        rsi_summary = f"RSI is at **{rsi}** ({rsi_zone_emoji} {rsi_zone}), showing **{rsi_trend}** momentum from {rsi_values[0]} to {rsi_values[-1]} over 7 days."

        macd_summary = f"MACD line at **{macd}** vs signal at **{macd_signal}**, histogram at **{macd_hist}**. {macd_momentum}."
        if crossover_info:
            macd_summary += f" **{crossover_info}**."

        ma_summary = f"MA5 (**{ma5}**) is **{ma_trend}** vs MA10 (**{ma10}**) with {ma_spread}% spread."

        volume_summary = f"Volume is **{volume_trend}** compared to 7-day average."

        # --- Risk-Aware Recommendation ---
        if overall_sentiment == "**BULLISH**":
            if rsi_zone == "overbought":
                recommendation = f"**Wait for pullback** - Strong bullish signals but RSI overbought. Consider buying on dips near support levels with stop-loss at {ma10}."
            elif "approaching overbought" in rsi_zone:
                recommendation = f"**Cautiously buy** - Bullish trend confirmed but approaching overbought. Scale in positions with stop-loss at {ma10}."
            else:
                recommendation = f"**Consider buying** - Multiple bullish signals aligned. Entry near {close_price} with stop-loss at {ma10}."
        elif overall_sentiment == "**BEARISH**":
            if rsi_zone == "oversold":
                recommendation = f"**Watch for reversal** - Bearish but oversold. Potential bounce near current levels. Wait for bullish confirmation."
            else:
                recommendation = f"**Consider selling/avoid buying** - Bearish signals dominant. Reduce exposure or wait for trend reversal above {ma5}."
        else:
            recommendation = f"**Monitor/range trade** - Mixed signals. Consider range-bound strategies between support {ma10} and resistance {ma5}."

        # --- Format Output ---
        output = f"""### {sentiment_color} Technical Analysis for {symbol}

**Overall Sentiment:** {overall_sentiment}

**Current Price:** ${close_price}

#### 📊 RSI Analysis (Momentum)
{rsi_summary}

#### 🎯 MACD Analysis (Trend Following)
{macd_summary}

#### 📈 Moving Average (Trend Confirmation)
{ma_summary}

#### 📊 Volume Context  
{volume_summary}

#### 💡 Recommendation
{recommendation}

#### 🧠 Key Levels to Watch
- **Support:** ${ma10} (MA10)
- **Resistance:** ${ma5} (MA5)
- **RSI Zone:** {rsi_zone.title()}
"""

        return output

    except Exception as e:
        print(f"Error generating analysis: {e}")
        return f"### ❌ Analysis Generation Failed\nError: {str(e)}"


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
            "AI_Review": ai_review_text,
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
