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
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
    if not SECRET_KEY:
        if IS_PRODUCTION:
            raise EnvironmentError("FLASK_SECRET_KEY is required in production environment.")
        SECRET_KEY = 'dev_fixed_key_for_local_testing_only'

    # Session Configuration
    SESSION_TIMEOUT = timedelta(minutes=30)
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = IS_PRODUCTION
    SESSION_COOKIE_SAMESITE = 'None' if IS_PRODUCTION else 'Lax'

    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    REDIRECT_URI = os.getenv('REDIRECT_URI', 'http://localhost:5000/oauth2callback')
    CLIENT_REDIRECT_URL = os.getenv('CLIENT_REDIRECT_URL', 'http://localhost:5000')

    # JWT Configuration
    ACCESS_TOKEN_JWT_SECRET = os.getenv('ACCESS_TOKEN_JWT_SECRET', secrets.token_hex(32))
    REFRESH_TOKEN_JWT_SECRET = os.getenv('REFRESH_TOKEN_JWT_SECRET', secrets.token_hex(32))
    ACCESS_TOKEN_EXPIRETIME = os.getenv('ACCESS_TOKEN_EXPIRETIME', '15m')
    REFRESH_TOKEN_EXPIRETIME = os.getenv('REFRESH_TOKEN_EXPIRETIME', '7d')

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