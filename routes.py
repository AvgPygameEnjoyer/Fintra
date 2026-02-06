"""
Routes Module
Defines all Flask routes and API endpoints.
"""
import logging
import os
import secrets
import traceback
import jwt
import requests
import yfinance as yf
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from flask import Blueprint, request, jsonify, session, redirect, make_response
import pandas as pd

from config import Config
from auth import (
    generate_jwt_token, verify_jwt_token,
    set_token_cookies, require_auth
)
from database import db
from models import User, Position
from analysis import (
    latest_symbol_data, conversation_context, clean_df,
    compute_rsi, compute_macd, generate_rule_based_analysis, call_gemini_api,
    get_gemini_ai_analysis, get_gemini_position_summary,
    find_recent_macd_crossover
)
from backtesting import BacktestEngine, load_stock_data, check_data_availability, DATA_LAG_DAYS
from mc_engine import MonteCarloEngine, SimulationConfig

# Redis and RAG imports
try:
    from redis_client import redis_client, init_redis, ChatCache, RateLimiter, DataCache
    from rag_engine import rag_engine, init_rag
    REDIS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Redis/RAG modules not available: {e}")
    REDIS_AVAILABLE = False

# Helper function to apply SEBI compliance lag to yfinance data
def apply_sebi_lag_to_data(hist_df):
    """Apply 31-day SEBI compliance lag to yfinance DataFrame."""
    if hist_df.empty:
        return hist_df
    
    # Create lag date with UTC timezone to match yfinance data
    lag_date = datetime.now(timezone.utc) - timedelta(days=DATA_LAG_DAYS)
    original_count = len(hist_df)
    
    # Convert index to UTC if timezone-aware, or keep as-is if naive
    if hist_df.index.tz is not None:
        lag_date = lag_date.astimezone(hist_df.index.tz)
    
    # Filter to only include data up to lag date
    filtered_df = hist_df[hist_df.index <= lag_date].copy()
    
    if len(filtered_df) < original_count:
        logger.info(f"Applied {DATA_LAG_DAYS}-day SEBI lag to yfinance data: {original_count - len(filtered_df)} rows excluded")
    
    return filtered_df

logger = logging.getLogger(__name__)

# Create Blueprint for all routes
api = Blueprint('api', __name__)


# ==================== PORTFOLIO HELPERS ====================
def get_user_from_token():
    """Helper to get user_id and db_user from access token."""
    access_token = request.cookies.get('access_token')

    # Fallback: Check Authorization Header if cookie is missing
    if not access_token:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]

    if not access_token:
        return None, None

    payload = verify_jwt_token(access_token, Config.ACCESS_TOKEN_JWT_SECRET)
    if not payload:
        return None, None

    user_id = payload.get('user_id')
    if not user_id:
        return None, None

    db_user = User.query.filter_by(google_user_id=user_id).first()
    if not db_user:
        logger.warning(f"⚠️ Auth Debug: Token valid for user_id '{user_id}', but User not found in DB.")
    return user_id, db_user


# ==================== AUTHENTICATION ROUTES ====================
@api.route('/auth/login', methods=['GET', 'OPTIONS'])
def auth_login():
    """Initiate Google OAuth flow."""
    try:
        state = secrets.token_urlsafe(32)
        
        logger.info(f"Generating auth URL with redirect_uri: {Config.REDIRECT_URI}")

        auth_params = {
            'client_id': Config.GOOGLE_CLIENT_ID,
            'redirect_uri': Config.REDIRECT_URI,
            'response_type': 'code',
            'scope': ' '.join(Config.SCOPES),
            'access_type': 'offline',
            'prompt': 'select_account',
            'state': state
        }
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(auth_params)}"

        resp = jsonify(success=True, auth_url=auth_url, state_token=state)
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return resp, 200
    except Exception as e:
        logger.error(f"❌ OAuth initiation error: {e}")
        return jsonify(error=f"Failed to initiate OAuth: {str(e)}"), 500


