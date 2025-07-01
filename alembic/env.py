# backend/alembic/env.py
from logging.config import fileConfig
import os 
import sys 

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- START: Crucial part for making Alembic find your models ---
PROJECT_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from app import db as app_db 
    from app.models import models as app_models # This import makes ChatHistory visible
except ImportError as e:
    print(f"Error importing Flask app components for Alembic: {e}")
    print("Ensure your FLASK_APP environment or project structure allows 'app' package import.")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)

target_metadata = app_db.metadata
# --- END: Crucial part ---


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from app import create_app
    flask_app = create_app()
    
    with flask_app.app_context():
        connectable = flask_app.extensions['sqlalchemy'].engine 

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()