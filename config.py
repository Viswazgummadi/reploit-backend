# backend/config.py
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env
import os


class Config:
    # Flask App Secret Key (for sessions, etc.)
    SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-fallback-super-secret-key-for-flask') # General Flask secret key

    # SQLAlchemy Configuration
    # Default to placing the DB in the 'instance' folder at the root of the backend project
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'reploit_dev.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False


    # JWT Configuration (these were specific to your manual JWT implementation)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'default-jwt-secret-key-please-change')
    JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
    JWT_EXP_DELTA_SECONDS = int(os.environ.get('JWT_EXP_DELTA_SECONDS', 3600)) # 1 hour

    # API Key Encryption
    API_ENCRYPTION_KEY = os.environ.get('API_ENCRYPTION_KEY') # Store the raw key string

    # CORS Configuration
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:5173')

    # Initial Admin User Credentials (for CLI command)
    INITIAL_ADMIN_USERNAME = os.environ.get('INITIAL_ADMIN_USERNAME', 'admin')
    INITIAL_ADMIN_PASSWORD = os.environ.get('INITIAL_ADMIN_PASSWORD', '123')
        # ✅ ADD THESE LINES FOR GOOGLE OAUTH
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', None)
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', None)
    # The redirect URI should point to our backend callback endpoint
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5001/api/connect/google/callback')