@api.route('/oauth2callback', methods=['GET'])
def oauth_callback():
    """Handle OAuth callback safely with detailed logging."""
    try:
        logger.info("--- OAuth Callback Start ---")
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')

        if error:
            logger.error(f"Google returned error: {error}")
            return redirect(f'{Config.CLIENT_REDIRECT_URL}?error=auth_failed&reason={error}')

        if not code:
            logger.error("No 'code' parameter found in callback.")
            return redirect(f'{Config.CLIENT_REDIRECT_URL}?error=no_code')

        logger.info(f"State parameter received: {state}. In a full stateless flow, this would be validated against a client-provided token.")

        logger.info("Exchanging code for tokens...")
        token_data = {
            'code': code,
            'client_id': Config.GOOGLE_CLIENT_ID,
            'client_secret': Config.GOOGLE_CLIENT_SECRET,
            'redirect_uri': Config.REDIRECT_URI,
            'grant_type': 'authorization_code'
        }
        
        try:
            token_response = requests.post("https://oauth2.googleapis.com/token", data=token_data, timeout=10)
            token_response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Token exchange request failed: {e}")
            return redirect(f'{Config.CLIENT_REDIRECT_URL}?error=token_exchange_failed&reason=network_error')

        tokens = token_response.json()
        id_token = tokens.get('id_token')
        if not id_token:
            logger.error(f"Token exchange response did not include an id_token: {tokens}")
            return redirect(f'{Config.CLIENT_REDIRECT_URL}?error=missing_id_token')

        logger.info("Tokens received. Decoding ID token...")

        try:
            user_info = jwt.decode(id_token, options={"verify_signature": False})
        except Exception as e:
            logger.error(f"Failed to decode ID token: {e}")
            return redirect(f'{Config.CLIENT_REDIRECT_URL}?error=invalid_id_token')

        user_id = user_info.get('sub')
        if not user_id:
            logger.error("No 'sub' (user_id) in ID token.")
            return redirect(f'{Config.CLIENT_REDIRECT_URL}?error=missing_user_id')
        logger.info(f"OAuth callback processing for Google User ID: {user_id}")

        # --- NEW: Sync with database ---
        # Find user in our DB or create them if they are new.
        db_user = User.query.filter_by(google_user_id=user_id).first()
        if not db_user:
            db_user = User(
                google_user_id=user_id,
                email=user_info.get('email'),
                name=user_info.get('name'),
                picture=user_info.get('picture')
            )
            db.session.add(db_user)
        else: # Update user info if it has changed
            db_user.email = user_info.get('email')
            db_user.name = user_info.get('name')
            db_user.picture = user_info.get('picture')
        db.session.commit()

        logger.info(f"User '{user_info.get('email')}' authenticated. Storing session.")
        # This user_data is only for JWT generation, not for in-memory session state.
        user_data_for_jwt = {
            'user_id': user_id,
            'email': user_info.get('email'),
            'name': user_info.get('name')
        }

        jwt_access = generate_jwt_token(user_data_for_jwt, Config.ACCESS_TOKEN_JWT_SECRET,
                                        Config.ACCESS_TOKEN_EXPIRETIME)
        jwt_refresh = generate_jwt_token(user_data_for_jwt, Config.REFRESH_TOKEN_JWT_SECRET,
                                         Config.REFRESH_TOKEN_EXPIRETIME)

        # Generate redirect URL with tokens as query params (Fallback for when cookies are blocked)
        # This allows the frontend to grab tokens from URL if Set-Cookie fails.
        redirect_params = {
            'access_token': jwt_access,
            'refresh_token': jwt_refresh
        }
        redirect_url = f"{Config.CLIENT_REDIRECT_URL}?{urlencode(redirect_params)}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
            <head><title>Redirecting...</title></head>
            <body>
                <p>Authentication successful. Redirecting you to the app...</p>
                <script>window.location.href = "{redirect_url}";</script>
            </body>
        </html>
        """
        response = make_response(html_content)
        response.headers['Content-Type'] = 'text/html'
        set_token_cookies(response, jwt_access, jwt_refresh)

        logger.info("--- OAuth Callback End: Success ---")
        return response

    except Exception as e:
        logger.error(f"CRITICAL ERROR in /oauth2callback: {e}")
        logger.error(traceback.format_exc()) # Log the full traceback for debugging
        # Create a safe, user-friendly error message without newlines
        error_reason = "db_connection_failed" if "OperationalError" in str(e) else "internal_error"
        return redirect(f'{Config.CLIENT_REDIRECT_URL}?error=callback_crash&reason={error_reason}')


@api.route('/auth/token/refresh', methods=['POST'])
def refresh_token():
    """Refresh JWT access token"""
    # This endpoint is now deprecated. The `require_auth` decorator handles token refresh automatically.
    return jsonify(error="This endpoint is deprecated. Token refresh is handled by the auth middleware."), 410


@api.route('/auth/logout', methods=['POST', 'OPTIONS'])
def logout():
    """Logout user and clear session"""
    try:
        logger.info("User logout initiated.")
        response = jsonify(success=True, message="Logged out")
        response.set_cookie('access_token', '', max_age=0, path='/')
        response.set_cookie('refresh_token', '', max_age=0, path='/')
        return response, 200
    except Exception as e:
        logger.error(f"❌ Logout error: {e}")
        return jsonify(error="Logout failed"), 500


@api.route('/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status with robust token handling"""
    logger.info("🔍 /auth/status called - Checking for tokens...")
    try:
        # Prioritize cookie, but fall back to Authorization header.
        # This makes the endpoint compatible with both cookie-based sessions and the URL token fallback.
        access_token = request.cookies.get('access_token')
        refresh_token = request.cookies.get('refresh_token')

        if not access_token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith("Bearer "):
                logger.info("Auth status: No cookie found, using 'Authorization: Bearer' header.")
                access_token = auth_header.split(" ")[1]
        
        # 1. Try Access Token
        if access_token:
            payload = verify_jwt_token(access_token, Config.ACCESS_TOKEN_JWT_SECRET)
            if payload:
                user_id = payload.get('user_id')
                if user_id:
                    db_user = User.query.filter_by(google_user_id=user_id).first()
                    if db_user:
                        expires_at = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
                        response = jsonify(
                            authenticated=True,
                            user={
                                "email": db_user.email,
                                "name": db_user.name,
                                "picture": db_user.picture,
                                "expires_in": int((expires_at - datetime.now(timezone.utc)).total_seconds())
                            }
                        )
                        # Prevent caching of auth status
                        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                        return response, 200
                    else:
                        logger.warning(f"Auth status: Valid access token for user_id {user_id}, but user not found in DB.")
                else:
                    logger.warning("Auth status: Access token payload missing user_id.")
        
        # 2. Fallback: Try Refresh Token (if access token missing or invalid)
        if refresh_token:
            payload = verify_jwt_token(refresh_token, Config.REFRESH_TOKEN_JWT_SECRET)
            if payload:
                user_id = payload.get('user_id')
                if user_id:
                    db_user = User.query.filter_by(google_user_id=user_id).first()
                    if db_user:
                        # Generate new access token
                        user_data = {'user_id': db_user.google_user_id, 'email': db_user.email, 'name': db_user.name}
                        new_access_token = generate_jwt_token(user_data, Config.ACCESS_TOKEN_JWT_SECRET, Config.ACCESS_TOKEN_EXPIRETIME)
                        
                        # Return authenticated with new cookie
                        response = jsonify(
                            authenticated=True,
                            user={
                                "email": db_user.email,
                                "name": db_user.name,
                                "picture": db_user.picture,
                                "expires_in": Config.parse_time_to_seconds(Config.ACCESS_TOKEN_EXPIRETIME)
                            }
                        )
                        set_token_cookies(response, new_access_token, refresh_token)
                        logger.info(f"🔄 Auth status recovered session via refresh token for {db_user.email}")
                        # Prevent caching
                        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                        return response, 200
                    else:
                        logger.warning(f"Auth status: Valid refresh token for user_id {user_id}, but user not found in DB.")
                else:
                    logger.warning("Auth status: Refresh token payload missing user_id.")

        logger.info(f"Auth status check failed. Access cookie present: {bool(access_token)}, Refresh cookie present: {bool(refresh_token)}")
        response = jsonify(authenticated=False)
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response, 200
    except Exception as e:
        logger.error(f"❌ Auth status error: {e}")
        logger.error(traceback.format_exc())
        return jsonify(authenticated=False), 200

