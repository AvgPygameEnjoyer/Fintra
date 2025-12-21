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
    user_sessions, generate_jwt_token, verify_jwt_token,
    set_token_cookies, refresh_oauth_token, require_auth
)
from database import db
from models import User, Position
from analysis import (
    latest_symbol_data, conversation_context, clean_df,
    compute_rsi, compute_macd, generate_rule_based_analysis,
    get_gemini_ai_analysis, call_gemini_with_user_token,
    find_recent_macd_crossover
)

logger = logging.getLogger(__name__)

# Create Blueprint for all routes
api = Blueprint('api', __name__)


# ==================== PORTFOLIO HELPERS ====================
def get_user_from_token():
    """Helper to get user_id and db_user from access token."""
    access_token = request.cookies.get('access_token')
    if not access_token:
        return None, None

    payload = verify_jwt_token(access_token, Config.ACCESS_TOKEN_JWT_SECRET)
    if not payload:
        return None, None

    user_id = payload.get('user_id')
    if not user_id:
        return None, None

    db_user = User.query.filter_by(google_user_id=user_id).first()
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

        # --- NEW: Sync with database ---
        # Find user in our DB or create them if they are new.
        db_user = User.query.filter_by(google_user_id=user_id).first()
        if not db_user:
            db_user = User(
                google_user_id=user_id,
                email=user_info.get('email'),
                name=user_info.get('name')
            )
            db.session.add(db_user)
        else: # Update user info if it has changed
            db_user.email = user_info.get('email')
            db_user.name = user_info.get('name')
        db.session.commit()

        logger.info(f"User '{user_info.get('email')}' authenticated. Storing session.")
        user_sessions[user_id] = {
            'user_id': user_id,
            'email': user_info.get('email'),
            'name': user_info.get('name'),
            'picture': user_info.get('picture'),
            'oauth_token': tokens.get('access_token'),
            'refresh_token': tokens.get('refresh_token'),
            'token_expiry': datetime.now(timezone.utc) + timedelta(seconds=tokens.get('expires_in', 3600)),
            'expires_at': datetime.now(timezone.utc) + timedelta(seconds=Config.parse_time_to_seconds(Config.REFRESH_TOKEN_EXPIRETIME)),
            'granted_scopes': tokens.get('scope', '').split(' ')
        }

        jwt_access = generate_jwt_token(user_sessions[user_id], Config.ACCESS_TOKEN_JWT_SECRET,
                                        Config.ACCESS_TOKEN_EXPIRETIME)
        jwt_refresh = generate_jwt_token(user_sessions[user_id], Config.REFRESH_TOKEN_JWT_SECRET,
                                         Config.REFRESH_TOKEN_EXPIRETIME)

        # Use JS redirect to ensure cookies are set reliably across domains (fixes double login)
        response = make_response(f'<script>window.location.href = "{Config.CLIENT_REDIRECT_URL}";</script>')
        response.headers['Content-Type'] = 'text/html'
        set_token_cookies(response, jwt_access, jwt_refresh)

        logger.info("--- OAuth Callback End: Success ---")
        return response

    except Exception as e:
        logger.error(f"CRITICAL ERROR in /oauth2callback: {e}")
        return redirect(f'{Config.CLIENT_REDIRECT_URL}?error=callback_crash&reason={str(e)}')


@api.route('/auth/token/refresh', methods=['POST'])
def refresh_token():
    """Refresh JWT access token"""
    try:
        refresh_token_cookie = request.cookies.get('refresh_token')
        if not refresh_token_cookie:
            return jsonify(error="No refresh token provided"), 401

        payload = verify_jwt_token(refresh_token_cookie, Config.REFRESH_TOKEN_JWT_SECRET)
        if not payload:
            return jsonify(error="Invalid or expired refresh token"), 401

        user_id = payload['user_id']
        if user_id not in user_sessions:
            return jsonify(error="User session not found"), 401

        user_data = user_sessions[user_id]
        if user_data.get('refresh_token') and datetime.now(timezone.utc) > user_data['token_expiry'] - timedelta(
                minutes=5):
            refresh_oauth_token(user_id)

        new_access_token = generate_jwt_token(user_data, Config.ACCESS_TOKEN_JWT_SECRET, Config.ACCESS_TOKEN_EXPIRETIME)
        response = jsonify(success=True, message="Access token refreshed")
        set_token_cookies(response, new_access_token, refresh_token_cookie)
        return response, 200
    except Exception as e:
        logger.error(f"❌ Token refresh error: {e}")
        return jsonify(error="Internal token refresh error"), 500


