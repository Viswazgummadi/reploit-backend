# backend/app/__init__.py

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_migrate import Migrate
from cryptography.fernet import Fernet

db = SQLAlchemy()
bcrypt = Bcrypt()
migrate = Migrate()

def create_app(config_object_path='config.Config'):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object_path)

    app.config['SECRET_KEY'] = app.config.get('JWT_SECRET_KEY') or app.config.get('SECRET_KEY')

    # Apply a simple global CORS. The real work is now on the blueprints.
    CORS(app)
    
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    
    api_encryption_key_str = app.config.get('API_ENCRYPTION_KEY')
    if api_encryption_key_str:
        app.fernet_cipher = Fernet(api_encryption_key_str.encode('utf-8'))
    else:
        app.fernet_cipher = None
    
    with app.app_context():
        from .models import models

    from .routes.general_routes import general_bp
    from .routes.admin_routes import admin_bp
    from .routes.chat_routes import chat_bp
    from .routes.data_source_routes import data_source_bp
    from .routes.github_routes import github_bp
    from .routes.google_routes import google_bp

    # ✅ CRUCIAL FIX: Register blueprints WITHOUT a url_prefix here.
    # The prefix is now defined in the blueprint file itself.
    app.register_blueprint(general_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(data_source_bp)
    app.register_blueprint(github_bp)
    app.register_blueprint(google_bp)

    app.logger.info("Flask app created and configured.")
    return app