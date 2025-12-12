"""
Configuration Management Module
Handles environment variables, secrets, and application settings.
"""
import os
import secrets
from datetime import timedelta
import dotenv

# Load environment variables
dotenv.load_dotenv()


class Config:
    """Base configuration class"""

    # Environment
    ENV = os.getenv('FLASK_ENV', 'development')
    IS_PRODUCTION = ENV == 'production'

    # Flask Settings
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'a_default_secret_key_for_jwt_signing')
    SESSION_COOKIE_SECURE = IS_PRODUCTION
    SESSION_COOKIE_SAMESITE = 'None' if IS_PRODUCTION else 'Lax'

    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

    # Use production URL if IS_PRODUCTION is true, otherwise use local URL
    _prod_redirect_uri = 'https://stock-dashboard-fqtn.onrender.com/api/oauth2callback'
    _local_redirect_uri = 'http://localhost:5000/api/oauth2callback'
    REDIRECT_URI = _prod_redirect_uri if IS_PRODUCTION else os.getenv('REDIRECT_URI', _local_redirect_uri)

    # This should be the root of the frontend application.
    _prod_client_url = 'https://budgetwarrenbuffet.vercel.app/'
    _local_client_url = 'http://localhost:5000/' # In a unified server model, this is the correct local URL.
    CLIENT_REDIRECT_URL = _prod_client_url if IS_PRODUCTION else os.getenv('CLIENT_REDIRECT_URL', _local_client_url)

    # Force HTTP for local OAuth to prevent misconfiguration
    if not IS_PRODUCTION and 'https' in REDIRECT_URI:
        REDIRECT_URI = REDIRECT_URI.replace('https://', 'http://')

    # Force 'localhost' over '127.0.0.1' in development for cookie consistency
    if not IS_PRODUCTION and '127.0.0.1' in CLIENT_REDIRECT_URL:
        CLIENT_REDIRECT_URL = CLIENT_REDIRECT_URL.replace('127.0.0.1', 'localhost')

    # JWT Configuration
    # These MUST be loaded from the environment for stability across restarts.
    ACCESS_TOKEN_JWT_SECRET = os.getenv('ACCESS_TOKEN_JWT_SECRET')
    REFRESH_TOKEN_JWT_SECRET = os.getenv('REFRESH_TOKEN_JWT_SECRET')
    ACCESS_TOKEN_EXPIRETIME = os.getenv('ACCESS_TOKEN_EXPIRETIME', '15m')
    REFRESH_TOKEN_EXPIRETIME = os.getenv('REFRESH_TOKEN_EXPIRETIME', '7d')

    if not ACCESS_TOKEN_JWT_SECRET or not REFRESH_TOKEN_JWT_SECRET:
        raise EnvironmentError(
            "FATAL: ACCESS_TOKEN_JWT_SECRET and REFRESH_TOKEN_JWT_SECRET must be set in the .env file."
        )

    # OAuth Scopes
    SCOPES = [
        'openid',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/generative-language.peruserquota',
        'https://www.googleapis.com/auth/generative-language.retriever',
        'https://www.googleapis.com/auth/generative-language.tuning'
    ]

    # CORS Configuration
    CORS_ORIGINS = [
        "http://localhost:5000", # For unified local server
        "https://budgetwarrenbuffet.vercel.app" # Your production frontend
    ]

    # Cookie Domain
    # In production, set this to your parent domain (e.g., ".yourdomain.com") if frontend and backend are on subdomains.
    # For Vercel/Render on different root domains, this might not be needed if SameSite=None is used.
    COOKIE_DOMAIN = os.getenv('COOKIE_DOMAIN') if IS_PRODUCTION else "localhost"

    @staticmethod
    def parse_time_to_seconds(time_str: str) -> int:
        """Convert time string like '15m' or '7d' to seconds"""
        if time_str.endswith('m'):
            return int(time_str[:-1]) * 60
        elif time_str.endswith('h'):
            return int(time_str[:-1]) * 3600
        elif time_str.endswith('d'):
            return int(time_str[:-1]) * 86400
        return 900
    REDIRECT_URI = os.getenv('REDIRECT_URI', _local_redirect_uri)

    # Force HTTP for local OAuth to prevent misconfiguration
    if not IS_PRODUCTION and 'https' in REDIRECT_URI:
        REDIRECT_URI = REDIRECT_URI.replace('https://', 'http://')

    # This should be the root of the frontend server, which is proxied.
    CLIENT_REDIRECT_URL = os.getenv('CLIENT_REDIRECT_URL', 'http://localhost:5500/')

    # Force 'localhost' over '127.0.0.1' in development for cookie consistency
    if not IS_PRODUCTION and '127.0.0.1' in CLIENT_REDIRECT_URL:
        CLIENT_REDIRECT_URL = CLIENT_REDIRECT_URL.replace('127.0.0.1', 'localhost')

    # JWT Configuration
    # These MUST be loaded from the environment for stability across restarts.
    ACCESS_TOKEN_JWT_SECRET = os.getenv('ACCESS_TOKEN_JWT_SECRET')
    REFRESH_TOKEN_JWT_SECRET = os.getenv('REFRESH_TOKEN_JWT_SECRET')
    ACCESS_TOKEN_EXPIRETIME = os.getenv('ACCESS_TOKEN_EXPIRETIME', '15m')
    REFRESH_TOKEN_EXPIRETIME = os.getenv('REFRESH_TOKEN_EXPIRETIME', '7d')

    if not ACCESS_TOKEN_JWT_SECRET or not REFRESH_TOKEN_JWT_SECRET:
        raise EnvironmentError(
            "FATAL: ACCESS_TOKEN_JWT_SECRET and REFRESH_TOKEN_JWT_SECRET must be set in the .env file."
        )

    # OAuth Scopes
    SCOPES = [
        'openid',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/generative-language.peruserquota',
        'https://www.googleapis.com/auth/generative-language.retriever',
        'https://www.googleapis.com/auth/generative-language.tuning'
    ]

    # CORS Configuration
    CORS_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:5000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",  # Default for VS Code Live Server
        "https://budgetwarrenbuffet.vercel.app",
        CLIENT_REDIRECT_URL
    ]

    # Cookie Domain
    COOKIE_DOMAIN = os.getenv('COOKIE_DOMAIN') if IS_PRODUCTION else None

    @staticmethod
    def parse_time_to_seconds(time_str: str) -> int:
        """Convert time string like '15m' or '7d' to seconds"""
        if time_str.endswith('m'):
            return int(time_str[:-1]) * 60
        elif time_str.endswith('h'):
            return int(time_str[:-1]) * 3600
        elif time_str.endswith('d'):
            return int(time_str[:-1]) * 86400
        return 900