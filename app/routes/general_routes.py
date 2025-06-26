# backend/app/routes/general_routes.py
from flask import Blueprint, jsonify

general_bp = Blueprint('general_api', __name__) # Renamed for clarity

@general_bp.route('/hello')
def hello():
    return jsonify(message="Hello from Refactored Reploit Backend!")