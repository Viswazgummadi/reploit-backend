# backend/app/routes/admin_routes.py
import datetime
import urllib.parse
from flask import Blueprint, request, jsonify, current_app
# REMOVED: from flask_cors import CORS
import jwt

from ..utils.auth import token_required, encrypt_value, decrypt_value
from ..models.models import db, AdminUser, APIKey, ConfiguredModel
from .. import bcrypt
from ..core_config.static_model_data import get_predefined_model_suggestions

admin_bp = Blueprint('admin_api_routes', __name__)

# REMOVED: CORS(admin_bp, supports_credentials=True)

# --- ADMIN LOGIN ---
@admin_bp.route('/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    if not data: return jsonify({"error": "Missing JSON data"}), 400
    username_attempt = data.get('username')
    password_attempt = data.get('password')
    if not username_attempt or not password_attempt:
        return jsonify({"error": "Missing username or password"}), 400

    admin_user = db.session.query(AdminUser).filter_by(username=username_attempt).first()
    if admin_user and bcrypt.check_password_hash(admin_user.password_hash, password_attempt):
        token_payload = {
            'sub': admin_user.username,
            'iat': datetime.datetime.utcnow(),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=current_app.config['JWT_EXP_DELTA_SECONDS'])
        }
        try:
            access_token = jwt.encode(token_payload, current_app.config['JWT_SECRET_KEY'], algorithm=current_app.config['JWT_ALGORITHM'])
            return jsonify({"message": "Admin login successful", "token": access_token}), 200
        except Exception as e:
            current_app.logger.error(f"Error encoding JWT: {e}")
            return jsonify({"error": "Could not generate token"}), 500
    else:
        return jsonify({"error": "Invalid admin credentials"}), 401

# ... the rest of the file remains the same ...
@admin_bp.route('/profile', methods=['GET'])
@token_required
def admin_profile(current_admin_username):
    admin_user = db.session.query(AdminUser).filter_by(username=current_admin_username).first()
    if not admin_user:
        return jsonify({"error": "Admin user not found."}), 404
    return jsonify({
        "message": f"Welcome Admin: {admin_user.username}!",
        "profile_data": {
            "id": admin_user.id,
            "username": admin_user.username,
            "joined_on": admin_user.created_at.isoformat() if admin_user.created_at else None
        }
    }), 200

@admin_bp.route('/settings/apikeys', methods=['GET'])
@token_required
def get_api_keys_status(current_admin_username):
    if not current_app.fernet_cipher:
        return jsonify({"error": "API Key encryption is not configured."}), 503
    try:
        keys = db.session.query(APIKey).all()
        keys_status = [{"service_name": key.service_name, "is_set": True, "updated_at": key.updated_at.isoformat() if key.updated_at else None} for key in keys]
        return jsonify(keys_status), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching API keys: {e}")
        return jsonify({"error": "Could not retrieve API keys."}), 500

@admin_bp.route('/settings/apikeys', methods=['POST'])
@token_required
def add_or_update_api_key(current_admin_username):
    if not current_app.fernet_cipher:
        return jsonify({"error": "API Key encryption is not configured."}), 503
    data = request.get_json()
    service_name = data.get('service_name')
    key_value = data.get('key_value')
    if not service_name or not key_value:
        return jsonify({"error": "Missing service_name or key_value"}), 400

    encrypted_value = encrypt_value(key_value)
    if not encrypted_value:
        return jsonify({"error": "Failed to encrypt API key."}), 500

    try:
        api_key_entry = db.session.query(APIKey).filter_by(service_name=service_name).first()
        is_new_key = False
        if api_key_entry:
            api_key_entry.key_value_encrypted = encrypted_value
            api_key_entry.updated_at = datetime.datetime.utcnow()
            message = f"API key for '{service_name}' updated."
        else:
            is_new_key = True
            api_key_entry = APIKey(service_name=service_name, key_value_encrypted=encrypted_value)
            db.session.add(api_key_entry)
            message = f"API key for '{service_name}' added."
        db.session.commit()
        return jsonify({"message": message}), 201 if is_new_key else 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"DB error for API key {service_name}: {e}")
        return jsonify({"error": "Could not save API key."}), 500

@admin_bp.route('/settings/apikeys/<path:service_name_encoded>', methods=['DELETE'])
@token_required
def delete_api_key(current_admin_username, service_name_encoded):
    if not current_app.fernet_cipher:
        return jsonify({"error": "API Key encryption is not configured."}), 503
    try:
        service_name = urllib.parse.unquote_plus(service_name_encoded)
    except Exception as e:
        return jsonify({"error": f"Invalid service name encoding: {e}"}), 400

    try:
        api_key_entry = db.session.query(APIKey).filter_by(service_name=service_name).first()
        if not api_key_entry:
            return jsonify({"error": f"API key for '{service_name}' not found."}), 404
        db.session.delete(api_key_entry)
        db.session.commit()
        return jsonify({"message": f"API key for '{service_name}' deleted."}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"DB error deleting API key {service_name}: {e}")
        return jsonify({"error": "Could not delete API key."}), 500

