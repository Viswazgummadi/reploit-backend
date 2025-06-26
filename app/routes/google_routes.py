import os
# ✅ Force the insecure transport flag for local development (MUST BE AT THE TOP)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' 

from flask import Blueprint, request, jsonify, current_app, redirect
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from ..models import db, APIKey
from ..utils.auth import token_required, encrypt_value, decrypt_value

google_bp = Blueprint('google_routes', __name__)

SCOPES = ['https://www.googleapis.com/auth/userinfo.profile', 'https://www.googleapis.com/auth/drive.readonly']

def get_google_flow():
    """
    Helper function to create the Google OAuth Flow object
    by reading the client_secret.json file directly.
    """
    client_secrets_file = os.path.join(current_app.instance_path, 'client_secret.json')
    
    return Flow.from_client_secrets_file(
        client_secrets_file=client_secrets_file,
        scopes=SCOPES,
        redirect_uri=current_app.config['GOOGLE_REDIRECT_URI']
    )

@google_bp.route('/connect/google/auth-url', methods=['GET'])
@token_required
def get_google_auth_url(current_admin_username):
    flow = get_google_flow()
    authorization_url, state = flow.authorization_url(access_type='offline', prompt='consent')
    return jsonify({'authorization_url': authorization_url})

@google_bp.route('/connect/google/callback', methods=['GET'])
def google_callback():
    try:
        flow = get_google_flow()
        flow.fetch_token(authorization_response=request.url)
    except Exception as e:
        # This is where the error is happening. Check the server log for the exact error message.
        current_app.logger.error(f"Failed to fetch Google token: {e}", exc_info=True)
        return redirect(f"http://localhost:5173/admin/repos?gauth=error")

    credentials = flow.credentials
    
    try:
        if credentials.refresh_token:
            encrypted_refresh_token = encrypt_value(credentials.refresh_token)
            refresh_token_entry = db.session.query(APIKey).filter_by(service_name='GOOGLE_REFRESH_TOKEN').first()
            if refresh_token_entry:
                refresh_token_entry.key_value_encrypted = encrypted_refresh_token
            else:
                db.session.add(APIKey(service_name='GOOGLE_REFRESH_TOKEN', key_value_encrypted=encrypted_refresh_token))
        
        encrypted_access_token = encrypt_value(credentials.token)
        access_token_entry = db.session.query(APIKey).filter_by(service_name='GOOGLE_ACCESS_TOKEN').first()
        if access_token_entry:
            access_token_entry.key_value_encrypted = encrypted_access_token
        else:
            db.session.add(APIKey(service_name='GOOGLE_ACCESS_TOKEN', key_value_encrypted=encrypted_access_token))

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"DB Error saving Google tokens: {e}", exc_info=True)
        return redirect(f"http://localhost:5173/admin/repos?gauth=dberror")

    return redirect(f"http://localhost:5173/admin/repos?gauth=success")


@google_bp.route('/connect/google/available-files', methods=['GET'])
@token_required
def get_available_google_files(current_admin_username):
    refresh_token_entry = db.session.query(APIKey).filter_by(service_name='GOOGLE_REFRESH_TOKEN').first()
    if not refresh_token_entry:
        return jsonify({"error": "Google Drive not authenticated. Please connect via Admin Settings."}), 401
    
    decrypted_refresh_token = decrypt_value(refresh_token_entry.key_value_encrypted)

    creds = Credentials(
        token=None,
        refresh_token=decrypted_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=current_app.config['GOOGLE_CLIENT_ID'],
        client_secret=current_app.config['GOOGLE_CLIENT_SECRET']
    )

    try:
        service = build('drive', 'v3', credentials=creds)
        results = service.files().list(
            q="mimeType='application/vnd.google-apps.folder'",
            pageSize=50,
            fields="nextPageToken, files(id, name, webViewLink)"
        ).execute()
        
        items = results.get('files', [])
        return jsonify(items)
    except Exception as e:
        current_app.logger.error(f"Google Drive API error: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch files from Google Drive. Please try re-authenticating."}), 500