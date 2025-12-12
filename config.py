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

    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

    # Production OAuth Redirect URI
    REDIRECT_URI = 'https://stock-dashboard-fqtn.onrender.com/api/oauth2callback'

    # Production Frontend URL
    CLIENT_REDIRECT_URL = 'https://budgetwarrenbuffet.vercel.app/'

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
        'https://www.googleapis.com/auth/generative-language.peruserquota',
        'https://www.googleapis.com/auth/generative-language.retriever',
        'https://www.googleapis.com/auth/generative-language.tuning'
    ]

    # CORS Configuration
    CORS_ORIGINS = [
        "https://budgetwarrenbuffet.vercel.app" # Your production frontend
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