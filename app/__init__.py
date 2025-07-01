# backend/app/__init__.py

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_migrate import Migrate
from cryptography.fernet import Fernet
from datetime import timedelta
from celery import Celery

db = SQLAlchemy()
bcrypt = Bcrypt()
migrate = Migrate()
celery_app = None

def create_app(config_object_path='config.Config'):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object_path)

    # Create the directory for cloned repos if it doesn't exist
    if not os.path.exists(app.config['REPO_CLONE_PATH']):
        os.makedirs(app.config['REPO_CLONE_PATH'])

    app.config['SECRET_KEY'] = app.config.get('JWT_SECRET_KEY') or app.config.get('SECRET_KEY')
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)
    app.config['SESSION_COOKIE_SAMESITE'] = 'None'
    app.config['SESSION_COOKIE_SECURE'] = True 
    
    # --- START OF CHANGE ---
    # Replace the old CORS(app) line with this more specific configuration
    origins = app.config.get('CORS_ORIGINS', 'http://localhost:5173').split(',')
    CORS(app, supports_credentials=True, origins=origins)
    # --- END OF CHANGE ---
    
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

    global celery_app
    celery_app = Celery(
        app.import_name,
        broker=app.config['CELERY_BROKER_URL'],
        backend=app.config['CELERY_RESULT_BACKEND']
    )
    celery_app.conf.update(app.config)

    class ContextTask(celery_app.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery_app.Task = ContextTask

    # Import and register blueprints
    from .routes.general_routes import general_bp
    from .routes.admin_routes import admin_bp
    from .routes.chat_routes import chat_bp
    from .routes.data_source_routes import data_source_bp
    from .routes.github_routes import github_bp
    from .routes.google_routes import google_bp
    app.register_blueprint(general_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(data_source_bp)
    app.register_blueprint(github_bp)
    app.register_blueprint(google_bp)

    app.logger.info("Flask app created and configured.")
    return app