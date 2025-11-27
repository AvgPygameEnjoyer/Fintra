"""
Main Application Entry Point
Initializes Flask app, configures middleware, registers blueprints.
"""
import os
import logging
import traceback
from sys import stdout
from flask import Flask, jsonify
from flask_cors import CORS

from config import Config
from auth import cleanup_expired_sessions, user_sessions
from routes import api

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    handlers=[logging.StreamHandler(stdout)]
)
logger = logging.getLogger(__name__)


# ==================== APPLICATION FACTORY ====================
def create_app():
    """Application factory pattern"""
    app = Flask(__name__, static_folder="static")

    # Load configuration
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY

    # Session configuration
    if Config.IS_PRODUCTION:
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_SAMESITE='None'
        )
        logger.info("Running in PRODUCTION mode. Session cookies are Secure and SameSite=None.")
    else:
        app.config.update(
            SESSION_COOKIE_SECURE=False,
            SESSION_COOKIE_SAMESITE='Lax'
        )
        logger.info("Running in DEVELOPMENT mode. Session cookies are Insecure and SameSite=Lax.")

    # CORS configuration
    CORS(
        app,
        supports_credentials=True,
        origins=Config.CORS_ORIGINS,
        methods=["GET", "POST", "OPTIONS"]
    )

    app.permanent_session_lifetime = Config.PERMANENT_SESSION_LIFETIME

    # Register blueprints
    app.register_blueprint(api)

    # Request hooks
    @app.before_request
    def cleanup_and_session_setup():
        """Run before every request to clean up expired sessions."""
        cleanup_expired_sessions()

    # Error handlers
    @app.errorhandler(Exception)
    def handle_exception(e):
        """Global exception handler."""
        tb_str = traceback.format_exc()
        logger.error(f"Unhandled Exception: {e}\n{tb_str}")
        response = jsonify(
            error="An internal server error occurred.",
            details=str(e) if not Config.IS_PRODUCTION else None
        )
        response.status_code = 500
        return response

    # Static file routes
    @app.route('/')
    def home():
        return app.send_static_file("index.html")

    @app.route('/<path:path>')
    def serve_static(path):
        return app.send_static_file(path)

    return app

app = create_app()
# ==================== APPLICATION STARTUP ====================
def main():
    """Main entry point"""
    
    port = int(os.environ.get("PORT", 5000))
    host = '0.0.0.0'

    print("=" * 70)
    print(" 📊 STOCK ANALYSIS BACKEND v4.0 (MODULAR)")
    print("=" * 70)
    print(f" 🚀 Server running on: http://{host}:{port}")
    print(f" 🔐 OAuth Status: {'✅ Configured' if Config.GOOGLE_CLIENT_ID else '⚠️ Missing credentials'}")
    print(f" 🌍 Environment: {'Production (HTTPS required)' if Config.IS_PRODUCTION else 'Development (HTTP OK)'}")
    print(
        f" 📦 Secret Key Set: {'✅' if app.secret_key and app.secret_key != 'dev_fixed_key_for_local_testing_only' else '⚠️ Development Key'}")
    print("-" * 70)
    print(" 🔍 REGISTERED ROUTES:")
    with app.app_context():
        for rule in app.url_map.iter_rules():
            if 'static' not in str(rule):
                print(f"    ✅ {str(rule):40} | Endpoint: {rule.endpoint}")
    print("-" * 70)
    print(f" 📁 Module Structure:")
    print(f"    ✅ config.py - Configuration management")
    print(f"    ✅ auth.py - Authentication & sessions")
    print(f"    ✅ analysis.py - Stock analysis & AI")
    print(f"    ✅ routes.py - API endpoints")
    print(f"    ✅ app.py - Main application")
    print("=" * 70)

    app.run(host=host, port=port, debug=not Config.IS_PRODUCTION)


if __name__ == "__main__":

    main()
