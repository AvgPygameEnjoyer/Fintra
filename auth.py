from dotenv import load_dotenv
from flask import request, jsonify, session, redirect, current_app, Blueprint
from functools import wraps
from datetime import datetime, timedelta
from urllib.parse import urlencode
import requests
import secrets
import jwt
import os
import dotenv

dotenv.load_dotenv()
# ==================== BLUEPRINT DEFINITION ====================
# This object is imported by app.py to register all routes defined below
auth_bp = Blueprint('auth', __name__)

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

# Data Storage (must remain in auth.py as other files import it)
user_sessions = {}
SESSION_TIMEOUT = timedelta(minutes=30)


# ==================== HELPER FUNCTIONS ====================
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


# ==================== OAUTH ROUTES ====================
@auth_bp.route('/auth/login', methods=['GET'])
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
            'access_type': 'offline',
            'prompt': 'select_account',
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

@auth_bp.route('/oauth2callback', methods=['GET'])
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
        stored_state = session.get('oauth_state')

        if not stored_state:
            print("❌ Error: No state found in session. Cookie might have been dropped.")
            # Debug hint:
            print(f"     Session keys present: {list(session.keys())}")
            return redirect(f'{CLIENT_REDIRECT_URL}?error=invalid_state&reason=missing_session')

        if state != stored_state:
            print(f"❌ State mismatch! Received: {state[:10]}... | Stored: {stored_state[:10]}...")
            return redirect(f'{CLIENT_REDIRECT_URL}?error=invalid_state&reason=mismatch')

        # Exchange code for tokens
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'code': code,
                'client_id': GOOGLE_CLIENT_ID,
                'client_secret': GOOGLE_CLIENT_SECRET,
                'redirect_uri': REDIRECT_URI,
                'grant_type': 'authorization_code'
            },
            timeout=10
        )

        if token_response.status_code != 200:
            print(f"❌ Failed to exchange token: {token_response.text}")
            return redirect(f'{CLIENT_REDIRECT_URL}?error=token_failed')

        tokens = token_response.json()
        access_token = tokens['access_token']

        # Get user info
        user_response = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )

        if user_response.status_code != 200:
            return redirect(f'{CLIENT_REDIRECT_URL}?error=user_info_failed')

        user_info = user_response.json()

        if not user_info.get('email_verified', False):
            return redirect(f'{CLIENT_REDIRECT_URL}?error=email_not_verified')

        user_id = user_info['sub']

        # Create persistent server-side session
        user_sessions[user_id] = {
            'user_id': user_id,
            'email': user_info['email'],
            'name': user_info.get('name', 'User'),
            'picture': user_info.get('picture'),
            'oauth_token': access_token,
            'refresh_token': tokens.get('refresh_token'),  # May be null if not prompt=consent
            'id_token': tokens.get('id_token'),
            'token_expiry': datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600)),
            'created_at': datetime.now(),
            'expires_at': datetime.now() + SESSION_TIMEOUT,
            'granted_scopes': tokens.get('scope', '').split(' ') if tokens.get('scope') else []
        }

        # Setup user session
        session['user_id'] = user_id
        session.permanent = True

        # Cleanup OAuth state
        session.pop('oauth_state', None)
        session.pop('oauth_initiated', None)

        # Generate JWT tokens
        jwt_access = generate_jwt_token(user_sessions[user_id], ACCESS_TOKEN_JWT_SECRET, ACCESS_TOKEN_EXPIRETIME)
        jwt_refresh = generate_jwt_token(user_sessions[user_id], REFRESH_TOKEN_JWT_SECRET, REFRESH_TOKEN_EXPIRETIME)

        response = redirect(f'{CLIENT_REDIRECT_URL}?auth=success')
        response = set_token_cookies(response, jwt_access, jwt_refresh)

        return response

    except Exception as e:
        print(f"❌ OAuth callback error: {e}")
        session.clear()
        return redirect(f'{CLIENT_REDIRECT_URL}?error=callback_error')

@auth_bp.route('/auth/token/refresh', methods=['POST'])
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
            # You might want to check expiry here before force refreshing
            if datetime.now() > user_data['token_expiry'] - timedelta(minutes=5):
                refresh_oauth_token(user_id)

        new_access_token = generate_jwt_token(user_data, ACCESS_TOKEN_JWT_SECRET, ACCESS_TOKEN_EXPIRETIME)

        response = jsonify({
            "success": True,
            "message": "Token refreshed successfully"
        })

        # Use current_app to get the correct secure flag
        is_production = current_app.config.get('SESSION_COOKIE_SECURE', False)

        response.set_cookie(
            'access_token',
            new_access_token,
            httponly=True,
            secure=is_production,
            samesite='Lax',
            max_age=parse_time_to_seconds(ACCESS_TOKEN_EXPIRETIME)
        )

        return response, 200

    except Exception as e:
        print(f"❌ Token refresh error: {e}")
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/auth/logout', methods=['POST'])
def logout():
    """Logout and clear all sessions"""
    try:
        user_id = session.get('user_id')

        if user_id and user_id in user_sessions:
            user_data = user_sessions[user_id]
            token = user_data.get('oauth_token')

            if token:
                try:
                    requests.post(
                        'https://oauth2.googleapis.com/revoke',
                        params={'token': token},
                        headers={'content-type': 'application/x-www-form-urlencoded'},
                        timeout=5
                    )
                except:
                    pass

            del user_sessions[user_id]
            print(f"✅ User logged out: {user_id}")

        session.clear()

        response = jsonify({"success": True, "message": "Logged out successfully"})
        response.set_cookie('access_token', '', expires=0)
        response.set_cookie('refresh_token', '', expires=0)
        response.set_cookie('session', '', expires=0)  # Clear flask session cookie too

        return response, 200

    except Exception as e:
        print(f"❌ Logout error: {e}")
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/auth/status', methods=['GET'])
def auth_status():
    """Check authentication via JWT first, fallback to server session."""
    try:
        # JWT first
        access_token = request.cookies.get('access_token')
        if access_token:
            payload = verify_jwt_token(access_token, ACCESS_TOKEN_JWT_SECRET)
            if payload:
                user_id = payload['user_id']
                if user_id in user_sessions:
                    user_sessions[user_id]['expires_at'] = datetime.now() + SESSION_TIMEOUT
                    u = user_sessions[user_id]
                    return jsonify({
                        "authenticated": True,
                        "user": {
                            "email": u['email'],
                            "name": u['name'],
                            "picture": u.get('picture')
                        }
                    }), 200

        # Session fallback
        user_id = session.get('user_id')
        if user_id and user_id in user_sessions:
            user_sessions[user_id]['expires_at'] = datetime.now() + SESSION_TIMEOUT
            u = user_sessions[user_id]
            return jsonify({
                "authenticated": True,
                "user": {
                    "email": u['email'],
                    "name": u['name'],
                    "picture": u.get('picture')
                }
            }), 200

        return jsonify({"authenticated": False}), 200

    except Exception as e:
        print(f"❌ Auth status error: {e}")
        return jsonify({"authenticated": False}), 200


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

                    if datetime.now() <= user_session['expires_at']:
                        user_session['expires_at'] = datetime.now() + SESSION_TIMEOUT

                        if datetime.now() > user_session['token_expiry']:
                            if not refresh_oauth_token(user_id):
                                return jsonify({"error": "Token refresh failed"}), 401

                        return f(*args, **kwargs)

        user_id = session.get('user_id')

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
