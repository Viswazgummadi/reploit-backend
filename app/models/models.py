# backend/app/models/models.py

import uuid
from datetime import datetime
from . import db
from . import bcrypt
from sqlalchemy.dialects.postgresql import JSONB 

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

    # Relationships (Optional but good for clarity in ORM)
    chat_history = db.relationship('ChatHistory', backref='user', lazy=True)
    
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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'service_name': self.service_name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
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
    context_window = db.Column(db.Integer, nullable=True)

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
            'context_window': self.context_window,
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
    # 2. Change db.JSON to JSONB
    connection_details = db.Column(JSONB, nullable=False, unique=True)
    status = db.Column(db.String(50), nullable=False, default="pending") 
    last_indexed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chat_history = db.relationship('ChatHistory', backref='data_source', lazy=True)

    def __repr__(self):
        return f'<DataSource {self.id} - {self.name} ({self.status})>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'source_type': self.source_type,
            'connection_details': self.connection_details,
            'status': self.status,
            'last_indexed_at': self.last_indexed_at.isoformat() if self.last_indexed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

# --- NEW MODEL FOR CHAT HISTORY ---
class ChatHistory(db.Model):
    """
    Stores individual messages in a conversation, linked to a session, user, and data source.
    """
    __tablename__ = 'chat_history'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), nullable=False, index=True) # UUID for conversation session
    
    # Link to AdminUser (assuming chat is initiated by an admin for now)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    
    # Link to the DataSource (repository) the chat is about
    data_source_id = db.Column(db.String, db.ForeignKey('data_sources.id'), nullable=False, index=True)
    
    message_content = db.Column(db.Text, nullable=False)
    sender = db.Column(db.String(10), nullable=False) # 'user' or 'llm' (or 'system_error' if we want to store it)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'data_source_id': self.data_source_id,
            'text': self.message_content, # 'text' to match frontend's 'message.text'
            'author': self.sender,       # 'author' to match frontend's 'message.author'
            'timestamp': self.timestamp.isoformat()
        }