@api.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify(
        status="healthy",
        services={
            "yfinance": "operational",
            "rule_based_analysis": "operational",
            "oauth_authentication": "enabled"
        },
        version="5.0-Stateless",
        env="production" # Hardcoded for production
    ), 200


@api.route('/ping')
def ping():
    return "ok", 200


@api.route('/data/availability', methods=['GET'])
def get_data_availability():
    """
    Get data availability information including SEBI compliance lag status.
    Returns information about available data range and compliance.
    """
    try:
        availability = check_data_availability()
        return jsonify(availability), 200
    except Exception as e:
        logger.error(f"Error getting data availability: {e}")
        return jsonify({
            'available': False,
            'error': str(e),
            'lag_days': DATA_LAG_DAYS
        }), 500


@api.route('/stock/<symbol>/date_range', methods=['GET'])
def get_stock_date_range(symbol):
    """
    Get available date range for a specific stock symbol.
    Returns first and last available dates from parquet data.
    """
    try:
        if not symbol:
            return jsonify(error="Symbol is required"), 400
        
        symbol = symbol.upper().strip()
        df, compliance_info = load_stock_data(symbol, apply_lag=True)
        
        if df is None:
            return jsonify(error=f"Data not found for symbol {symbol}"), 404
        
        return jsonify({
            'symbol': symbol,
            'first_date': df.index.min().strftime('%Y-%m-%d'),
            'last_date': df.index.max().strftime('%Y-%m-%d'),
            'total_days': len(df),
            'lag_days': DATA_LAG_DAYS,
            'lag_date': (datetime.now() - timedelta(days=DATA_LAG_DAYS)).strftime('%Y-%m-%d')
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting date range for {symbol}: {e}")
        return jsonify(error=str(e)), 500


# ==================== DATA & ANALYSIS ROUTES ====================
@api.route('/get_data', methods=['POST'])
def get_data():
    """Fetch and analyze stock data"""
    auth_response = require_auth()
    if auth_response:
        return auth_response
    logger.info("Received request for /api/get_data") # This log is now reachable
    data = request.get_json()
    symbol = data.get('symbol', '').upper().strip()
    user_id, _ = get_user_from_token()

    if not symbol:
        return jsonify(error="No symbol provided"), 400

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="90d", interval="1d")

        if hist.empty:
            return jsonify(error=f"Could not retrieve data for {symbol}"), 404
        
        # Apply 31-day SEBI compliance lag
        hist = apply_sebi_lag_to_data(hist)
        
        if hist.empty:
            return jsonify(error=f"No data available for {symbol} within SEBI compliance lag period ({DATA_LAG_DAYS} days)"), 404

        hist['MA5'] = hist['Close'].rolling(window=5).mean()
        hist['MA10'] = hist['Close'].rolling(window=10).mean()
        hist['RSI'] = compute_rsi(hist['Close'])
        hist['MACD'], hist['Signal'], hist['Histogram'] = compute_macd(hist['Close'])

        hist_display = hist.dropna(subset=['MA5', 'MA10', 'RSI', 'MACD', 'Signal', 'Histogram'])
        latest_data_list = clean_df(hist_display,
                                    ['Open', 'High', 'Low', 'Close', 'Volume', 'MA5', 'MA10', 'RSI', 'MACD', 'Signal',
                                     'Histogram'])

        latest_symbol_data[symbol] = latest_data_list

        rule_based_text = generate_rule_based_analysis(symbol, latest_data_list)
        gemini_analysis = get_gemini_ai_analysis(symbol, latest_data_list)

        if user_id not in conversation_context:
            conversation_context[user_id] = {
                "current_symbol": symbol,
                "conversation_history": [],
                "last_active": datetime.now(timezone.utc).isoformat(),
                "user_positions": {}
            }
        else:
            conversation_context[user_id]["current_symbol"] = symbol
            conversation_context[user_id]["last_active"] = datetime.now(timezone.utc).isoformat()

        # Prepare compliance information
        lag_date = datetime.now() - timedelta(days=DATA_LAG_DAYS)
        effective_date = hist.index.max().strftime('%Y-%m-%d') if not hist.empty else None
        
        return jsonify(
            ticker=symbol,
            OHLCV=clean_df(hist_display, ['Open', 'High', 'Low', 'Close', 'Volume']),
            MA=clean_df(hist_display, ['MA5', 'MA10']),
            RSI=clean_df(hist_display, ['RSI']),
            MACD=clean_df(hist_display, ['MACD', 'Signal', 'Histogram']),
            AI_Review=gemini_analysis,
            Rule_Based_Analysis=rule_based_text,
            sebi_compliance={
                'data_lag_days': DATA_LAG_DAYS,
                'effective_last_date': effective_date,
                'lag_date': lag_date.strftime('%Y-%m-%d'),
                'compliance_notice': f"This analysis uses historical data with a mandatory {DATA_LAG_DAYS}-day lag in accordance with SEBI regulations. No current market data is included."
            }
        ), 200
    except Exception as e:
        logger.error(f"❌ Error in /api/get_data: {e}")
        return jsonify(error=f"Server error: {str(e)}"), 500


@api.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    """
    Chatbot endpoint with Redis caching, rate limiting, and RAG.
    Provides educational responses about technical analysis.
    """
    if request.method == 'OPTIONS':
        return jsonify(success=True), 200

    auth_response = require_auth()
    if auth_response:
        return auth_response

    # Get user ID for rate limiting
    user_id = request.cookies.get('access_token', 'anonymous')
    
    # Rate limiting check (30 requests per minute)
    if REDIS_AVAILABLE and RateLimiter.is_allowed(user_id, 'chat', max_requests=30):
        remaining = RateLimiter.get_remaining(user_id, 'chat', max_requests=30)
    else:
        return jsonify(
            error="Rate limit exceeded. Please wait a moment before sending more messages.",
            retry_after=60
        ), 429

    data = request.get_json()
    if not data:
        return jsonify(error="No data provided"), 400

    query = data.get('query', '').strip()
    if not query:
        return jsonify(error="No query provided"), 400

    # Get context mode and related data
    mode = data.get('mode', 'none')  # 'none', 'market', or 'portfolio'
    symbol = data.get('symbol')  # For market mode
    selected_position_id = data.get('position_id')  # For portfolio mode

    # Build cache key context
    cache_context = {
        "mode": mode,
        "symbol": symbol,
        "position_id": selected_position_id
    }

    try:
        # Check cache first
        if REDIS_AVAILABLE:
            cached_response = ChatCache.get(query, cache_context)
            if cached_response:
                logger.debug("Chat cache hit - returning cached response")
                return jsonify(
                    response=cached_response,
                    context=cache_context,
                    cached=True,
                    rate_limit_remaining=remaining
                ), 200

        # Load system prompt
        import os
        BASE_DIR = os.path.dirname(os.path.dirname(__file__))
        system_prompt_path = os.path.join(BASE_DIR, 'system_prompt.txt')
        
        try:
            with open(system_prompt_path, 'r') as f:
                system_prompt = f.read().strip()
        except Exception as e:
            logger.warning(f"Could not load system prompt: {e}")
            system_prompt = "You are Fintra, a friendly AI assistant helping users learn about stock market technical analysis. Be conversational and educational."

        # Build context based on mode
        context_str = ""
        current_context = {"mode": mode}

        if mode == 'market' and symbol:
            # Market mode - user selected a stock
            context_str = f"\n[MARKET CONTEXT]: The user is asking about {symbol}. This is historical data (31-day lag per SEBI). Current stock: {symbol}"
            current_context["symbol"] = symbol
            
        elif mode == 'portfolio' and selected_position_id:
            # Portfolio mode - user selected a position
            _, db_user = get_user_from_token()
            if db_user:
                position = Position.query.filter_by(id=selected_position_id, user_id=db_user.id).first()
                if position:
                    context_str = f"\n[PORTFOLIO CONTEXT]: The user has a position in {position.symbol} - {position.quantity} shares at entry price ₹{position.entry_price}. This is historical performance data (31-day lag per SEBI)."
                    current_context["position"] = {
                        "symbol": position.symbol,
                        "quantity": position.quantity,
                        "entry_price": float(position.entry_price)
                    }
        else:
            # General chat mode - no specific context
            context_str = "\n[GENERAL CHAT]: No specific stock or position context. Answer general educational questions."
            current_context["mode"] = "none"

        # RAG: Retrieve relevant knowledge
        rag_context = ""
        sources = []
        if REDIS_AVAILABLE and rag_engine.model:
            try:
                retrieved_docs = rag_engine.search(query, top_k=2)
                if retrieved_docs:
                    rag_context = rag_engine.assemble_context(query, retrieved_docs)
                    sources = [doc['title'] for doc in retrieved_docs]
                    logger.debug(f"RAG retrieved {len(retrieved_docs)} documents")
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}")

        # Build prompt
        safe_query = query[:500]  # Limit query length
        
        # Construct full prompt with RAG context if available
        if rag_context:
            full_prompt = f"{system_prompt}\n\n{rag_context}\n{context_str}\n\nUser: {safe_query}\n\nUse the knowledge base information above to provide an accurate, educational response."
        elif mode == 'none':
            # General chat - no forced context
            full_prompt = f"{system_prompt}\n\nUser: {safe_query}"
        else:
            # Context-aware chat
            full_prompt = f"{system_prompt}{context_str}\n\nUser: {safe_query}"
        
        full_prompt = full_prompt.replace('\r', ' ')  # Remove carriage returns

        # Call API
        assistant_response = call_gemini_api(full_prompt)
        
        if not assistant_response:
            assistant_response = "I'm sorry, I couldn't generate a response. Please try asking in a different way."
        elif len(assistant_response) > 1000:
            assistant_response = assistant_response[:997] + "..."

        # Cache the response
        if REDIS_AVAILABLE:
            ChatCache.set(query, cache_context, assistant_response)

        return jsonify(
            response=assistant_response,
            context=current_context,
            sources=sources if sources else None,
            rate_limit_remaining=remaining,
            cached=False
        ), 200

    except Exception as e:
        logger.error(f"Chat error: {e}")
        logger.error(traceback.format_exc())
        return jsonify(error="Unable to process request"), 500




