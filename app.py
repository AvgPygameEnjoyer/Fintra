from flask import Flask, request, jsonify
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import numpy as np
import os
from google import genai
from google.genai.errors import APIError 
# CORRECT IMPORT: ResourceExhaustedError is usually found in google.api_core.exceptions
from google.api_core.exceptions import ResourceExhaustedError 
import dotenv

app = Flask(__name__)
dotenv.load_dotenv()

# ALLOW YOUR FRONTEND OR ALL ORIGINS (prod safe)
CORS(app, origins="https://budgetjordanbuffet.vercel.app", supports_credentials=True, allow_headers="*", methods=["GET","POST","OPTIONS"])


# --- Gemini API Initialization ---
try:
    # Uses the GEMINI_API_KEY environment variable automatically
    client = genai.Client()
    print("Gemini client initialized successfully.")
except Exception as e:
    # This will catch if the key is not set or invalid upon initialization
    print(f"Warning: Failed to initialize Gemini client. Check GEMINI_API_KEY environment variable. Error: {e}")
    client = None


# --- Helper Functions (RSI, MACD, Serialization) ---

def compute_rsi(series, period=14):
    """Calculate RSI indicator (using EWM for standard formula)"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Standard formula uses ewm (exponentially weighted moving average)
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


# --- GEMINI AI Function (with Rate Limit Fallback) ---

def generate_gemini_review(symbol, latest_data_json):
    """
    Connects to the Gemini API to generate a technical analysis review.
    Includes specific error handling for API issues like rate limits.
    """
    if client is None:
        return """
        ### 🤖 AI Review Unavailable
        The Gemini API client failed to initialize. Please check the `GEMINI_API_KEY` environment variable.
        """

    # --- Construct the Prompt ---
    system_instruction = (
        "You are an expert financial analyst focused solely on technical indicators "
        "for the last 7 days of trading data. Your goal is to provide a concise, "
        "professional summary in a markdown format."
    )

    prompt = (
        f"**Stock Symbol:** {symbol}\n\n"
        "**Technical Indicator Data (Last 7 Trading Days):**\n"
        f"```json\n{latest_data_json}\n```\n\n"
        "**Instructions:**\n"
        "1. Start with a main heading '### AI Technical Summary for {symbol}'.\n"
        "2. Provide an 'Overall Sentiment' (**BULLISH**, **BEARISH**, or **NEUTRAL**) based on the MACD crossover and RSI levels.\n"
        "3. Create separate sub-sections for 'RSI Analysis (Momentum)' and 'MACD Analysis (Trend Following)'.\n"
        "4. Conclude with a 'Recommendation' (e.g., 'Monitor,' 'Cautiously buy,' 'Hold').\n"
        "5. Use **bold** formatting for key figures and sentiment words, but do NOT include the markdown code block in the final output."
    ).format(symbol=symbol)

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_instruction,
            )
        )
        return response.text
    # Catch specific rate limit exception
    except ResourceExhaustedError:
        print(f"Gemini API Rate Limit hit for {symbol}.")
        return """
        ### ⚠️ AI Review Error: Rate Limit Exceeded
        The Gemini API rate limit has been reached. The technical data below is still valid, please try the AI review again shortly.
        """
    # Catch other general API errors
    except APIError as e:
        print(f"Gemini API Error: {e}")
        return f"""
        ### ❌ AI Review Generation Failed
        An API error occurred: {e}. The technical data below is still valid.
        """
    except Exception as e:
        print(f"General AI Error: {e}")
        return f"""
        ### ❌ AI Review Generation Failed
        An unexpected error occurred during AI generation: {e}. The technical data below is still valid.
        """


# --- API Route (Decoupled from AI Error) ---
@app.route('/get_data', methods=['POST'])
def get_data():
    try:
        data = request.json
        symbol = data.get('symbol', '').strip().upper()

        if not symbol:
            return jsonify({"error": "Stock symbol is required"}), 400

        stock = yf.Ticker(symbol)
        # Fetch 3 months of data to ensure RSI and MACD (which have lookback periods of 14/26) are fully calculated.
        hist = stock.history(period="3mo")

        if hist.empty:
            return jsonify(
                {"error": f"No data found for symbol '{symbol}'. Please check the symbol and try again."}), 404

        # Calculate indicators
        hist['MA5'] = hist['Close'].rolling(window=5, min_periods=1).mean()
        hist['MA10'] = hist['Close'].rolling(window=10, min_periods=1).mean()
        hist['RSI'] = compute_rsi(hist['Close'])
        hist['MACD'], hist['Signal'], hist['Histogram'] = compute_macd(hist['Close'])

        # Get the last 7 days for the dashboard display AND for the AI prompt
        hist_display = hist.tail(7)

        # Prepare the data needed for the AI prompt
        ai_data_for_prompt = clean_df(
            hist_display,
            ['Close', 'MA5', 'MA10', 'RSI', 'MACD', 'Signal', 'Histogram']
        )
        # Convert the list of dicts to a JSON string for the prompt
        ai_data_json = pd.Series(ai_data_for_prompt).to_json(indent=2)

        # AI Call: If this fails, it returns a string error message, but does not crash the function.
        ai_review_text = generate_gemini_review(symbol, ai_data_json)

        # Prepare JSON response
        response = {
            "ticker": symbol,
            "OHLCV": clean_df(hist_display, ['Open', 'High', 'Low', 'Close', 'Volume']),
            "MA": clean_df(hist_display, ['MA5', 'MA10']),
            "RSI": [convert_to_serializable(x) for x in hist_display['RSI'].tolist()],
            "MACD": clean_df(hist_display, ['MACD', 'Signal', 'Histogram']),
            "AI_Review": ai_review_text  # Will contain the review or the error message string
        }

        # Return the response with HTTP 200, as the core stock data succeeded.
        return jsonify(response), 200

    except Exception as e:
        print(f"Error: {str(e)}")
        # This general catch block is now only for critical stock-data-related errors (e.g., yfinance failure)
        if "No data found" in str(e):
            return jsonify({"error": f"No data found for symbol '{symbol}'. Please verify the ticker."}), 404

        return jsonify({"error": f"An unexpected server error occurred. Please try again later. ({str(e)})"}), 500


# --- Health Check Route ---
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
