"""
Routes Module
Defines all Flask routes and API endpoints.
"""
import logging
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
from backtesting import BacktestEngine, load_stock_data
from mc_engine import MonteCarloEngine, SimulationConfig

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

        return jsonify(
            ticker=symbol,
            OHLCV=clean_df(hist_display, ['Open', 'High', 'Low', 'Close', 'Volume']),
            MA=clean_df(hist_display, ['MA5', 'MA10']),
            RSI=clean_df(hist_display, ['RSI']),
            MACD=clean_df(hist_display, ['MACD', 'Signal', 'Histogram']),
            AI_Review=gemini_analysis,
            Rule_Based_Analysis=rule_based_text
        ), 200
    except Exception as e:
        logger.error(f"❌ Error in /api/get_data: {e}")
        return jsonify(error=f"Server error: {str(e)}"), 500


@api.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    """Handle AI chat queries"""
    # For complex requests, the browser sends a preflight OPTIONS request first.
    # We must allow this request to pass through without authentication checks.
    if request.method == 'OPTIONS':
        return jsonify(success=True), 200

    auth_response = require_auth()
    if auth_response:
        return auth_response
    data = request.get_json()
    query = data.get('query', '').strip()    
    user_id, db_user = get_user_from_token()
    context_symbols = data.get('context_symbols', [])
    use_portfolio = data.get('use_portfolio', False)
    current_symbol_hint = data.get('current_symbol')

    if not query:
        return jsonify(error="No query provided"), 400

    try:
        if user_id not in conversation_context:
            conversation_context[user_id] = {
                "current_symbol": None,
                "conversation_history": [],
                "last_active": datetime.now(timezone.utc).isoformat(),
                "user_positions": {}
            }

        session_ctx = conversation_context[user_id]
        if "user_positions" not in session_ctx:
            session_ctx["user_positions"] = {}
        session_ctx["last_active"] = datetime.now(timezone.utc).isoformat()
        
        # --- NEW: Fetch real portfolio positions from DB ---
        user_db_positions = []
        if db_user:
            user_db_positions = Position.query.filter_by(user_id=db_user.id).all()
        
        portfolio_summary = []
        for p in user_db_positions:
            portfolio_summary.append(f"{p.symbol} ({p.quantity} @ ${p.entry_price})")
        portfolio_context_str = ("PORTFOLIO: " + ", ".join(portfolio_summary)) if portfolio_summary else ""

        # Enhanced symbol matching: Check portfolio symbols first, then cached data
        def get_symbol_from_query(q):
            for p in user_db_positions:
                if p.symbol.lower() in q.lower(): return p.symbol
            for s in latest_symbol_data.keys():
                if s.lower() in q.lower(): return s
            # Fallback for symbols in text that aren't in cache yet
            found_symbols = re.findall(r'\b[A-Z]{1,5}\b', q.upper())
            if found_symbols: return found_symbols[0]
            return None

        # Determine the final list of symbols to analyze
        final_context_symbols = []
        if context_symbols:
            final_context_symbols = context_symbols
        else:
            # Fallback logic if no context is explicitly passed
            symbol_from_query = get_symbol_from_query(query)
            if symbol_from_query:
                final_context_symbols.append(symbol_from_query)
            elif current_symbol_hint:
                final_context_symbols.append(current_symbol_hint)
            elif session_ctx.get("current_symbol"):
                final_context_symbols.append(session_ctx["current_symbol"])

        # Deduplicate
        final_context_symbols = list(set(final_context_symbols))

        # Update session context with the primary symbol (first one)
        primary_symbol = final_context_symbols[0] if final_context_symbols else None
        if primary_symbol:
            session_ctx["current_symbol"] = primary_symbol

        # --- Build context for all symbols ---
        technical_summaries = []
        position_infos = []
        has_any_position = False

        for symbol in final_context_symbols:
            # Fetch data if not in cache
            if symbol not in latest_symbol_data:
                logger.info(f"Chat context: No cached data for {symbol}. Fetching now.")
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="60d", interval="1d")
                    if not hist.empty:
                        hist['RSI'] = compute_rsi(hist['Close'])
                        hist['MACD'], hist['Signal'], hist['Histogram'] = compute_macd(hist['Close'])
                        latest_symbol_data[symbol] = clean_df(hist.dropna(), ['Open', 'High', 'Low', 'Close', 'Volume', 'RSI', 'MACD', 'Signal', 'Histogram'])
                except Exception as e:
                    logger.error(f"Chat context fetch failed for {symbol}: {e}")

            # Add technical summary
            if symbol in latest_symbol_data:
                tech_summary = generate_rule_based_analysis(symbol, latest_symbol_data[symbol])
                technical_summaries.append(f"--- CONTEXT FOR {symbol} ---\n{tech_summary}")

            # Add position info
            db_pos = next((p for p in user_db_positions if p.symbol == symbol), None)
            if db_pos:
                has_any_position = True
                entry = db_pos.entry_price
                qty = db_pos.quantity
                
                current_price = None
                if symbol in latest_symbol_data and latest_symbol_data[symbol]:
                    current_price = latest_symbol_data[symbol][-1].get('Close')
                
                if current_price:
                    pnl_dollars = (current_price - entry) * qty
                    pnl_percent = (current_price - entry) / entry * 100 if entry != 0 else 0
                    position_infos.append(f"User owns **{qty} shares** of {symbol} at avg price **${entry:.2f}**. Current Price: ${current_price:.2f}. P&L: **${pnl_dollars:.2f} ({pnl_percent:.2f}%)**.")
                else:
                    position_infos.append(f"User owns **{qty} shares** of {symbol} at avg price **${entry:.2f}**.")

        # Combine contexts
        technical_context_str = "\n\n".join(technical_summaries)
        position_context_str = "\n".join(position_infos)

        # Add a specific instruction for comparison if multiple symbols are present
        comparison_instruction = ""
        if len(final_context_symbols) > 1:
            comparison_instruction = f"The user has provided multiple stocks: {', '.join(final_context_symbols)}. **Your primary goal is to compare them** based on the user's query and the provided context. Use a table or bullet points for easy comparison."

        history_text = "\n".join(
            f"User: {h['user']}\nAssistant: {h['assistant']}" for h in session_ctx["conversation_history"][-3:])

        prompt = f"""You are an **experienced trading analyst chatbot** named **QuantAI**. Your goal is to provide concise, direct, and actionable advice to a recreational trader based on their question and the provided context.
RESPONSE GUIDELINES:
1. **Tone**: Sound like a savvy trader/mentor. Use simple, confident language.
2. **Context**: Use the CURRENT STOCK and TECHNICAL CONTEXT for analysis.
3. **Position**: If P&L is available, calculate it precisely and state it first. Reference the user's specific holdings.
4. **Portfolio**: You have access to the user's portfolio. Reference it if they ask about "my stocks" or "my portfolio".
5. **Comparison**: {comparison_instruction or 'Focus on the single stock in context.'}
6. **Length**: Be brief (2-3 sentences) unless they need detailed analysis.
7. If user mentions 'detailed', give a longer more in depth answer preferably in markdown.

STOCKS IN CONTEXT: {', '.join(final_context_symbols) or 'None'}
{portfolio_context_str}
{position_context_str}
TECHNICAL CONTEXT:
{technical_context_str[:2000] if technical_context_str else 'No technical data available.'}
CONVERSATION HISTORY (Last 3 turns):
{history_text}
USER QUESTION: {query}
RESPONSE RULES:
- If they ask about profit/loss and you have their entry price, CALCULATE IT EXACTLY.
- Reference their specific entry price if they gave you one.
- Be brief (2-3 sentences) unless they need detailed analysis.
- Sound like a trader chatting, not a robot.
Respond now:"""

        assistant_response = call_gemini_api(prompt)

        session_ctx["conversation_history"].append({
            "user": query,
            "assistant": assistant_response,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        if len(session_ctx["conversation_history"]) > 15:
            session_ctx["conversation_history"] = session_ctx["conversation_history"][-15:]

        return jsonify(
            response=assistant_response,
            context={
                "current_symbol": primary_symbol,
                "has_position": has_any_position,
                "history_length": len(session_ctx["conversation_history"])
            }
        ), 200
    except Exception as e:
        logger.error(f"❌ Chat handler error: {e}")
        logger.error(traceback.format_exc())
        return jsonify(error=f"Server error: {str(e)}"), 500


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

                position_payload = {
                    "id": p.id,
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "entry_price": p.entry_price,
                    "entry_date": p.entry_date.strftime('%Y-%m-%d'),
                    "notes": p.notes,
                    "current_price": current_price, # Used for AI summary
                    "current_value": current_value,
                    "pnl": pnl, # Used for AI summary
                    "pnl_percent": pnl_percent, # Used for AI summary
                    "rsi": latest.get('RSI'),
                    "ma5": latest.get('MA5'),
                    "ma10": latest.get('MA10'),
                    "macd_status": macd_status,
                    "chart_data": chart_data
                }

                # Get the new AI Position Summary
                position_payload['ai_position_summary'] = get_gemini_position_summary(position_payload)

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
                    "ai_position_summary": "⚠️ AI summary could not be generated due to a data error."
                })

        return jsonify(portfolio_data), 200
    except Exception as e:
        logger.error(f"❌ Error fetching portfolio: {e}")
        return jsonify(error="Failed to fetch portfolio data."), 500


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
        df = load_stock_data(symbol)
        if df is None:
            return jsonify(error=f"Data not found for symbol {symbol}. Please check if it's a valid Indian stock."), 404

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
                As an expert trading analyst, analyze this backtest performance for {symbol}:

                Performance Metrics:
                {performance_summary}

                Please provide insights on:
                1. Strategy effectiveness and why it succeeded/failed
                2. Risk management effectiveness
                3. Key improvement suggestions
                4. Market conditions impact
                5. Specific trade analysis (biggest wins/losses)

                Keep analysis concise but actionable for traders.
                Focus on practical insights that can improve real trading performance.

                IMPORTANT: Format your response using markdown with:
                - Headers (##, ###)
                - Bullet points
                - Bold text for key metrics
                - Code blocks for any data tables
                """

                try:
                    ai_analysis = call_gemini_api(ai_prompt)
                    performance['ai_analysis'] = ai_analysis
                except Exception as e:
                    logger.error(f"AI analysis failed: {e}")
                    performance['ai_analysis'] = "AI analysis temporarily unavailable. Please try again later."

        # Remove the DataFrame from the response to avoid serialization issues
        performance.pop('trades_df', None)

        return jsonify(performance)

    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:
        logger.error(f"❌ Backtest error: {e}")
        return jsonify(error=f"Server error: {str(e)}"), 500    except ValueError as e:
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
