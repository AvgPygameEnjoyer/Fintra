from flask import Flask, request, jsonify
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import numpy as np
import os
import traceback
import json
from datetime import datetime, timedelta

app = Flask(__name__)

# Load environment variables
try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed")

# Simple in-memory cache for AI responses
ai_cache = {}
CACHE_DURATION = timedelta(hours=1)  # Cache AI responses for 1 hour

# CORS Configuration - Allow both production and local development
allowed_origins = [
    "https://budgetjordanbuffet.vercel.app",
    "https://stock-dashboard-fqtn.onrender.com",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173"
]

CORS(app, 
     resources={r"/*": {"origins": allowed_origins}},
     supports_credentials=True, 
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "OPTIONS"])


# --- Gemini API Initialization ---
client = None
try:
    from google import genai
    from google.genai.errors import APIError 
    from google.api_core.exceptions import ResourceExhausted
    
    api_key = os.getenv('GEMINI_API_KEY')
    if api_key:
        client = genai.Client(api_key=api_key)
        print("✓ Gemini client initialized successfully.")
    else:
        print("⚠ Warning: GEMINI_API_KEY not found in environment variables")
except ImportError as e:
    print(f"⚠ Warning: Gemini libraries not installed: {e}")
except Exception as e:
    print(f"⚠ Warning: Failed to initialize Gemini client: {e}")


# --- Helper Functions (RSI, MACD, Serialization) ---

def compute_rsi(series, period=14):
    """Calculate RSI indicator (using EWM for standard formula)"""
    try:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    except Exception as e:
        print(f"Error computing RSI: {e}")
        return pd.Series([None] * len(series), index=series.index)


def compute_macd(series):
    """Calculate MACD, Signal line, and Histogram"""
    try:
        ema12 = series.ewm(span=12, adjust=False).mean()
        ema26 = series.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal
        return macd, signal, histogram
    except Exception as e:
        print(f"Error computing MACD: {e}")
        null_series = pd.Series([None] * len(series), index=series.index)
        return null_series, null_series, null_series


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
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def clean_df(df, columns):
    """Clean DataFrame and convert to JSON-safe format"""
    try:
        df = df.copy().reset_index()

        if 'Date' in df.columns:
            df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')

        for col in columns:
            if col in df.columns:
                df[col] = df[col].apply(convert_to_serializable)

        cols_to_include = ['Date'] + [col for col in columns if col in df.columns]
        return df[cols_to_include].to_dict(orient='records')
    except Exception as e:
        print(f"Error in clean_df: {e}")
        return []


# --- GEMINI AI Function (with Rate Limit Fallback) ---

def generate_gemini_review(symbol, latest_data_list):
    """
    Connects to the Gemini API to generate a technical analysis review.
    Includes specific error handling for API issues like rate limits.
    """
    if client is None:
        return """
### 🤖 AI Review Unavailable
The AI analysis service is currently unavailable. Technical indicators are displayed below.
"""

    try:
        # Convert list of dicts to properly formatted JSON string
        latest_data_json = json.dumps(latest_data_list, indent=2)

        # --- Construct the Prompt ---
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

**Instructions:**
1. Start with a main heading '### AI Technical Summary for {symbol}'.
2. Provide an 'Overall Sentiment' (**BULLISH**, **BEARISH**, or **NEUTRAL**) based on the MACD crossover and RSI levels.
3. Create separate sub-sections for 'RSI Analysis (Momentum)' and 'MACD Analysis (Trend Following)'.
4. Conclude with a 'Recommendation' (e.g., 'Monitor,' 'Cautiously buy,' 'Hold').
5. Use **bold** formatting for key figures and sentiment words, but do NOT include the markdown code block in the final output."""

        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_instruction,
            )
        )
        return response.text
    except NameError:
        return """
### 🤖 AI Review Unavailable
Gemini API libraries not available. Technical indicators are displayed below.
"""
    except Exception as e:
        error_name = type(e).__name__
        if 'ResourceExhausted' in error_name:
            print(f"Gemini API Rate Limit hit for {symbol}.")
            return """