@api.route('/price/<symbol>', methods=['GET'])
def get_current_price(symbol):
    """Get current price for a symbol (proxy for frontend to avoid CORS)."""
    if not symbol:
        return jsonify(error="Symbol required"), 400
    
    try:
        ticker = yf.Ticker(symbol)
        # Fast fetch of 1 day history
        hist = ticker.history(period="1d")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
            return jsonify(price=price), 200
        return jsonify(error="Price not found"), 404
    except Exception as e:
        logger.error(f"Price fetch error: {e}")
        if "Too Many Requests" in str(e) or "Rate limited" in str(e):
            return jsonify(error="Rate limit exceeded. Please try again later."), 429
        return jsonify(error="Server error"), 500


# ==================== PORTFOLIO ROUTES ====================
@api.route('/portfolio', methods=['GET'])
def get_portfolio():
    """Fetch all positions for the current user."""
    auth_response = require_auth()
    if auth_response:
        return auth_response

    _, db_user = get_user_from_token()
    if not db_user:
        return jsonify(error="Database user not found for this session."), 401

    try:
        positions = Position.query.filter_by(user_id=db_user.id).order_by(Position.symbol).all()
        
        if not positions:
            return jsonify([]), 200

        # Batch fetch current prices from yfinance
        symbols = [p.symbol for p in positions]
        
        # Use yf.download for batch fetching history
        tickers_hist = None
        if symbols:
            try:
                tickers_hist = yf.download(symbols, period="60d", interval="1d", group_by='ticker', progress=False)
            except Exception as e:
                logger.error(f"Batch download failed: {e}")
        
        portfolio_data = []
        for p in positions:
            latest_date = None  # Initialize for transparency
            try:
                hist = pd.DataFrame()
                # 1. Try extracting from batch
                if tickers_hist is not None and not tickers_hist.empty:
                    try:
                        if len(symbols) > 1:
                            hist = tickers_hist[p.symbol]
                        else:
                            hist = tickers_hist
                    except Exception:
                        pass # Symbol might be missing from batch, fall through to individual fetch

                # 2. Fallback to individual fetch if batch failed or data is missing
                if hist.empty or 'Close' not in hist.columns:
                    hist = yf.Ticker(p.symbol).history(period="60d", interval="1d")

                # 3. Validate and Clean
                if hist.empty or 'Close' not in hist.columns:
                    raise ValueError(f"No valid history for {p.symbol}")

                # Create a copy to avoid SettingWithCopyWarning on slices
                hist = hist.copy()
                hist = hist.dropna(subset=['Close'])
                
                if hist.empty:
                    raise ValueError(f"History is empty after dropping NaNs for {p.symbol}")

                # Calculate indicators
                hist['RSI'] = compute_rsi(hist['Close'])
                hist['MA5'] = hist['Close'].rolling(window=5).mean()
                hist['MA10'] = hist['Close'].rolling(window=10).mean()
                hist['MACD'], hist['Signal'], hist['Histogram'] = compute_macd(hist['Close'])
                
                latest = hist.iloc[-1]
                current_price = latest['Close']
                
                hist_list_for_macd = clean_df(hist.dropna(subset=['MACD', 'Signal']), ['MACD', 'Signal'])
                crossover_type, crossover_days_ago = find_recent_macd_crossover(hist_list_for_macd, lookback=7)
                macd_status = "None"
                if crossover_type != 'none':
                    macd_status = f"{crossover_type.capitalize()} {crossover_days_ago}d ago"
                
                current_value = p.quantity * current_price
                entry_value = p.quantity * p.entry_price
                pnl = current_value - entry_value
                pnl_percent = (pnl / entry_value) * 100 if entry_value != 0 else 0

                chart_data = clean_df(hist.tail(30), ['Date', 'Close'])
                
                # Get the latest date for transparency
                latest_date = latest.name.strftime('%Y-%m-%d') if hasattr(latest.name, 'strftime') else str(latest.name)

                position_payload = {
                    "id": p.id,
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "entry_price": p.entry_price,
                    "entry_date": p.entry_date.strftime('%Y-%m-%d'),
                    "notes": p.notes,
                    "current_price": current_price,
                    "current_value": current_value,
                    "pnl": pnl,
                    "pnl_percent": pnl_percent,
                    "rsi": latest.get('RSI'),
                    "ma5": latest.get('MA5'),
                    "ma10": latest.get('MA10'),
                    "macd_status": macd_status,
                    "chart_data": chart_data,
                    "data_date": latest_date  # Include the date of the data for transparency
                }

                portfolio_data.append(position_payload)

            except Exception as e:
                logger.error(f"❌ CRITICAL ERROR processing {p.symbol}: {str(e)}")
                logger.error(traceback.format_exc())
                # Append with data we have, even if live price fails
                portfolio_data.append({
                    "id": p.id, "symbol": p.symbol, "quantity": p.quantity,
                    "entry_price": p.entry_price, "entry_date": p.entry_date.strftime('%Y-%m-%d'),
                    "notes": p.notes, "current_price": p.entry_price, "current_value": p.quantity * p.entry_price,
                    "pnl": 0, "pnl_percent": 0,
                    "rsi": None, "ma5": None, "ma10": None, "macd_status": "N/A", "chart_data": [],
                    "data_date": None
                })

        return jsonify(portfolio_data), 200
    except Exception as e:
        logger.error(f"❌ Error fetching portfolio: {e}")
        return jsonify(error="Failed to fetch portfolio data."), 500


