# backend/app/routes/chat_routes.py
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context, g
# import google.generativeai as genai
import json
from flask_cors import CORS
from langchain_core.messages import HumanMessage, AIMessage

from ..utils.auth import decrypt_value, token_required # Import token_required
from ..models.models import db, APIKey, ConfiguredModel, DataSource, ChatHistory, AdminUser # Import ChatHistory and AdminUser
from ..ai_core.agent import agent_graph

chat_bp = Blueprint('chat_api_routes', __name__, url_prefix='/api/chat')
CORS(chat_bp, supports_credentials=True)

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

# NEW ROUTE: Fetch chat history for a session
@chat_bp.route('/history/<session_id>/', methods=['GET'])
@token_required # Ensure only authenticated users can fetch their history
def get_chat_history(current_user_identity, session_id):
    data_source_id = request.args.get('repo_id') # Frontend sends repo_id as query param

    if not data_source_id:
        return jsonify({"error": "Missing repo_id query parameter."}), 400

    user = db.session.query(AdminUser).filter_by(username=current_user_identity).first()
    if not user:
        current_app.logger.error(f"Authenticated user '{current_user_identity}' not found.")
        return jsonify({"error": "User not found."}), 404

    try:
        history_messages = db.session.query(ChatHistory).filter_by(
            session_id=session_id,
            user_id=user.id, # Filter by user_id to ensure ownership
            data_source_id=data_source_id
        ).order_by(ChatHistory.timestamp.asc()).all() # Order by timestamp
        
        return jsonify([msg.to_dict() for msg in history_messages]), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching chat history for session {session_id}: {e}", exc_info=True)
        return jsonify({"error": "Could not retrieve chat history", "details": str(e)}), 500


