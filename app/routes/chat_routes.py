# backend/app/routes/chat_routes.py
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
import google.generativeai as genai
import json

from ..utils.auth import decrypt_value
from ..models.models import db, APIKey, ConfiguredModel, DataSource

chat_bp = Blueprint('chat_api_routes', __name__)

# ✅ CRUCIAL FIX: Add trailing slash
@chat_bp.route('/available-models/', methods=['GET'])
def get_available_chat_models():
    available_models_from_db = []
    try:
        configured_db_models = db.session.query(ConfiguredModel).filter_by(is_active=True).all()
        
        for model_config in configured_db_models:
            is_truly_available = False
            api_key_name = model_config.api_key_name_ref

            if not api_key_name: 
                is_truly_available = True
            elif current_app.fernet_cipher:
                api_key_entry = db.session.query(APIKey).filter_by(service_name=api_key_name).first()
                if api_key_entry and decrypt_value(api_key_entry.key_value_encrypted):
                    is_truly_available = True
            
            if is_truly_available:
                available_models_from_db.append({
                    "id": model_config.model_id_string, 
                    "name": model_config.display_name,
                    "provider": model_config.provider,
                    "notes": model_config.notes or ""
                })
        
        if not current_app.fernet_cipher and any(mc.api_key_name_ref for mc in configured_db_models if mc.is_active):
            current_app.logger.warning("Fernet cipher not available, so API key-based models cannot be fully verified for availability.")

        return jsonify(available_models_from_db), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching available models from DB: {e}", exc_info=True)
        return jsonify({"error": "Could not retrieve available models", "details": str(e)}), 500

# ✅ Simplified this route; the global CORS in __init__.py handles OPTIONS correctly now
@chat_bp.route('/', methods=['POST'])
def chat_handler():
    # The OPTIONS preflight is now handled by the global CORS configuration.
    # No need for the `if request.method == 'OPTIONS':` block.

    data = request.get_json()
    user_query = data.get('query')
    selected_model_id_from_frontend = data.get('model')
    data_source_id = data.get('data_source_id')

    if not user_query: return jsonify({"error": "Missing query"}), 400
    if not selected_model_id_from_frontend: return jsonify({"error": "Missing model selection"}), 400
    
    if not data_source_id:
        current_app.logger.warning("Chat request received without a selected data_source_id.")
    else:
        selected_data_source = db.session.get(DataSource, data_source_id)
        if selected_data_source:
            current_app.logger.info(f"Chat initiated for data source: {selected_data_source.name} (ID: {data_source_id})")
        else:
            current_app.logger.warning(f"Data source with ID {data_source_id} not found for chat request.")

    db_model_config = db.session.query(ConfiguredModel).filter_by(
        model_id_string=selected_model_id_from_frontend, 
        is_active=True
    ).first()

    if not db_model_config:
        return jsonify({"error": f"Model '{selected_model_id_from_frontend}' is not configured or not active."}), 400

    api_key_name_for_model = db_model_config.api_key_name_ref
    decrypted_key = None

    if api_key_name_for_model:
        if not current_app.fernet_cipher:
            return jsonify({"error": "API Key encryption is not configured on server."}), 503
        
        api_key_entry = db.session.query(APIKey).filter_by(service_name=api_key_name_for_model).first()
        if not api_key_entry:
            return jsonify({"error": f"Required API key '{api_key_name_for_model}' for model '{db_model_config.display_name}' is not found."}), 503
        
        decrypted_key = decrypt_value(api_key_entry.key_value_encrypted)
        if not decrypted_key:
            current_app.logger.error(f"Failed to decrypt API key '{api_key_name_for_model}'.")
            return jsonify({"error": f"Could not decrypt API key '{api_key_name_for_model}'."}), 500
    
    try:
        if db_model_config.provider.lower() == "google":
            if api_key_name_for_model and not decrypted_key:
                 return jsonify({"error": "Google AI API key is required but was not processed correctly."}), 500
            
            if api_key_name_for_model:
                genai.configure(api_key=decrypted_key)
            
            model_instance = genai.GenerativeModel(db_model_config.model_id_string)
            
            gemini_stream = model_instance.generate_content(user_query, stream=True)

            def generate_stream_chunks():
                try:
                    for chunk in gemini_stream:
                        if chunk.text:
                            data_payload = json.dumps({"chunk": chunk.text})
                            yield f"data: {data_payload}\n\n"
                        if chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                            error_payload = json.dumps({"error": f"Content blocked: {chunk.prompt_feedback.block_reason_message}"})
                            yield f"data: {error_payload}\n\n"
                            current_app.logger.warning(f"Gemini content blocked: {chunk.prompt_feedback.block_reason_message}")
                            return

                except Exception as e:
                    current_app.logger.error(f"Error during Gemini stream generation: {e}", exc_info=True)
                    error_payload = json.dumps({"error": f"Stream generation error: {str(e)}"})
                    yield f"data: {error_payload}\n\n"

            response = Response(stream_with_context(generate_stream_chunks()), mimetype='text/event-stream')
            # These headers are for SSE and are handled differently from CORS headers, so they are fine here.
            response.headers.add("Cache-Control", "no-cache")
            response.headers.add("X-Accel-Buffering", "no")
            return response

        else:
            current_app.logger.error(f"Unsupported provider '{db_model_config.provider}'.")
            return jsonify({"error": f"Provider '{db_model_config.provider}' is not yet supported for streaming."}), 501

    except genai.types.generation_types.BlockedPromptException as bpe:
        current_app.logger.error(f"Gemini request blocked for model {db_model_config.model_id_string}: {bpe}", exc_info=True)
        return jsonify({"error": f"Your request was blocked by the content safety filter: {bpe}"}), 400
    except Exception as e:
        current_app.logger.error(f"An error occurred with the AI service {db_model_config.model_id_string}: {e}", exc_info=True)
        return jsonify({"error": f"An error occurred with the AI service: {str(e)}"}), 502