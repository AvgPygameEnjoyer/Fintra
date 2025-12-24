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
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'None'

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

    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

    # Production OAuth Redirect URI
    REDIRECT_URI = 'https://stock-dashboard-fqtn.onrender.com/api/oauth2callback'

    # Production Frontend URL
    CLIENT_REDIRECT_URL = 'https://fintraio.vercel.app/'

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
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/generative-language.tuning'
    ]

    # CORS Configuration
    CORS_ORIGINS = [
        "https://fintraio.vercel.app" # Your production frontend
    ]

    # Cookie Domain
    # In production, set this to your parent domain (e.g., ".yourdomain.com") if frontend and backend are on subdomains.
    COOKIE_DOMAIN = os.getenv('COOKIE_DOMAIN') # e.g., ".yourdomain.com"

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
