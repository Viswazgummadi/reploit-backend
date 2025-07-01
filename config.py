# backend/config.py
from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    # --- Existing Flask, DB, JWT, Celery Config ---
    SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-fallback-super-secret-key-for-flask')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app_data.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'default-jwt-secret-key-please-change')
    JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
    JWT_EXP_DELTA_SECONDS = int(os.environ.get('JWT_EXP_DELTA_SECONDS', 3600))
    API_ENCRYPTION_KEY = os.environ.get('API_ENCRYPTION_KEY')
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:5173')
    INITIAL_ADMIN_USERNAME = os.environ.get('INITIAL_ADMIN_USERNAME', 'admin')
    INITIAL_ADMIN_PASSWORD = os.environ.get('INITIAL_ADMIN_PASSWORD', '123')
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5001/api/connect/google/callback')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GITHUB_PAT = os.environ.get('GITHUB_PAT')
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    REPO_CLONE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'repos_cloned')

    # --- NEW: Neo4j AuraDB Configuration ---
    NEO4J_URI = os.environ.get('NEO4J_URI')
    NEO4J_USERNAME = os.environ.get('NEO4J_USERNAME')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD')
    # --- END NEW ---
    PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY')
    # PINECONE_ENVIRONMENT = os.environ.get('PINECONE_ENVIRONMENT')
    
    # We will keep these for our rate-limiting strategy
    EMBEDDING_BATCH_SIZE = 100 # Gemini allows up to 100 texts per request
    EMBEDDING_REQUEST_DELAY = 1.5 # Wait 1.5 seconds between batches
    ENABLE_AI_DOCSTRING_GENERATION = True