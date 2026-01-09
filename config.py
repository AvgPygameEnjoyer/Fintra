"""
Configuration Management Module
Handles environment variables, secrets, and application settings.
"""
import os
import secrets
from datetime import timedelta

class Config:
    """Base configuration class"""

    # Flask Settings
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
    
    # Detect environment: Assume production if RENDER env var is set or FLASK_ENV is production
    # We default to True if not explicitly development to ensure security headers on cloud deployments
    IS_PRODUCTION = os.getenv('RENDER') is not None or os.getenv('FLASK_ENV') == 'production' or os.getenv('FLASK_ENV') != 'development'
    
    # Force secure cookies in production for cross-site usage (Vercel -> Render)
    SESSION_COOKIE_SECURE = IS_PRODUCTION
    SESSION_COOKIE_SAMESITE = 'None' if IS_PRODUCTION else 'Lax' 

    # Define a data directory, configurable via environment variable. Defaults to the project root.
    DATA_DIR = os.getenv('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))

    # Database Configuration
    # Check for DATABASE_URL. If provided by Render/Neon, it might start with 'postgres://'
    # SQLAlchemy requires 'postgresql://', so we fix it if necessary.
    _db_url = os.getenv('DATABASE_URL')
    
    # Robust cleaning: strip whitespace and quotes that might have been pasted in
    if _db_url:
        _db_url = _db_url.strip().strip('"').strip("'")

    if _db_url and _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = _db_url if _db_url else f"sqlite:///{os.path.join(DATA_DIR, 'portfolio.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Engine options to improve connection pool reliability, especially for serverless DBs like Neon.
    # pool_pre_ping checks if a connection is alive before using it, preventing OperationalError
    # on stale connections.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

    # Gemini API Key
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

    # Production OAuth Redirect URI
    REDIRECT_URI = os.getenv('REDIRECT_URI', 'http://localhost:5000/api/oauth2callback')

    # Production Frontend URL
    CLIENT_REDIRECT_URL = os.getenv('CLIENT_REDIRECT_URL', 'http://localhost:5000/')

    # JWT Configuration
    # These MUST be loaded from the environment for stability across restarts.
    ACCESS_TOKEN_JWT_SECRET = os.getenv('ACCESS_TOKEN_JWT_SECRET')
    REFRESH_TOKEN_JWT_SECRET = os.getenv('REFRESH_TOKEN_JWT_SECRET')
    ACCESS_TOKEN_EXPIRETIME = '15m'
    REFRESH_TOKEN_EXPIRETIME = '7d'

    if not ACCESS_TOKEN_JWT_SECRET or not REFRESH_TOKEN_JWT_SECRET:
        raise EnvironmentError(
            "FATAL: ACCESS_TOKEN_JWT_SECRET and REFRESH_TOKEN_JWT_SECRET must be set in the .env file."
        )

    # OAuth Scopes
    SCOPES = [
        'openid',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile'
    ]

    # CORS Configuration
    CORS_ORIGINS = [
        "http://localhost:5000",
        "http://127.0.0.1:5000"
    ]

    if os.getenv('CLIENT_ORIGIN'):
        CORS_ORIGINS.append(os.getenv('CLIENT_ORIGIN'))

    # Cookie Domain
    # In production, set this to your parent domain (e.g., ".yourdomain.com") if frontend and backend are on subdomains.
    # If frontend (Vercel) and backend (Render) are on different domains, leave this as None to default to the backend host.
    COOKIE_DOMAIN = None

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
