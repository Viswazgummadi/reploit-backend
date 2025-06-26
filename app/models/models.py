# backend/app/models/models.py

import uuid
from datetime import datetime
from . import db
from . import bcrypt

# --- Renamed User to AdminUser to match your application's imports ---
class AdminUser(db.Model):
    """
    User model for admin authentication.
    """
    __tablename__ = 'users' # The database table name can remain 'users'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=True, nullable=False)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

class APIKey(db.Model):
    """
    Stores encrypted API keys for external services like Gemini.
    """
    __tablename__ = 'api_keys'

    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(100), unique=True, nullable=False)
    key_value_encrypted = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) # ✅ ADD THIS LINE

    def to_dict(self):
        return {
            'id': self.id,
            'service_name': self.service_name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() # ✅ (Optional but good practice) ADD THIS LINE

        }

class ConfiguredModel(db.Model):
    """
    Represents an LLM model that has been configured by an admin to be available in the app.
    """
    __tablename__ = 'configured_models'

    id = db.Column(db.Integer, primary_key=True)
    model_id_string = db.Column(db.String(255), unique=True, nullable=False)
    display_name = db.Column(db.String(255), nullable=False)
    provider = db.Column(db.String(100), nullable=False)
    api_key_name_ref = db.Column(db.String(100), db.ForeignKey('api_keys.service_name'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    context_window = db.Column(db.Integer, nullable=True) # ✅ ADD THIS LINE

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'model_id_string': self.model_id_string,
            'display_name': self.display_name,
            'provider': self.provider,
            'api_key_name_ref': self.api_key_name_ref,
            'is_active': self.is_active,
            'notes': self.notes,
            'context_window': self.context_window, # ✅ AND ADD THIS LINE
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class DataSource(db.Model):
    """
    Represents a connected data source, such as a GitHub repository.
    """
    __tablename__ = 'data_sources'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    source_type = db.Column(db.String(50), nullable=False)
    connection_details = db.Column(db.JSON, nullable=False, unique=True)
    status = db.Column(db.String(50), nullable=False, default="pending_indexing")
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<DataSource {self.id} - {self.name} ({self.status})>'

    def to_dict(self):
        """Serializes the object to a dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'source_type': self.source_type,
            'connection_details': self.connection_details,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }