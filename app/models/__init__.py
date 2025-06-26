# backend/app/models/__init__.py

# This file makes the 'db' and 'bcrypt' objects available to the other files
# in the 'models' package.
from .. import db, bcrypt

# It also needs to import the actual model classes from models.py so that
# other parts of the application can import them from the 'app.models' package.
from .models import AdminUser, APIKey, ConfiguredModel, DataSource