# backend/app/__init__.py

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_migrate import Migrate
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken as FernetInvalidToken

db = SQLAlchemy()
bcrypt = Bcrypt()
migrate = Migrate()
# fernet_cipher = None # This global variable is no longer needed, app.fernet_cipher is used

def create_app(config_object_path='config.Config'):
    """
    Application factory pattern.
    """
    app = Flask(__name__, instance_relative_config=True)
    # Load configuration from config.py
    app.config.from_object(config_object_path)

    # --- ✅ CRUCIAL ADDITION FOR FLASK SESSIONS ---
    # Flask sessions require a SECRET_KEY. We are reusing the JWT_SECRET_KEY
    # from your config, or falling back to the general SECRET_KEY.
    app.config['SECRET_KEY'] = app.config.get('JWT_SECRET_KEY') or app.config.get('SECRET_KEY')
    if not app.config['SECRET_KEY']:
        app.logger.error("FLASK_SECRET_KEY (or JWT_SECRET_KEY) is not set! Flask sessions will not work securely.")
        # In production, you might want to raise an error here or use a dummy key for dev only.

    # Global CORS Initialization
    # This uses app.config['CORS_ORIGINS'] if set, otherwise a very permissive default.
    # Note: app.config['CORS_ORIGINS'] might be a comma-separated string,
    # so .split(',') is necessary to turn it into a list of origins.
    cors_origins = app.config['CORS_ORIGINS'].split(',') if app.config.get('CORS_ORIGINS') else "*"
    CORS(app, resources={r"/api/*": {"origins": cors_origins}})
    app.logger.info(f"CORS initialized with origins: {cors_origins}")
    
    try:
        os.makedirs(app.instance_path)
        app.logger.info(f"Instance folder created at {app.instance_path}")
    except OSError:
        pass

    # --- Initialize Extensions ---
    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    
    # Initialize Fernet cipher for API key encryption/decryption
    api_encryption_key_str = app.config.get('API_ENCRYPTION_KEY')
    if not api_encryption_key_str:
        app.logger.warning("API_ENCRYPTION_KEY is not set in config. API key encryption/decryption will be impaired.")
        app.fernet_cipher = None
    else:
        try:
            # Fernet key must be bytes and base64-encoded
            app.fernet_cipher = Fernet(api_encryption_key_str.encode('utf-8'))
            app.logger.info("Fernet cipher initialized successfully for API key encryption.")
        except Exception as e:
            app.logger.error(f"Failed to init Fernet from config (invalid key format?): {e}")
            app.fernet_cipher = None
    
    # This `with app.app_context(): from .models import models` line is generally not needed here
    # as models are typically imported directly into blueprints or other modules as needed.
    # However, it doesn't hurt.
    with app.app_context():
        from .models import models

    # --- Register Blueprints ---
    from .routes.general_routes import general_bp
    from .routes.admin_routes import admin_bp
    from .routes.chat_routes import chat_bp
    from .routes.data_source_routes import data_source_bp
    from .routes.github_routes import github_bp
    from .routes.google_routes import google_bp

    app.register_blueprint(general_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(data_source_bp, url_prefix='/api/data-sources')
    app.register_blueprint(github_bp, url_prefix='/api') # Routes like /api/connect/github/...
    app.register_blueprint(google_bp, url_prefix='/api') # Routes like /api/connect/google/...

    app.logger.info("Flask app created and configured.")
    return app