@api.route('/portfolio/positions/list', methods=['GET'])
def get_portfolio_positions_list():
    """Get simplified list of portfolio positions for chat selection."""
    auth_response = require_auth()
    if auth_response:
        return auth_response

    _, db_user = get_user_from_token()
    if not db_user:
        return jsonify(error="Database user not found."), 401

    try:
        positions = Position.query.filter_by(user_id=db_user.id).order_by(Position.symbol).all()
        
        positions_list = []
        for p in positions:
            positions_list.append({
                "id": p.id,
                "symbol": p.symbol,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "entry_date": p.entry_date.strftime('%Y-%m-%d')
            })

        return jsonify(positions_list), 200
    except Exception as e:
        logger.error(f"❌ Error fetching positions list: {e}")
        return jsonify(error="Failed to fetch positions."), 500


@api.route('/positions', methods=['POST'])
def add_position():
    """Add a new position to the user's portfolio."""
    auth_response = require_auth()
    if auth_response: return auth_response
    
    _, db_user = get_user_from_token()
    if not db_user: return jsonify(error="Database user not found."), 401

    data = request.get_json()
    # Basic validation
    required_fields = ['symbol', 'quantity', 'entry_price']
    if not all(field in data for field in required_fields):
        return jsonify(error=f"Missing required fields: {', '.join(required_fields)}"), 400

    try:
        # Handle date parsing safely (empty string from form becomes today)
        entry_date_str = data.get('entry_date')
        if entry_date_str:
            entry_date = datetime.strptime(entry_date_str, '%Y-%m-%d').date()
        else:
            entry_date = datetime.now(timezone.utc).date()

        new_position = Position(
            symbol=data['symbol'].upper(),
            quantity=float(data['quantity']),
            entry_price=float(data['entry_price']),
            entry_date=entry_date,
            notes=data.get('notes'),
            user_id=db_user.id
        )
        db.session.add(new_position)
        db.session.commit()
        return jsonify(id=new_position.id, message="Position added successfully"), 201
    except Exception as e:
        logger.error(f"❌ Error adding position: {e}")
        db.session.rollback()
        return jsonify(error="Failed to add position."), 500