@admin_bp.route('/configured-models', methods=['POST'])
@token_required
def add_configured_model(current_admin_username):
    data = request.get_json()
    if not data:
        return jsonify({"msg": "Missing JSON in request"}), 400

    required_fields = ['model_id_string', 'display_name', 'provider', 'api_key_name_ref']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"msg": f"Missing or empty required field: {field}"}), 400

    api_key_exists = db.session.query(APIKey).filter_by(service_name=data['api_key_name_ref']).first()
    if not api_key_exists:
        return jsonify({"msg": f"API Key name '{data['api_key_name_ref']}' not found in stored API keys."}), 400

    existing_model = db.session.query(ConfiguredModel).filter_by(
        model_id_string=data['model_id_string'],
        provider=data['provider']
    ).first()
    if existing_model:
        return jsonify({"msg": "A model with this ID and provider already exists."}), 409

    try:
        new_model = ConfiguredModel(
            model_id_string=data['model_id_string'],
            display_name=data['display_name'],
            provider=data['provider'],
            api_key_name_ref=data['api_key_name_ref'],
            is_active=data.get('is_active', True),
            notes=data.get('notes'),
            context_window=data.get('context_window')
        )
        db.session.add(new_model)
        db.session.commit()

        response_data = {
            "id": new_model.id, "model_id_string": new_model.model_id_string,
            "display_name": new_model.display_name, "provider": new_model.provider,
            "api_key_name_ref": new_model.api_key_name_ref, "is_active": new_model.is_active,
            "notes": new_model.notes, "context_window": new_model.context_window,
            "created_at": new_model.created_at.isoformat() if new_model.created_at else None,
        }
        return jsonify({"msg": "Model configured successfully", "model": response_data}), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding configured model: {e}", exc_info=True)
        return jsonify({"msg": "Failed to configure model", "error": str(e)}), 500

@admin_bp.route('/configured-models', methods=['GET'])
@token_required
def get_configured_models(current_admin_username):
    try:
        models = db.session.query(ConfiguredModel).order_by(ConfiguredModel.display_name).all()
        results = [{
            "id": model.id, "model_id_string": model.model_id_string,
            "display_name": model.display_name, "provider": model.provider,
            "api_key_name_ref": model.api_key_name_ref, "is_active": model.is_active,
            "notes": model.notes, "context_window": model.context_window,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        } for model in models]
        return jsonify(results), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching configured models: {e}", exc_info=True)
        return jsonify({"msg": "Failed to fetch models", "error": str(e)}), 500

@admin_bp.route('/configured-models/<int:model_id>', methods=['PUT'])
@token_required
def update_configured_model(current_admin_username, model_id):
    model_to_update = db.session.query(ConfiguredModel).get(model_id)
    if not model_to_update:
        return jsonify({"msg": "Configured model not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"msg": "Missing JSON in request"}), 400

    if 'api_key_name_ref' in data and data['api_key_name_ref']:
        api_key_exists = db.session.query(APIKey).filter_by(service_name=data['api_key_name_ref']).first()
        if not api_key_exists:
            return jsonify({"msg": f"API Key name '{data['api_key_name_ref']}' not found."}), 400
        model_to_update.api_key_name_ref = data['api_key_name_ref']

    new_model_id_string = data.get('model_id_string', model_to_update.model_id_string)
    new_provider = data.get('provider', model_to_update.provider)
    if (new_model_id_string != model_to_update.model_id_string or \
        new_provider != model_to_update.provider):
        existing_model_check = db.session.query(ConfiguredModel).filter(
            ConfiguredModel.model_id_string == new_model_id_string,
            ConfiguredModel.provider == new_provider,
            ConfiguredModel.id != model_id
        ).first()
        if existing_model_check:
            return jsonify({"msg": "Another model with this ID and provider already exists."}), 409

    try:
        model_to_update.model_id_string = new_model_id_string
        model_to_update.display_name = data.get('display_name', model_to_update.display_name)
        model_to_update.provider = new_provider
        model_to_update.is_active = data.get('is_active', model_to_update.is_active)
        model_to_update.notes = data.get('notes', model_to_update.notes)
        model_to_update.context_window = data.get('context_window', model_to_update.context_window)

        db.session.commit()
        response_data = {
            "id": model_to_update.id, "model_id_string": model_to_update.model_id_string,
            "display_name": model_to_update.display_name, "provider": model_to_update.provider,
            "api_key_name_ref": model_to_update.api_key_name_ref, "is_active": model_to_update.is_active,
            "notes": model_to_update.notes, "context_window": model_to_update.context_window,
            "updated_at": model_to_update.updated_at.isoformat() if model_to_update.updated_at else None,
        }
        return jsonify({"msg": "Model configuration updated", "model": response_data}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating configured model {model_id}: {e}", exc_info=True)
        return jsonify({"msg": "Failed to update model configuration", "error": str(e)}), 500

@admin_bp.route('/configured-models/<int:model_id>', methods=['DELETE'])
@token_required
def delete_configured_model(current_admin_username, model_id):
    model_to_delete = db.session.query(ConfiguredModel).get(model_id)
    if not model_to_delete:
        return jsonify({"msg": "Configured model not found"}), 404
    try:
        db.session.delete(model_to_delete)
        db.session.commit()
        return jsonify({"msg": "Model configuration deleted"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting configured model {model_id}: {e}", exc_info=True)
        return jsonify({"msg": "Failed to delete model configuration", "error": str(e)}), 500

@admin_bp.route('/model-suggestions', methods=['GET'])
@token_required
def get_model_suggestions_route(current_admin_username):
    try:
        suggestions = get_predefined_model_suggestions()
        configured_db_models = db.session.query(ConfiguredModel.model_id_string, ConfiguredModel.provider).all()
        configured_ids = set((cm.model_id_string, cm.provider) for cm in configured_db_models)

        filtered_suggestions = [
            sugg for sugg in suggestions 
            if (sugg['id'], sugg['provider']) not in configured_ids
        ]

        return jsonify(filtered_suggestions), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching model suggestions: {e}", exc_info=True)
        return jsonify({"msg": "Failed to fetch model suggestions", "error": str(e)}), 500