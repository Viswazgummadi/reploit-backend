# backend/app/routes/data_source_routes.py

from flask import Blueprint, request, jsonify, current_app
from flask_cors import CORS 
from ..models import db, DataSource
from ..utils.auth import token_required
from ..tasks.repo_ingestion_tasks import process_data_source_for_ai # Import the Celery task
from .. import celery_app # Import the celery_app instance for checking task status

data_source_bp = Blueprint('data_source_api_routes', __name__,url_prefix='/api/data-sources')
CORS(data_source_bp, supports_credentials=True)

@data_source_bp.route('/', methods=['GET'])
@token_required
def get_data_sources(current_admin_username):
    """
    Fetches all connected data sources from the database.
    This route is protected and requires an admin token.
    """
    try:
        # In a real multi-user app, you might filter by user_id
        sources = DataSource.query.order_by(DataSource.created_at.desc()).all()
        return jsonify([source.to_dict() for source in sources]), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching data sources for user '{current_admin_username}': {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve data sources"}), 500

@data_source_bp.route('/connect/', methods=['POST'])
@token_required
def connect_data_source(current_admin_username):
    """
    Creates a new DataSource record and triggers the background ingestion task.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    name = data.get('name')
    source_type = data.get('source_type')
    connection_details = data.get('connection_details')

    if not all([name, source_type, connection_details]):
        return jsonify({"error": "Missing required fields: name, source_type, connection_details"}), 400
    
    SUPPORTED_SOURCE_TYPES = ['github', 'google_drive']
    if source_type not in SUPPORTED_SOURCE_TYPES:
        return jsonify({"error": f"Source type '{source_type}' is not supported."}), 400

    try:
        # Check if the data source already exists
        existing_source = None
        if source_type == 'github':
            repo_full_name = connection_details.get('repo_full_name')
            if repo_full_name:
                existing_source = db.session.query(DataSource).filter(
                    DataSource.connection_details['repo_full_name'].as_string() == repo_full_name
                ).first()
        # Add similar checks for other source types if needed

        if existing_source:
            return jsonify({"error": f"This data source is already connected."}), 409

        # Create the new source with 'pending' status
        new_source = DataSource(
            name=name,
            source_type=source_type,
            connection_details=connection_details,
            status='pending'
        )
        
        db.session.add(new_source)
        db.session.commit()
        
        current_app.logger.info(f"User '{current_admin_username}' connected new data source: {new_source.name} ({new_source.id}). Triggering background processing.")
        
        # Trigger the Celery background task. .delay() sends it to the message queue.
        # We don't wait for it to finish, so the API responds instantly.
        task = process_data_source_for_ai.delay(new_source.id) 

        # Return the new source object along with the task ID for optional frontend polling
        response_data = new_source.to_dict()
        response_data['task_id'] = task.id
        
        return jsonify(response_data), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error connecting data source: {e}", exc_info=True)
        return jsonify({"error": "Failed to connect new data source"}), 500

@data_source_bp.route('/<string:data_source_id>/reindex/', methods=['POST'])
@token_required
def reindex_data_source(current_admin_username, data_source_id):
    """
    Initiates a full re-indexing process for an existing data source.
    """
    source = db.session.get(DataSource, data_source_id)
    if source is None:
        return jsonify({"error": "Data source not found"}), 404
    
    # Immediately update the status to 'indexing' for instant UI feedback
    source.status = 'indexing'
    db.session.add(source)
    db.session.commit()
    
    current_app.logger.info(f"Admin '{current_admin_username}' requested re-indexing for data source: {data_source_id}. Triggering background task.")
    
    # Trigger the same background task for re-indexing
    task = process_data_source_for_ai.delay(data_source_id) 

    return jsonify({"message": f"Re-indexing initiated for {source.name}.", "task_id": task.id}), 202

@data_source_bp.route('/<string:data_source_id>/sync/', methods=['POST'])
@token_required
def sync_data_source(current_admin_username, data_source_id):
    """
    Initiates a sync process. For now, it triggers a full re-index.
    """
    source = db.session.get(DataSource, data_source_id)
    if source is None:
        return jsonify({"error": "Data source not found"}), 404
    
    # Immediately update the status to 'indexing'
    source.status = 'indexing'
    db.session.add(source)
    db.session.commit()
    
    current_app.logger.info(f"Admin '{current_admin_username}' requested sync for data source: {data_source_id}. Triggering background task.")
    
    task = process_data_source_for_ai.delay(data_source_id) 

    return jsonify({"message": f"Sync initiated for {source.name}.", "task_id": task.id}), 202

@data_source_bp.route('/<string:data_source_id>', methods=['DELETE'])
@token_required
def delete_data_source(current_admin_username, data_source_id):
    """
    Deletes a connected data source from the database.
    """
    try:
        source_to_delete = db.session.get(DataSource, data_source_id)
        if source_to_delete is None:
            return jsonify({"error": "Data source not found"}), 404
            
        # TODO: In future steps, trigger a Celery task here to clean up:
        # 1. The cloned repository folder from the server.
        # 2. All associated nodes and relationships from the Neo4j Knowledge Graph.
        # 3. All associated vectors from the ChromaDB Vector Database.

        db.session.delete(source_to_delete)
        db.session.commit()
        
        current_app.logger.info(f"Admin '{current_admin_username}' successfully deleted data source: {source_to_delete.name} ({data_source_id}).")
        return '', 204

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting data source {data_source_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to delete data source"}), 500

# NEW ROUTE: To check the status of a background task
@data_source_bp.route('/task-status/<string:task_id>/', methods=['GET'])
@token_required
def get_task_status(current_admin_username, task_id):
    """
    Retrieves the current status and result of a Celery task, allowing the frontend to poll for progress.
    """
    task = celery_app.AsyncResult(task_id)
    
    response_data = {
        'task_id': task.id,
        'state': task.state, # PENDING, STARTED, SUCCESS, FAILURE, RETRY
        'info': task.info,   # This will contain the return value on SUCCESS or the error on FAILURE
    }
    
    return jsonify(response_data), 200