### ⚠️ AI Review Error: Rate Limit Exceeded
The Gemini API rate limit has been reached. Please try again shortly.
"""
        print(f"Gemini API Error ({error_name}): {e}")
        return """
### ⚠️ AI Review Temporarily Unavailable
Unable to generate AI analysis at this time. Technical indicators are displayed below.
"""


# --- Root Route ---
@app.route('/', methods=['GET', 'OPTIONS'])
def root():
    """Root endpoint"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        return response, 200
    
    return jsonify({
        "message": "Stock Analysis API",
        "version": "1.0",
        "status": "running",
        "ai_enabled": client is not None,
        "frontend": "https://budgetjordanbuffet.vercel.app",
        "endpoints": {
            "/health": "GET - Health check",
            "/get_data": "POST - Get stock data and analysis (requires 'symbol' in JSON body)"
        }
    }), 200


# --- API Route (Decoupled from AI Error) ---
@app.route('/get_data', methods=['POST', 'OPTIONS'])
def get_data():
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        return response, 200
    
    try:
        # Parse request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
            
        symbol = data.get('symbol', '').strip().upper()

        if not symbol:
            return jsonify({"error": "Stock symbol is required"}), 400

        print(f"Fetching data for symbol: {symbol}")

        # Fetch stock data
        stock = yf.Ticker(symbol)
        hist = stock.history(period="3mo")

        if hist.empty:
            return jsonify(
                {"error": f"No data found for symbol '{symbol}'. Please check the symbol and try again."}), 404

        print(f"Successfully fetched {len(hist)} rows of data for {symbol}")

        # Calculate indicators
        hist['MA5'] = hist['Close'].rolling(window=5, min_periods=1).mean()
        hist['MA10'] = hist['Close'].rolling(window=10, min_periods=1).mean()
        hist['RSI'] = compute_rsi(hist['Close'])
        hist['MACD'], hist['Signal'], hist['Histogram'] = compute_macd(hist['Close'])

        # Get the last 7 days for display
        hist_display = hist.tail(7)

        # Prepare the data for the AI prompt
        ai_data_for_prompt = clean_df(
            hist_display,
            ['Close', 'MA5', 'MA10', 'RSI', 'MACD', 'Signal', 'Histogram']
        )

        # AI Call
        ai_review_text = generate_gemini_review(symbol, ai_data_for_prompt)

        # Prepare JSON response
        response_data = {
            "ticker": symbol,
            "OHLCV": clean_df(hist_display, ['Open', 'High', 'Low', 'Close', 'Volume']),
            "MA": clean_df(hist_display, ['MA5', 'MA10']),
            "RSI": [convert_to_serializable(x) for x in hist_display['RSI'].tolist()],
            "MACD": clean_df(hist_display, ['MACD', 'Signal', 'Histogram']),
            "AI_Review": ai_review_text
        }

        print(f"Successfully prepared response for {symbol}")
        return jsonify(response_data), 200

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Error in get_data: {str(e)}")
        print(f"Traceback:\n{error_trace}")
        
        if "No data found" in str(e):
            return jsonify({"error": f"No data found for symbol. Please verify the ticker."}), 404

        return jsonify({
            "error": "An unexpected server error occurred. Please try again later.",
            "details": str(e) if app.debug else None
        }), 500


# --- Health Check Route ---
@app.route('/health', methods=['GET', 'OPTIONS'])
def health():
    """Health check endpoint"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,OPTIONS')
        return response, 200
    
    return jsonify({
        "status": "healthy",
        "ai_enabled": client is not None,
        "timestamp": pd.Timestamp.now().isoformat()
    }), 200


# --- Error Handlers ---
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found. Available endpoints: /, /health, /get_data"}), 404


@app.errorhandler(500)
def internal_error(e):
    print(f"500 Error: {str(e)}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Starting Flask server on port {port}...")
    print(f"📍 Available endpoints: /, /health, /get_data")
    print(f"🤖 AI Status: {'Enabled' if client else 'Disabled'}")
    app.run(host="0.0.0.0", port=port, debug=False)