@api.route('/positions/<int:position_id>', methods=['DELETE'])
def delete_position(position_id):
    """Delete a position."""
    auth_response = require_auth()
    if auth_response: return auth_response
    
    _, db_user = get_user_from_token()
    if not db_user: return jsonify(error="Database user not found."), 401

    position = Position.query.get_or_404(position_id)
    if position.user_id != db_user.id:
        return jsonify(error="Forbidden: You do not own this position."), 403

    db.session.delete(position)
    db.session.commit()
    return jsonify(message="Position deleted successfully"), 200

@api.route('/backtest', methods=['POST'])
def run_backtest():
    """
    Run backtest strategy on historical data.
    """
    auth_response = require_auth()
    if auth_response:
        return auth_response

    data = request.get_json()
    symbol = data.get('symbol', '').upper().strip()
    strategy = data.get('strategy', 'composite')
    initial_balance = float(data.get('initial_balance', 100000))
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    mode = data.get('mode', 'beginner')
    atr_multiplier = float(data.get('atr_multiplier', 3.0))
    risk_per_trade = float(data.get('risk_per_trade', 0.02))

    if not symbol:
        return jsonify(error="No symbol provided"), 400

    try:
        df, compliance_info = load_stock_data(symbol, apply_lag=True)
        if df is None:
            return jsonify(error=f"Data not found for symbol {symbol}. Please check if it's a valid Indian stock."), 404
        
        # Get available date range from the data
        available_first_date = df.index.min().strftime('%Y-%m-%d')
        available_last_date = df.index.max().strftime('%Y-%m-%d')
        
        # Validate dates
        if start_date and start_date < available_first_date:
            return jsonify(error=f"Start date {start_date} is before available data start ({available_first_date})"), 400
        if end_date and end_date > available_last_date:
            return jsonify(error=f"End date {end_date} is after available data end ({available_last_date})"), 400
        if start_date and end_date and start_date > end_date:
            return jsonify(error="Start date cannot be after end date"), 400

        engine = BacktestEngine(df)
        result_df = engine.run_strategy(strategy)

        performance = engine.get_performance_summary(
            initial_capital=initial_balance,
            is_long_only=True,
            start_date=start_date,
            end_date=end_date,
            atr_multiplier=atr_multiplier,
            tax_rate=0.002
        )

        # Add AI analysis using existing Gemini integration
        if not performance.get("error"):
            trades_df = performance.get('trades_df', pd.DataFrame())
            if not trades_df.empty:
                if 'result' not in trades_df.columns:
                    trades_df['result'] = trades_df.get('result', pd.Series(['Loss'] * len(trades_df)))

                performance_summary = f"""
                Backtest Results Summary for {symbol}:
                - Strategy: {strategy}
                - Period: {start_date} to {end_date}
                - Initial Capital: ₹{initial_balance:,.2f}
                - Final Value: ₹{performance['final_portfolio_value']:,.2f}
                - Total Return: {performance['strategy_return_pct']:.2f}%
                - Buy & Hold Return: {performance['market_return_pct']:.2f}%
                - Sharpe Ratio: {performance['sharpe_ratio']:.2f}
                - Max Drawdown: {performance['max_drawdown_pct']:.2f}%
                - Total Trades: {len(trades_df)}
                - Win Rate: {(len(trades_df[trades_df['result'] == 'Win']) / len(trades_df) * 100):.1f}%

                Trade Details:
                {trades_df[['entry_date', 'exit_date', 'entry_price', 'exit_price', 'pnl_pct', 'result', 'reason']].to_string(index=False)}
                """

                ai_prompt = f"""
You are the **Fintra Historical Strategy Analysis Engine**. Your role is to provide a neutral, 
quantitative decomposition of HISTORICAL backtest data. This is pure historical analysis, not current market assessment.

**⚠️ CRITICAL CONTEXT: HISTORICAL BACKTEST ONLY ⚠️**
- This is a backtest of historical data from {start_date} to {end_date}
- Data includes a mandatory 31-day SEBI compliance lag
- This analysis examines what happened in the past, not what to do now
- All performance metrics are hypothetical historical simulations

### HISTORICAL INPUT DATA FOR {symbol} (Period: {start_date} to {end_date}):
{performance_summary}

### OBJECTIVES - HISTORICAL ANALYSIS ONLY:
1. **📊 Historical Statistical Performance:** Compare the Strategy Final Value against the Buy & Hold benchmark during the historical period {start_date} to {end_date}. State the historical delta objectively using past tense.
2. **📉 Historical Risk Attribution:** Describe the historical relationship between the Max Drawdown and Sharpe Ratio. (e.g., "During the backtest period from {start_date} to {end_date}, the strategy experienced a drawdown of X while maintaining a reward-to-risk metric of Y").
3. **🔍 Historical Variable Sensitivity:** Identify which historical parameters (like Exit Reasons or Stop Loss frequency) most heavily influenced the total historical P&L during this period. 
4. **📅 Historical Market Regime Context:** Note how the strategy performed during specific historical market conditions (high-volatility vs. low-volatility periods) found in the data from {start_date} to {end_date}.
5. **🧩 Historical Edge Case Analysis:** Identify the single largest historical win and loss during {start_date} to {end_date}; describe the technical conditions of those specific historical events.

### MANDATORY CONSTRAINTS:
- **⏰ TIME CONTEXT:** ALWAYS reference the historical period ({start_date} to {end_date}) and use past tense
- **📖 HISTORICAL FRAMING:** Use "During the backtest period...", "In this historical simulation...", "From {start_date} to {end_date}..."
- **🚫 NO CURRENT REFERENCES:** Never imply this is current or applicable to today's market
- **🚫 NO PRESCRIPTIONS:** Do not suggest "improvements," "next steps," or "adjustments." Instead, use "Historical data suggests sensitivity to [Variable] during this period."
- **📊 OBJECTIVE TONE:** Avoid evaluative words like "Concerning," "Good," "Bad," "Successful," or "Failed." Use "Underperformed benchmark" or "Exceeded historical volatility."
- **🚫 NO DIRECTIVES:** Never use "Buy," "Sell," "Hold," "Trade," or "Traders should."
- **DISCLAIMER:** Conclude with the Mandatory Disclaimer below.

### FORMATTING:
- Use ## for Headers.
- Use **Bold** for all numerical values.
- Use Code Blocks (```) for any data comparisons.
- Include date range ({start_date} to {end_date}) in section headers.

## MANDATORY DISCLAIMER
⚠️ **HISTORICAL BACKTEST ALERT:** This analysis is based on historical data from {start_date} to {end_date} with a mandatory 30+ day lag per SEBI regulations. This is a hypothetical historical simulation, NOT a current market assessment, NOT financial advice, and NOT a recommendation to trade. Past results do not predict future returns. All trading involves substantial risk.
"""
                try:
                    ai_analysis = call_gemini_api(ai_prompt)
                    performance['ai_analysis'] = ai_analysis
                except Exception as e:
                    logger.error(f"AI analysis failed: {e}")
                    performance['ai_analysis'] = "AI analysis temporarily unavailable. Please try again later."

        # Remove the DataFrame from the response to avoid serialization issues
        performance.pop('trades_df', None)
        
        # Add SEBI compliance information to response
        performance['sebi_compliance'] = {
            'data_lag_days': DATA_LAG_DAYS,
            'data_range': compliance_info.get('date_range'),
            'rows_excluded_for_compliance': compliance_info.get('rows_excluded', 0),
            'effective_end_date': compliance_info.get('effective_end_date'),
            'compliance_notice': f"This analysis uses historical data with a mandatory {DATA_LAG_DAYS}-day lag in accordance with SEBI regulations. No current market data is included."
        }

        return jsonify(performance)

    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:
        logger.error(f"❌ Backtest error: {e}")
        return jsonify(error=f"Server error: {str(e)}"), 500  
    


