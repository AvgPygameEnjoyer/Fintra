from flask import Flask, request, jsonify, session
from flask_cors import CORS
import os
import dotenv
from datetime import datetime, timedelta
import secrets
import logging
from sys import stdout

# Import modular components
from auth import (
    auth_bp,                     # <-- NEW: The Blueprint object containing all auth routes
    require_auth,                # Keep: Still used as a decorator for API routes
    cleanup_expired_sessions,    # Keep: Used in before_request hook
    user_sessions                # Keep: Used in the /health check
)
from analysis import (
    get_data_handler, chat_handler, latest_symbol_data, conversation_context
)

# ==================== LOGGING SETUP ====================
# Configure global logging for production visibility
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    handlers=[logging.StreamHandler(stdout)]
)
logger = logging.getLogger(__name__)

# ==================== ENVIRONMENT CONFIGURATION ====================
dotenv.load_dotenv()

is_production = os.getenv('FLASK_ENV', 'development') == 'production'

# ==================== APPLICATION SETUP ====================
app = Flask(__name__, static_folder="static")

# 1. Secret Key (MANDATORY for sessions)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

if not app.secret_key:
    if is_production:
        logger.critical("FATAL: FLASK_SECRET_KEY is required in production environment.")
        raise EnvironmentError("FLASK_SECRET_KEY is required in production environment.")
    else:
        # Fallback for local development, but use a fixed, known key
        app.secret_key = 'dev_fixed_key_for_local_testing_only'
        logger.warning("Using development fallback FLASK_SECRET_KEY.")


# 2. Session Cookie Settings
# Production settings require HTTPS (Secure=True)
if is_production:
    app.config['SESSION_COOKIE_SECURE'] = True
    # Setting this on Render is CRITICAL for the OAuth state cookie to work.
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' 
    logger.info("Running in PRODUCTION mode. Session cookies are Secure and Lax.")
else:
    # Relaxed settings for localhost (HTTP)
    app.config['SESSION_COOKIE_SECURE'] = False
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    logger.info("Running in DEVELOPMENT mode. Session cookies are NOT Secure.")

app.config['SESSION_COOKIE_HTTPONLY'] = True    # Security best practice
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# CORS Configuration
# Adjust origins in production to your actual domain(s)
CORS(app, supports_credentials=True)

# 3. Register the Blueprint (NEW & CRITICAL STEP)
# All routes defined in auth.py are now registered to the app instance here.
app.register_blueprint(auth_bp) 


# ==================== REQUEST HOOKS ====================
@app.before_request
def before_request():
    """Run before each request to clean up expired sessions"""
    cleanup_expired_sessions()


# ==================== AUTHENTICATION ROUTES (REMOVED) ====================
# The authentication routes (/auth/login, /oauth2callback, /auth/status, /auth/logout)
# are now defined and registered via the 'auth_bp' blueprint.


# ==================== API ROUTES ====================
@app.route('/get_data', methods=['POST'])
@require_auth
def get_stock_data():
    """Handles stock data retrieval and analysis."""
    return get_data_handler()

@app.route('/chat', methods=['POST'])
@require_auth
def chat_with_gemini():
    """Handles context-aware chatbot - Protected"""
    return chat_handler()


# ==================== STATIC FILE ROUTES ====================
@app.route('/')
def home():
    """Serves the main application file."""
    return app.send_static_file("index.html")

@app.route('/<path:path>')
def serve_static(path):
    """Serves other static files."""
    return app.send_static_file(path)

@app.route('/health', methods=['GET'])
def health():
    """Health check for load balancers/monitors."""
    return jsonify({
        "status": "healthy",
        "services": {
            "yfinance": "operational",
            "rule_based_analysis": "operational",
            "oauth_authentication": "enabled"
        },
        "version": "3.2-ProdReady",
        "active_sessions": len(user_sessions),
        "env": "production" if is_production else "development"
    }), 200


# ==================== APPLICATION STARTUP ====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = '0.0.0.0' # Listen on all interfaces

    print("=" * 70)
    print(" 📊 STOCK ANALYSIS BACKEND v3.2 (PRODUCTION-READY)")
    print("=" * 70)
    print(f" 🚀 Server running on: http://{host}:{port}")
    print(f" 🔐 OAuth Status: {'✅ Configured' if os.getenv('GOOGLE_CLIENT_ID') else '⚠️ Missing credentials'}")
    print(f" 🌍 Environment: {'Production (HTTPS required)' if is_production else 'Development (HTTP OK)'}")
    print(f" 📦 Secret Key Set: {'✅' if app.secret_key and app.secret_key != 'dev_fixed_key_for_local_testing_only' else '⚠️'}")
    print(f" 🔒 Session Secure: {'✅ True' if app.config['SESSION_COOKIE_SECURE'] else '❌ False'}")
    print("-" * 70)

    # In production, use a production WSGI server (like Gunicorn).
    # This block is primarily for dev/testing.
    app.run(host=host, port=port, debug=not is_production)
