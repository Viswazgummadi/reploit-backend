import requests
from flask import Blueprint, jsonify, current_app
from flask_cors import CORS # ✅ Ensure CORS is imported

from ..utils.auth import token_required, decrypt_value
from ..models.models import db, APIKey, DataSource

github_bp = Blueprint('github_routes', __name__, url_prefix='/api/connect/github')
CORS(github_bp, supports_credentials=True)

@github_bp.route('/available-repos/', methods=['GET'])
@token_required
def get_available_github_repos(current_admin_username):
    """
    Fetches the user's repositories from GitHub using the stored PAT
    and flags which ones are already connected as a DataSource.
    """
    # 1. Retrieve and decrypt the GitHub Personal Access Token (PAT)
    github_pat_entry = db.session.query(APIKey).filter_by(service_name='GITHUB_PAT').first()
    if not github_pat_entry:
        return jsonify({"error": "GITHUB_PAT is not configured in Admin Settings."}), 404

    decrypted_pat = decrypt_value(github_pat_entry.key_value_encrypted)
    if not decrypted_pat:
        return jsonify({"error": "Failed to decrypt GitHub PAT. Check server configuration."}), 500

    # 2. Call the GitHub API to get the user's repositories
    headers = {
        'Authorization': f'token {decrypted_pat}',
        'Accept': 'application/vnd.github.v3+json',
    }
    try:
        response = requests.get('https://api.github.com/user/repos?type=all&sort=updated', headers=headers)
        response.raise_for_status()  # This will raise an exception for 4xx or 5xx errors
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return jsonify({"error": "GitHub PAT is invalid or has expired. Please update it."}), 401
        return jsonify({"error": f"Failed to fetch from GitHub API: {e}"}), 502
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Network error connecting to GitHub: {e}"}), 502

    github_repos_data = response.json()

    # 3. Get all existing connected repository 'full_name's for efficient lookup
    existing_sources = db.session.query(DataSource).filter_by(source_type='github').all()
    # Assuming connection_details stores a dict like {'repo_full_name': 'user/repo'}
    connected_repo_full_names = {source.connection_details.get('repo_full_name') for source in existing_sources}

    # 4. Process the list to be clean and add the 'is_connected' flag
    processed_repos = []
    for repo in github_repos_data:
        is_connected = repo['full_name'] in connected_repo_full_names
        processed_repos.append({
            'name': repo['name'],
            'full_name': repo['full_name'],
            'description': repo['description'],
            'private': repo['private'],
            'html_url': repo['html_url'],
            'is_connected': is_connected,
        })

    return jsonify(processed_repos), 200