@api.route('/backtest/monte_carlo', methods=['POST'])
def run_monte_carlo():
    """
    Run Monte Carlo simulation analysis on backtest results.
    
    This endpoint analyzes whether backtest results are due to luck or skill
    by running thousands of randomized simulations.
    """
    auth_response = require_auth()
    if auth_response:
        return auth_response
    
    data = request.get_json()
    
    # Required parameters
    trades = data.get('trades', [])
    prices = data.get('prices', [])  # List of historical prices
    
    # Optional parameters
    num_simulations = int(data.get('num_simulations', 10000))
    seed = int(data.get('seed', 0))
    initial_capital = float(data.get('initial_capital', 100000))
    
    # Original strategy metrics for comparison
    original_return = float(data.get('original_return', 0))
    original_sharpe = float(data.get('original_sharpe', 0))
    original_max_dd = float(data.get('original_max_dd', 0))
    
    if not trades or len(trades) < 2:
        return jsonify(error="At least 2 trades required for Monte Carlo analysis"), 400
    
    try:
        logger.info(f"🎲 Starting Monte Carlo analysis: {num_simulations} simulations")
        
        # Initialize Monte Carlo engine
        mc_engine = MonteCarloEngine(seed=seed)
        mc_engine.set_trades(trades)
        
        # Set daily returns if prices provided
        if prices and len(prices) > 1:
            import pandas as pd
            price_series = pd.Series(prices)
            mc_engine.set_daily_returns(price_series)
        
        # Configure simulation
        config = SimulationConfig(
            num_simulations=num_simulations,
            seed=mc_engine.seed,
            initial_capital=initial_capital
        )
        
        # Run analysis
        start_time = datetime.now()
        analysis = mc_engine.run_analysis(config)
        
        # Calculate p-values and update interpretation
        analysis = mc_engine.calculate_p_values(
            analysis, 
            original_return, 
            original_sharpe
        )
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        # Prepare response
        response = analysis.to_dict()
        response['performance'] = {
            'elapsed_time_seconds': elapsed_time,
            'simulations_per_second': round(num_simulations / elapsed_time, 2)
        }
        
        logger.info(f"✅ Monte Carlo analysis complete in {elapsed_time:.2f}s")
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"❌ Monte Carlo analysis error: {e}")
        logger.error(traceback.format_exc())
        return jsonify(error=f"Monte Carlo analysis failed: {str(e)}"), 500


