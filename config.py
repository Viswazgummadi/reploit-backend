# backend/config.py
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env
import os


class Config:
    # Flask App Secret Key (for sessions, etc.)
    # Using JWT_SECRET_KEY as the general SECRET_KEY is common if it's strong.
    SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-fallback-super-secret-key-for-flask')

    # SQLAlchemy Configuration
    # For Render, we'll use an ephemeral SQLite database for now.
    # This means data will be reset on restarts/redeploys.
    # If DATABASE_URL env var is set (e.g., for PostgreSQL), it will use that.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app_data.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'default-jwt-secret-key-please-change')
    JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
    JWT_EXP_DELTA_SECONDS = int(os.environ.get('JWT_EXP_DELTA_SECONDS', 3600)) # 1 hour

    # API Key Encryption (Fernet)
    API_ENCRYPTION_KEY = os.environ.get('API_ENCRYPTION_KEY') # This key is crucial for encryption/decryption

    # CORS Configuration
    # This will be 'http://localhost:5173' for local, and your Vercel URL in production
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:5173')

    # Initial Admin User Credentials (for CLI command)
    INITIAL_ADMIN_USERNAME = os.environ.get('INITIAL_ADMIN_USERNAME', 'admin')
    INITIAL_ADMIN_PASSWORD = os.environ.get('INITIAL_ADMIN_PASSWORD', '123')

    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    # The redirect URI should point to our deployed backend callback endpoint
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5001/api/connect/google/callback')

    # --- ✅ ADDED LLM & GitHub API Keys ---
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GITHUB_PAT = os.environ.get('GITHUB_PAT')