# MODIFIED ROUTE: Handle chat submission and save history
@chat_bp.route('/', methods=['POST'])
@token_required # Apply the decorator to protect the route
def chat_handler(current_user_identity): # current_user_identity is passed by token_required
    data = request.get_json()
    user_query = data.get('query')
    selected_model_id_from_frontend = data.get('model')
    data_source_id = data.get('data_source_id')
    session_id = data.get('session_id') # Get session_id from frontend

    if not user_query: return jsonify({"error": "Missing query"}), 400
    if not selected_model_id_from_frontend: return jsonify({"error": "Missing model selection"}), 400
    if not session_id: return jsonify({"error": "Missing session_id"}), 400
    if not data_source_id: return jsonify({"error": "Missing data_source_id"}), 400

    user = db.session.query(AdminUser).filter_by(username=current_user_identity).first()
    if not user:
        current_app.logger.error(f"Authenticated user '{current_user_identity}' not found.")
        return jsonify({"error": "Authentication error: User not found."}), 401

    selected_data_source = db.session.get(DataSource, data_source_id)
    if selected_data_source:
        current_app.logger.info(f"Chat initiated for data source: {selected_data_source.name} (ID: {data_source_id}) by user {user.username}")
    else:
        current_app.logger.warning(f"Data source with ID {data_source_id} not found for chat request by user {user.username}.")
        return jsonify({"error": f"Data source with ID {data_source_id} not found."}), 404

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
    
    # --- SAVE USER MESSAGE TO HISTORY ---
    new_user_message_entry = ChatHistory(
        session_id=session_id,
        user_id=user.id,
        data_source_id=data_source_id,
        message_content=user_query,
        sender='user'
    )
    db.session.add(new_user_message_entry)
    db.session.commit() # Commit immediately to ensure user message is saved even if AI fails

    try:
        if db_model_config.provider.lower() == "google":
            if api_key_name_for_model and not decrypted_key:
                 return jsonify({"error": "Google AI API key is required but was not processed correctly."}), 500
            
            if api_key_name_for_model:
                genai.configure(api_key=decrypted_key)
            
            model_instance = genai.GenerativeModel(db_model_config.model_id_string)
            
            # TODO: In Phase 2, this is where you'd integrate LangGraph with retrieved history
            # For now, it's just passing the user_query directly
            gemini_stream = model_instance.generate_content(user_query, stream=True)

            ai_response_chunks = [] # To accumulate AI response for saving
            def generate_stream_chunks():
                nonlocal ai_response_chunks # Allow modification of outer variable
                try:
                    for chunk in gemini_stream:
                        if chunk.text:
                            ai_response_chunks.append(chunk.text) # Accumulate chunks
                            data_payload = json.dumps({"chunk": chunk.text})
                            yield f"data: {data_payload}\n\n"
                        if chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                            error_payload = json.dumps({"error": f"Content blocked: {chunk.prompt_feedback.block_reason_message}"})
                            yield f"data: {error_payload}\n\n"
                            current_app.logger.warning(f"Gemini content blocked: {chunk.prompt_feedback.block_reason_message}")
                            # Do not save blocked content as successful AI response
                            ai_response_chunks = ["Content Blocked by AI Provider."] 
                            return

                except Exception as e:
                    current_app.logger.error(f"Error during Gemini stream generation: {e}", exc_info=True)
                    error_payload = json.dumps({"error": f"Stream generation error: {str(e)}"})
                    yield f"data: {error_payload}\n\n"
                    ai_response_chunks = [f"Error: {str(e)}"] # Save error message
                finally:
                    # --- SAVE AI RESPONSE TO HISTORY AFTER STREAM COMPLETES/ERRORS ---
                    # This code runs when the generator function finishes
                    if ai_response_chunks:
                        full_ai_response = "".join(ai_response_chunks)
                        new_ai_message_entry = ChatHistory(
                            session_id=session_id,
                            user_id=user.id,
                            data_source_id=data_source_id,
                            message_content=full_ai_response,
                            sender='llm' # 'llm' to match frontend expected author
                        )
                        db.session.add(new_ai_message_entry)
                        db.session.commit()
                        current_app.logger.info(f"AI response saved for session {session_id}.")


            response = Response(stream_with_context(generate_stream_chunks()), mimetype='text/event-stream')
            response.headers.add("Cache-Control", "no-cache")
            response.headers.add("X-Accel-Buffering", "no")
            return response

        else:
            current_app.logger.error(f"Unsupported provider '{db_model_config.provider}'.")
            # If AI service isn't supported, we should also save an error message for the AI response
            error_message = f"Provider '{db_model_config.provider}' is not yet supported for streaming."
            new_ai_message_entry = ChatHistory(
                session_id=session_id,
                user_id=user.id,
                data_source_id=data_source_id,
                message_content=f"Error: {error_message}",
                sender='llm'
            )
            db.session.add(new_ai_message_entry)
            db.session.commit()
            return jsonify({"error": error_message}), 501

    except genai.types.generation_types.BlockedPromptException as bpe:
        current_app.logger.error(f"Gemini request blocked for model {db_model_config.model_id_string}: {bpe}", exc_info=True)
        # Save blocked message to history
        new_ai_message_entry = ChatHistory(
            session_id=session_id,
            user_id=user.id,
            data_source_id=data_source_id,
            message_content=f"Your request was blocked by the AI content safety filter: {bpe}",
            sender='llm'
        )
        db.session.add(new_ai_message_entry)
        db.session.commit()
        return jsonify({"error": f"Your request was blocked by the content safety filter: {bpe}"}), 400
    except Exception as e:
        current_app.logger.error(f"An error occurred with the AI service {db_model_config.model_id_string}: {e}", exc_info=True)
        # Save error message to history
        new_ai_message_entry = ChatHistory(
            session_id=session_id,
            user_id=user.id,
            data_source_id=data_source_id,
            message_content=f"An error occurred with the AI service: {str(e)}",
            sender='llm'
        )
        db.session.add(new_ai_message_entry)
        db.session.commit()
        return jsonify({"error": f"An error occurred with the AI service: {str(e)}"}), 502