@api.route('/backtest/quick_mc', methods=['POST'])
def run_quick_monte_carlo():
    """
    Quick Monte Carlo analysis (1,000 simulations) for fast preview.
    """
    auth_response = require_auth()
    if auth_response:
        return auth_response
    
    data = request.get_json()
    data['num_simulations'] = 1000  # Force 1k simulations
    
    # Forward to main endpoint
    return run_monte_carlo()


@api.route('/admin/init-redis', methods=['POST'])
def admin_init_redis():
    """
    Admin endpoint to initialize Redis and index knowledge base.
    This is a workaround for Render free tier which doesn't support Shell access.
    
    Usage:
    - POST to /api/admin/init-redis with admin key
    - Or access via browser: GET /api/admin/init-redis?key=YOUR_ADMIN_KEY
    
    Security: Requires ADMIN_KEY environment variable
    """
    # Check admin key
    admin_key = request.args.get('key') or request.headers.get('X-Admin-Key')
    expected_key = os.getenv('ADMIN_KEY')
    
    if not expected_key:
        return jsonify(
            error="ADMIN_KEY not configured",
            message="Set ADMIN_KEY environment variable to use this endpoint"
        ), 500
    
    if admin_key != expected_key:
        logger.warning(f"Unauthorized admin access attempt from {request.remote_addr}")
        return jsonify(error="Unauthorized"), 401
    
    try:
        results = {
            "timestamp": datetime.now().isoformat(),
            "steps": []
        }
        
        # Step 1: Initialize Redis
        results["steps"].append({"step": 1, "action": "Initialize Redis connection"})
        if REDIS_AVAILABLE:
            if redis_client.is_connected():
                results["steps"][-1]["status"] = "✅ Already connected"
            else:
                try:
                    redis_client.connect()
                    results["steps"][-1]["status"] = "✅ Connected"
                except Exception as e:
                    results["steps"][-1]["status"] = f"❌ Failed: {str(e)}"
                    return jsonify(results), 500
        else:
            results["steps"][-1]["status"] = "❌ Redis module not available"
            return jsonify(results), 500
        
        # Step 2: Initialize RAG index
        results["steps"].append({"step": 2, "action": "Create vector search index"})
        try:
            if rag_engine.create_index():
                results["steps"][-1]["status"] = "✅ Index ready"
            else:
                results["steps"][-1]["status"] = "⚠️ Index may already exist"
        except Exception as e:
            results["steps"][-1]["status"] = f"⚠️ {str(e)}"
        
        # Step 3: Index knowledge base
        results["steps"].append({"step": 3, "action": "Index knowledge base documents"})
        try:
            import subprocess
            import sys
            
            # Run indexing script
            result = subprocess.run(
                [sys.executable, "scripts/index_knowledge.py"],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                results["steps"][-1]["status"] = "✅ Knowledge base indexed"
                results["steps"][-1]["output"] = result.stdout[-500:]  # Last 500 chars
            else:
                results["steps"][-1]["status"] = f"❌ Indexing failed"
                results["steps"][-1]["error"] = result.stderr[-500:]
                
        except Exception as e:
            results["steps"][-1]["status"] = f"❌ Error: {str(e)}"
        
        # Step 4: Verify index
        results["steps"].append({"step": 4, "action": "Verify index contents"})
        try:
            stats = rag_engine.get_stats()
            results["steps"][-1]["status"] = f"✅ {stats.get('document_count', 0)} documents indexed"
            results["stats"] = stats
        except Exception as e:
            results["steps"][-1]["status"] = f"⚠️ {str(e)}"
        
        # Overall status
        success = all("❌" not in step.get("status", "") for step in results["steps"])
        results["success"] = success
        
        return jsonify(results), 200 if success else 500
        
    except Exception as e:
        logger.error(f"Admin init error: {e}")
        return jsonify(
            error="Initialization failed",
            message=str(e)
        ), 500


@api.route('/admin/redis-status', methods=['GET'])
def admin_redis_status():
    """
    Check Redis and RAG status.
    Can be accessed without auth to verify deployment.
    """
    status = {
        "timestamp": datetime.now().isoformat(),
        "redis_available": REDIS_AVAILABLE,
        "redis_connected": False,
        "rag_ready": False,
        "knowledge_base": {}
    }
    
    if REDIS_AVAILABLE:
        try:
            status["redis_connected"] = redis_client.is_connected()
            if status["redis_connected"]:
                status["rag_ready"] = rag_engine.model is not None
                status["knowledge_base"] = rag_engine.get_stats()
        except Exception as e:
            status["error"] = str(e)
    
    return jsonify(status), 200