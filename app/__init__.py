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
fernet_cipher = None

def create_app(config_object_path='config.Config'):
    """
    Application factory pattern.
    """
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object_path)

    # --- ✅ MODIFIED CORS INITIALIZATION ---
    # We are using the simplest possible setup for debugging.
    # This applies default, permissive CORS settings to the entire app.
    CORS(app)
    app.logger.info("CORS initialized in simple, permissive mode for debugging.")
    
    try:
        os.makedirs(app.instance_path)
        app.logger.info(f"Instance folder created at {app.instance_path}")
    except OSError:
        pass

    # --- Initialize Extensions ---
    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    
    global fernet_cipher
    api_encryption_key_str = app.config.get('API_ENCRYPTION_KEY')
    if not api_encryption_key_str:
        app.logger.warning("API_ENCRYPTION_KEY is not set in config. API key functionality will be impaired.")
        fernet_cipher = None
    else:
        try:
            fernet_cipher = Fernet(api_encryption_key_str.encode())
            app.logger.info("Fernet cipher initialized successfully for API key encryption.")
        except Exception as e:
            app.logger.error(f"Failed to init Fernet from config: {e}")
            fernet_cipher = None
    
    app.fernet_cipher = fernet_cipher

    with app.app_context():
        from .models import models

    # --- Register Blueprints ---
    from .routes.general_routes import general_bp
    from .routes.admin_routes import admin_bp
    from .routes.chat_routes import chat_bp
    from .routes.data_source_routes import data_source_bp
    from .routes.github_routes import github_bp # ✅ 1. IMPORT THE NEW BLUEPRINT
    from .routes.google_routes import google_bp # ✅ 1. IMPORT THE NEW BLUEPRINT


    app.register_blueprint(general_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(data_source_bp, url_prefix='/api/data-sources')
    app.register_blueprint(github_bp, url_prefix='/api') # ✅ 2. REGISTER THE NEW BLUEPRINT
    app.register_blueprint(google_bp, url_prefix='/api') # ✅ 2. REGISTER THE NEW BLUEPRINT

    app.logger.info("Flask app created and configured.")
    return app