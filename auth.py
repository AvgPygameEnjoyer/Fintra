"""
Authentication Module
Handles OAuth, JWT tokens, session management, and authentication middleware.
"""
import logging
import jwt
import requests
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import session, request, jsonify, current_app
from typing import Optional, Dict

from config import Config

logger = logging.getLogger(__name__)

# Global session storage
user_sessions = {}

def generate_jwt_token(user_data: dict, secret: str, expires_in: str) -> str:
    """Generate JWT token"""
    expiry_seconds = Config.parse_time_to_seconds(expires_in)
    payload = {
        'user_id': user_data['user_id'],
        'email': user_data['email'],
        'name': user_data.get('name', ''),
        'exp': datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds),
        'iat': datetime.now(timezone.utc)
    }
    return jwt.encode(payload, secret, algorithm='HS256')

def verify_jwt_token(token: str, secret: str) -> Optional[dict]:
    """Verify JWT token"""
    try:
        return jwt.decode(token, secret, algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

def set_token_cookies(response, access_token: str, refresh_token: str):
    """Set cookies safely so browser actually stores them."""
    is_production = current_app.config.get('SESSION_COOKIE_SECURE', False)
    cookie_domain = Config.COOKIE_DOMAIN if is_production else "localhost"

    response.set_cookie(
        'access_token',
        access_token,
        httponly=True,
        secure=is_production,
        samesite='None' if is_production else 'Lax',
        max_age=Config.parse_time_to_seconds(Config.ACCESS_TOKEN_EXPIRETIME),
        domain=cookie_domain
    )

    response.set_cookie(
        'refresh_token',
        refresh_token,
        httponly=True,
        secure=is_production,
        samesite='None' if is_production else 'Lax',
        max_age=Config.parse_time_to_seconds(Config.REFRESH_TOKEN_EXPIRETIME),
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
        logger.warning(f"No refresh token for user {user_id}")
        return False

    try:
        logger.info(f"🔄 Refreshing OAuth token for user {user_id}")
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": Config.GOOGLE_CLIENT_ID,
                "client_secret": Config.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            },
            timeout=10
        )

        if response.status_code == 200:
            tokens = response.json()
            user_session['oauth_token'] = tokens['access_token']
            user_session['token_expiry'] = datetime.now(timezone.utc) + timedelta(seconds=tokens.get('expires_in', 3600))
            logger.info(f"✅ OAuth token refreshed for user {user_id}")
            return True
        else:
            logger.error(f"❌ Token refresh failed ({response.status_code}): {response.text}")
            return False

    except Exception as e:
        logger.error(f"❌ Exception during OAuth token refresh: {e}")
        return False

def require_auth():
    """
    Authentication check function.
    Returns a Flask Response object if auth fails, otherwise returns None.
    """
    logger.debug("--- Auth check initiated ---")
    access_token = request.cookies.get('access_token')

    # Try access token first
    if access_token:
        logger.debug("Found access_token cookie. Verifying...")
        payload = verify_jwt_token(access_token, Config.ACCESS_TOKEN_JWT_SECRET)
        if payload:
            logger.debug("Access token is valid.")
            user_id = payload['user_id']
            if user_id in user_sessions:
                logger.debug(f"User session found for user_id: {user_id}. Granting access.")
                user_session = user_sessions[user_id]
                if datetime.now(timezone.utc) > user_session['token_expiry'] - timedelta(minutes=5):
                    refresh_oauth_token(user_id)
                return None  # Success!
            else:
                logger.warning(f"Access token valid, but no active session found for user_id: {user_id}. Denying access.")
        else:
            logger.warning("Access token found but it is invalid or expired.")
    else:
        logger.debug("No access_token cookie found.")

    # Try refresh token
    logger.debug("Attempting to use refresh_token...")
    refresh_token_cookie = request.cookies.get('refresh_token')
    if refresh_token_cookie:
        logger.debug("Found refresh_token cookie. Verifying...")
        payload = verify_jwt_token(refresh_token_cookie, Config.REFRESH_TOKEN_JWT_SECRET)
        if payload:
            logger.debug("Refresh token is valid.")
            user_id = payload['user_id']
            if user_id in user_sessions:
                logger.info(f"User session found for user_id: {user_id}. Issuing new access token.")
                user_data = user_sessions[user_id]
                new_access_token = generate_jwt_token(user_data, Config.ACCESS_TOKEN_JWT_SECRET, Config.ACCESS_TOKEN_EXPIRETIME)
                if datetime.now(timezone.utc) > user_data['token_expiry'] - timedelta(minutes=5):
                    if not refresh_oauth_token(user_id):
                        logger.error("Failed to refresh the underlying OAuth token. Denying access.")
                        return jsonify({"error": "Token refresh failed"}), 401
                response = jsonify({"error": "Access token refreshed. Please retry the request."})
                set_token_cookies(response, new_access_token, refresh_token_cookie)
                return response, 401  # Use 401 to signal the client needs to retry with the new token.
            else:
                logger.warning(f"Refresh token valid, but no active session found for user_id: {user_id}.")
        else:
            logger.warning("Refresh token found but it is invalid or expired.")
    else:
        logger.debug("No refresh_token cookie found.")

    logger.error("--- Auth check failed: No valid tokens or sessions found. Denying access. ---")
    return jsonify({"error": "Not authenticated. Please sign in."}), 401

def cleanup_expired_sessions():
    """Clean up expired user sessions"""
    current_time = datetime.now(timezone.utc)
    expired_users = [
        user_id for user_id, session_data in user_sessions.items()
        if current_time > session_data['expires_at']
    ]
    for user_id in expired_users:
        del user_sessions[user_id]
        logger.info(f"🧹 Cleaned up expired session for user: {user_id}")
