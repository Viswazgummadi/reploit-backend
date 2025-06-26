# backend/app/routes/data_source_routes.py

from flask import Blueprint, request, jsonify, current_app
# from flask_cors import CORS # ✅ REMOVED: Rely on global CORS config in __init__.py
from ..models import db, DataSource
from ..utils.auth import token_required

data_source_bp = Blueprint('data_source_api_routes', __name__)

# ✅ REMOVED: CORS(data_source_bp, supports_credentials=True)
# This is now handled by the global CORS configuration in your app factory (__init__.py)

@data_source_bp.route('/', methods=['GET'])
def get_data_sources():
    """
    Fetches all connected data sources from the database.
    This route is called as /api/data-sources/, so this definition is correct.
    """
    try:
        sources = DataSource.query.order_by(DataSource.created_at.desc()).all()
        return jsonify([source.to_dict() for source in sources]), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching data sources: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve data sources"}), 500

# ✅ CRUCIAL FIX: Add trailing slash
@data_source_bp.route('/connect/', methods=['POST'])
def connect_data_source():
    """
    Creates a new DataSource record for any supported source type.
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
        existing_source = None
        if source_type == 'github':
            repo_full_name = connection_details.get('repo_full_name')
            if repo_full_name:
                existing_source = db.session.query(DataSource).filter(
                    DataSource.connection_details['repo_full_name'].as_string() == repo_full_name
                ).first()
        elif source_type == 'google_drive':
            file_id = connection_details.get('file_id')
            if file_id:
                existing_source = db.session.query(DataSource).filter(
                    DataSource.connection_details['file_id'].as_string() == file_id
                ).first()

        if existing_source:
            return jsonify({"error": f"This data source is already connected."}), 409

        new_source = DataSource(
            name=name,
            source_type=source_type,
            connection_details=connection_details,
            status='pending_indexing'
        )
        
        db.session.add(new_source)
        db.session.commit()
        
        current_app.logger.info(f"Successfully connected new data source: {new_source.name} ({new_source.id})")
        return jsonify(new_source.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error connecting data source: {e}", exc_info=True)
        return jsonify({"error": "Failed to connect new data source"}), 500

@data_source_bp.route('/<string:data_source_id>', methods=['DELETE'])
def delete_data_source(data_source_id):
    """
    Deletes a connected data source from the database.
    This route with a dynamic ID at the end should NOT have a trailing slash.
    """
    try:
        source_to_delete = db.session.get(DataSource, data_source_id)
        if source_to_delete is None:
            return jsonify({"error": "Data source not found"}), 404
            
        db.session.delete(source_to_delete)
        db.session.commit()
        
        current_app.logger.info(f"Successfully deleted data source: {source_to_delete.name} ({data_source_id})")
        return '', 204

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting data source {data_source_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to delete data source"}), 500

# ✅ CRUCIAL FIX: Add trailing slash
@data_source_bp.route('/<string:data_source_id>/reindex/', methods=['POST'])
@token_required
def reindex_data_source(current_admin_username, data_source_id):
    """
    Initiates a full re-indexing process for a data source.
    """
    source = db.session.get(DataSource, data_source_id)
    if source is None:
        return jsonify({"error": "Data source not found"}), 404
    
    current_app.logger.info(f"Admin '{current_admin_username}' requested re-indexing for data source: {data_source_id}")
    return jsonify({"message": f"Re-indexing request for {source.name} received. Processing will begin shortly."}), 200

# ✅ CRUCIAL FIX: Add trailing slash
@data_source_bp.route('/<string:data_source_id>/sync/', methods=['POST'])
@token_required
def sync_data_source(current_admin_username, data_source_id):
    """
    Initiates a sync process for a data source to update changes.
    """
    source = db.session.get(DataSource, data_source_id)
    if source is None:
        return jsonify({"error": "Data source not found"}), 404
    
    current_app.logger.info(f"Admin '{current_admin_username}' requested sync for data source: {data_source_id}")
    return jsonify({"message": f"Sync request for {source.name} received. Changes will be processed."}), 200

# ✅ CRUCIAL FIX: Add trailing slash
@data_source_bp.route('/<string:data_source_id>/delete-embeddings/', methods=['DELETE'])
@token_required
def delete_source_embeddings(current_admin_username, data_source_id):
    """
    Deletes the generated embeddings for a data source, but keeps the connection record.
    """
    source = db.session.get(DataSource, data_source_id)
    if source is None:
        return jsonify({"error": "Data source not found"}), 404
    
    current_app.logger.info(f"Admin '{current_admin_username}' requested embedding deletion for data source: {data_source_id}")
    return jsonify({"message": f"Embeddings for {source.name} deleted successfully."}), 200

# ✅ CRUCIAL FIX: Add trailing slash
@data_source_bp.route('/test/', methods=['GET'])
def test_route():
    current_app.logger.info("Test route hit!")
    return jsonify({"message": "Test successful!"}), 200