# backend/celery_worker.py
from dotenv import load_dotenv

# Load .env variables BEFORE importing the app factory.
# This is the crucial fix. It makes all variables from .env
# (like DATABASE_URL) available to the Celery worker process.
load_dotenv()

from app import create_app, celery_app

# The rest of the file is the same.
app = create_app()
app.app_context().push()