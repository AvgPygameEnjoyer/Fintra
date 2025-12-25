"""
Main Application Entry Point
Initializes Flask app, configures middleware, registers blueprints.
"""
import os
import logging
import traceback
from sys import stdout
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import text

from config import Config
from database import db
from routes import api

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    handlers=[logging.StreamHandler(stdout)]
)
logger = logging.getLogger(__name__)

#DevEasterEgg
# ==================== APPLICATION FACTORY ====================
def create_app():
    """Application factory pattern"""
    # Define the static folder using an absolute path for reliability, especially in Docker.
    # This ensures Flask knows exactly where to find files like main.js and styles.css.
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app = Flask(__name__, 
                static_folder=static_dir, 
                static_url_path='')

    # Load configuration
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)

    # CORS setup
    CORS(
        app,
        supports_credentials=True,
        origins=Config.CORS_ORIGINS,
        methods=["GET", "POST", "OPTIONS", "DELETE", "PUT"]
    )

    # Register blueprints
    app.register_blueprint(api, url_prefix='/api')

    # Request hooks
    @app.before_request
    def before_request_logging():
        """Log preflight requests for easier CORS debugging."""
        if request.method == 'OPTIONS':
            logger.info(f"Received PREFLIGHT {request.method} request for {request.path}")

    # Error handlers
    @app.errorhandler(Exception)
    def handle_exception(e):
        """Global exception handler with enhanced logging."""
        tb_str = traceback.format_exc()
        
        request_details = {}
        try:
            request_details = {
                "method": request.method,
                "path": request.path,
                "headers": dict(request.headers),
            }
        except Exception as req_exc:
            logger.error(f"Could not extract request details during exception handling: {req_exc}")

        logger.error(f"--- Unhandled Exception ---")
        logger.error(f"Request: {request_details}")
        logger.error(f"Exception: {e}\n{tb_str}")
        logger.error(f"--- End Exception ---")
        
        response = jsonify(
            error="An internal server error occurred.",
            details=None # In production, do not expose internal error details
        )
        response.status_code = 500
        return response

    @app.errorhandler(404)
    def not_found(e):
        # If the path starts with /api, it's a genuine API 404 error.
        if request.path.startswith('/api/'):
            return jsonify(error="API endpoint not found"), 404
        else:
            # Otherwise, it's a frontend route; serve the main app.
            return app.send_static_file("index.html")

    # Add a startup log to display critical configuration
    with app.app_context():
        # Create database tables if they don't exist
        db.create_all()

        # --- SCHEMA MIGRATION ---
        # db.create_all() does not update existing tables. We manually ensure the 'picture' column exists.
        try:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS picture VARCHAR(512)'))
                conn.commit()
        except Exception as e:
            logger.warning(f"Schema migration check failed: {e}")

        logger.info(" 🗃️  Database tables ensured.")

        logger.info("=" * 70)
        logger.info(" 🚀 BACKEND SERVER STARTING UP")
        logger.info(f" 🌍 Environment: Production")
        logger.info(f" 🔐 Google Client ID: {Config.GOOGLE_CLIENT_ID[:10] if Config.GOOGLE_CLIENT_ID else 'NOT SET'}{'...' if Config.GOOGLE_CLIENT_ID else ''}")
        logger.info(f" ↪️ Google Redirect URI: {Config.REDIRECT_URI}")
        logger.info(f" 🌐 Frontend Redirect URL: {Config.CLIENT_REDIRECT_URL}")
        logger.info(f" 🔑 JWT Secrets Loaded: {'✅' if Config.ACCESS_TOKEN_JWT_SECRET and Config.REFRESH_TOKEN_JWT_SECRET else '❌ NOT FOUND'}")
        logger.info("=" * 70)

    return app
    
app = create_app()
