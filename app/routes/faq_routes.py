from flask import Blueprint, request, jsonify, current_app
from ..models import db, FAQ, DataSource
from ..utils.auth import token_required

faq_bp = Blueprint('faq_api_routes', __name__)

@faq_bp.route('/', methods=['GET'])
@token_required
def get_faqs(current_admin_username):
    """
    Retrieves generated FAQs, optionally filtered by data_source_id.
    """
    data_source_id = request.args.get('data_source_id')

    try:
        query = db.session.query(FAQ)
        
        if data_source_id:
            query = query.filter_by(data_source_id=data_source_id)

        faqs = query.order_by(FAQ.generated_at.desc()).all()

        faqs_data = []
        for faq in faqs:
            faq_dict = faq.to_dict()
            if faq.data_source_id:
                data_source = db.session.get(DataSource, faq.data_source_id)
                faq_dict['data_source_name'] = data_source.name if data_source else "Unknown Source"
            else:
                faq_dict['data_source_name'] = "General"
            faqs_data.append(faq_dict)

        return jsonify(faqs_data), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching FAQs: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve FAQs"}), 500

@faq_bp.route('/<string:faq_id>', methods=['DELETE'])
@token_required
def delete_faq(current_admin_username, faq_id):
    """
    Deletes a specific FAQ entry from the database.
    """
    try:
        faq_to_delete = db.session.get(FAQ, faq_id)
        if faq_to_delete is None:
            return jsonify({"error": "FAQ not found"}), 404
        
        db.session.delete(faq_to_delete)
        db.session.commit()
        
        current_app.logger.info(f"Admin '{current_admin_username}' deleted FAQ: {faq_id}")
        return jsonify({"message": "FAQ deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting FAQ {faq_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to delete FAQ"}), 500