@api.route('/auth/logout', methods=['POST', 'OPTIONS'])
def logout():
    """Logout user and clear session"""
    try:
        logger.info("User logout initiated.")
        response = jsonify(success=True, message="Logged out")
        response.set_cookie('access_token', '', max_age=0)
        response.set_cookie('refresh_token', '', max_age=0)
        return response, 200
    except Exception as e:
        logger.error(f"❌ Logout error: {e}")
        return jsonify(error="Logout failed"), 500


@api.route('/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status"""
    try:
        access_token = request.cookies.get('access_token')
        if not access_token:
            return jsonify(authenticated=False), 200

        payload = verify_jwt_token(access_token, Config.ACCESS_TOKEN_JWT_SECRET)
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
        gemini_analysis = get_gemini_ai_analysis(symbol, latest_data_list, user_id)

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
    current_symbol_hint = data.get('current_symbol')
    use_portfolio = data.get('use_portfolio', False)

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
        if db_user and use_portfolio:
            user_db_positions = Position.query.filter_by(user_id=db_user.id).all()
        
        portfolio_summary = []
        for p in user_db_positions:
            portfolio_summary.append(f"{p.symbol} ({p.quantity} @ ${p.entry_price})")
        portfolio_context_str = ("PORTFOLIO: " + ", ".join(portfolio_summary)) if portfolio_summary else ("PORTFOLIO: Empty" if use_portfolio else "")

        # Enhanced symbol matching: Check portfolio symbols first, then cached data
        def get_symbol_from_query(q):
            for p in user_db_positions:
                if p.symbol.lower() in q.lower(): return p.symbol
            for s in latest_symbol_data.keys():
                if s.lower() in q.lower(): return s
            return None

        matched_symbol = get_symbol_from_query(query) or current_symbol_hint or session_ctx["current_symbol"]

        if matched_symbol:
            session_ctx["current_symbol"] = matched_symbol

        technical_summary = ""
        if matched_symbol:
            # If we don't have recent data for the symbol, fetch it now for context
            if matched_symbol not in latest_symbol_data:
                logger.info(f"Chat context: No cached data for {matched_symbol}. Fetching now.")
                try:
                    ticker = yf.Ticker(matched_symbol)
                    hist = ticker.history(period="60d", interval="1d")
                    if not hist.empty:
                        hist['RSI'] = compute_rsi(hist['Close'])
                        hist['MACD'], hist['Signal'], hist['Histogram'] = compute_macd(hist['Close'])
                        latest_symbol_data[matched_symbol] = clean_df(hist.dropna(), ['Open', 'High', 'Low', 'Close', 'Volume', 'RSI', 'MACD', 'Signal', 'Histogram'])
                except Exception as e:
                    logger.error(f"Chat context fetch failed for {matched_symbol}: {e}")
            
            if matched_symbol in latest_symbol_data:
                technical_summary = generate_rule_based_analysis(matched_symbol, latest_symbol_data[matched_symbol])

        position_info, has_position = "", False
        if matched_symbol:
            # 1. Check DB Position (Priority)
            db_pos = next((p for p in user_db_positions if p.symbol == matched_symbol), None)
            
            # 2. Check Chat Session Updates (Override/Hypothetical)
            position_match = re.search(r'(?:bought|sold|entry|long|short|got)\s+at\s+\$?(\d+\.?\d*)', query,
                                       re.IGNORECASE)
            if position_match:
                entry_price = float(position_match.group(1))
                session_ctx["user_positions"][matched_symbol] = {
                    "entry_price": entry_price,
                    "date": datetime.now(timezone.utc).isoformat()
                }
                position_info = f"User mentioned in chat: **long** {matched_symbol} at **${entry_price}**."
            
            elif db_pos:
                has_position = True
                entry = db_pos.entry_price
                qty = db_pos.quantity
                
                # Try to get current price from cache
                current_price = None
                if matched_symbol in latest_symbol_data and latest_symbol_data[matched_symbol]:
                    current_price = latest_symbol_data[matched_symbol][-1].get('Close')
                
                if current_price:
                    pnl_dollars = (current_price - entry) * qty
                    pnl_percent = (current_price - entry) / entry * 100
                    position_info = f"User owns **{qty} shares** of {matched_symbol} at avg price **${entry:.2f}**. Current Price: ${current_price:.2f}. P&L: **${pnl_dollars:.2f} ({pnl_percent:.2f}%)**."
                else:
                    position_info = f"User owns **{qty} shares** of {matched_symbol} at avg price **${entry:.2f}**."

            elif matched_symbol in session_ctx["user_positions"]:
                has_position = True
                entry = session_ctx["user_positions"][matched_symbol]['entry_price']
                current_price = latest_symbol_data[matched_symbol][-1]['Close'] if matched_symbol in latest_symbol_data else None
                if current_price:
                    pnl_dollars = current_price - entry
                    pnl_percent = (current_price - entry) / entry * 100
                    position_info = f"User mentioned previously: entry at **${entry}**. Current: ${current_price}. P&L: **${pnl_dollars:.2f} ({pnl_percent:.2f}%)**."

        history_text = "\n".join(
            f"User: {h['user']}\nAssistant: {h['assistant']}" for h in session_ctx["conversation_history"][-3:])

        prompt = f"""You are an **experienced trading analyst chatbot** named **QuantAI**. Your goal is to provide concise, direct, and actionable advice to a recreational trader based on their question and the provided context.
RESPONSE GUIDELINES:
1. **Tone**: Sound like a savvy trader/mentor. Use simple, confident language.
2. **Context**: Use the CURRENT STOCK and TECHNICAL CONTEXT for analysis.
3. **Position**: If P&L is available, calculate it precisely and state it first. Reference the user's specific holdings.
4. **Portfolio**: You have access to the user's portfolio. Reference it if they ask about "my stocks" or "my portfolio".
5. **Length**: Be brief (2-3 sentences) unless they need detailed analysis.
6. If user mentions 'detailed', give a longer more in depth answer preferably in markdown.
CURRENT STOCK: {matched_symbol or 'None'}
{portfolio_context_str}
{position_info}
TECHNICAL CONTEXT:
{technical_summary[:500] if technical_summary else 'No technical data available.'}
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
                "current_symbol": matched_symbol,
                "has_position": has_position,
                "history_length": len(session_ctx["conversation_history"])
            }
        ), 200
    except Exception as e:
        logger.error(f"❌ Chat handler error: {e}")
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
        return jsonify(error="Database user not found for this session."), 404

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

                portfolio_data.append({
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
                    "chart_data": chart_data
                })
            except Exception as e:
                logger.error(f"Could not fetch live price for {p.symbol}: {e}. Using entry price.")
                logger.error(f"❌ CRITICAL ERROR processing {p.symbol}: {str(e)}")
                logger.error(traceback.format_exc())
                # Append with data we have, even if live price fails
                portfolio_data.append({
                    "id": p.id, "symbol": p.symbol, "quantity": p.quantity,
                    "entry_price": p.entry_price, "entry_date": p.entry_date.strftime('%Y-%m-%d'),
                    "notes": p.notes, "current_price": p.entry_price, "current_value": p.quantity * p.entry_price,
                    "pnl": 0, "pnl_percent": 0,
                    "rsi": None, "ma5": None, "ma10": None, "macd_status": "N/A", "chart_data": []
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
    if not db_user: return jsonify(error="Database user not found."), 404

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
    if not db_user: return jsonify(error="Database user not found."), 404

    position = Position.query.get_or_404(position_id)
    if position.user_id != db_user.id:
        return jsonify(error="Forbidden: You do not own this position."), 403

    db.session.delete(position)
    db.session.commit()
    return jsonify(message="Position deleted successfully"), 200

# ==================== HEALTH CHECK ====================
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
        version="4.0-Modular",
        active_sessions=len(user_sessions),
        env="production" # Hardcoded for production
    ), 200
