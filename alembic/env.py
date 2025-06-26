# backend/alembic/env.py
from logging.config import fileConfig
import os # Added os
import sys # Added sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- START: Crucial part for making Alembic find your models ---
# Add the project root (backend directory) to sys.path
# This allows Alembic to import your 'app' package
PROJECT_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Now, import your db object from your Flask app package
# This assumes your SQLAlchemy instance is named 'db' and is in app/__init__.py
# and your models are defined using this 'db.Model'
try:
    from app import db as app_db # Import your SQLAlchemy instance
    # If your models are in app.models.models and use db.Model from app package
    # you might need to ensure they are implicitly imported when app_db is imported,
    # or explicitly import them here to register with app_db.metadata.
    # Typically, if models.py uses `from .. import db` and then `class MyModel(db.Model):`,
    # app_db.metadata will contain them after app_db is initialized.
    # Let's also import the models to be safe, so their table definitions are known
    from app.models import models as app_models # Imports your app/models/models.py
except ImportError as e:
    print(f"Error importing Flask app components for Alembic: {e}")
    print("Ensure your FLASK_APP environment or project structure allows 'app' package import.")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)

# target_metadata should point to your SQLAlchemy models' metadata
# If using Flask-SQLAlchemy, this is usually db.metadata
target_metadata = app_db.metadata
# --- END: Crucial part ---


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # Get the database URL from alembic.ini or from your app's config
    # If using app config (recommended for consistency):
    from app import create_app
    flask_app = create_app() # Create a temporary app instance to get config
    url = flask_app.config.get('SQLALCHEMY_DATABASE_URI')
    if not url: # Fallback to alembic.ini if not in app config
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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Create a temporary app instance to get the SQLAlchemy engine
    # This ensures Alembic uses the same database configuration as your app
    from app import create_app
    flask_app = create_app()
    
    # Get the engine from your Flask-SQLAlchemy instance (db)
    # This requires the app context to be active for db.engine to be valid
    with flask_app.app_context():
        connectable = flask_app.extensions['sqlalchemy'].engine # More robust way to get engine

    # If the above doesn't work or you prefer direct config:
    # connectable_config = config.get_section(config.config_ini_section)
    # if 'sqlalchemy.url' not in connectable_config and flask_app:
    #     connectable_config['sqlalchemy.url'] = flask_app.config['SQLALCHEMY_DATABASE_URI']
    # connectable = engine_from_config(
    #     connectable_config, # Use section from alembic.ini
    #     prefix="sqlalchemy.",
    #     poolclass=pool.NullPool,
    # )


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